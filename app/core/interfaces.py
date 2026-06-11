"""接口抽象层

架构：
- 定义核心接口
- 支持实现替换
- 便于测试 Mock
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
import numpy as np


class IEmbeddingService(ABC):
    """向量嵌入服务接口"""
    
    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """单个文本向量化
        
        Args:
            text: 文本内容
            
        Returns:
            向量数组
        """
        pass
    
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """批量文本向量化
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        pass


class IVectorStore(ABC):
    """向量存储接口"""
    
    @abstractmethod
    async def add_document(
        self,
        content: str,
        embedding: np.ndarray,
        metadata: Dict[str, Any] = None,
        source: str = "",
        doc_type: str = "text"
    ) -> int:
        """添加单个文档
        
        Args:
            content: 文档内容
            embedding: 向量
            metadata: 元数据
            source: 来源
            doc_type: 文档类型
            
        Returns:
            文档ID
        """
        pass
    
    @abstractmethod
    async def add_documents_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[int]:
        """批量添加文档
        
        Args:
            documents: 文档列表
            
        Returns:
            文档ID列表
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        threshold: float = 0.0,
        doc_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """向量检索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            threshold: 相似度阈值
            doc_type: 文档类型过滤
            
        Returns:
            搜索结果列表
        """
        pass
    
    @abstractmethod
    async def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """获取单个文档"""
        pass
    
    @abstractmethod
    async def delete_document(self, doc_id: int) -> bool:
        """删除文档"""
        pass
    
    @abstractmethod
    async def delete_by_source(self, source: str) -> int:
        """按来源删除"""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pass


class ILLMService(ABC):
    """LLM 服务接口"""
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Any],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """生成文本
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            生成的文本
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Any],
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """流式生成
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            
        Yields:
            生成的文本片段
        """
        pass
    
    @abstractmethod
    def bind_tools(self, tools: List[Any]) -> Any:
        """绑定工具"""
        pass


class IDocumentLoader(ABC):
    """文档加载接口"""
    
    @abstractmethod
    def load_file(self, file_path: str) -> List[Any]:
        """加载单个文件"""
        pass
    
    @abstractmethod
    def load_directory(
        self,
        directory: str,
        file_types: List[str] = None
    ) -> List[Any]:
        """加载目录"""
        pass


class IRetriever(ABC):
    """检索器接口"""
    
    @abstractmethod
    async def retrieve(
        self,
        question: str,
        top_k: int = 5,
        threshold: float = 0.5,
        doc_type: Optional[str] = None,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """检索相关文档"""
        pass
    
    @abstractmethod
    async def hybrid_retrieve(
        self,
        question: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """混合检索"""
        pass


class IToolRegistry(ABC):
    """工具注册中心接口"""
    
    @abstractmethod
    def register(self, tool: Any):
        """注册工具"""
        pass
    
    @abstractmethod
    def get_tool(self, name: str) -> Optional[Any]:
        """获取工具"""
        pass
    
    @abstractmethod
    def list_tools(self) -> List[Any]:
        """列出所有工具"""
        pass
    
    @abstractmethod
    async def execute(self, name: str, args: dict) -> Any:
        """执行工具"""
        pass


class IMemoryService(ABC):
    """记忆服务接口"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取记忆"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = None):
        """设置记忆"""
        pass
    
    @abstractmethod
    async def delete(self, key: str):
        """删除记忆"""
        pass


class IRAGService(ABC):
    """RAG 服务接口"""
    
    @abstractmethod
    async def query(
        self,
        question: str,
        top_k: int = 5,
        threshold: float = 0.5,
        doc_type: Optional[str] = None,
        filters: Dict[str, Any] = None,
        hybrid: bool = False
    ) -> Dict[str, Any]:
        """查询
        
        Args:
            question: 问题
            top_k: 返回数量
            threshold: 相似度阈值
            doc_type: 文档类型过滤
            filters: 其他过滤条件
            hybrid: 是否混合检索
            
        Returns:
            查询结果
        """
        pass
    
    @abstractmethod
    async def ingest_file(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """导入文件"""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pass