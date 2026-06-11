"""向量嵌入模块

功能：
- 文档向量化（支持多种 Embedding 服务）
- 向量存储管理（Qdrant）
- 文档加载与解析
- 向量检索

支持的 Embedding Provider：
- zhipu: 智谱 AI embedding-3
- openai: OpenAI text-embedding-3-small/large

配置方式：
- 在 .env 中设置 EMBEDDING_PROVIDER=zhipu/openai
- 设置 EMBEDDING_API_KEY
- 无需修改代码即可切换模型
"""
from .zhipu_embedding import ZhipuEmbeddingService
from .document import DocumentLoader, DocumentChunk
from .retriever import Retriever
from .qdrant_store import (
    QdrantVectorStore,
    QdrantKnowledgeStore,
    QdrantVectorStoreAdapter,
    get_qdrant_store,
    get_qdrant_adapter,
)
from .providers import EmbeddingProviderRegistry
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def get_embedding_service(provider: str = None, **kwargs):
    """获取 Embedding 服务实例

    根据配置动态创建 Embedding 服务实例，支持热加载。

    Args:
        provider: 提供商名称（zhipu/openai），默认从配置读取
        **kwargs: 传递给提供商工厂函数的额外参数

    Returns:
        Embedding 服务实例

    使用示例：
        # 使用默认配置（从 .env 读取）
        service = get_embedding_service()

        # 指定提供商
        service = get_embedding_service(provider='openai')

        # 传递额外参数
        service = get_embedding_service(
            provider='zhipu',
            model_name='embedding-3',
            cache_enabled=False
        )
    """
    # 从配置读取提供商
    provider_name = provider or settings.EMBEDDING_PROVIDER

    # 验证提供商
    if not provider_name:
        raise ValueError(
            "EMBEDDING_PROVIDER not configured. "
            "Please set EMBEDDING_PROVIDER in .env file. "
            "Available providers: zhipu, openai"
        )
    
    # 获取提供商信息
    provider_info = EmbeddingProviderRegistry.get_provider_info(provider_name)
    logger.info(
        f"Creating embedding service: provider={provider_name}, "
        f"model={settings.EMBEDDING_MODEL_NAME}, "
        f"description={provider_info.get('description', 'N/A')}"
    )
    
    # 创建服务实例
    return EmbeddingProviderRegistry.create_service(provider_name, **kwargs)


def list_embedding_providers():
    """列出所有可用的 Embedding 提供商
    
    Returns:
        提供商信息字典
    """
    return EmbeddingProviderRegistry.list_providers()


__all__ = [
    # 核心服务
    "get_embedding_service",
    "list_embedding_providers",
    
    # 提供商注册表
    "EmbeddingProviderRegistry",
    
    # 具体实现
    "ZhipuEmbeddingService",
    
    # 文档处理
    "DocumentLoader",
    "DocumentChunk",
    
    # 检索
    "Retriever",
    
    # 向量存储
    "QdrantVectorStore",
    "QdrantKnowledgeStore",
    "QdrantVectorStoreAdapter",
    "get_qdrant_store",
    "get_qdrant_adapter",
]