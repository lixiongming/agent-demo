"""MySQL 数据库查询工具 - 大厂标准实现

核心改进：
- 使用 Function Calling 替代手动 JSON 解析
- 完善参数 Schema 定义
- Text-to-SQL（LLM 自动生成 SQL）
- 安全防护（SQL 注入防护）
- 权限控制（只允许特定表查询）
- 限流熔断（防止数据库过载）
- 链路追踪（监控查询性能）

参考：
- OpenAI: GPT-4 + SQL 执行
- Google: BigQuery + AI 查询
- 阿里: 智能数据助手
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.db.database import async_engine
from app.core.logger import get_logger
from app.core.rate_limit import CircuitBreaker, CircuitBreakerManager
from app.core.tracing import tracer
from app.tools.registry import register_tool, ToolConfig
from sqlalchemy import text
import asyncio
import re
import json

logger = get_logger(__name__)


# ============================================
# 安全配置
# ============================================

# 允许查询的表（白名单）
ALLOWED_TABLES = [
    "users", "sessions", "messages",
    # 添加你的业务表
    "orders", "products", "customers"
]

# 禁止的关键词（SQL 注入防护）
FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT",
    "ALTER", "CREATE", "TRUNCATE",
    "GRANT", "REVOKE", "EXEC",
    "--", ";--", "/*", "*/"
]

# 最大返回行数（防止数据过载）
MAX_ROWS = 1000


# ============================================
# 参数 Schema 定义（大厂标准）
# ============================================

class MySQLQueryArgs(BaseModel):
    """MySQL 查询参数 - 完整 Schema
    
    用于 Function Calling 的参数定义
    """
    question: str = Field(
        ...,
        description="用户问题（如：查询最近10个用户、统计订单总数）"
    )
    table_info: Optional[str] = Field(
        None,
        description="表结构信息（可选）"
    )
    direct_sql: Optional[str] = Field(
        None,
        description="直接执行的 SQL（可选，优先级更高）"
    )


class SQLGenerationResult(BaseModel):
    """SQL 生成结果 - Function Calling Schema
    
    LLM 返回的 SQL 生成结果
    """
    sql: str = Field(
        ...,
        description="生成的 SQL 查询语句"
    )
    table: str = Field(
        "",
        description="查询的表名"
    )
    limit: int = Field(
        100,
        description="返回行数限制",
        ge=1,
        le=1000
    )
    reason: str = Field(
        "",
        description="生成原因"
    )


# ============================================
# SQL 安全检查
# ============================================

def validate_sql(sql: str) -> tuple[bool, str]:
    """验证 SQL 安全性
    
    检查：
    - 是否包含禁止关键词
    - 是否查询白名单表
    - 是否符合安全规范
    
    Args:
        sql: SQL 查询语句
        
    Returns:
        (是否安全, 错误信息)
    """
    sql_upper = sql.upper().strip()
    
    # 1. 检查禁止关键词
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            return False, f"SQL 包含禁止关键词: {keyword}"
    
    # 2. 检查是否是 SELECT 语句
    if not sql_upper.startswith("SELECT"):
        return False, "只允许 SELECT 查询"
    
    # 3. 检查是否查询白名单表
    tables_in_sql = re.findall(r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)', sql_upper)
    tables = [t[0] or t[1] for t in tables_in_sql]
    
    for table in tables:
        if table.lower() not in [t.lower() for t in ALLOWED_TABLES]:
            return False, f"表 '{table}' 不在白名单中，允许的表: {ALLOWED_TABLES}"
    
    # 4. 检查是否包含 LIMIT（防止全表扫描）
    if "LIMIT" not in sql_upper:
        return False, "必须包含 LIMIT 限制返回行数"
    
    return True, ""


# ============================================
# Text-to-SQL 生成 - Function Calling（大厂标准）
# ============================================

async def generate_sql_from_question(question: str, table_info: Optional[str] = None) -> str:
    """使用 LLM Function Calling 生成 SQL
    
    核心改进：
    - 使用 bind_tools() 替代手动 JSON 解析
    - 直接使用 tool_calls 属性
    - 无需解析 JSON，格式保证正确
    
    Args:
        question: 用户问题
        table_info: 表结构信息（可选）
        
    Returns:
        生成的 SQL 语句
    """
    from app.llm.factory import get_llm
    from app.config import get_settings
    from langchain_core.messages import HumanMessage
    
    settings = get_settings()
    llm = get_llm(settings.DEFAULT_MODEL)
    
    # 定义 Function Calling 工具（大厂标准）
    tools = [{
        "type": "function",
        "function": {
            "name": "generate_sql",
            "description": "根据用户问题生成安全的 SQL 查询语句",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "生成的 SQL 查询语句（必须是 SELECT 语句，必须包含 LIMIT）"
                    },
                    "table": {
                        "type": "string",
                        "description": "查询的表名",
                        "enum": ALLOWED_TABLES
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回行数限制（最大1000）",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": ["sql", "table"]
            }
        }
    }]
    
    # 绑定工具到 LLM（大厂标准）
    llm_with_tools = llm.bind_tools(tools)
    
    # 构建提示词
    table_desc = table_info or f"可用表: {', '.join(ALLOWED_TABLES)}"
    
    prompt = f"""你是一个 SQL 专家，需要根据用户问题生成安全的 SQL 查询。

