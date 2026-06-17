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
    
    manager = ForgettingManager(session_id, db)
    
    # 应用时间衰减
    await manager.apply_time_decay()
    
    # 检查容量并淘汰
    await manager.check_capacity_and_evict()
    
    # 更新记忆权重（访问时）
    await manager.update_importance(memory_id, boost=0.1)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, update, delete
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
        db: AsyncSession,
        decay_rate: float = 0.01,
        max_capacity: int = 1000,
        evict_threshold: float = 0.1,
        access_boost: float = 0.05
    ):
        """初始化遗忘管理器
        
        Args:
            session_id: 会话 ID
            db: 数据库会话
            decay_rate: 时间衰减速率（每小时）
            max_capacity: 最大记忆容量
            evict_threshold: 淘汰阈值（低于此值淘汰）
            access_boost: 每次访问的重要性增益
        """
        self.session_id = session_id
        self.db = db
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
    
    async def apply_time_decay(self) -> Dict[str, Any]:
        """应用时间衰减
        
        对所有记忆应用时间衰减公式：
        weight = initial_weight * exp(-decay_rate * hours_since_creation)
        
        Returns:
            衰减统计信息
        """
        try:
            # 获取所有记忆及其创建时间
            query = text("""
                SELECT id, weight, importance, created_at
                FROM long_term_memory
                WHERE session_id = :session_id
            """)
            
            result = await self.db.execute(
                query, {"session_id": self.session_id}
            )
            
            memories = result.fetchall()
            decayed_count = 0
            
            for memory in memories:
                memory_id = memory.id
                old_weight = memory.weight or 1.0
                created_at = memory.created_at
                
                # 计算时间差（小时）
                hours_since_creation = (
                    datetime.now() - created_at
                ).total_seconds() / 3600
                
                # 应用衰减公式
                new_weight = old_weight * math.exp(
                    -self.decay_rate * hours_since_creation
                )
                
                # 更新权重
                update_query = text("""
                    UPDATE long_term_memory
                    SET weight = :weight
                    WHERE id = :id
                """)
                
                await self.db.execute(
                    update_query,
                    {"weight": new_weight, "id": memory_id}
                )
                
                decayed_count += 1
                
                logger.debug(
                    f"记忆衰减: id={memory_id}, "
                    f"old_weight={old_weight:.3f}, new_weight={new_weight:.3f}"
                )
            
            await self.db.commit()
            
            self.stats["decay_applied"] += decayed_count
            
            logger.info(f"时间衰减完成: {decayed_count} 条记忆")
            
            return {
                "success": True,
                "decayed_count": decayed_count,
                "decay_rate": self.decay_rate
            }
        
        except Exception as e:
            logger.error(f"时间衰减失败: {e}")
            await self.db.rollback()
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
            # 获取当前记忆数量
            count_query = text("""
                SELECT COUNT(*) as count
                FROM long_term_memory
                WHERE session_id = :session_id
            """)
            
            result = await self.db.execute(
                count_query, {"session_id": self.session_id}
            )
            current_count = result.scalar()
            
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
            
            # 计算综合评分并排序
            # score = weight * importance
            score_query = text("""
                SELECT id, content, weight, importance,
                       (weight * importance) as score
                FROM long_term_memory
                WHERE session_id = :session_id
                ORDER BY score ASC
                LIMIT :evict_count
            """)
            
            result = await self.db.execute(
                score_query,
                {
                    "session_id": self.session_id,
                    "evict_count": evict_count
                }
            )
            
            memories_to_evict = result.fetchall()
            evicted_ids = []
            
            # 淘汰低评分记忆
            for memory in memories_to_evict:
                # 检查是否低于阈值（重要记忆不淘汰）
                score = memory.score or 0
                if score < self.evict_threshold:
                    delete_query = text("""
                        DELETE FROM long_term_memory
                        WHERE id = :id
                    """)
                    
                    await self.db.execute(
                        delete_query, {"id": memory.id}
                    )
                    
                    evicted_ids.append(memory.id)
                    
                    logger.info(
                        f"记忆淘汰: id={memory.id}, "
                        f"score={score:.3f}, content={memory.content[:30]}..."
                    )
            
            await self.db.commit()
            
            self.stats["memories_evicted"] += len(evicted_ids)
            
            return {
                "success": True,
                "current_count": current_count,
                "evicted_count": len(evicted_ids),
                "evicted_ids": evicted_ids
            }
        
        except Exception as e:
            logger.error(f"容量淘汰失败: {e}")
            await self.db.rollback()
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
            memory_id: 记忆 ID
            boost: 增益值（默认使用 access_boost）
            
        Returns:
            更新结果
        """
        try:
            boost = boost or self.access_boost
            
            # 更新重要性
            query = text("""
                UPDATE long_term_memory
                SET importance = importance + :boost,
                    last_accessed = NOW(),
                    access_count = access_count + 1
                WHERE id = :id
            """)
            
            await self.db.execute(
                query, {"boost": boost, "id": memory_id}
            )
            
            await self.db.commit()
            
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
            await self.db.rollback()
            return {"success": False, "error": str(e)}
    
    async def get_memory_scores(self) -> List[Dict[str, Any]]:
        """获取所有记忆的评分
        
        用于分析和调试
        
        Returns:
            记忆评分列表
        """
        try:
            query = text("""
                SELECT id, content, weight, importance,
                       (weight * importance) as score,
                       created_at, last_accessed, access_count
                FROM long_term_memory
                WHERE session_id = :session_id
                ORDER BY score DESC
            """)
            
            result = await self.db.execute(
                query, {"session_id": self.session_id}
            )
            
            memories = []
            for row in result:
                memories.append({
                    "id": row.id,
                    "content": row.content[:100],
                    "weight": row.weight,
                    "importance": row.importance,
                    "score": row.score,
                    "created_at": row.created_at,
                    "last_accessed": row.last_accessed,
                    "access_count": row.access_count
                })
            
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