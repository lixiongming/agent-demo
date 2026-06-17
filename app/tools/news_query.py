"""新闻查询工具 - 大厂标准实现

功能：
- 新闻搜索
- 热门新闻
- 最近新闻
- 作者新闻
- 新闻统计

核心改进：
- 使用 Function Calling 替代手动 JSON 解析
- 完善参数 Schema 定义
- 支持多查询类型
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.db.database import AsyncSessionLocal
from app.db.repositories.news import NewsRepository
from app.core.logger import get_logger
from app.core.tracing import tracer
from app.tools.registry import register_tool, ToolConfig

logger = get_logger(__name__)


# ============================================
# 参数 Schema 定义（大厂标准）
# ============================================

class NewsQueryArgs(BaseModel):
    """新闻查询参数 - 完整 Schema
    
    用于 Function Calling 的参数定义
    """
    question: str = Field(
        ...,
        description="用户问题（自动解析查询类型，如：热门新闻、搜索科技新闻、新华社的新闻）"
    )


class NewsQueryDecision(BaseModel):
    """新闻查询决策结果 - Function Calling Schema
    
    LLM 返回的查询决策
    """
    query_type: str = Field(
        ...,
        description="查询类型：hot(热门)、recent(最近)、search(搜索)、author(作者)、stats(统计)、today(今天)、week(本周)、month(本月)"
    )
    keyword: Optional[str] = Field(
        None,
        description="搜索关键词（search 类型使用）"
    )
    author: Optional[str] = Field(
        None,
        description="作者名称（author 类型使用）"
    )
    limit: int = Field(
        10,
        description="返回数量（默认10）",
        ge=1,
        le=50
    )
    days: Optional[int] = Field(
        None,
        description="时间范围（天数）",
        ge=1,
        le=365
    )
    reason: str = Field(
        "",
        description="决策原因"
    )


# ============================================
# 新闻查询工具
# ============================================

async def news_query_tool(
    query_type: str = "search",
    keyword: Optional[str] = None,
    author: Optional[str] = None,
    limit: int = 10,
    days: Optional[int] = None
) -> Dict[str, Any]:
    """新闻查询工具
    
    功能：
    - 搜索新闻（关键词搜索）
    - 热门新闻（浏览量排序）
    - 最近新闻（时间排序）
    - 作者新闻（按作者查询）
    - 新闻统计（统计数据）
    
    Args:
        query_type: 查询类型
        keyword: 搜索关键词
        author: 作者名称
        limit: 返回数量
        days: 时间范围
        
    Returns:
        查询结果
    """
    async with tracer.span("news_query") as span:
        span.set_attribute("query_type", query_type)
        span.set_attribute("limit", limit)
        
        logger.info(f"News query: type={query_type}, keyword={keyword}, author={author}")
        
        try:
            async with AsyncSessionLocal() as db:
                repo = NewsRepository(db)
                
                # 根据查询类型执行不同查询
                if query_type == "search":
                    if not keyword:
                        return {
                            "success": False,
                            "error": "搜索需要提供关键词"
                        }
                    news_list = await repo.search(keyword, limit)
                    result_type = "搜索结果"
                    
                elif query_type == "hot":
                    if days:
                        news_list = await repo.get_hot_news_by_time(days, limit)
                        result_type = f"最近{days}天热门新闻"
                    else:
                        news_list = await repo.get_hot_news(limit)
                        result_type = "热门新闻"
                    
                elif query_type == "recent":
                    news_list = await repo.get_recent(limit)
                    result_type = "最近新闻"
                    
                elif query_type == "author":
                    if not author:
                        return {
                            "success": False,
                            "error": "作者查询需要提供作者名称"
                        }
                    news_list = await repo.get_by_author(author, limit)
                    result_type = f"作者 '{author}' 的新闻"
                    
                elif query_type == "stats":
                    stats = await repo.get_stats()
                    span.set_attribute("result", "success")
                    return {
                        "success": True,
                        "query_type": query_type,
                        "stats": stats,
                        "summary": f"新闻总数: {stats['total_count']}，总浏览量: {stats['total_views']}"
                    }
                    
                elif query_type == "today":
                    news_list = await repo.get_today_news(limit)
                    result_type = "今天新闻"
                    
                elif query_type == "week":
                    news_list = await repo.get_this_week_news(limit)
                    result_type = "本周新闻"
                    
                elif query_type == "month":
                    news_list = await repo.get_this_month_news(limit)
                    result_type = "本月新闻"
                    
                else:
                    news_list = await repo.get_recent(limit)
                    result_type = "最近新闻"
                
                # 格式化结果
                if not news_list:
                    span.set_attribute("result", "no_data")
                    return {
                        "success": True,
                        "query_type": query_type,
                        "news_count": 0,
                        "message": f"没有找到{result_type}",
                        "news_list": []
                    }
                
                news_data = [news.to_summary_dict() for news in news_list]
                
                span.set_attribute("news_count", len(news_list))
                span.set_attribute("result", "success")
                
                logger.info(f"News query success: {len(news_list)} news found")
                
                return {
                    "success": True,
                    "query_type": query_type,
                    "news_count": len(news_list),
                    "result_type": result_type,
                    "news_list": news_data,
                    "keyword": keyword,
                    "author": author
                }
        
        except Exception as e:
            span.set_status("error", str(e))
            logger.error(f"News query error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query_type": query_type
            }


# ============================================
# 智能新闻查询 - Function Calling（大厂标准）
# ============================================

async def smart_news_query(question: str) -> Dict[str, Any]:
    """智能新闻查询 - Function Calling 实现
    
    核心改进：
    - 使用 bind_tools() 替代手动 JSON 解析
    - 直接使用 tool_calls 属性
    - 无需解析 JSON，格式保证正确
    
    Args:
        question: 用户问题
        
    Returns:
        查询结果
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
            "name": "news_query_decision",
            "description": "根据用户问题判断新闻查询类型和参数",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["hot", "recent", "search", "author", "stats", "today", "week", "month"],
                        "description": "查询类型：hot(热门新闻)、recent(最近新闻)、search(关键词搜索)、author(作者新闻)、stats(统计)、today(今天)、week(本周)、month(本月)"
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（仅 search 类型使用）"
                    },
                    "author": {
                        "type": "string",
                        "description": "作者名称（仅 author 类型使用）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量（默认10，最大50）",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "days": {
                        "type": "integer",
                        "description": "时间范围天数（可选）",
                        "minimum": 1,
                        "maximum": 365
                    }
                },
                "required": ["query_type"]
            }
        }
    }]
    
    # 绑定工具到 LLM（大厂标准）
    llm_with_tools = llm.bind_tools(tools)
    
    # 构建提示词
    prompt = f"""分析用户问题，判断应该使用哪种新闻查询类型。

重要规则：
1. "热门"、"最热" → hot 类型
2. "最近"、"最新" → recent 类型
3. "搜索"、"关于" → search 类型（需要提取关键词）
4. "作者"、"某某的" → author 类型（需要提取作者名）
5. "统计"、"总数" → stats 类型
6. "今天" → today 类型
7. "本周" → week 类型
8. "本月" → month 类型

用户问题：{question}

请调用 news_query_decision 函数返回决策结果。"""

    try:
        # 调用 LLM（大厂标准）
        response = await llm_with_tools.ainvoke([HumanMessage(content=prompt)])
        
        # 直接使用 tool_calls 属性（无需手动解析）
        if hasattr(response, "tool_calls") and response.tool_calls:
            tc = response.tool_calls[0]
            args = tc.get("args", {})
            
            query_type = args.get("query_type", "recent")
            keyword = args.get("keyword")
            author = args.get("author")
            limit = args.get("limit", 10)
            days = args.get("days")
            
            logger.info(f"Smart news query (Function Calling): type={query_type}, keyword={keyword}, author={author}")
            
            # 执行查询
            return await news_query_tool(
                query_type=query_type,
                keyword=keyword,
                author=author,
                limit=limit,
                days=days
            )
        
        # LLM 未返回工具调用，降级为搜索
        logger.warning("LLM did not return tool_calls, fallback to search")
        return await news_query_tool(
            query_type="search",
            keyword=question,
            limit=10
        )
    
    except Exception as e:
        logger.error(f"Smart news query error: {e}")
        # 降级：默认搜索
        return await news_query_tool(
            query_type="search",
            keyword=question,
            limit=10
        )


