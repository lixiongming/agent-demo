"""记忆管理器 - 统一管理入口

功能：
1. 统一管理短期记忆、长期记忆
2. 集成遗忘机制、冲突修正、记忆整合
3. 提供完整的记忆生命周期管理
4. 支持记忆检索、存储、更新、删除

大厂实践：
- Google MemGPT：分层记忆 + 智能管理
- OpenAI Memory API：统一接口 + 自动整合
- 阿里通义：记忆生命周期 + 智能遗忘

使用示例：
    from app.memory.manager import MemoryManager
    
    manager = MemoryManager(session_id, db, llm)
    
    # 添加记忆
    await manager.add_memory(content, metadata)
    
    # 检索记忆
    memories = await manager.retrieve(query)
    
    # 运行遗忘周期
    await manager.run_forgetting_cycle()
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain_core.language_models import BaseChatModel
from app.core.logger import get_logger
from app.config import get_settings
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory
from app.memory.forgetting import ForgettingManager
from app.memory.conflict import ConflictResolver
from app.memory.integration import MemoryIntegrator
from app.embeddings import get_embedding_service
import json

logger = get_logger(__name__)
settings = get_settings()


class MemoryManager:
    """记忆管理器 - 统一管理入口
    
    核心功能：
    1. 短期记忆管理（Redis）
    2. 长期记忆管理（Qdrant）
    3. 遗忘机制（时间衰减 + 容量限制）
    4. 冲突修正（事实检测 + 信息更新）
    5. 记忆整合（事实提取 + 实体识别）
    
    记忆生命周期：
    1. 短期记忆 → 对话上下文（Redis，自动过期）
    2. 长期记忆 → 关键事实（Qdrant，向量存储）
    3. 遗忘周期 → 定期清理低权重记忆
    4. 冲突检测 → 新信息与旧信息冲突处理
    5. 记忆整合 → 对话结束时提取关键事实
    """
    
    def __init__(
        self,
        session_id: str,
        db: AsyncSession,
        llm: BaseChatModel,
        config: Optional[Dict[str, Any]] = None
    ):
        """初始化记忆管理器
        
        Args:
            session_id: 会话 ID
            db: 数据库会话
            llm: 语言模型
            config: 配置参数
        """
        self.session_id = session_id
        self.db = db
        self.llm = llm
        self.config = config or {}
        
        # 嵌入模型
        self.embedding_model = get_embedding_service()
        
        # 初始化子模块
        self.short_term = ShortTermMemory(session_id)
        self.long_term = LongTermMemory(session_id, db)
        self.forgetting = ForgettingManager(
            session_id, db,
            decay_rate=self.config.get("decay_rate", 0.01),
            max_capacity=self.config.get("max_capacity", 1000)
        )
        self.conflict_resolver = ConflictResolver(llm, db)
        self.integrator = MemoryIntegrator(llm, db, self.embedding_model)
        
        # 统计
        self.stats = {
            "memories_added": 0,
            "memories_retrieved": 0,
            "forgetting_cycles": 0,
            "conflicts_resolved": 0
        }
        
        logger.info(f"记忆管理器初始化: session={session_id}")
    
    async def init(self):
        """初始化短期记忆（Redis 连接）"""
        await self.short_term.init()
        logger.debug("短期记忆初始化完成")
    
    async def add_message(self, role: str, content: str, metadata: Optional[dict] = None):
        """添加对话消息
        
        存储到短期记忆
        
        Args:
            role: 角色（user/assistant）
            content: 内容
            metadata: 元数据
        """
        await self.short_term.add_message(role, content, metadata)
        self.stats["memories_added"] += 1
        logger.debug(f"消息添加: role={role}")
    
    async def add_long_term_memory(
        self,
        content: str,
        metadata: Optional[dict] = None,
        check_conflict: bool = True
    ) -> Dict[str, Any]:
        """添加长期记忆
        
        步骤：
        1. 检查冲突
        2. 解决冲突
        3. 存储记忆
        
        Args:
            content: 记忆内容
            metadata: 元数据
            check_conflict: 是否检查冲突
            
        Returns:
            添加结果
        """
        try:
            # 生成向量
            embedding = await self.embedding_model.embed_text(content)
            # numpy 数组转列表
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()
            
            # 检查冲突
            if check_conflict:
                # 提取事实
                fact = await self.conflict_resolver.extract_fact(content)
                
                if fact.get("fact_type") != "none":
                    # 获取现有记忆
                    existing = await self.long_term.get_recent(limit=50)
                    
                    # 检测冲突
                    conflicts = await self.conflict_resolver.detect_conflicts(
                        fact, existing
                    )
                    
                    # 解决冲突
                    if conflicts:
                        resolution = await self.conflict_resolver.resolve_conflicts(
                            conflicts, self.session_id
                        )
                        
                        self.stats["conflicts_resolved"] += resolution.get("resolved_count", 0)
                        
                        # 如果更新了现有记忆，不需要再添加
                        if resolution.get("actions"):
                            for action in resolution["actions"]:
                                if action["resolution"]["action"] == "update":
                                    return {
                                        "success": True,
                                        "action": "updated",
                                        "conflicts": conflicts
                                    }
            
            # 存储新记忆
            await self.long_term.add_memory(content, metadata, embedding)
            
            self.stats["memories_added"] += 1
            
            logger.info(f"长期记忆添加: {content[:50]}...")
            
            return {
                "success": True,
                "action": "added",
                "content": content
            }
        
        except Exception as e:
            logger.error(f"长期记忆添加失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def retrieve(
        self,
        query: str,
        limit: int = 10,
        use_rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """检索记忆
        
        步骤：
        1. 向量检索长期记忆
        2. 获取短期记忆
        3. 合并结果
        4. Rerank 重排序
        
        Args:
            query: 查询文本
            limit: 返回数量
            use_rerank: 是否使用 Rerank
            
        Returns:
            记忆列表
        """
        try:
            # 1. 向量检索长期记忆
            query_embedding = await self.embedding_model.embed_text(query)
            # numpy 数组转列表
            if hasattr(query_embedding, "tolist"):
                query_embedding = query_embedding.tolist()
            long_term_memories = await self.long_term.search_similar(
                query_embedding, limit=limit * 2
            )
            
            # 2. 获取短期记忆
            short_term_memories = await self.short_term.get_messages(limit=10)
            
            # 3. 合并结果
            all_memories = []
            
            # 添加长期记忆
            for memory in long_term_memories:
                all_memories.append({
                    "source": "long_term",
                    "content": memory["content"],
                    "metadata": memory["metadata"],
                    "similarity": memory["similarity"],
                    "created_at": memory["created_at"]
                })
            
            # 添加短期记忆
            for memory in short_term_memories:
                all_memories.append({
                    "source": "short_term",
                    "content": memory["content"],
                    "metadata": memory["metadata"],
                    "role": memory["role"]
                })
            
            # 4. Rerank 重排序
            if use_rerank and len(all_memories) > 0:
                from app.services.rerank import rerank_documents
                
                contents = [m["content"] for m in all_memories]
                rerank_results = await rerank_documents(query, contents, top_k=limit)
                
                # 重新排序
                reranked_memories = []
                for result in rerank_results:
                    idx = result["index"]
                    if idx < len(all_memories):
                        memory = all_memories[idx].copy()
                        memory["rerank_score"] = result["relevance_score"]
                        reranked_memories.append(memory)
                
                all_memories = reranked_memories
            
            # 更新访问重要性
            for memory in all_memories:
                if memory.get("source") == "long_term" and memory.get("id"):
                    await self.forgetting.update_importance(memory["id"])
            
            self.stats["memories_retrieved"] += len(all_memories)
            
            logger.info(f"记忆检索: {len(all_memories)} 条")
            
            return all_memories
        
        except Exception as e:
            logger.error(f"记忆检索失败: {e}")
            return []
    
    async def run_forgetting_cycle(self) -> Dict[str, Any]:
        """运行遗忘周期
        
        定期执行：
        1. 时间衰减
        2. 容量检查
        3. 淘汰低权重记忆
        
        Returns:
            遗忘周期结果
        """
        result = await self.forgetting.run_forgetting_cycle()
        
        self.stats["forgetting_cycles"] += 1
        
        logger.info(f"遗忘周期完成: {result}")
        
        return result
    
    async def integrate_conversation(self) -> Dict[str, Any]:
        """整合对话
        
        对话结束时：
        1. 提取关键事实
        2. 存储长期记忆
        3. 清理短期记忆
        
        Returns:
            整合结果
        """
        try:
            # 获取短期记忆
            messages = await self.short_term.get_messages()
            
            if not messages:
                return {
                    "success": True,
                    "facts_count": 0,
                    "reason": "无对话内容"
                }
            
            # 提取事实
            integration_result = await self.integrator.integrate_conversation(
                messages, self.session_id
            )
            
            facts = integration_result.get("facts", [])
            
            # 存储事实
            stored_count = 0
            for fact in facts:
                if fact.get("fact_type") != "none":
                    result = await self.integrator.store_integrated_memory(
                        fact, self.session_id
                    )
                    if result.get("success"):
                        stored_count += 1
            
            logger.info(f"对话整合完成: {stored_count} 条事实存储")
            
            return {
                "success": True,
                "facts_count": len(facts),
                "stored_count": stored_count,
                "integration": integration_result
            }
        
        except Exception as e:
            logger.error(f"对话整合失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_context_for_llm(self, query: str, limit: int = 5) -> str:
        """获取 LLM 上下文
        
        为 LLM 提供记忆上下文
        
        Args:
            query: 当前查询
            limit: 记忆数量
            
        Returns:
            上下文文本
        """
        # 检索相关记忆
        memories = await self.retrieve(query, limit=limit)
        
        if not memories:
            return ""
        
        # 构建上下文
        context_parts = ["以下是相关的记忆信息："]
        
        for i, memory in enumerate(memories, 1):
            content = memory.get("content", "")
            source = memory.get("source", "")
            score = memory.get("rerank_score", memory.get("similarity", 0))
            
            context_parts.append(f"{i}. [{source}] {content} (相关性: {score:.2f})")
        
        context = "\n".join(context_parts)
        
        logger.debug(f"LLM 上下文: {len(memories)} 条记忆")
        
        return context
    
    async def clear_session(self):
        """清空会话记忆"""
        await self.short_term.clear()
        await self.long_term.clear()
        
        logger.info(f"会话记忆清空: {self.session_id}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        short_term_stats = await self.short_term.get_stats()
        long_term_stats = await self.long_term.get_stats()
        forgetting_stats = self.forgetting.get_stats()
        conflict_stats = self.conflict_resolver.get_stats()
        integration_stats = self.integrator.get_stats()
        
        return {
            "session_id": self.session_id,
            "short_term": short_term_stats,
            "long_term": long_term_stats,
            "forgetting": forgetting_stats,
            "conflict": conflict_stats,
            "integration": integration_stats,
            "manager": self.stats
        }


# 全局单例管理（线程安全）
_memory_managers: Dict[str, MemoryManager] = {}
_manager_lock = __import__('threading').Lock()


async def get_memory_manager(
    session_id: str,
    db: AsyncSession,
    llm: BaseChatModel
) -> MemoryManager:
    """获取记忆管理器（不缓存实例，避免 db 会话过期问题）
    
    每次调用都创建新的 MemoryManager，因为 AsyncSession 是短生命周期的，
    缓存会导致使用已关闭的数据库会话。
    """
    manager = MemoryManager(session_id, db, llm)
    await manager.init()
    return manager


def clear_memory_manager(session_id: str):
    """清除记忆管理器"""
    with _manager_lock:
        if session_id in _memory_managers:
            del _memory_managers[session_id]
            logger.info(f"记忆管理器清除: {session_id}")