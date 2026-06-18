"""Qdrant 向量存储实现"""
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import numpy as np
import hashlib
from app.config import get_settings


def _generate_int_id(doc_id: str) -> int:
    """将字符串 ID 转换为整数 ID（用于内存模式）"""
    # 使用 MD5 哈希生成一个稳定的整数 ID
    hash_value = hashlib.md5(doc_id.encode()).hexdigest()
    return int(hash_value[:8], 16)  # 取前8位转为整数


class QdrantVectorStore:
    """Qdrant 向量存储"""

    def __init__(
        self,
        collection_name: str = "knowledge_base",
        host: str = "localhost",
        port: int = 6333,
        vector_size: int = 2048,  # 默认使用智谱 embedding-3 的维度
        distance: Distance = Distance.COSINE,
        api_key: Optional[str] = None,
        path: Optional[str] = None,  # 本地存储路径（内存模式为 None）
    ):
        """
        初始化 Qdrant 向量存储

        Args:
            collection_name: 集合名称
            host: Qdrant 服务地址
            port: Qdrant 服务端口
            vector_size: 向量维度
            distance: 距离度量方式
            api_key: API 密钥（Qdrant Cloud 使用）
            path: 本地存储路径，None 表示内存模式
        """
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.distance = distance
        self._id_map: Dict[int, str] = {}  # 整数ID到原始ID的映射

        # 初始化客户端
        if path:
            # 本地持久化模式
            self.client = QdrantClient(path=path)
        elif api_key:
            # Qdrant Cloud
            self.client = QdrantClient(host=host, port=port, api_key=api_key)
        else:
            # 本地服务模式
            self.client = QdrantClient(host=host, port=port)

        # 创建集合（如果不存在）
        self._ensure_collection()

    def _ensure_collection(self):
        """确保集合存在"""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=self.distance,
                ),
            )
            print(f"[OK] 创建集合: {self.collection_name}")

    def add_vectors(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> bool:
        """
        批量添加向量

        Args:
            vectors: 向量列表
            payloads: 元数据列表
            ids: 文档ID列表（可选）

        Returns:
            是否成功
        """
        if len(vectors) != len(payloads):
            raise ValueError("向量数量与元数据数量不匹配")

        # 构建点结构
        points = []
        for i, (vector, payload) in enumerate(zip(vectors, payloads)):
            # 使用整数 ID（内存模式兼容）
            if ids and ids[i]:
                point_id = _generate_int_id(ids[i])
                # 保存原始 doc_id 到 payload
                payload["original_id"] = ids[i]
            else:
                point_id = i
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        # 批量上传
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        return True

    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        score_threshold: float = 0.0,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索

        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            filter_conditions: 过滤条件

        Returns:
            搜索结果列表
        """
        # 构建过滤条件
        query_filter = None
        if filter_conditions:
            must_conditions = []
            for key, value in filter_conditions.items():
                if isinstance(value, list):
                    # 多值匹配
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchAny(any=value),
                        )
                    )
                else:
                    # 单值匹配
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value),
                        )
                    )
            query_filter = models.Filter(must=must_conditions)

        # 执行搜索
        # 转换 numpy 数组为列表
        if isinstance(query_vector, np.ndarray):
            query_vector = query_vector.tolist()

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )

        # 格式化结果
        search_results = []
        for result in results:
            search_results.append(
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload,
                }
            )

        return search_results

    def delete_by_ids(self, ids: List[str]) -> bool:
        """根据ID删除向量"""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(
                points=ids,
            ),
        )
        return True

    def delete_collection(self) -> bool:
        """删除整个集合"""
        self.client.delete_collection(collection_name=self.collection_name)
        return True

    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        info = self.client.get_collection(collection_name=self.collection_name)
        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": info.status.value,
        }

    def clear_collection(self) -> bool:
        """清空集合"""
        self.delete_collection()
        self._ensure_collection()
        return True


class QdrantKnowledgeStore(QdrantVectorStore):
    """LOL 知识库专用 Qdrant 存储"""

    def __init__(self, collection_name: str = "knowledge_base", **kwargs):
        super().__init__(collection_name=collection_name, **kwargs)

    def add_document(
        self,
        doc_id: str,
        doc_type: str,
        content: str,
        vector: List[float],
        keywords: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        添加单个文档

        Args:
            doc_id: 文档ID
            doc_type: 文档类型（hero, item, skill, map, etc.）
            content: 文档内容
            vector: 向量
            keywords: 关键词列表
            metadata: 额外元数据
        """
        payload = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "content": content,
            "keywords": keywords or [],
            **(metadata or {}),
        }

        return self.add_vectors(
            vectors=[vector],
            payloads=[payload],
            ids=[doc_id],
        )

    def add_documents_batch(
        self,
        documents: List[Dict[str, Any]],
        vectors: Any,
    ) -> bool:
        """
        批量添加文档

        Args:
            documents: 文档列表，每个文档包含 doc_id, doc_type, content, keywords 等
            vectors: 对应的向量列表（可以是 numpy 数组或列表）
        """
        payloads = []
        ids = []

        # 转换 numpy 数组为列表
        if isinstance(vectors, np.ndarray):
            vectors = vectors.tolist()

        for doc in documents:
            payload = {
                "doc_id": doc.get("doc_id"),
                "doc_type": doc.get("doc_type"),
                "content": doc.get("content", ""),
                "embedding_text": doc.get("embedding_text", ""),
                "keywords": doc.get("keywords", []),
                "title": doc.get("title", ""),
                "summary": doc.get("summary", ""),
            }
            # 添加其他元数据
            for key in ["hero_name", "item_name", "skill_name", "map_name", "tier", "role", "tags"]:
                if key in doc:
                    payload[key] = doc[key]

            payloads.append(payload)
            ids.append(doc.get("doc_id"))

        return self.add_vectors(vectors=vectors, payloads=payloads, ids=ids)

    def search_by_type(
        self,
        query_vector: List[float],
        doc_type: str,
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """按文档类型搜索"""
        return self.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_conditions={"doc_type": doc_type},
        )

    def search_by_keywords(
        self,
        query_vector: List[float],
        keywords: List[str],
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """按关键词搜索"""
        return self.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_conditions={"keywords": keywords},
        )


