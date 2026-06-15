"""工具模块"""
from .registry import ToolRegistry, get_registry, register_tool
from .knowledge import knowledge_search, RAG_TOOL_DEFINITION
from .mysql_query import mysql_query_tool, MYSQL_TOOL_DEFINITION
from .news_query import news_query_tool, smart_news_query, NEWS_TOOL_DEFINITION
from langchain_core.tools import StructuredTool

__all__ = [
    "ToolRegistry", "get_registry", "register_tool",
    "knowledge_search", "RAG_TOOL_DEFINITION",
    "mysql_query_tool", "MYSQL_TOOL_DEFINITION",
    "news_query_tool", "smart_news_query", "NEWS_TOOL_DEFINITION"
]


# 注册RAG工具
def register_rag_tool():
    """注册RAG检索工具"""
    from pydantic import BaseModel, Field
    
    class RAGSearchArgs(BaseModel):
        """RAG检索参数"""
        query: str = Field(description="查询问题或关键词")
        top_k: int = Field(default=5, description="返回结果数量")
        threshold: float = Field(default=0.5, description="相似度阈值")
    
    tool = StructuredTool(
        name="knowledge_search",
        coroutine=knowledge_search,  # 异步函数
        description="从知识库中检索相关文档内容。当用户询问产品信息、技术文档、业务规则等知识性问题时使用此工具。",
        args_schema=RAGSearchArgs
    )
    
    get_registry().register(tool)


# 注册其他工具
def register_all_tools():
    """注册所有工具"""
    # 导入并注册其他工具（它们会在导入时自动注册）
    from .search import search_tool
    from .calculator import calculator_tool
    from .weather import weather_tool
    from .mysql_query import create_mysql_tool
    from .news_query import create_news_tool
    
    # 注册RAG工具
    register_rag_tool()
    
    print("所有工具已注册完成")


# 启动时注册
register_all_tools()