数据库表信息：
{table_desc}

安全规则：
1. 只生成 SELECT 查询
2. 必须包含 LIMIT 限制（最多 {MAX_ROWS} 行）
3. 不要使用 DROP、DELETE、UPDATE、INSERT 等危险操作
4. 只查询白名单中的表

用户问题：{question}

请调用 generate_sql 函数返回 SQL 查询语句。

示例：
问题："查询最近10个用户"
调用：generate_sql(sql="SELECT * FROM users ORDER BY created_at DESC LIMIT 10", table="users", limit=10)

问题："统计订单总数"
调用：generate_sql(sql="SELECT COUNT(*) as total FROM orders LIMIT 1", table="orders", limit=1)
"""

    try:
        # 调用 LLM（大厂标准）
        response = await llm_with_tools.ainvoke([HumanMessage(content=prompt)])
        
        # 直接使用 tool_calls 属性（无需手动解析）
        if hasattr(response, "tool_calls") and response.tool_calls:
            tc = response.tool_calls[0]
            args = tc.get("args", {})
            
            sql = args.get("sql", "")
            
            # 清理 SQL（去除可能的 markdown 格式）
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()
            
            logger.info(f"Generated SQL (Function Calling): {sql}")
            
            return sql
        
        # LLM 未返回工具调用，降级为默认查询
        logger.warning("LLM did not return tool_calls, fallback to default")
        return f"SELECT * FROM users LIMIT 10"
    
    except Exception as e:
        logger.error(f"SQL generation error: {e}")
        return f"SELECT * FROM users LIMIT 10"


# ============================================
# 执行 SQL 查询
# ============================================

async def execute_sql_query(
    sql: str,
    params: Optional[Dict] = None,
    timeout: int = 30
) -> Dict[str, Any]:
    """执行 SQL 查询
    
    功能：
    - 安全验证
    - 限流熔断
    - 超时控制
    - 链路追踪
    - 结果格式化
    
    Args:
        sql: SQL 查询语句
        params: 查询参数（可选）
        timeout: 超时时间（秒）
        
    Returns:
        查询结果
    """
    async with tracer.span("mysql_query") as span:
        span.set_attribute("sql", sql)
        
        # 1. 安全验证
        is_safe, error_msg = validate_sql(sql)
        if not is_safe:
            span.set_status("error", error_msg)
            logger.warning(f"SQL validation failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "sql": sql
            }
        
        # 2. 获取熔断器
        breaker = CircuitBreakerManager.get_breaker(
            "mysql_query",
            threshold=5,
            timeout=30
        )
        
        # 3. 熔断检查
        if breaker.state.value == "open":
            span.set_status("error", "Circuit breaker open")
            return {
                "success": False,
                "error": "数据库查询暂时不可用（熔断保护）",
                "sql": sql
            }
        
        try:
            # 4. 执行查询（带超时）
            async with async_engine.connect() as conn:
                result = await asyncio.wait_for(
                    conn.execute(text(sql), params or {}),
                    timeout=timeout
                )
                
                rows = result.fetchall()
                
                # 转换为字典列表
                columns = result.keys()
                data = [dict(zip(columns, row)) for row in rows]
                
                # 限制返回行数
                if len(data) > MAX_ROWS:
                    data = data[:MAX_ROWS]
                    logger.warning(f"Result truncated to {MAX_ROWS} rows")
                
                # 记录成功
                breaker._record_success()
                span.set_attribute("rows_count", len(data))
                span.set_status("ok")
                
                logger.info(f"SQL query executed: {len(data)} rows returned")
                
                return {
                    "success": True,
                    "sql": sql,
                    "rows_count": len(data),
                    "data": data,
                    "columns": list(columns)
                }
        
        except asyncio.TimeoutError:
            breaker._record_failure()
            span.set_status("error", "Timeout")
            logger.error(f"SQL query timeout: {sql}")
            return {
                "success": False,
                "error": f"查询超时（{timeout}秒）",
                "sql": sql
            }
        
        except Exception as e:
            breaker._record_failure()
            span.set_status("error", str(e))
            logger.error(f"SQL query error: {e}")
            return {
                "success": False,
                "error": str(e),
                "sql": sql
            }


# ============================================
# MySQL 查询工具
# ============================================

async def mysql_query_tool(
    question: str,
    table_info: Optional[str] = None,
    direct_sql: Optional[str] = None
) -> Dict[str, Any]:
    """MySQL 数据库查询工具
    
    功能：
    - Text-to-SQL（自动生成 SQL）
    - 直接执行 SQL（可选）
    - 安全防护
    - 限流熔断
    
    Args:
        question: 用户问题（自动生成 SQL）
        table_info: 表结构信息（可选）
        direct_sql: 直接执行的 SQL（可选，优先级更高）
        
    Returns:
        查询结果
    """
    logger.info(f"MySQL query tool called: question={question[:50]}...")
    
    try:
        # 1. 确定查询方式
        if direct_sql:
            sql = direct_sql
            logger.info("Using direct SQL")
        else:
            # Text-to-SQL（Function Calling）
            sql = await generate_sql_from_question(question, table_info)
        
        # 2. 执行查询
        result = await execute_sql_query(sql)
        
        # 3. 如果查询成功，让 LLM 总结结果
        if result.get("success") and result.get("data"):
            from app.llm.factory import get_llm
            from app.config import get_settings
            from langchain_core.messages import HumanMessage
            
            settings = get_settings()
            llm = get_llm(settings.DEFAULT_MODEL)
            
            # 构建总结提示词
            summary_prompt = f"""用户问题：{question}

