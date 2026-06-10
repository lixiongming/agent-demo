"""RAG检索工具

让Agent可以自主调用知识库检索
"""
from typing import Dict, Any, Optional
from app.services.rag import RAGService
from app.core.logger import get_logger

logger = get_logger(__name__)

# RAG服务实例
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取RAG服务实例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


async def knowledge_search(
    query: str,
    top_k: int = 5,
    threshold: float = 0.5
) -> Dict[str, Any]:
    """知识库检索工具
    
    从向量知识库中检索与查询相关的文档内容。
    
    Args:
        query: 查询问题或关键词
        top_k: 返回结果数量，默认5
        threshold: 相似度阈值，默认0.5
        
    Returns:
        检索结果，包含相关文档内容
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


# 工具定义（用于注册到ToolRegistry）
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