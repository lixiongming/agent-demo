"""网络搜索工具 - 生产标准实现

接入 Tavily API（LangChain 推荐的搜索工具）

生产标准：
- 真实 API 接入（非示例代码）
- 错误处理和降级
- 限流熔断保护
- 结果格式化

Tavily 特点：
- 专为 AI 应用设计
- 返回结构化搜索结果
- 支持搜索深度控制
- 高性能和准确性

配置：
- TAVILY_API_KEY: 在 .env 中配置
"""
from typing import List, Dict, Any, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.tools.registry import register_tool, ToolConfig
from app.core.logger import get_logger
from app.config import get_settings
import httpx

logger = get_logger(__name__)
settings = get_settings()


# ============================================
# Tavily 搜索 API
# ============================================

async def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic"
) -> Dict[str, Any]:
    """Tavily 搜索
    
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数
        search_depth: 搜索深度（basic/advanced）
    
    Returns:
        搜索结果
    """
    tavily_api_key = settings.TAVILY_API_KEY
    
    if not tavily_api_key:
        logger.warning("TAVILY_API_KEY 未配置，搜索功能不可用")
        return {
            "success": False,
            "error": "搜索功能未配置，请在 .env 中设置 TAVILY_API_KEY",
            "query": query,
            "hint": "获取 API Key: https://tavily.com"
        }
    
    try:
        url = "https://api.tavily.com/search"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {tavily_api_key}"
        }
        
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": True,
            "include_raw_content": False,
            "include_images": False
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Tavily API error: {response.status_code}")
                return {
                    "success": False,
                    "error": f"搜索 API 错误: {response.status_code}",
                    "query": query
                }
            
            data = response.json()
            
            # 格式化结果
            results = data.get("results", [])
            answer = data.get("answer", "")
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0)
                })
            
            logger.info(f"Tavily 搜索成功: 找到 {len(formatted_results)} 条结果")
            
            return {
                "success": True,
                "query": query,
                "answer": answer,
                "results_count": len(formatted_results),
                "results": formatted_results
            }
    
    except httpx.TimeoutException:
        logger.error("Tavily API timeout")
        return {
            "success": False,
            "error": "搜索超时，请稍后重试",
            "query": query
        }
    
    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query
        }


# ============================================
# 网络搜索工具
# ============================================

async def web_search(
    query: str,
    num_results: int = 5
) -> Dict[str, Any]:
    """网络搜索工具
    
    使用 Tavily API 进行网络搜索
    
    Args:
        query: 搜索关键词
        num_results: 返回结果数量
    
    Returns:
        搜索结果
    """
    return await tavily_search(query, max_results=num_results)


# ============================================
# 工具注册
# ============================================

class WebSearchInput(BaseModel):
    """网络搜索参数"""
    query: str = Field(
        ...,
        description="搜索关键词"
    )
    num_results: int = Field(
        default=5,
        description="返回结果数量，默认5"
    )


def search_tool():
    """创建网络搜索工具（生产标准）"""
    tool = StructuredTool(
        name="web_search",
        coroutine=web_search,  # 异步函数
        description="""网络搜索工具（Tavily API）。

功能：
- 搜索网络获取实时信息
- 返回结构化搜索结果
- 支持搜索深度控制

使用场景：
- 查询实时新闻
- 搜索最新信息
- 获取网络内容

输入参数：
- query: 搜索关键词
- num_results: 返回结果数量（默认5）

配置要求：
- 需要在 .env 中配置 TAVILY_API_KEY
- 获取 API Key: https://tavily.com

示例：
- "最新科技新闻" → 返回科技新闻搜索结果
- "Python 教程" → 返回 Python 学习资源
""",
        args_schema=WebSearchInput
    )
    
    # 配置：超时30秒，每分钟50次，失败5次熔断
    config = ToolConfig(
        name="web_search",
        description="网络搜索工具（Tavily API）",
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
search_tool()