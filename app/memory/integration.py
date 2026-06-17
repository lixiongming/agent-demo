"""记忆整合 - 大厂标准记忆管理

功能：
1. 事实提取：从对话中提取关键事实
2. 实体识别：识别用户、时间、地点等实体
3. 关系建立：建立实体间关系
4. 记忆压缩：合并相似记忆，减少冗余

大厂实践：
- Google MemGPT：事实提取 + 实体关系图
- OpenAI Memory：关键信息提取 + 结构化存储
- 阿里通义：记忆压缩 + 智能整合

使用示例：
    from app.memory.integration import MemoryIntegrator
    
    integrator = MemoryIntegrator(llm, embedding_model)
    
    # 整合对话
    result = await integrator.integrate_conversation(messages)
    
    # 提取实体
    entities = await integrator.extract_entities(text)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from app.core.logger import get_logger
from app.config import get_settings
from app.embeddings.zhipu_embedding import get_embedding_model
import json

logger = get_logger(__name__)
settings = get_settings()


class MemoryIntegrator:
    """记忆整合管理器
    
    核心功能：
    1. 事实提取：使用 LLM 从对话中提取结构化事实
    2. 实体识别：识别关键实体（人、时间、地点）
    3. 关系建立：建立实体间的关系
    4. 记忆压缩：合并相似记忆，减少冗余
    
    实体类型：
    - person: 人物（用户、朋友、家人）
    - time: 时间（日期、时刻）
    - location: 地点（地址、城市）
    - event: 事件（会议、活动）
    - object: 物品（产品、文件）
    """
    
    # 实体类型定义
    ENTITY_TYPES = {
        "person": ["我", "你", "他", "她", "朋友", "家人", "同事"],
        "time": ["今天", "明天", "下周", "时间", "日期"],
        "location": ["家", "公司", "地址", "城市", "地点"],
        "event": ["会议", "活动", "计划", "安排"],
        "object": ["产品", "文件", "项目", "任务"]
    }
    
    def __init__(
        self,
        llm: BaseChatModel,
        db: Optional[AsyncSession] = None,
        embedding_model: Optional[Any] = None
    ):
        """初始化记忆整合器
        
        Args:
            llm: 语言模型
            db: 数据库会话
            embedding_model: 向量嵌入模型
        """
        self.llm = llm
        self.db = db
        self.embedding_model = embedding_model or get_embedding_model()
        
        # 统计
        self.stats = {
            "facts_extracted": 0,
            "entities_identified": 0,
            "relations_created": 0,
            "memories_compressed": 0
        }
        
        logger.info("记忆整合器初始化完成")
    
    async def extract_facts_from_conversation(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从对话中提取事实
        
        使用 LLM 分析对话，提取关键事实
        
        Args:
            messages: 对话消息列表
            
        Returns:
            事实列表
        """
        try:
            # 构建对话文本
            conversation_text = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation_text += f"{role}: {content}\n"
            
            # 构建提示
            prompt = f"""请从以下对话中提取关键事实信息，以 JSON 数组格式返回。

对话：
{conversation_text}

提取规则：
1. 只提取明确陈述的事实，不要推断
2. 每个事实包含：fact_type, fact_key, fact_value, confidence, source
3. fact_type 类型：identity/preference/location/schedule/relation
4. confidence 范围：0.0-1.0

返回格式：
[
    {
        "fact_type": "identity",
        "fact_key": "姓名",
        "fact_value": "张三",
        "confidence": 0.9,
        "source": "用户直接陈述"
    },
    ...
]

如果没有明显的事实，返回空数组：[]

只返回 JSON 数组，不要其他内容。"""

            # 调用 LLM
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # 解析结果
            content = response.content.strip()
            
            # 清理格式
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            # 解析 JSON
            try:
                facts = json.loads(content)
                
                if not isinstance(facts, list):
                    facts = []
                
                self.stats["facts_extracted"] += len(facts)
                
                logger.info(f"事实提取完成: {len(facts)} 条")
                
                return facts
            
            except json.JSONDecodeError:
                logger.warning(f"JSON 解析失败: {content}")
                return []
        
        except Exception as e:
            logger.error(f"事实提取失败: {e}")
            return []
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取实体
        
        使用 LLM 提取关键实体
        
        Args:
            text: 输入文本
            
        Returns:
            实体列表
        """
        try:
            prompt = f"""请从以下文本中提取关键实体，以 JSON 数组格式返回。

