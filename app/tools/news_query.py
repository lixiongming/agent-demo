"""新闻查询工具

功能：
- 新闻搜索
- 热门新闻
- 最近新闻
- 作者新闻
- 新闻统计

用于聊天机器人智能查询新闻数据
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import Tool
from app.db.database import AsyncSessionLocal
from app.db.repositories.news import NewsRepository
from app.core.logger import get_logger
from app.core.tracing import tracer
from app.tools.registry import register_tool, ToolConfig
import json

logger = get_logger(__name__)


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
            - search: 搜索新闻
            - hot: 热门新闻
            - recent: 最近新闻
            - author: 作者新闻
            - stats: 新闻统计
            - today: 今天新闻
            - week: 本周新闻
            - month: 本月新闻
        keyword: 搜索关键词（search 类型）
        author: 作者名称（author 类型）
        limit: 返回数量
        days: 时间范围（天数）
        
    Returns:
        查询结果
    """
    async with tracer.span("news_query") as span:
        span.set_attribute("query_type", query_type)
        span.set_attribute("limit", limit)
        
        logger.info(f"News query: type={query_type}, keyword={keyword}, author={author}")
        
        try:
            # 获取数据库会话
            async with AsyncSessionLocal() as db:
                repo = NewsRepository(db)
                
                # 根据查询类型执行不同查询
                if query_type == "search":
                    # 搜索新闻
                    if not keyword:
                        return {
                            "success": False,
                            "error": "搜索需要提供关键词"
                        }
                    
                    news_list = await repo.search(keyword, limit)
                    result_type = "搜索结果"
                    
                elif query_type == "hot":
                    # 热门新闻
                    if days:
                        news_list = await repo.get_hot_news_by_time(days, limit)
                        result_type = f"最近{days}天热门新闻"
                    else:
                        news_list = await repo.get_hot_news(limit)
                        result_type = "热门新闻"
                    
                elif query_type == "recent":
                    # 最近新闻
                    news_list = await repo.get_recent(limit)
                    result_type = "最近新闻"
                    
                elif query_type == "author":
                    # 作者新闻
                    if not author:
                        return {
                            "success": False,
                            "error": "作者查询需要提供作者名称"
                        }
                    
                    news_list = await repo.get_by_author(author, limit)
                    result_type = f"作者 '{author}' 的新闻"
                    
                elif query_type == "stats":
                    # 新闻统计
                    stats = await repo.get_stats()
                    span.set_attribute("result", "success")
                    
                    return {
                        "success": True,
                        "query_type": query_type,
                        "stats": stats,
                        "summary": f"新闻总数: {stats['total_count']}，总浏览量: {stats['total_views']}"
                    }
                    
                elif query_type == "today":
                    # 今天新闻
                    news_list = await repo.get_today_news(limit)
                    result_type = "今天新闻"
                    
                elif query_type == "week":
                    # 本周新闻
                    news_list = await repo.get_this_week_news(limit)
                    result_type = "本周新闻"
                    
                elif query_type == "month":
                    # 本月新闻
                    news_list = await repo.get_this_month_news(limit)
                    result_type = "本月新闻"
                    
                else:
                    # 默认：最近新闻
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
                
                # 转换为摘要列表
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
# 智能新闻查询（LLM 决策）
# ============================================

async def smart_news_query(question: str) -> Dict[str, Any]:
    """智能新闻查询
    
    根据用户问题自动判断查询类型
    
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
    
    # 构建 LLM 提示词
    prompt = f"""你是一个新闻查询助手，需要根据用户问题判断查询类型。

可用查询类型：
- hot: 热门新闻（浏览量排序，不限制时间范围，返回所有热门新闻）
- recent: 最近新闻（时间排序，返回最新新闻）
- search: 搜索新闻（关键词搜索）
- author: 作者新闻（按作者查询）
- stats: 新闻统计（统计数据）
- today: 今天新闻（只返回今天的新闻）
- week: 本周新闻（只返回本周的新闻）
- month: 本月新闻（只返回本月的新闻）

用户问题：{question}

请分析用户问题，判断应该使用哪种查询类型。

重要规则：
1. 如果用户问题包含"热门"、"最热"、"热门新闻"等关键词，必须判断为 hot 类型
2. hot 类型不设置时间范围（days参数），返回所有热门新闻
3. 只有用户明确提到"今天"、"本周"、"本月"等时间词时，才使用 today/week/month 类型

请以JSON格式返回：
{{"query_type": "查询类型", "reason": "判断原因"}}

只返回JSON，不要其他内容。"""

    # 调用 LLM
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    
    # 解析结果
    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        decision = json.loads(content)
        
        logger.info(f"Smart news query decision: {decision}")
        
        # 执行查询
        return await news_query_tool(
            query_type=decision.get("query_type", "recent"),
            keyword=decision.get("keyword"),
            author=decision.get("author"),
            limit=decision.get("limit", 10),
            days=decision.get("days")
        )
    
    except Exception as e:
        logger.error(f"Smart news query parse error: {e}")
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
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    # 定义参数 schema
    class NewsQueryArgs(BaseModel):
        """新闻查询参数"""
        question: str = Field(description="用户问题（自动解析查询类型）")
    
    # 使用 StructuredTool 正确处理异步函数
    tool = StructuredTool(
        name="news_query",
        coroutine=smart_news_query,  # 异步函数
        args_schema=NewsQueryArgs,  # 参数 schema
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
    
    # 配置：超时30秒，每分钟100次，失败5次熔断
    config = ToolConfig(
        name="news_query",
        description="新闻查询工具",
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