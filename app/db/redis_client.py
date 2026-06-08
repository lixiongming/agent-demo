"""Redis 连接"""
import redis.asyncio as redis
from typing import Optional
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Redis客户端
redis_client: Optional[redis.Redis] = None


async def get_redis() -> Optional[redis.Redis]:
    """获取Redis客户端"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            redis_client = None
    return redis_client


async def init_redis():
    """初始化Redis"""
    global redis_client
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Running without Redis cache.")
        redis_client = None  # 允许在没有Redis的情况下运行


async def close_redis():
    """关闭Redis连接"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Redis connection closed")


class RedisCache:
    """Redis缓存工具"""
    
    def __init__(self, redis: redis.Redis):
        self.redis = redis
    
    async def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, ttl: int = None):
        """设置缓存"""
        if ttl:
            await self.redis.setex(key, ttl, value)
        else:
            await self.redis.set(key, value)
    
    async def delete(self, key: str):
        """删除缓存"""
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        return await self.redis.exists(key) > 0
    
    async def get_json(self, key: str) -> Optional[dict]:
        """获取JSON缓存"""
        import json
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set_json(self, key: str, value: dict, ttl: int = None):
        """设置JSON缓存"""
        import json
        await self.set(key, json.dumps(value), ttl)
    
    async def incr(self, key: str) -> int:
        """计数器增加"""
        return await self.redis.incr(key)
    
    async def expire(self, key: str, seconds: int):
        """设置过期时间"""
        await self.redis.expire(key, seconds)