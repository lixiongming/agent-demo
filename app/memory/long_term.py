"""长期记忆 - Qdrant 向量存储

架构设计：
- 使用 Qdrant 存储长期记忆向量（而非 MySQL，MySQL 不支持向量操作）
- 所有 session 的记忆存储在同一个集合 long_term_memory 中
- 通过 session_id 过滤条件区分不同会话的记忆
- 向量检索使用 Qdrant 原生搜索，而非数据库的 <=> 操作符

大厂实践：
- OpenAI：向量存储关键事实
- Google MemGPT：语义检索记忆
- 阿里通义：Qdrant 向量存储
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio

from app.config import get_settings
from app.core.logger import get_logger
from app.embeddings import get_embedding_service
from app.embeddings.qdrant_store import QdrantVectorStore
import json

logger = get_logger(__name__)
settings = get_settings()


class LongTermMemory:
    """长期记忆

    使用 Qdrant 向量数据库存储长期记忆，支持向量检索和语义搜索。

    设计原则：
    1. 向量存储和检索全部走 Qdrant（MySQL 不支持向量操作）
    2. 所有 session 共用一个集合，通过 payload 的 session_id 区分
    3. 每条记忆的 payload 包含：session_id, content, metadata, created_at
    """

    # 统一使用一个集合存储所有会话的长期记忆
    COLLECTION_NAME = "long_term_memory"

    def __init__(self, session_id: str, db=None):
        """初始化长期记忆

        Args:
            session_id: 会话 ID
            db: 数据库会话（保留参数兼容，但不再用于向量操作）
        """
        self.session_id = session_id
        self.db = db
        self.limit = settings.MEMORY_LONG_TERM_LIMIT

        # 使用 Qdrant 存储向量，集合名统一为 long_term_memory
        self.qdrant = QdrantVectorStore(
            collection_name=self.COLLECTION_NAME,
            host=getattr(settings, "QDRANT_HOST", "localhost"),
            port=getattr(settings, "QDRANT_PORT", 6333),
            vector_size=getattr(settings, "EMBEDDING_DIM", 2048),
        )

        # 使用正确的 embedding 服务
        self.embedding_model = get_embedding_service()

    async def add_memory(
        self,
        content: str,
        metadata: Optional[dict] = None,
        embedding: Optional[List[float]] = None,
    ):
        """添加长期记忆

        Args:
            content: 记忆内容
            metadata: 元数据
            embedding: 预计算的向量（可选，如果没有则自动生成）
        """
        try:
            # 如果没有提供向量，自动生成
            if embedding is None:
                embedding = await self.embedding_model.embed_text(content)
                # numpy 数组转列表
                if hasattr(embedding, "tolist"):
                    embedding = embedding.tolist()

            # 生成唯一 ID
            memory_id = f"mem_{self.session_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            # 构建存储到 Qdrant 的 payload
            payload = {
                "session_id": self.session_id,
                "content": content,
                "metadata": json.dumps(metadata or {}),
                "created_at": datetime.now().isoformat(),
            }

            # 存储到 Qdrant
            await asyncio.to_thread(
                self.qdrant.add_vectors,
                vectors=[embedding],
                payloads=[payload],
                ids=[memory_id],
            )

            logger.debug(f"Long-term memory added: {content[:50]}")

        except Exception as e:
            logger.error(f"Failed to add long-term memory: {e}")

    async def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索

        使用 Qdrant 原生向量搜索，而非数据库的 <=> 操作符。

        Args:
            query_embedding: 查询向量
            limit: 返回数量
            threshold: 相似度阈值

        Returns:
            记忆列表
        """
        try:
            # numpy 数组转列表
            if hasattr(query_embedding, "tolist"):
                query_embedding = query_embedding.tolist()

            # 使用 Qdrant 搜索，通过 session_id 过滤
            results = await asyncio.to_thread(
                self.qdrant.search,
                query_vector=query_embedding,
                top_k=limit,
                score_threshold=threshold,
                filter_conditions={"session_id": self.session_id},
            )

            # 格式化结果
            memories = []
            for result in results:
                payload = result.get("payload", {})
                metadata = payload.get("metadata", "{}")
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}

                memories.append({
                    "content": payload.get("content", ""),
                    "metadata": metadata,
                    "created_at": payload.get("created_at", ""),
                    "similarity": result.get("score", 0.0),
                })

            return memories

        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    async def search_by_keyword(
        self,
        keyword: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """关键词搜索

        使用 Qdrant 的 payload 过滤进行关键词匹配。
        注意：Qdrant 的全文搜索需要额外配置，这里使用简单的匹配。

        Args:
            keyword: 关键词
            limit: 返回数量

        Returns:
            记忆列表
        """
        try:
            # Qdrant 不直接支持 LIKE 查询
            # 方案：先通过向量搜索获取相关记忆，再在结果中过滤关键词
            # 更好的方案：使用 Qdrant 的全文索引功能（需要配置）
            # 这里使用向量搜索 + 关键词过滤的混合方式

            # 先用关键词生成向量，做向量搜索
            keyword_embedding = await self.embedding_model.embed_text(keyword)
            if hasattr(keyword_embedding, "tolist"):
                keyword_embedding = keyword_embedding.tolist()

            # 向量搜索，获取较多结果
            results = await asyncio.to_thread(
                self.qdrant.search,
                query_vector=keyword_embedding,
                top_k=limit * 3,  # 多取一些，后面再过滤
                score_threshold=0.3,  # 降低阈值，让更多结果进入
                filter_conditions={"session_id": self.session_id},
            )

            # 在结果中过滤包含关键词的记忆
            memories = []
            for result in results:
                payload = result.get("payload", {})
                content = payload.get("content", "")

                # 关键词匹配（不区分大小写）
                if keyword.lower() in content.lower():
                    metadata = payload.get("metadata", "{}")
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            metadata = {}

                    memories.append({
                        "content": content,
                        "metadata": metadata,
                        "created_at": payload.get("created_at", ""),
                    })

                    if len(memories) >= limit:
                        break

            return memories

        except Exception as e:
            logger.error(f"Keyword search error: {e}")
            return []

    async def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近记忆

        通过 Qdrant 的 scroll API 获取，按 created_at 排序。

        Args:
            limit: 返回数量

        Returns:
            记忆列表
        """
        try:
            # 使用 Qdrant scroll 获取所有记忆
            from qdrant_client.http import models

            points, _ = await asyncio.to_thread(
                self.qdrant.client.scroll,
                collection_name=self.qdrant.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="session_id",
                            match=models.MatchValue(value=self.session_id),
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

            # 按 created_at 排序（最新的在前）
            memories = []
            for point in points:
                payload = point.payload or {}
                metadata = payload.get("metadata", "{}")
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}

                memories.append({
                    "content": payload.get("content", ""),
                    "metadata": metadata,
                    "created_at": payload.get("created_at", ""),
                })

            # 按 created_at 降序排序
            memories.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return memories[:limit]

        except Exception as e:
            logger.error(f"Get recent error: {e}")
            return []

    async def clear(self):
        """清空当前会话的长期记忆"""
        try:
            from qdrant_client.http import models

            # 通过过滤条件删除当前会话的所有记忆
            await asyncio.to_thread(
                self.qdrant.client.delete,
                collection_name=self.qdrant.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="session_id",
                                match=models.MatchValue(value=self.session_id),
                            )
                        ]
                    )
                ),
            )

            logger.info(f"Long-term memory cleared: {self.session_id}")

        except Exception as e:
            logger.error(f"Clear error: {e}")

    async def get_stats(self) -> dict:
        """获取统计"""
        try:
            from qdrant_client.http import models

            # 使用 scroll 获取当前会话的记忆数量
            points, _ = await asyncio.to_thread(
                self.qdrant.client.scroll,
                collection_name=self.qdrant.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="session_id",
                            match=models.MatchValue(value=self.session_id),
                        )
                    ]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False,
            )

            # 获取精确计数
            count_result = await asyncio.to_thread(
                self.qdrant.client.count,
                collection_name=self.qdrant.collection_name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="session_id",
                            match=models.MatchValue(value=self.session_id),
                        )
                    ]
                ),
            )

            return {
                "session_id": self.session_id,
                "memory_count": count_result.count,
                "limit": self.limit,
                "backend": "qdrant",
            }

        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {"session_id": self.session_id, "memory_count": 0, "backend": "qdrant"}