def get_qdrant_store(
    collection_name: str = "knowledge_base",
    use_memory: bool = False,
    path: Optional[str] = None,
) -> QdrantVectorStore:
    """
    获取 Qdrant 存储实例

    Args:
        collection_name: 集合名称
        use_memory: 是否使用内存模式
        path: 本地存储路径
    """
    settings = get_settings()

    if use_memory:
        return QdrantVectorStore(
            collection_name=collection_name,
            path=":memory:",
        )

    return QdrantVectorStore(
        collection_name=collection_name,
        host=getattr(settings, "QDRANT_HOST", "localhost"),
        port=getattr(settings, "QDRANT_PORT", 6333),
        api_key=getattr(settings, "QDRANT_API_KEY", None),
        path=path,
    )


class QdrantVectorStoreAdapter:
    """
    Qdrant 向量存储适配器

    将 QdrantVectorStore 适配到现有的 RAGService 和 Retriever 接口
    兼容 IVectorStore 接口和 search_by_similarity 方法
    """

    def __init__(
        self,
        collection_name: str = "knowledge_base",
        host: str = "localhost",
        port: int = 6333,
        use_memory: bool = False,
        **kwargs
    ):
        """
        初始化适配器

        Args:
            collection_name: 集合名称
            host: Qdrant 服务地址
            port: Qdrant 服务端口
            use_memory: 是否使用内存模式
        """
        if use_memory:
            self._store = QdrantVectorStore(
                collection_name=collection_name,
                path=":memory:",
                **kwargs
            )
        else:
            self._store = QdrantVectorStore(
                collection_name=collection_name,
                host=host,
                port=port,
                **kwargs
            )

        # 用于兼容 Retriever 的 Session 属性
        self.Session = lambda: None

    def add_document(
        self,
        content: str,
        embedding: np.ndarray,
        metadata: Dict[str, Any] = None,
        source: str = "",
        doc_type: str = "text"
    ) -> int:
        """
        添加单个文档（兼容 IVectorStore 接口）

        Args:
            content: 文档内容
            embedding: 向量
            metadata: 元数据
            source: 来源
            doc_type: 文档类型

        Returns:
            文档ID
        """
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()

        doc_id = f"{doc_type}_{source}_{hashlib.md5(content.encode()).hexdigest()[:8]}"

        payload = {
            "content": content,
            "metadata": metadata or {},
            "source": source,
            "doc_type": doc_type,
        }

        self._store.add_vectors(
            vectors=[embedding],
            payloads=[payload],
            ids=[doc_id],
        )

        return _generate_int_id(doc_id)

    def add_documents_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[int]:
        """
        批量添加文档（兼容 IVectorStore 接口）

        Args:
            documents: 文档列表，每个文档包含 content, embedding, metadata 等

        Returns:
            文档ID列表
        """
        vectors = []
        payloads = []
        ids = []

        for doc in documents:
            embedding = doc.get("embedding")
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            vectors.append(embedding)

            payload = {
                "content": doc.get("content", ""),
                "metadata": doc.get("metadata", {}),
                "source": doc.get("source", ""),
                "doc_type": doc.get("doc_type", "text"),
            }
            payloads.append(payload)

            # 生成文档ID
            doc_id = f"{doc.get('doc_type', 'text')}_{doc.get('source', '')}_{hashlib.md5(doc.get('content', '').encode()).hexdigest()[:8]}"
            ids.append(doc_id)

        self._store.add_vectors(vectors=vectors, payloads=payloads, ids=ids)

        return [_generate_int_id(id_) for id_ in ids]

    def search_by_similarity(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        threshold: float = 0.0,
        doc_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索（兼容 Retriever 接口）

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            threshold: 相似度阈值
            doc_type: 文档类型过滤

        Returns:
            搜索结果列表
        """
        if isinstance(query_embedding, np.ndarray):
            query_embedding = query_embedding.tolist()

        filter_conditions = None
        if doc_type:
            filter_conditions = {"doc_type": doc_type}

        results = self._store.search(
            query_vector=query_embedding,
            top_k=top_k,
            score_threshold=threshold,
            filter_conditions=filter_conditions,
        )

        # 格式化结果以兼容 Retriever
        formatted_results = []
        for result in results:
            payload = result.get("payload", {})
            formatted_results.append({
                "id": result.get("id"),
                "content": payload.get("content", ""),
                "score": result.get("score", 0.0),
                "metadata": payload.get("metadata", {}),
                "source": payload.get("source", ""),
                "doc_type": payload.get("doc_type", ""),
            })

        return formatted_results

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        threshold: float = 0.0,
        doc_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """别名方法，兼容不同调用方式"""
        return self.search_by_similarity(
            query_embedding=query_embedding,
            top_k=top_k,
            threshold=threshold,
            doc_type=doc_type
        )

    def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """获取单个文档"""
        # Qdrant 不支持直接按ID获取，需要通过scroll
        try:
            results = self._store.client.scroll(
                collection_name=self._store.collection_name,
                limit=1,
                with_payload=True,
                with_vectors=False,
            )[0]

            for point in results:
                if point.id == doc_id:
                    payload = point.payload
                    return {
                        "id": point.id,
                        "content": payload.get("content", ""),
                        "metadata": payload.get("metadata", {}),
                        "source": payload.get("source", ""),
                        "doc_type": payload.get("doc_type", ""),
                    }
        except Exception:
            pass

        return None

    def delete_document(self, doc_id: int) -> bool:
        """删除文档"""
        try:
            self._store.client.delete(
                collection_name=self._store.collection_name,
                points_selector=models.PointIdsList(points=[doc_id]),
            )
            return True
        except Exception:
            return False

    def delete_by_source(self, source: str) -> int:
        """按来源删除"""
        # Qdrant 需要通过过滤条件删除
        try:
            self._store.client.delete(
                collection_name=self._store.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="source",
                                match=models.MatchValue(value=source),
                            )
                        ]
                    )
                ),
            )
            return 1  # 无法精确返回删除数量
        except Exception:
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        info = self._store.get_collection_info()
        return {
            "collection_name": info["name"],
            "total_documents": info["points_count"],
            "status": info["status"],
            "backend": "qdrant",
        }

    # 代理其他 Qdrant 方法
    def __getattr__(self, name):
        return getattr(self._store, name)


def get_qdrant_adapter(
    collection_name: str = "knowledge_base",
    use_memory: bool = False,
    **kwargs
) -> QdrantVectorStoreAdapter:
    """
    获取 Qdrant 适配器实例（用于 RAGService）

    Args:
        collection_name: 集合名称
        use_memory: 是否使用内存模式
    """
    settings = get_settings()
    
    # 从配置获取向量维度
    vector_size = getattr(settings, "EMBEDDING_DIM", 2048)

    return QdrantVectorStoreAdapter(
        collection_name=collection_name,
        host=getattr(settings, "QDRANT_HOST", "localhost"),
        port=getattr(settings, "QDRANT_PORT", 6333),
        use_memory=use_memory,
        vector_size=vector_size,  # 使用配置的向量维度
        **kwargs
    )