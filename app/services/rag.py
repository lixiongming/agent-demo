"""RAG业务服务

功能：
- 文档入库流程
- 检索+生成流程
- 结果优化
- 三级相似度策略

- 依赖注入支持
- 异步操作
- 可测试
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import asyncio

from app.embeddings import ZhipuEmbeddingService, DocumentLoader, Retriever, DocumentChunk, get_embedding_service
from app.embeddings.qdrant_store import get_qdrant_adapter
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# 允许入库的基础目录（安全白名单）
ALLOWED_BASE_DIRS = os.environ.get("RAG_ALLOWED_DIRS", "/data/documents,/app/documents").split(",")


class RAGService:
    """RAG检索增强生成服务
    
    功能：
    - 完整的RAG流程
    - 文档入库自动化
    - 检索优化
    - 结果生成
    
    - 支持依赖注入
    - 异步操作
    - 三级相似度策略
    """
    
    def __init__(
        self,
        embedding_model: str = None,
        collection_name: str = None,
        llm_client: Any = None,
        chunk_size: int = 500,
        top_k: int = 5,
        # 依赖注入参数（可选）
        embedding_service: Any = None,
        vector_store: Any = None,
        document_loader: Any = None
    ):
        """初始化RAG服务
        
        Args:
            embedding_model: 向量化模型名称（默认从配置读取）
            collection_name: Qdrant 集合名称
            llm_client: LLM客户端
            chunk_size: 文档分块大小
            top_k: 检索数量
            embedding_service: 向量嵌入服务（依赖注入）
            vector_store: 向量存储（依赖注入）
            document_loader: 文档加载器（依赖注入）
        """
        settings = get_settings()
        
        # 依赖注入支持
        if embedding_service:
            self.embedding_service = embedding_service
        else:
            # 使用智谱 AI Embedding 服务
            self.embedding_service = get_embedding_service()
        
        if vector_store:
            self.vector_store = vector_store
        else:
            # 使用 Qdrant 向量存储
            collection_name = collection_name or getattr(settings, "QDRANT_COLLECTION", "knowledge_base")
            self.vector_store = get_qdrant_adapter(collection_name=collection_name)
        
        if document_loader:
            self.document_loader = document_loader
        else:
            self.document_loader = DocumentLoader(chunk_size=chunk_size)
        
        self.retriever = Retriever(
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            top_k=top_k
        )
        
        self.llm_client = llm_client
        self.top_k = top_k
        
        logger.info("RAGService initialized")
        
    async def ingest_document(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """文档入库
        
        Args:
            file_path: 文件路径
            metadata: 额外元数据
            
        Returns:
            入库结果
        """
        # 1. 加载文档
        chunks = self.document_loader.load_file(file_path)
        
        # 2. 批量向量化
        contents = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_service.embed_texts(contents)
        
        # 3. 批量存储
        documents = []
        for i, chunk in enumerate(chunks):
            doc_metadata = chunk.metadata.copy()
            if metadata:
                doc_metadata.update(metadata)
            
            documents.append({
                "content": chunk.content,
                "embedding": embeddings[i],
                "metadata": doc_metadata,
                "source": chunk.source,
                "doc_type": chunk.doc_type
            })
        
        doc_ids = await asyncio.to_thread(self.vector_store.add_documents_batch, documents)
        
        return {
            "file_path": file_path,
            "total_chunks": len(chunks),
            "stored_ids": doc_ids,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    
    async def ingest_directory(
        self,
        directory: str,
        file_types: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """批量入库目录
        
        Args:
            directory: 目录路径（必须在白名单目录内）
            file_types: 文件类型过滤
            metadata: 额外元数据
            
        Returns:
            入库结果
        """
        # 路径安全检查：防止路径遍历
        real_dir = os.path.realpath(directory)
        allowed = any(real_dir.startswith(os.path.realpath(d)) for d in ALLOWED_BASE_DIRS if os.path.isdir(d))
        if not allowed:
            logger.warning(f"Directory access denied: {directory} (resolved: {real_dir})")
            return {
                "directory": directory,
                "total_chunks": 0,
                "stored_ids": [],
                "status": "access_denied",
                "message": f"目录不在允许列表内: {ALLOWED_BASE_DIRS}",
                "timestamp": datetime.now().isoformat()
            }
        
        chunks = await asyncio.to_thread(
            self.document_loader.load_directory, directory, file_types
        )
        
        if not chunks:
            return {
                "directory": directory,
                "total_chunks": 0,
                "stored_ids": [],
                "status": "no_documents",
                "timestamp": datetime.now().isoformat()
            }
        
        contents = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_service.embed_texts(contents)
        
        documents = []
        for i, chunk in enumerate(chunks):
            doc_metadata = chunk.metadata.copy()
            if metadata:
                doc_metadata.update(metadata)
            
            documents.append({
                "content": chunk.content,
                "embedding": embeddings[i],
                "metadata": doc_metadata,
                "source": chunk.source,
                "doc_type": chunk.doc_type
            })
        
        doc_ids = await asyncio.to_thread(self.vector_store.add_documents_batch, documents)
        
        logger.info(f"Directory ingested: {directory}, chunks: {len(chunks)}")
        
        return {
            "directory": directory,
            "total_chunks": len(chunks),
            "stored_ids": doc_ids,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    
    async def ingest_text(
        self,
        content: str,
        source: str = "",
        metadata: Dict[str, Any] = None
    ) -> int:
        """单文本入库
        
        Args:
            content: 文本内容
            source: 来源标识
            metadata: 元数据
            
        Returns:
            文档ID
        """
        embedding = await self.embedding_service.embed_text(content)
        
        doc_id = await asyncio.to_thread(
            self.vector_store.add_document,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            source=source,
            doc_type="text"
        )
        
        logger.info(f"Text ingested: doc_id={doc_id}, source={source}")
        
        return doc_id
    
    async def query(
        self,
        question: str,
        top_k: int = 5,
        threshold: float = 0.5,
        doc_type: Optional[str] = None,
        filters: Dict[str, Any] = None,
        hybrid: bool = False
    ) -> Dict[str, Any]:
        """RAG查询
        
        Args:
            question: 问题
            top_k: 检索数量
            threshold: 相似度阈值
            doc_type: 文档类型过滤
            filters: 其他过滤条件
            hybrid: 是否使用混合检索
            
        Returns:
            查询结果
        """
        logger.info(f"RAG query: question='{question[:50]}...', top_k={top_k}")
        
        # 1. 检索相关文档
        if hybrid:
            results = await self.retriever.hybrid_retrieve(question, top_k=top_k)
        else:
            results = await self.retriever.retrieve(
                question,
                top_k=top_k,
                threshold=threshold,
                doc_type=doc_type,
                filters=filters
            )
        
        # 2. 构建上下文
        context = self._build_context(results)
        
        # 3. 如果有LLM，生成回答
        answer = None
        if self.llm_client and results:
            answer = await self._generate_answer(question, context)
        
        logger.info(f"RAG query result: {len(results)} documents found")
        
        return {
            "question": question,
            "answer": answer,
            "context": context,
            "sources": [
                {
                    "id": r["id"],
                    "content": r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"],
                    "score": r["score"],
                    "source": r.get("source", "")
                }
                for r in results
            ],
            "total_results": len(results),
            "search_type": "hybrid" if hybrid else "vector",
            "timestamp": datetime.now().isoformat()
        }
    
    def _build_context(
        self,
        results: List[Dict[str, Any]]
    ) -> str:
        """构建上下文
        
        Args:
            results: 检索结果
            
        Returns:
            上下文文本
        """
        if not results:
            return ""
        
        context_parts = []
        
        for i, result in enumerate(results):
            context_parts.append(f"[文档{i+1}]\n{result['content']}\n")
        
        return "\n".join(context_parts)
    
    async def _generate_answer(
        self,
        question: str,
        context: str
    ) -> str:
        """生成回答
        
        Args:
            question: 问题
            context: 上下文
            
        Returns:
            回答
        """
        if not self.llm_client:
            return ""
        
        prompt = f"""基于以下文档内容回答问题。

