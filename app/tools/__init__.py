"""工具模块 - 生产标准实现

统一管理所有工具的注册和导出

生产标准：
- 统一注册入口（避免重复注册）
- 模块化导入
- 清晰的导出列表
"""
from .registry import ToolRegistry, get_registry, register_tool, ToolConfig
from langchain_core.tools import StructuredTool

__all__ = [
    # 注册中心
    "ToolRegistry", 
    "get_registry", 
    "register_tool",
    "ToolConfig",
    
    # 工具定义（用于智能路由）
    "RAG_TOOL_DEFINITION",
    "MYSQL_TOOL_DEFINITION",
    "NEWS_TOOL_DEFINITION",
    
    # 工具函数
    "knowledge_search",
    "smart_news_query",
]


# ============================================
# 工具定义导入
# ============================================

from .knowledge import RAG_TOOL_DEFINITION, knowledge_search, knowledge_tool
from .mysql_query import MYSQL_TOOL_DEFINITION, mysql_query_tool
from .news_query import NEWS_TOOL_DEFINITION, smart_news_query, news_query_tool


# ============================================
# 统一注册入口
# ============================================

def register_all_tools():
    """注册所有工具（统一入口）
    
    生产标准：
    - 统一注册入口
    - 避免重复注册
    - 清晰的注册顺序
    
    注册的工具：
    1. calculator - 数学计算器
    2. web_search - 网络搜索
    3. get_weather - 天气查询
    4. mysql_query - 数据库查询
    5. news_query - 新闻查询
    6. knowledge_search - 知识库检索
    """
    # 导入工具模块（触发自动注册）
    from .calculator import calculator_tool
    from .search import search_tool
    from .weather import weather_tool
    from .mysql_query import mysql_query_tool
    from .news_query import news_query_tool
    
    # 注册 RAG 工具（手动注册，避免重复）
    from .knowledge import knowledge_tool
    knowledge_tool()
    
    # 打印注册信息
    registry = get_registry()
    tool_names = registry.get_tool_names()
    print(f"所有工具已注册完成: {tool_names}")


# ============================================
# 启动时注册
# ============================================

register_all_tools()