查询结果（{result['rows_count']} 行数据）：
{json.dumps(result['data'][:10], ensure_ascii=False, indent=2)}

请用简洁的语言总结查询结果，回答用户问题。"""

            # 调用 LLM 总结
            response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
            summary = response.content
            
            result["summary"] = summary
            result["question"] = question
        
        return result
    
    except Exception as e:
        logger.error(f"MySQL query tool error: {e}")
        return {
            "success": False,
            "error": str(e),
            "question": question
        }


# ============================================
# 工具注册
# ============================================

def create_mysql_tool():
    """创建 MySQL 查询工具"""
    tool = StructuredTool(
        name="mysql_query",
        coroutine=mysql_query_tool,
        args_schema=MySQLQueryArgs,
        description="""MySQL 数据库查询工具。

功能：
- 根据用户问题自动生成 SQL 查询
- 执行安全的 SELECT 查询
- 返回查询结果和总结

使用场景：
- 查询用户数据
- 查询订单信息
- 查询统计数据
- 查询业务数据

安全保护：
- 只允许 SELECT 查询
- 只允许查询白名单表
- 必须包含 LIMIT 限制
- SQL 注入防护

输入参数：
- question: 用户问题（如"查询最近10个用户"）
- table_info: 表结构信息（可选）
- direct_sql: 直接执行的 SQL（可选）

示例：
- "查询最近一周的订单"
- "统计用户总数"
- "搜索商品名称包含'手机'的产品"
"""
    )
    
    config = ToolConfig(
        name="mysql_query",
        description="MySQL 数据库查询工具（Function Calling 实现）",
        timeout=30,
        rate_limit=50,
        rate_period=60,
        failure_threshold=5,
        recovery_timeout=60,
        max_retries=2
    )
    
    register_tool(tool, config)
    return tool


# 自动注册
create_mysql_tool()


# ============================================
# 工具定义（用于智能路由）
# ============================================

MYSQL_TOOL_DEFINITION = {
    "name": "mysql_query",
    "description": "MySQL 数据库查询工具。根据用户问题自动生成 SQL 并执行查询。",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "用户问题（如'查询最近10个用户'）"
            },
            "table_info": {
                "type": "string",
                "description": "表结构信息（可选）"
            },
            "direct_sql": {
                "type": "string",
                "description": "直接执行的 SQL（可选，优先级更高）"
            }
        },
        "required": ["question"]
    }
}