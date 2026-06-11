"""Embedding 服务插件注册表

功能：
- 支持多种 Embedding 服务提供商
- 插件化架构，易于扩展
- 配置驱动，无需代码改动

支持的 Provider：
- zhipu: 智谱 AI embedding-3
- openai: OpenAI text-embedding-3-small/large
"""
from typing import Dict, Callable, Any, Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingProviderRegistry:
    """Embedding 服务提供商注册表
    
    功能：
    - 注册 Embedding 服务提供商
    - 根据配置动态创建服务实例
    - 支持运行时热加载
    """
    
    _providers: Dict[str, Callable] = {}
    _provider_info: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        factory: Callable,
        info: Optional[Dict[str, Any]] = None
    ):
        """注册 Embedding 服务提供商
        
        Args:
            name: 提供商名称（如 'zhipu', 'openai'）
            factory: 工厂函数，返回服务实例
            info: 提供商信息（描述、默认模型等）
        """
        cls._providers[name] = factory
        cls._provider_info[name] = info or {}
        logger.info(f"Registered embedding provider: {name}")
    
    @classmethod
    def get_provider(cls, name: str) -> Optional[Callable]:
        """获取提供商工厂函数
        
        Args:
            name: 提供商名称
            
        Returns:
            工厂函数
        """
        return cls._providers.get(name)
    
    @classmethod
    def get_provider_info(cls, name: str) -> Dict[str, Any]:
        """获取提供商信息
        
        Args:
            name: 提供商名称
            
        Returns:
            提供商信息
        """
        return cls._provider_info.get(name, {})
    
    @classmethod
    def list_providers(cls) -> Dict[str, Dict[str, Any]]:
        """列出所有已注册的提供商
        
        Returns:
            提供商列表
        """
        return {
            name: cls._provider_info.get(name, {})
            for name in cls._providers.keys()
        }
    
    @classmethod
    def create_service(cls, name: str, **kwargs) -> Any:
        """创建服务实例
        
        Args:
            name: 提供商名称
            **kwargs: 传递给工厂函数的参数
            
        Returns:
            服务实例
        """
        factory = cls._providers.get(name)
        if not factory:
            raise ValueError(
                f"Unknown embedding provider: {name}. "
                f"Available providers: {list(cls._providers.keys())}"
            )
        
        logger.info(f"Creating embedding service: provider={name}")
        return factory(**kwargs)
    
    @classmethod
    def clear(cls):
        """清除所有注册（测试用）"""
        cls._providers.clear()
        cls._provider_info.clear()


# ============================================
# 注册内置 Provider
# ============================================

def _create_zhipu_embedding(**kwargs):
    """创建智谱 AI Embedding 服务"""
    from app.embeddings.zhipu_embedding import ZhipuEmbeddingService
    from app.config import get_settings

    settings = get_settings()

    return ZhipuEmbeddingService(
        api_key=kwargs.get('api_key') or settings.EMBEDDING_API_KEY,
        model_name=kwargs.get('model_name') or settings.EMBEDDING_MODEL_NAME or 'embedding-3',
        cache_enabled=kwargs.get('cache_enabled', True),
        batch_size=kwargs.get('batch_size', 32)
    )


def _create_openai_embedding(**kwargs):
    """创建 OpenAI Embedding 服务"""
    from app.config import get_settings

    settings = get_settings()

    # 动态导入，避免强制依赖
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        raise ImportError(
            "OpenAI embeddings requires langchain-openai. "
            "Install it with: pip install langchain-openai"
        )

    return OpenAIEmbeddings(
        api_key=kwargs.get('api_key') or settings.EMBEDDING_API_KEY,
        model=kwargs.get('model_name') or settings.EMBEDDING_MODEL_NAME or 'text-embedding-3-small'
    )


# 注册内置 Provider
EmbeddingProviderRegistry.register(
    name='zhipu',
    factory=_create_zhipu_embedding,
    info={
        'description': '智谱 AI Embedding 服务',
        'default_model': 'embedding-3',
        'embedding_dim': 2048,  # embedding-3 实际维度
        'requires': ['EMBEDDING_API_KEY'],
        'supports_batch': True,
        'supports_cache': True
    }
)

EmbeddingProviderRegistry.register(
    name='openai',
    factory=_create_openai_embedding,
    info={
        'description': 'OpenAI Embedding 服务',
        'default_model': 'text-embedding-3-small',
        'embedding_dim': 1536,
        'requires': ['EMBEDDING_API_KEY'],
        'supports_batch': True,
        'supports_cache': False
    }
)


__all__ = ['EmbeddingProviderRegistry']