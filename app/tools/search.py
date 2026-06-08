"""搜索工具"""
from typing import Optional, List
from langchain_core.tools import Tool
from app.tools.registry import register_tool
import httpx


async def web_search(query: str, num_results: int = 5) -> List[dict]:
    """网络搜索
    
    Args:
        query: 搜索关键词
        num_results: 返回结果数量
    
    Returns:
        搜索结果列表
    """
    # 示例实现 - 可接入真实搜索API
    results = [
        {
            "title": f"搜索结果 {i+1}",
            "url": f"https://example.com/result/{i+1}",
            "snippet": f"关于 {query} 的搜索结果..."
        }
        for i in range(num_results)
    ]
    
    return results


def search_tool():
    """创建搜索工具"""
    tool = Tool(
        name="web_search",
        func=lambda q: web_search(q),
        description="搜索网络获取信息。输入搜索关键词，返回相关结果列表。"
    )
    register_tool(tool)
    return tool


# 自动注册
search_tool()