文档内容：
{context}

问题：{question}

请根据文档内容给出准确、详细的回答。如果文档中没有相关信息，请说明。"""
        
        try:
            if hasattr(self.llm_client, 'ainvoke'):
                response = await self.llm_client.ainvoke(prompt)
                return response.content
            elif hasattr(self.llm_client, 'invoke'):
                response = await asyncio.to_thread(self.llm_client.invoke, prompt)
                return response.content
            else:
                return str(self.llm_client(prompt))
        except Exception as e:
            logger.error(f"Generate answer error: {e}")
            return f"生成回答失败: {str(e)}"
    
    async def delete_document(self, doc_id: int) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
        """
        result = await asyncio.to_thread(self.vector_store.delete_document, doc_id)
        logger.info(f"Document deleted: doc_id={doc_id}, result={result}")
        return result
    
    async def delete_by_source(self, source: str) -> int:
        """按来源删除
        
        Args:
            source: 来源标识
            
        Returns:
            删除数量
        """
        count = await asyncio.to_thread(self.vector_store.delete_by_source, source)
        logger.info(f"Documents deleted by source: source={source}, count={count}")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "vector_store": self.vector_store.get_stats(),
            "embedding": self.embedding_service.get_model_info(),
            "retriever": {
                "top_k": self.retriever.top_k,
                "threshold": self.retriever.threshold,
                "rerank_enabled": self.retriever.rerank_enabled
            }
        }