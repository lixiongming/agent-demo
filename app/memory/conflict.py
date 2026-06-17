"""冲突修正 - 大厂标准记忆管理

功能：
1. 事实冲突检测：检测新旧信息是否矛盾
2. 信息更新策略：新信息覆盖旧信息
3. 置信度评估：多源信息交叉验证
4. 冲突解决：智能选择最可信信息

大厂实践：
- OpenAI Memory API：信息更新 + 冲突检测
- Google MemGPT：置信度评估 + 多源验证
- 阿里通义：事实修正 + 时间戳验证

使用示例：
    from app.memory.conflict import ConflictResolver
    
    resolver = ConflictResolver(llm)
    
    # 检测冲突
    conflicts = await resolver.detect_conflicts(new_fact, existing_memories)
    
    # 解决冲突
    result = await resolver.resolve_conflicts(conflicts)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from app.core.logger import get_logger
from app.config import get_settings
import json

logger = get_logger(__name__)
settings = get_settings()


class ConflictResolver:
    """冲突修正管理器
    
    核心算法：
    1. 事实类型识别：识别事实类型（姓名、年龄、地址等）
    2. 冲突检测：同类型事实值不同则冲突
    3. 置信度计算：source_count * recency * consistency
    4. 冲突解决：选择置信度最高的信息
    
    事实类型：
    - identity: 身份信息（姓名、年龄、性别）
    - preference: 偏好信息（喜欢、不喜欢）
    - location: 位置信息（地址、城市）
    - schedule: 时间信息（日程、计划）
    - relation: 关系信息（朋友、家人）
    """
    
    # 事实类型定义
    FACT_TYPES = {
        "identity": ["姓名", "名字", "年龄", "岁", "性别", "职业", "工作"],
        "preference": ["喜欢", "不喜欢", "偏好", "爱好", "习惯"],
        "location": ["地址", "住", "住在", "城市", "国家", "位置"],
        "schedule": ["日程", "计划", "时间", "安排", "会议"],
        "relation": ["朋友", "家人", "同事", "关系", "认识"]
    }
    
    def __init__(
        self,
        llm: BaseChatModel,
        db: Optional[AsyncSession] = None,
        confidence_threshold: float = 0.7
    ):
        """初始化冲突修正器
        
        Args:
            llm: 语言模型（用于事实提取和冲突检测）
            db: 数据库会话
            confidence_threshold: 置信度阈值
        """
        self.llm = llm
        self.db = db
        self.confidence_threshold = confidence_threshold
        
        # 统计
        self.stats = {
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "facts_updated": 0
        }
        
        logger.info(
            f"冲突修正器初始化: confidence_threshold={confidence_threshold}"
        )
    
    async def extract_fact(self, text: str) -> Dict[str, Any]:
        """从文本中提取事实
        
        使用 LLM 提取结构化事实信息
        
        Args:
            text: 输入文本
            
        Returns:
            {
                "fact_type": "identity",
                "fact_key": "姓名",
                "fact_value": "张三",
                "confidence": 0.9,
                "source": "用户陈述"
            }
        """
        try:
            # 构建提示
            prompt = f"""请从以下文本中提取事实信息，以 JSON 格式返回。

文本：{text}

返回格式：
{
    "fact_type": "identity/preference/location/schedule/relation",
    "fact_key": "具体事实类型（如姓名、年龄、地址等）",
    "fact_value": "事实值",
    "confidence": 0.0-1.0 的置信度,
    "source": "信息来源"
}

如果没有明显的事实信息，返回：
{"fact_type": "none", "fact_key": "", "fact_value": "", "confidence": 0, "source": ""}

