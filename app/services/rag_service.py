"""RAG业务服务

功能：
- 文档入库流程
- 检索+生成流程
- 结果优化
- 会话管理

功能：
- 业务逻辑封装
- 流程编排
- 异步处理
"""
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime
import os

from app.embeddings import EmbeddingService, VectorStore, DocumentLoader, Retriever
from app.embeddings.document_loader import DocumentChunk


class RAGService:
    """RAG检索增强生成服务
    
    功能：
    - 完整的RAG流程
    - 文档入库自动化
    - 检索优化
    - 结果生成
    """
    
    def __init__(
        self,
        embedding_model: str = "bge-large-zh-v1.5",
        db_config: Dict[str, Any] = None,
        llm_client: Any = None,
        chunk_size: int = 500,
        top_k: int = 5
    ):
        """初始化RAG服务
        
        Args:
            embedding_model: 向量化模型
            db_config: 数据库配置
            llm_client: LLM客户端
            chunk_size: 文档分块大小
            top_k: 检索数量
        """
        # 默认数据库配置
        self.db_config = db_config or {
            "db_host": os.getenv("MYSQL_HOST", "localhost"),
            "db_port": int(os.getenv("MYSQL_PORT", 3306)),
            "db_user": os.getenv("MYSQL_USER", "root"),
            "db_password": os.getenv("MYSQL_PASSWORD", ""),
            "db_name": os.getenv("MYSQL_DATABASE", "agent_db")
        }
        
        # 初始化组件
        self.embedding_service = EmbeddingService(
            model_name=embedding_model,
            model_path=os.path.join(os.getcwd(), embedding_model) if os.path.exists(os.path.join(os.getcwd(), embedding_model)) else None
        )
        
        self.vector_store = VectorStore(**self.db_config)
        
        self.document_loader = DocumentLoader(chunk_size=chunk_size)
        
        self.retriever = Retriever(
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            top_k=top_k
        )
        
        self.llm_client = llm_client
        
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
        embeddings = self.embedding_service.embed_texts(contents)
        
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
        
        doc_ids = self.vector_store.add_documents_batch(documents)
        
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
            directory: 目录路径
            file_types: 文件类型过滤
            metadata: 额外元数据
            
        Returns:
            入库结果
        """
        # 加载所有文档
        chunks = self.document_loader.load_directory(
            directory,
            file_types=file_types
        )
        
        if not chunks:
            return {
                "directory": directory,
                "total_chunks": 0,
                "stored_ids": [],
                "status": "no_documents",
                "timestamp": datetime.now().isoformat()
            }
        
        # 批量向量化
        contents = [chunk.content for chunk in chunks]
        embeddings = self.embedding_service.embed_texts(contents)
        
        # 批量存储
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
        
        doc_ids = self.vector_store.add_documents_batch(documents)
        
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
        # 向量化
        embedding = self.embedding_service.embed_text(content)
        
        # 存储
        doc_id = self.vector_store.add_document(
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            source=source,
            doc_type="text"
        )
        
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
        # 1. 检索相关文档
        if hybrid:
            results = self.retriever.hybrid_retrieve(question, top_k=top_k)
        else:
            results = self.retriever.retrieve(
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
        
        # 构建提示词
        prompt = f"""基于以下文档内容回答问题。

文档内容：
{context}

问题：{question}

请根据文档内容给出准确、详细的回答。如果文档中没有相关信息，请说明。"""

        # 调用LLM
        try:
            if hasattr(self.llm_client, 'ainvoke'):
                response = await self.llm_client.ainvoke(prompt)
                return response.content
            elif hasattr(self.llm_client, 'invoke'):
                response = self.llm_client.invoke(prompt)
                return response.content
            else:
                return str(self.llm_client(prompt))
        except Exception as e:
            return f"生成回答失败: {str(e)}"
    
    async def delete_document(self, doc_id: int) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
        """
        return self.vector_store.delete_document(doc_id)
    
    async def delete_by_source(self, source: str) -> int:
        """按来源删除
        
        Args:
            source: 来源标识
            
        Returns:
            删除数量
        """
        return self.vector_store.delete_by_source(source)
    
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