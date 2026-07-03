"""遗忘机制 - 大厂标准记忆管理

功能：
1. 时间衰减：旧记忆权重随时间降低
2. 容量限制：超过限制时淘汰低权重记忆
3. 重要性评分：根据访问频率调整权重
4. 智能淘汰：优先淘汰低重要性记忆

大厂实践：
- Google MemGPT：时间衰减 + 容量管理
- OpenAI Memory：重要性评分 + 智能淘汰
- 阿里通义：访问频率 + 时间窗口

使用示例：
    from app.memory.forgetting import ForgettingManager

    manager = ForgettingManager(session_id, qdrant_store=store)

    # 应用时间衰减
    await manager.apply_time_decay()

    # 检查容量并淘汰
    await manager.check_capacity_and_evict()

    # 更新记忆权重（访问时）
    await manager.update_importance(memory_id, boost=0.1)
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from qdrant_client.http.models import PointStruct, PointIdsList, Filter, FieldCondition, MatchValue
from app.core.logger import get_logger
from app.config import get_settings
import math

logger = get_logger(__name__)
settings = get_settings()


class ForgettingManager:
    """遗忘机制管理器

    核心算法：
    1. 时间衰减公式：weight = initial_weight * exp(-decay_rate * hours)
    2. 重要性评分：importance = base + access_count * boost
    3. 综合评分：score = weight * importance
    4. 淘汰策略：优先淘汰 score 最低的记忆

    参数说明：
    - decay_rate：衰减速率（默认 0.01，每小时衰减 1%）
    - max_capacity：最大容量（默认 1000 条）
    - evict_threshold：淘汰阈值（默认 0.1）
    - access_boost：访问增益（默认 0.05）
    """

    def __init__(
        self,
        session_id: str,
        db=None,
        qdrant_store=None,
        decay_rate: float = 0.01,
        max_capacity: int = 1000,
        evict_threshold: float = 0.1,
        access_boost: float = 0.05
    ):
        """初始化遗忘管理器

        Args:
            session_id: 会话 ID
            db: 数据库会话（保留参数向后兼容，不再使用 SQL）
            qdrant_store: QdrantVectorStore 实例，用于操作长期记忆
            decay_rate: 时间衰减速率（每小时）
            max_capacity: 最大记忆容量
            evict_threshold: 淘汰阈值（低于此值淘汰）
            access_boost: 每次访问的重要性增益
        """
        self.session_id = session_id
        self.db = db
        self.qdrant_store = qdrant_store
        self.decay_rate = decay_rate
        self.max_capacity = max_capacity
        self.evict_threshold = evict_threshold
        self.access_boost = access_boost

        # 统计
        self.stats = {
            "decay_applied": 0,
            "memories_evicted": 0,
            "importance_updated": 0
        }

        logger.info(
            f"遗忘管理器初始化: session={session_id}, "
            f"decay_rate={decay_rate}, max_capacity={max_capacity}"
        )

    def _get_collection_name(self) -> str:
        """获取 Qdrant 集合名称"""
        return self.qdrant_store.collection_name

    def _build_session_filter(self) -> Filter:
        """构建当前 session 的 Qdrant 过滤条件"""
        return Filter(
            must=[
                FieldCondition(
                    key="session_id",
                    match=MatchValue(value=self.session_id),
                )
            ]
        )

    async def apply_time_decay(self) -> Dict[str, Any]:
        """应用时间衰减

        对所有记忆应用时间衰减公式：
        weight = initial_weight * exp(-decay_rate * hours_since_creation)

        Returns:
            衰减统计信息
        """
        try:
            collection_name = self._get_collection_name()
            session_filter = self._build_session_filter()

            # 通过 scroll API 获取当前 session 的所有点
            points, _ = await asyncio.to_thread(
                self.qdrant_store.client.scroll,
                collection_name=collection_name,
                scroll_filter=session_filter,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )

            decayed_count = 0

            if not points:
                return {
                    "success": True,
                    "decayed_count": 0,
                    "decay_rate": self.decay_rate
                }

            # 批量获取所有向量（一次调用代替 N 次单独 retrieve）
            point_vectors = await asyncio.to_thread(
                self.qdrant_store.client.retrieve,
                collection_name=collection_name,
                ids=[p.id for p in points],
                with_vectors=True,
            )

            # 构建 id -> vector 的映射
            vector_map = {pv.id: pv.vector for pv in point_vectors if pv.vector is not None}

            # 构建 PointStruct 列表
            points_to_upsert = []
            for point in points:
                payload = point.payload or {}
                created_at_str = payload.get("created_at")

                if not created_at_str:
                    continue

                # 解析创建时间
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                except (ValueError, TypeError):
                    continue

                # 计算时间差（小时）
                hours_since_creation = (
                    datetime.now() - created_at
                ).total_seconds() / 3600

                # 从初始权重计算衰减（修复累积衰减问题）
                initial_weight = payload.get("initial_weight")
                if initial_weight is None:
                    # 向后兼容：如果没有 initial_weight，使用当前 weight 作为初始值
                    initial_weight = payload.get("weight", 1.0)
                    payload["initial_weight"] = initial_weight

                # 应用衰减公式：始终从初始值计算
                new_weight = initial_weight * math.exp(
                    -self.decay_rate * hours_since_creation
                )

                old_weight = payload.get("weight", 1.0)
                payload["weight"] = new_weight

                # 从向量映射中获取向量
                vector = vector_map.get(point.id)
                if vector is None:
                    continue

                points_to_upsert.append(
                    PointStruct(
                        id=point.id,
                        vector=vector,
                        payload=payload,
                    )
                )

                decayed_count += 1

                logger.debug(
                    f"记忆衰减: id={point.id}, "
                    f"old_weight={old_weight:.3f}, new_weight={new_weight:.3f}"
                )

            # 批量 upsert 更新
            if points_to_upsert:
                await asyncio.to_thread(
                    self.qdrant_store.client.upsert,
                    collection_name=collection_name,
                    points=points_to_upsert,
                )

            self.stats["decay_applied"] += decayed_count

            logger.info(f"时间衰减完成: {decayed_count} 条记忆")

            return {
                "success": True,
                "decayed_count": decayed_count,
                "decay_rate": self.decay_rate
            }

        except Exception as e:
            logger.error(f"时间衰减失败: {e}")
            return {"success": False, "error": str(e)}

    async def check_capacity_and_evict(self) -> Dict[str, Any]:
        """检查容量并淘汰低权重记忆

        淘汰策略：
        1. 检查当前记忆数量
        2. 如果超过容量限制，计算综合评分
        3. 淘汰评分最低的记忆

        Returns:
            淘汰统计信息
        """
        try:
            collection_name = self._get_collection_name()
            session_filter = self._build_session_filter()

            # 获取当前 session 的记忆数量
            count_result = await asyncio.to_thread(
                self.qdrant_store.client.count,
                collection_name=collection_name,
                count_filter=session_filter,
            )
            current_count = count_result.count

            # 检查是否需要淘汰
            if current_count <= self.max_capacity:
                logger.debug(
                    f"容量检查: 当前 {current_count}/{self.max_capacity}, 无需淘汰"
                )
                return {
                    "success": True,
                    "current_count": current_count,
                    "evicted_count": 0,
                    "reason": "容量充足"
                }

            # 需要淘汰的数量
            evict_count = current_count - self.max_capacity

            logger.info(
                f"容量超限: 当前 {current_count}/{self.max_capacity}, "
                f"需要淘汰 {evict_count} 条"
            )

            # 获取所有点，计算综合评分并排序
            points, _ = await asyncio.to_thread(
                self.qdrant_store.client.scroll,
                collection_name=collection_name,
                scroll_filter=session_filter,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )

            # 计算综合评分 score = weight * importance
            scored_points = []
            for point in points:
                payload = point.payload or {}
                weight = payload.get("weight", 1.0)
                importance = payload.get("importance", 1.0)
                score = weight * importance
                scored_points.append((point, score))

            # 按 score 升序排序（最低的在前）
            scored_points.sort(key=lambda x: x[1])

            # 淘汰低评分记忆
            evicted_ids = []
            for point, score in scored_points:
                if len(evicted_ids) >= evict_count:
                    break

                # 检查是否低于阈值（重要记忆不淘汰）
                if score < self.evict_threshold:
                    evicted_ids.append(point.id)

                    payload = point.payload or {}
                    content = payload.get("content", "")
                    logger.info(
                        f"记忆淘汰: id={point.id}, "
                        f"score={score:.3f}, content={content[:30]}..."
                    )

            # 批量删除
            if evicted_ids:
                await asyncio.to_thread(
                    self.qdrant_store.client.delete,
                    collection_name=collection_name,
                    points_selector=PointIdsList(points=evicted_ids),
                )

            self.stats["memories_evicted"] += len(evicted_ids)

            return {
                "success": True,
                "current_count": current_count,
                "evicted_count": len(evicted_ids),
                "evicted_ids": evicted_ids
            }

        except Exception as e:
            logger.error(f"容量淘汰失败: {e}")
            return {"success": False, "error": str(e)}

    async def update_importance(
        self,
        memory_id: int,
        boost: Optional[float] = None
    ) -> Dict[str, Any]:
        """更新记忆重要性（访问时调用）

        每次访问记忆时，增加其重要性评分：
        importance = importance + boost

        Args:
            memory_id: 记忆点 ID（Qdrant 中的整数 ID）
            boost: 增益值（默认使用 access_boost）

        Returns:
            更新结果
        """
        try:
            boost = boost or self.access_boost
            collection_name = self._get_collection_name()

            # 获取指定点的当前数据
            points = await asyncio.to_thread(
                self.qdrant_store.client.retrieve,
                collection_name=collection_name,
                ids=[memory_id],
                with_payload=True,
                with_vectors=True,
            )

            if not points:
                logger.warning(f"记忆不存在: id={memory_id}")
                return {"success": False, "error": "记忆不存在"}

            point = points[0]
            payload = point.payload or {}

            # 更新 importance、access_count、last_accessed
            old_importance = payload.get("importance", 1.0)
            payload["importance"] = old_importance + boost
            payload["access_count"] = payload.get("access_count", 0) + 1
            payload["last_accessed"] = datetime.now().isoformat()

            # upsert 更新
            await asyncio.to_thread(
                self.qdrant_store.client.upsert,
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=point.id,
                        vector=point.vector,
                        payload=payload,
                    )
                ],
            )

            self.stats["importance_updated"] += 1

            logger.debug(
                f"重要性更新: id={memory_id}, boost={boost}"
            )

            return {
                "success": True,
                "memory_id": memory_id,
                "boost": boost
            }

        except Exception as e:
            logger.error(f"重要性更新失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_memory_scores(self) -> List[Dict[str, Any]]:
        """获取所有记忆的评分

        用于分析和调试

        Returns:
            记忆评分列表
        """
        try:
            collection_name = self._get_collection_name()
            session_filter = self._build_session_filter()

            points, _ = await asyncio.to_thread(
                self.qdrant_store.client.scroll,
                collection_name=collection_name,
                scroll_filter=session_filter,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )

            memories = []
            for point in points:
                payload = point.payload or {}
                weight = payload.get("weight", 1.0)
                importance = payload.get("importance", 1.0)
                score = weight * importance
                content = payload.get("content", "")

                memories.append({
                    "id": point.id,
                    "content": content[:100],
                    "weight": weight,
                    "importance": importance,
                    "score": score,
                    "created_at": payload.get("created_at"),
                    "last_accessed": payload.get("last_accessed"),
                    "access_count": payload.get("access_count", 0),
                })

            # 按 score 降序排序
            memories.sort(key=lambda x: x["score"], reverse=True)

            return memories

        except Exception as e:
            logger.error(f"获取评分失败: {e}")
            return []

    async def run_forgetting_cycle(self) -> Dict[str, Any]:
        """执行完整的遗忘周期

        步骤：
        1. 应用时间衰减
        2. 检查容量并淘汰
        3. 返回统计

        Returns:
            遗忘周期统计
        """
        logger.info(f"开始遗忘周期: session={self.session_id}")

        # 1. 时间衰减
        decay_result = await self.apply_time_decay()

        # 2. 容量淘汰
        evict_result = await self.check_capacity_and_evict()

        return {
            "success": True,
            "decay": decay_result,
            "evict": evict_result,
            "stats": self.stats
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "session_id": self.session_id,
            "decay_rate": self.decay_rate,
            "max_capacity": self.max_capacity,
            "evict_threshold": self.evict_threshold,
            "access_boost": self.access_boost,
            **self.stats
        }
