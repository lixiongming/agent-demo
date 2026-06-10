"""向量嵌入模块

功能：
- 文档向量化
- 向量存储管理（Qdrant）
- 文档加载与解析
- 向量检索
"""
from .embedding import EmbeddingService
from .document import DocumentLoader, DocumentChunk
from .retriever import Retriever
from .qdrant_store import (
    QdrantVectorStore,
    QdrantKnowledgeStore,
    QdrantVectorStoreAdapter,
    get_qdrant_store,
    get_qdrant_adapter,
)

__all__ = [
    "EmbeddingService",
    "DocumentLoader",
    "DocumentChunk",
    "Retriever",
    "QdrantVectorStore",
    "QdrantKnowledgeStore",
    "QdrantVectorStoreAdapter",
    "get_qdrant_store",
    "get_qdrant_adapter",
]