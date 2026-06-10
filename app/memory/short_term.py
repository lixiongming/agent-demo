"""短期记忆 - Redis"""
from typing import List, Optional, Dict, Any
import json
from app.db.cache import get_redis, RedisCache
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ShortTermMemory:
    """短期记忆
    
    使用Redis存储最近对话历史，支持快速访问和自动过期
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.redis: RedisCache = None
        self.key_prefix = f"memory:short:{session_id}"
        self.ttl = settings.MEMORY_SHORT_TERM_TTL
    
    async def init(self):
        """初始化Redis连接"""
        redis_client = await get_redis()
        self.redis = RedisCache(redis_client)
    
    async def add_message(self, role: str, content: str, metadata: Optional[dict] = None):
        """添加消息"""
        if not self.redis:
            await self.init()
        
        message = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": str(int(time.time()))
        }
        
        # 存储到Redis列表
        key = f"{self.key_prefix}:messages"
        await self.redis.redis.rpush(key, json.dumps(message))
        await self.redis.expire(key, self.ttl)
        
        logger.debug(f"Message added to short-term memory: {role}")
    
    async def get_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取消息列表"""
        if not self.redis:
            await self.init()
        
        key = f"{self.key_prefix}:messages"
        messages_raw = await self.redis.redis.lrange(key, -limit, -1)
        
        messages = []
        for msg_raw in messages_raw:
            try:
                messages.append(json.loads(msg_raw))
            except json.JSONDecodeError:
                continue
        
        return messages
    
    async def get_last_message(self) -> Optional[Dict[str, Any]]:
        """获取最后一条消息"""
        messages = await self.get_messages(limit=1)
        return messages[0] if messages else None
    
    async def clear(self):
        """清空记忆"""
        if not self.redis:
            await self.init()
        
        key = f"{self.key_prefix}:messages"
        await self.redis.delete(key)
        logger.info(f"Short-term memory cleared: {self.session_id}")
    
    async def set_context(self, key: str, value: Any):
        """设置上下文"""
        if not self.redis:
            await self.init()
        
        full_key = f"{self.key_prefix}:context:{key}"
        await self.redis.set_json(full_key, value, self.ttl)
    
    async def get_context(self, key: str) -> Optional[Any]:
        """获取上下文"""
        if not self.redis:
            await self.init()
        
        full_key = f"{self.key_prefix}:context:{key}"
        return await self.redis.get_json(full_key)
    
    async def get_stats(self) -> dict:
        """获取统计信息"""
        messages = await self.get_messages()
        return {
            "session_id": self.session_id,
            "message_count": len(messages),
            "ttl": self.ttl
        }


import time