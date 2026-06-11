"""依赖注入容器

生产级别服务管理：
- 单例管理
- 接口绑定
- 动态替换
- 测试友好
"""
from typing import Type, Dict, Any, Callable, Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class DIContainer:
    """依赖注入容器
    
    功能：
    - 服务注册
    - 单例管理
    - 接口绑定
    - 工厂模式
    
    使用示例：
        # 绑定接口到实现
        DIContainer.bind(IVectorStore, AsyncVectorStore)
        
        # 获取服务
        vector_store = DIContainer.get(IVectorStore)
        
        # 注册单例
        DIContainer.register_singleton("rag_config", RAGConfig())
        
        # 测试时替换
        DIContainer.bind(IVectorStore, MockVectorStore)
    """
    
    _services: Dict[Type, Any] = {}
    _bindings: Dict[Type, Type] = {}
    _factories: Dict[Type, Callable] = {}
    _singletons: Dict[str, Any] = {}
    
    @classmethod
    def bind(cls, interface: Type, implementation: Type):
        """绑定接口到实现
        
        Args:
            interface: 接口类型
            implementation: 实现类型
        """
        cls._bindings[interface] = implementation
        logger.debug(f"DI: Bound {interface.__name__} -> {implementation.__name__}")
    
    @classmethod
    def bind_factory(cls, interface: Type, factory: Callable):
        """绑定接口到工厂函数
        
        Args:
            interface: 接口类型
            factory: 工厂函数
        """
        cls._factories[interface] = factory
        logger.debug(f"DI: Bound {interface.__name__} -> factory")
    
    @classmethod
    def get(cls, interface: Type) -> Any:
        """获取服务实例
        
        Args:
            interface: 接口类型
            
        Returns:
            服务实例
        """
        # 检查缓存
        if interface in cls._services:
            return cls._services[interface]
        
        # 使用工厂
        if interface in cls._factories:
            instance = cls._factories[interface]()
            cls._services[interface] = instance
            return instance
        
        # 使用绑定
        if interface in cls._bindings:
            implementation = cls._bindings[interface]
            instance = implementation()
            cls._services[interface] = instance
            return instance
        
        # 直接创建
        try:
            instance = interface()
            cls._services[interface] = instance
            return instance
        except TypeError:
            raise ValueError(f"Cannot create instance of {interface.__name__}. Please bind it first.")
    
    @classmethod
    def register_singleton(cls, name: str, instance: Any):
        """注册单例
        
        Args:
            name: 名称
            instance: 实例
        """
        cls._singletons[name] = instance
        logger.debug(f"DI: Registered singleton '{name}'")
    
    @classmethod
    def get_singleton(cls, name: str) -> Optional[Any]:
        """获取单例
        
        Args:
            name: 名称
            
        Returns:
            实例
        """
        return cls._singletons.get(name)
    
    @classmethod
    def has(cls, interface: Type) -> bool:
        """检查服务是否存在
        
        Args:
            interface: 接口类型
            
        Returns:
            是否存在
        """
        return interface in cls._services or interface in cls._bindings or interface in cls._factories
    
    @classmethod
    def clear(cls):
        """清除所有服务（测试用）"""
        cls._services.clear()
        cls._bindings.clear()
        cls._factories.clear()
        cls._singletons.clear()
        logger.debug("DI: All services cleared")
    
    @classmethod
    def clear_services(cls):
        """只清除服务实例（保留绑定）"""
        cls._services.clear()
        logger.debug("DI: Service instances cleared")
    
    @classmethod
    def get_bindings_info(cls) -> Dict[str, str]:
        """获取绑定信息"""
        return {
            interface.__name__: impl.__name__
            for interface, impl in cls._bindings.items()
        }


def setup_container(collection_name: str = "knowledge_base", use_memory: bool = False):
    """
    配置依赖注入（使用 Qdrant 向量数据库）
    
    Args:
        collection_name: Qdrant 集合名称
        use_memory: 是否使用内存模式（测试用）
    
    改进：
    - 使用插件化 Embedding 服务
    - 支持配置驱动的 Provider 切换
    - 无需重建容器即可切换模型
    """
    from app.core.interfaces import (
        IEmbeddingService, IVectorStore, ILLMService,
        IDocumentLoader, IRetriever, IToolRegistry
    )
    from app.embeddings import get_embedding_service
    from app.embeddings.qdrant_store import get_qdrant_adapter
    from app.llm.factory import LLMFactory
    from app.embeddings.document import DocumentLoader
    from app.embeddings.retriever import Retriever
    from app.tools.registry import ToolRegistry
    from app.config import get_settings
    
    settings = get_settings()
    
    # 绑定接口到实现（使用插件化 Embedding）
    # 根据 EMBEDDING_PROVIDER 配置自动选择服务
    DIContainer.bind_factory(IEmbeddingService, get_embedding_service)
    DIContainer.bind_factory(IVectorStore, lambda: get_qdrant_adapter(collection_name, use_memory))
    DIContainer.bind_factory(ILLMService, lambda: LLMServiceAdapter())
    DIContainer.bind(IDocumentLoader, DocumentLoader)
    DIContainer.bind(IRetriever, Retriever)
    DIContainer.bind(IToolRegistry, ToolRegistry)
    
    logger.info(
        f"DI Container configured with Qdrant (collection: {collection_name}), "
        f"Embedding provider: {settings.EMBEDDING_PROVIDER}"
    )


class LLMServiceAdapter:
    """LLM 服务适配器
    
    将现有 LLMFactory 适配到接口
    """
    
    def __init__(self):
        from app.llm.factory import get_llm
        self._llm_factory = get_llm
    
    async def generate(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """生成文本"""
        llm = self._llm_factory()
        response = await llm.ainvoke(messages)
        return response.content
    
    async def generate_stream(
        self,
        messages: list,
        temperature: float = 0.7
    ):
        """流式生成"""
        llm = self._llm_factory()
        async for chunk in llm.astream(messages):
            yield chunk.content
    
    def bind_tools(self, tools: list):
        """绑定工具"""
        from app.llm.factory import get_llm_with_tools
        return get_llm_with_tools(None, tools)