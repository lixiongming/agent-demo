"""向量存储管理

功能：
- 向量文档存储
- MySQL持久化存储
- Redis缓存加速
- 向量检索
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import numpy as np
import json
from datetime import datetime
import pymysql
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os


Base = declarative_base()


@dataclass
class VectorDocument:
    """向量文档数据结构"""
    id: Optional[int] = None
    content: str = ""
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = None
    source: str = ""
    doc_type: str = "text"
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class VectorDocumentModel(Base):
    """向量文档数据库模型"""
    __tablename__ = "vector_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=True)  # 向量二进制存储
    metadata = Column(JSON, nullable=True)
    source = Column(String(255), nullable=True)
    doc_type = Column(String(50), default="text")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class VectorStore:
    """向量存储管理
    
    功能：
    - MySQL持久化存储
    - Redis缓存加速（可选）
    - 批量操作优化
    - 索引管理
    """
    
    def __init__(
        self,
        db_host: str = "localhost",
        db_port: int = 3306,
        db_user: str = "root",
        db_password: str = "",
        db_name: str = "agent_db",
        table_name: str = "vector_documents",
        use_cache: bool = True
    ):
        """初始化向量存储
        
        Args:
            db_host: 数据库主机
            db_port: 数据库端口
            db_user: 数据库用户
            db_password: 数据库密码
            db_name: 数据库名称
            table_name: 表名称
            use_cache: 是否使用缓存
        """
        self.table_name = table_name
        self.use_cache = use_cache
        
        # 创建数据库连接
        db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        self.engine = create_engine(db_url, pool_recycle=3600)
        self.Session = sessionmaker(bind=self.engine)
        
        # 创建表
        Base.metadata.create_all(self.engine)
        
        # 内存缓存（生产环境建议用Redis）
        self._cache: Dict[int, VectorDocument] = {}
        
    def add_document(
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
        session = self.Session()
        
        try:
            # 向量转二进制
            embedding_bytes = embedding.tobytes() if embedding is not None else None
            
            doc = VectorDocumentModel(
                content=content,
                embedding=embedding_bytes,
                metadata=metadata or {},
                source=source,
                doc_type=doc_type
            )
            
            session.add(doc)
            session.commit()
            
            doc_id = doc.id
            
            # 缓存
            if self.use_cache:
                self._cache[doc_id] = VectorDocument(
                    id=doc_id,
                    content=content,
                    embedding=embedding,
                    metadata=metadata,
                    source=source,
                    doc_type=doc_type
                )
            
            return doc_id
            
        finally:
            session.close()
    
    def add_documents_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[int]:
        """批量添加文档
        
        Args:
            documents: 文档列表，每个文档包含 content, embedding, metadata等
            
        Returns:
            文档ID列表
        """
        session = self.Session()
        
        try:
            doc_ids = []
            doc_models = []
            
            for doc_data in documents:
                content = doc_data.get("content", "")
                embedding = doc_data.get("embedding")
                metadata = doc_data.get("metadata", {})
                source = doc_data.get("source", "")
                doc_type = doc_data.get("doc_type", "text")
                
                embedding_bytes = embedding.tobytes() if embedding is not None else None
                
                doc = VectorDocumentModel(
                    content=content,
                    embedding=embedding_bytes,
                    metadata=metadata,
                    source=source,
                    doc_type=doc_type
                )
                
                doc_models.append(doc)
            
            # 批量插入
            session.bulk_save_objects(doc_models)
            session.commit()
            
            # 获取ID
            for doc in doc_models:
                doc_ids.append(doc.id)
            
            # 缓存
            if self.use_cache:
                for doc_id, doc_data in zip(doc_ids, documents):
                    self._cache[doc_id] = VectorDocument(
                        id=doc_id,
                        content=doc_data.get("content", ""),
                        embedding=doc_data.get("embedding"),
                        metadata=doc_data.get("metadata", {}),
                        source=doc_data.get("source", ""),
                        doc_type=doc_data.get("doc_type", "text")
                    )
            
            return doc_ids
            
        finally:
            session.close()
    
    def get_document(self, doc_id: int) -> Optional[VectorDocument]:
        """获取单个文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档对象
        """
        # 先查缓存
        if self.use_cache and doc_id in self._cache:
            return self._cache[doc_id]
        
        session = self.Session()
        
        try:
            doc = session.query(VectorDocumentModel).filter_by(id=doc_id).first()
            
            if doc is None:
                return None
            
            # 向量解码
            embedding = None
            if doc.embedding:
                # 假设向量维度为1024（bge-large-zh-v1.5）
                embedding = np.frombuffer(doc.embedding, dtype=np.float32)
            
            result = VectorDocument(
                id=doc.id,
                content=doc.content,
                embedding=embedding,
                metadata=doc.metadata or {},
                source=doc.source,
                doc_type=doc.doc_type,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            )
            
            # 缓存
            if self.use_cache:
                self._cache[doc_id] = result
            
            return result
            
        finally:
            session.close()
    
    def search_by_similarity(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        threshold: float = 0.0,
        doc_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            threshold: 相似度阈值
            doc_type: 文档类型过滤
            
        Returns:
            搜索结果列表
        """
        session = self.Session()
        
        try:
            # 查询所有文档（生产环境建议使用专门的向量数据库）
            query = session.query(VectorDocumentModel)
            
            if doc_type:
                query = query.filter_by(doc_type=doc_type)
            
            docs = query.all()
            
            results = []
            for doc in docs:
                if doc.embedding is None:
                    continue
                
                # 解码向量
                doc_embedding = np.frombuffer(doc.embedding, dtype=np.float32)
                
                # 计算相似度（cosine）
                similarity = float(np.dot(query_embedding, doc_embedding))
                
                if similarity >= threshold:
                    results.append({
                        "id": doc.id,
                        "content": doc.content,
                        "score": similarity,
                        "metadata": doc.metadata,
                        "source": doc.source,
                        "doc_type": doc.doc_type
                    })
            
            # 排序
            results.sort(key=lambda x: x["score"], reverse=True)
            
            return results[:top_k]
            
        finally:
            session.close()
    
    def delete_document(self, doc_id: int) -> bool:
        """删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
        """
        session = self.Session()
        
        try:
            doc = session.query(VectorDocumentModel).filter_by(id=doc_id).first()
            
            if doc is None:
                return False
            
            session.delete(doc)
            session.commit()
            
            # 清除缓存
            if self.use_cache and doc_id in self._cache:
                del self._cache[doc_id]
            
            return True
            
        finally:
            session.close()
    
    def delete_by_source(self, source: str) -> int:
        """按来源删除文档
        
        Args:
            source: 来源标识
            
        Returns:
            删除数量
        """
        session = self.Session()
        
        try:
            count = session.query(VectorDocumentModel).filter_by(source=source).delete()
            session.commit()
            
            # 清除缓存
            if self.use_cache:
                for doc_id in list(self._cache.keys()):
                    if self._cache[doc_id].source == source:
                        del self._cache[doc_id]
            
            return count
            
        finally:
            session.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        session = self.Session()
        
        try:
            total_count = session.query(VectorDocumentModel).count()
            
            # 按类型统计
            from sqlalchemy import func
            type_counts = session.query(
                VectorDocumentModel.doc_type,
                func.count(VectorDocumentModel.id)
            ).group_by(VectorDocumentModel.doc_type).all()
            
            return {
                "total_count": total_count,
                "type_counts": {t: c for t, c in type_counts},
                "cache_size": len(self._cache),
                "table_name": self.table_name
            }
            
        finally:
            session.close()
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()