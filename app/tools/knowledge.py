"""RAG检索工具 - 生产标准实现

功能：
- 知识库检索
- 向量相似度搜索
- 结果格式化

生产标准：
- 使用 StructuredTool 正确处理异步函数
- 限流熔断保护
- 链路追踪
- 错误处理
"""
from typing import Dict, Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.core.logger import get_logger
from app.core.container import DIContainer
from app.core.interfaces import IRAGService
from app.tools.registry import register_tool, ToolConfig

logger = get_logger(__name__)


# ============================================
# RAG 服务获取
# ============================================

def get_rag_service() -> IRAGService:
    """获取RAG服务实例（容器单例）
    
    生产标准：
    - 使用容器获取单例
    - 只初始化一次
    - 后续请求直接获取
    """
    return DIContainer.get(IRAGService)


# ============================================
# 知识库检索函数
# ============================================

async def knowledge_search(
    query: str,
    top_k: int = 5,
    threshold: float = 0.5
) -> Dict[str, Any]:
    """知识库检索工具
    
    从向量知识库中检索与查询相关的文档内容
    
    Args:
        query: 查询问题或关键词
        top_k: 返回结果数量，默认5
        threshold: 相似度阈值，默认0.5
        
    Returns:
        检索结果，包含相关文档内容
    
    示例:
        >>> result = await knowledge_search("产品功能介绍")
        >>> print(result["knowledge"])
    """
    logger.info(f"RAG工具调用: query={query}, top_k={top_k}")
    
    try:
        service = get_rag_service()
        
        result = await service.query(
            question=query,
            top_k=top_k,
            threshold=threshold
        )
        
        # 格式化返回结果
        sources = result.get("sources", [])
        
        if not sources:
            return {
                "success": True,
                "found": False,
                "message": "知识库中没有找到相关内容",
                "query": query
            }
        
        # 构建知识内容
        knowledge_content = []
        for i, source in enumerate(sources):
            knowledge_content.append(
                f"[{i+1}] {source.get('content', '')}"
            )
        
        logger.info(f"RAG检索成功: 找到 {len(sources)} 条相关内容")
        
        return {
            "success": True,
            "found": True,
            "query": query,
            "total_results": len(sources),
            "knowledge": "\n".join(knowledge_content),
            "sources": [
                {
                    "content": s.get("content", "")[:200],
                    "score": s.get("score", 0),
                    "source": s.get("source", "")
                }
                for s in sources
            ]
        }
        
    except Exception as e:
        logger.error(f"RAG检索失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query
        }


# ============================================
# 工具注册
# ============================================

class KnowledgeSearchInput(BaseModel):
    """知识库检索参数"""
    query: str = Field(
        ...,
        description="查询问题或关键词"
    )
    top_k: int = Field(
        default=5,
        description="返回结果数量，默认5"
    )
    threshold: float = Field(
        default=0.5,
        description="相似度阈值，默认0.5"
    )


def knowledge_tool():
    """创建知识库检索工具（生产标准）"""
    # 使用 StructuredTool 正确处理异步函数
    tool = StructuredTool(
        name="knowledge_search",
        coroutine=knowledge_search,  # 异步函数使用 coroutine
        description="""知识库检索工具。

功能：
- 从向量知识库中检索相关文档内容
- 支持相似度阈值过滤
- 返回格式化的知识内容

使用场景：
- 用户询问产品信息
- 查询技术文档
- 搜索业务规则
- 查找常见问题解答

输入参数：
- query: 查询问题或关键词
- top_k: 返回结果数量（默认5）
- threshold: 相似度阈值（默认0.5）

示例：
- "产品功能介绍" → 返回产品相关文档
- "API接口文档" → 返回API使用说明
- "如何使用" → 返回使用教程
""",
        args_schema=KnowledgeSearchInput
    )
    
    # 配置：超时30秒，每分钟200次，失败10次熔断
    config = ToolConfig(
        name="knowledge_search",
        description="知识库检索工具",
        timeout=30,
        rate_limit=200,
        rate_period=60,
        failure_threshold=10,
        recovery_timeout=30,
        max_retries=3
    )
    
    register_tool(tool, config)
    return tool


# ============================================
# 工具定义（用于智能路由）
# ============================================

RAG_TOOL_DEFINITION = {
    "name": "knowledge_search",
    "description": "从知识库中检索相关文档内容。当用户询问产品信息、技术文档、业务规则等知识性问题时使用此工具。",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "查询问题或关键词"
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量，默认5",
                "default": 5
            },
            "threshold": {
                "type": "number",
                "description": "相似度阈值，默认0.5",
                "default": 0.5
            }
        },
        "required": ["query"]
    }
}


# 注意：不在此文件自动注册，避免重复注册
# 注册由 __init__.py 的 register_all_tools() 统一管理