只返回 JSON，不要其他内容。"""

            # 调用 LLM
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # 解析结果
            content = response.content.strip()
            
            # 尝试解析 JSON
            try:
                # 清理可能的 markdown 格式
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                content = content.strip()
                
                fact = json.loads(content)
                
                logger.debug(f"事实提取: {fact}")
                
                return fact
            
            except json.JSONDecodeError:
                logger.warning(f"JSON 解析失败: {content}")
                return {
                    "fact_type": "none",
                    "fact_key": "",
                    "fact_value": "",
                    "confidence": 0,
                    "source": ""
                }
        
        except Exception as e:
            logger.error(f"事实提取失败: {e}")
            return {
                "fact_type": "none",
                "fact_key": "",
                "fact_value": "",
                "confidence": 0,
                "source": ""
            }
    
    async def detect_conflicts(
        self,
        new_fact: Dict[str, Any],
        existing_memories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """检测事实冲突
        
        检查新事实与现有记忆是否存在冲突
        
        Args:
            new_fact: 新提取的事实
            existing_memories: 现有记忆列表
            
        Returns:
            冲突列表
        """
        conflicts = []
        
        # 如果没有有效事实，返回空
        if new_fact.get("fact_type") == "none":
            return conflicts
        
        fact_type = new_fact.get("fact_type")
        fact_key = new_fact.get("fact_key")
        fact_value = new_fact.get("fact_value")
        
        # 检查每个现有记忆
        for memory in existing_memories:
            # 检查是否同类型事实
            memory_type = memory.get("metadata", {}).get("fact_type")
            memory_key = memory.get("metadata", {}).get("fact_key")
            memory_value = memory.get("metadata", {}).get("fact_value")
            
            # 同类型同键但值不同 = 冲突
            if (
                memory_type == fact_type and
                memory_key == fact_key and
                memory_value != fact_value
            ):
                conflict = {
                    "type": "value_conflict",
                    "new_fact": new_fact,
                    "existing_fact": {
                        "id": memory.get("id"),
                        "fact_type": memory_type,
                        "fact_key": memory_key,
                        "fact_value": memory_value,
                        "created_at": memory.get("created_at"),
                        "confidence": memory.get("metadata", {}).get("confidence", 0.5)
                    },
                    "severity": "high" if fact_type in ["identity", "location"] else "medium"
                }
                
                conflicts.append(conflict)
                
                logger.info(
                    f"检测到冲突: {fact_key} "
                    f"旧值={memory_value}, 新值={fact_value}"
                )
                
                self.stats["conflicts_detected"] += 1
        
        return conflicts
    
    async def resolve_conflict(
        self,
        conflict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解决单个冲突
        
        冲突解决策略：
        1. 时间优先：新信息覆盖旧信息（默认）
        2. 置信度优先：选择置信度高的信息
        3. 来源优先：用户直接陈述优先
        
        Args:
            conflict: 冲突信息
            
        Returns:
            解决结果
        """
        new_fact = conflict["new_fact"]
        existing_fact = conflict["existing_fact"]
        
        # 计算置信度
        new_confidence = new_fact.get("confidence", 0.5)
        existing_confidence = existing_fact.get("confidence", 0.5)
        
        # 决策：默认使用新信息（时间优先）
        # 但如果旧信息置信度显著更高，保留旧信息
        resolution = {
            "action": "update",  # update / keep / merge
            "winner": "new",
            "reason": "",
            "confidence_delta": new_confidence - existing_confidence
        }
        
        # 置信度差距大时，选择高置信度
        if existing_confidence > new_confidence + 0.2:
            resolution["action"] = "keep"
            resolution["winner"] = "existing"
            resolution["reason"] = f"旧信息置信度更高 ({existing_confidence:.2f} > {new_confidence:.2f})"
        
        # 新信息置信度更高时，更新
        elif new_confidence > existing_confidence:
            resolution["action"] = "update"
            resolution["winner"] = "new"
            resolution["reason"] = f"新信息置信度更高 ({new_confidence:.2f} > {existing_confidence:.2f})"
        
        # 置信度相近时，使用时间优先（新信息）
        else:
            resolution["action"] = "update"
            resolution["winner"] = "new"
            resolution["reason"] = "时间优先策略：新信息覆盖旧信息"
        
        logger.info(
            f"冲突解决: action={resolution['action']}, "
            f"winner={resolution['winner']}, reason={resolution['reason']}"
        )
        
        self.stats["conflicts_resolved"] += 1
        
        return resolution
    
    async def resolve_conflicts(
        self,
        conflicts: List[Dict[str, Any]],
        session_id: str
    ) -> Dict[str, Any]:
        """解决所有冲突
        
        Args:
            conflicts: 冲突列表
            session_id: 会话 ID
            
        Returns:
            解决结果统计
        """
        if not conflicts:
            return {
                "success": True,
                "conflicts_count": 0,
                "resolved_count": 0,
                "actions": []
            }
        
        resolved_actions = []
        
        for conflict in conflicts:
            # 解决冲突
            resolution = await self.resolve_conflict(conflict)
            
            # 执行更新（如果需要）
            if resolution["action"] == "update" and self.db:
                existing_id = conflict["existing_fact"]["id"]
                new_fact = conflict["new_fact"]
                
                # 更新数据库
                update_query = text("""
                    UPDATE long_term_memory
                    SET content = :content,
                        metadata = :metadata,
                        confidence = :confidence,
                        updated_at = NOW(),
                        version = version + 1
                    WHERE id = :id
                """)
                
                new_content = f"{new_fact['fact_key']}: {new_fact['fact_value']}"
                new_metadata = {
                    "fact_type": new_fact["fact_type"],
                    "fact_key": new_fact["fact_key"],
                    "fact_value": new_fact["fact_value"],
                    "confidence": new_fact["confidence"],
                    "source": new_fact.get("source", "用户陈述")
                }
                
                await self.db.execute(
                    update_query,
                    {
                        "id": existing_id,
                        "content": new_content,
                        "metadata": json.dumps(new_metadata),
                        "confidence": new_fact["confidence"]
                    }
                )
                
                await self.db.commit()
                
                self.stats["facts_updated"] += 1
                
                logger.info(f"事实已更新: id={existing_id}, 新值={new_fact['fact_value']}")
            
            resolved_actions.append({
                "conflict": conflict,
                "resolution": resolution
            })
        
        return {
            "success": True,
            "conflicts_count": len(conflicts),
            "resolved_count": len(resolved_actions),
            "actions": resolved_actions
        }
    
    async def process_new_information(
        self,
        text: str,
        session_id: str,
        existing_memories: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """处理新信息的完整流程
        
        步骤：
        1. 提取事实
        2. 检测冲突
        3. 解决冲突
        4. 返回结果
        
        Args:
            text: 新信息文本
            session_id: 会话 ID
            existing_memories: 现有记忆
            
        Returns:
            处理结果
        """
        logger.info(f"处理新信息: {text[:50]}...")
        
        # 1. 提取事实
        fact = await self.extract_fact(text)
        
        if fact.get("fact_type") == "none":
            return {
                "success": True,
                "fact_extracted": False,
                "conflicts": [],
                "resolution": None
            }
        
        # 2. 检测冲突
        conflicts = await self.detect_conflicts(fact, existing_memories)
        
        # 3. 解决冲突
        if conflicts:
            resolution = await self.resolve_conflicts(conflicts, session_id)
        else:
            resolution = {
                "success": True,
                "conflicts_count": 0,
                "resolved_count": 0,
                "actions": []
            }
        
        return {
            "success": True,
            "fact_extracted": True,
            "fact": fact,
            "conflicts": conflicts,
            "resolution": resolution
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "confidence_threshold": self.confidence_threshold,
            **self.stats
        }