# ============================================
# 工具注册
# ============================================

def create_news_tool():
    """创建新闻查询工具"""
    tool = StructuredTool(
        name="news_query",
        coroutine=smart_news_query,
        args_schema=NewsQueryArgs,
        description="""新闻查询工具。

功能：
- 搜索新闻（关键词搜索）
- 热门新闻（浏览量排序）
- 最近新闻（时间排序）
- 作者新闻（按作者查询）
- 新闻统计（统计数据）
- 时间范围查询（今天、本周、本月）

使用场景：
- 查询最新新闻
- 搜索特定主题新闻
- 查看热门新闻
- 查询作者新闻
- 统计新闻数据

输入参数：
- question: 用户问题（自动解析查询类型）

示例：
- "热门的新闻" → 自动识别为热门查询
- "搜索关于科技的新闻" → 自动识别为关键词搜索
- "最近一周的新闻" → 自动识别为时间范围查询
- "新华社的新闻" → 自动识别为作者查询
"""
    )
    
    config = ToolConfig(
        name="news_query",
        description="新闻查询工具（Function Calling 实现）",
        timeout=30,
        rate_limit=100,
        rate_period=60,
        failure_threshold=5,
        recovery_timeout=60,
        max_retries=2
    )
    
    register_tool(tool, config)
    return tool


# 自动注册
create_news_tool()