文本：{text}

实体类型：
- person: 人物
- time: 时间
- location: 地点
- event: 事件
- object: 物品

返回格式：
[
    {
        "entity_type": "person",
        "entity_name": "张三",
        "entity_value": "用户",
        "confidence": 0.9
    },
    ...
]

只返回 JSON 数组。"""

            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            content = response.content.strip()
            
            # 清理格式
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            try:
                entities = json.loads(content)
                
                if not isinstance(entities, list):
                    entities = []
                
                self.stats["entities_identified"] += len(entities)
                
                logger.debug(f"实体提取: {len(entities)} 个")
                
                return entities
            
            except json.JSONDecodeError:
                logger.warning(f"JSON 解析失败: {content}")
                return []
        
        except Exception as e:
            logger.error(f"实体提取失败: {e}")
            return []
    
    async def extract_relations(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """建立实体间关系
        
        分析实体之间的关系
        
        Args:
            entities: 实体列表
            
        Returns:
            关系列表
        """
        relations = []
        
        # 简单的关系提取逻辑
        # 在实际应用中，可以使用更复杂的算法
        
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                # 检查是否可能存在关系
                # 例如：person + location = 居住关系
                # person + time = 日程关系
                
                relation_type = None
                
                if (
                    entity1.get("entity_type") == "person" and
                    entity2.get("entity_type") == "location"
                ):
                    relation_type = "residence"
                
                elif (
                    entity1.get("entity_type") == "person" and
                    entity2.get("entity_type") == "time"
                ):
                    relation_type = "schedule"
                
                elif (
                    entity1.get("entity_type") == "person" and
                    entity2.get("entity_type") == "event"
                ):
                    relation_type = "participation"
                
                if relation_type:
                    relation = {
                        "relation_type": relation_type,
                        "source_entity": entity1.get("entity_name"),
                        "target_entity": entity2.get("entity_name"),
                        "confidence": min(
                            entity1.get("confidence", 0.5),
                            entity2.get("confidence", 0.5)
                        )
                    }
                    
                    relations.append(relation)
                    
                    self.stats["relations_created"] += 1
        
        logger.info(f"关系提取: {len(relations)} 条")
        
        return relations
    
    async def compress_similar_memories(
        self,
        memories: List[Dict[str, Any]],
        similarity_threshold: float = 0.9
    ) -> List[Dict[str, Any]]:
        """压缩相似记忆
        
        合理相似度高的记忆，减少冗余
        
        Args:
            memories: 记忆列表
            similarity_threshold: 相似度阈值
            
        Returns:
            压缩后的记忆列表
        """
        if len(memories) < 2:
            return memories
        
        compressed = []
        merged_count = 0
        
        # 获取所有记忆的向量
        memory_embeddings = []
        for memory in memories:
            content = memory.get("content", "")
            if content:
                embedding = await self.embedding_model.embed_query(content)
                memory_embeddings.append(embedding)
            else:
                memory_embeddings.append(None)
        
        # 检查相似度
        merged_indices = set()
        
        for i, memory1 in enumerate(memories):
            if i in merged_indices:
                continue
            
            # 检查与其他记忆的相似度
            for j, memory2 in enumerate(memories[i+1:], start=i+1):
                if j in merged_indices:
                    continue
                
                # 计算相似度
                emb1 = memory_embeddings[i]
                emb2 = memory_embeddings[j]
                
                if emb1 and emb2:
                    similarity = self._cosine_similarity(emb1, emb2)
                    
                    if similarity > similarity_threshold:
                        # 合并记忆
                        merged_memory = {
                            "content": memory1.get("content"),  # 保留第一个
                            "metadata": {
                                "merged_from": [
                                    memory1.get("id"),
                                    memory2.get("id")
                                ],
                                "merge_similarity": similarity,
                                "merge_time": datetime.now().isoformat()
                            },
                            "weight": max(
                                memory1.get("weight", 1.0),
                                memory2.get("weight", 1.0)
                            ),
                            "importance": max(
                                memory1.get("importance", 1.0),
                                memory2.get("importance", 1.0)
                            )
                        }
                        
                        compressed.append(merged_memory)
                        merged_indices.add(i)
                        merged_indices.add(j)
                        merged_count += 1
                        
                        logger.info(
                            f"记忆合并: similarity={similarity:.3f}, "
                            f"ids={memory1.get('id')}, {memory2.get('id')}"
                        )
        
        # 添加未合并的记忆
        for i, memory in enumerate(memories):
            if i not in merged_indices:
                compressed.append(memory)
        
        self.stats["memories_compressed"] += merged_count
        
        logger.info(
            f"记忆压缩完成: 原始 {len(memories)} 条, "
            f"压缩后 {len(compressed)} 条, 合并 {merged_count} 条"
        )
        
        return compressed
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        import numpy as np
        
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0
        
        return dot_product / (norm1 * norm2)
    
    async def integrate_conversation(
        self,
        messages: List[Dict[str, Any]],
        session_id: str
    ) -> Dict[str, Any]:
        """整合对话的完整流程
        
        步骤：
        1. 提取事实
        2. 提取实体
        3. 建立关系
        4. 返回结果
        
        Args:
            messages: 对话消息列表
            session_id: 会话 ID
            
        Returns:
            整合结果
        """
        logger.info(f"开始整合对话: session={session_id}")
        
        # 1. 提取事实
        facts = await self.extract_facts_from_conversation(messages)
        
        # 2. 提取实体（从所有消息）
        all_text = " ".join([m.get("content", "") for m in messages])
        entities = await self.extract_entities(all_text)
        
        # 3. 建立关系
        relations = await self.extract_relations(entities)
        
        return {
            "success": True,
            "session_id": session_id,
            "facts": facts,
            "entities": entities,
            "relations": relations,
            "stats": {
                "facts_count": len(facts),
                "entities_count": len(entities),
                "relations_count": len(relations)
            }
        }
    
    async def store_integrated_memory(
        self,
        fact: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """存储整合后的记忆
        
        Args:
            fact: 事实信息
            session_id: 会话 ID
            
        Returns:
            存储结果
        """
        if not self.db:
            return {"success": False, "error": "数据库未初始化"}
        
        try:
            # 构建记忆内容
            content = f"{fact['fact_key']}: {fact['fact_value']}"
            
            # 生成向量
            embedding = await self.embedding_model.embed_query(content)
            
            # 存储到数据库
            query = text("""
                INSERT INTO long_term_memory
                (session_id, content, metadata, embedding, weight, importance, confidence, created_at)
                VALUES (:session_id, :content, :metadata, :embedding, 1.0, 1.0, :confidence, NOW())
            """)
            
            metadata = {
                "fact_type": fact["fact_type"],
                "fact_key": fact["fact_key"],
                "fact_value": fact["fact_value"],
                "source": fact.get("source", "对话提取")
            }
            
            await self.db.execute(
                query,
                {
                    "session_id": session_id,
                    "content": content,
                    "metadata": json.dumps(metadata),
                    "embedding": embedding,
                    "confidence": fact.get("confidence", 0.5)
                }
            )
            
            await self.db.commit()
            
            logger.info(f"记忆已存储: {content}")
            
            return {"success": True, "content": content}
        
        except Exception as e:
            logger.error(f"记忆存储失败: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats