"""缓存服务

功能：
- RAG 检索结果缓存
- 路由决策缓存
- 多级缓存策略（内存 + Redis）

使用示例：
    from app.services.cache import CacheService
    
    # 缓存 RAG 结果
    await CacheService.set_rag_result(query, result)
    result = await CacheService.get_rag_result(query)
    
    # 缓存路由决策
    await CacheService.set_route_decision(query, decision)
    decision = await CacheService.get_route_decision(query)
"""

import hashlib
from typing import Optional, Dict, Any, List
from app.db.cache import get_redis, RedisCache
from app.core.logger import get_logger

logger = get_logger(__name__)


class CacheService:
    """缓存服务
    
    多级缓存策略：
    L1: 本地内存缓存（LRU，最快）
    L2: Redis 缓存（分布式）
    """
    
    # ===== 内存缓存 =====
    _rag_cache: Dict[str, Dict[str, Any]] = {}
    _route_cache: Dict[str, Dict[str, Any]] = {}
    
    # 缓存配置
    RAG_CACHE_TTL = 3600  # RAG 缓存 1 小时
    ROUTE_CACHE_TTL = 1800  # 路由缓存 30 分钟
    MAX_MEMORY_CACHE_SIZE = 1000  # 内存缓存最大条目数
    
    @staticmethod
    def _hash_key(key: str) -> str:
        """生成缓存键的哈希"""
        return hashlib.sha256(key.encode()).hexdigest()[:32]
    
    @staticmethod
    def _check_memory_cache_size(cache: dict):
        """检查内存缓存大小，超出则清理"""
        if len(cache) > CacheService.MAX_MEMORY_CACHE_SIZE:
            # 删除最早的一半缓存
            keys_to_remove = list(cache.keys())[:len(cache) // 2]
            for key in keys_to_remove:
                del cache[key]
            logger.info(f"Memory cache cleaned, removed {len(keys_to_remove)} items")
    
    @staticmethod
    async def _scan_keys(pattern: str) -> List[str]:
        """使用 SCAN 命令扫描匹配的键（生产安全，不阻塞 Redis）
        
        Args:
            pattern: 匹配模式，如 "rag:*"
        
        Returns:
            匹配的键列表
        """
        keys = []
        try:
            redis = await get_redis()
            if redis:
                async for key in redis.scan_iter(match=pattern, count=100):
                    keys.append(key)
        except Exception as e:
            logger.warning(f"Redis scan error: {e}")
        return keys
    
    # ===== RAG 缓存 =====
    
    @staticmethod
    async def get_rag_result(query: str) -> Optional[Dict[str, Any]]:
        """获取 RAG 缓存结果
        
        查找顺序：L1 内存 → L2 Redis
        """
        cache_key = f"rag:{CacheService._hash_key(query)}"
        
        # L1: 内存缓存
        if cache_key in CacheService._rag_cache:
            logger.debug(f"RAG cache hit (memory): {query[:20]}...")
            return CacheService._rag_cache[cache_key]
        
        # L2: Redis 缓存
        try:
            redis = await get_redis()
            if redis:
                cache = RedisCache(redis)
                result = await cache.get_json(cache_key)
                if result:
                    logger.debug(f"RAG cache hit (redis): {query[:20]}...")
                    # 回填内存缓存
                    CacheService._rag_cache[cache_key] = result
                    return result
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")
        
        return None
    
    @staticmethod
    async def set_rag_result(query: str, result: Dict[str, Any]):
        """设置 RAG 缓存结果
        
        同时写入 L1 内存和 L2 Redis
        """
        cache_key = f"rag:{CacheService._hash_key(query)}"
        
        # L1: 内存缓存
        CacheService._check_memory_cache_size(CacheService._rag_cache)
        CacheService._rag_cache[cache_key] = result
        
        # L2: Redis 缓存
        try:
            redis = await get_redis()
            if redis:
                cache = RedisCache(redis)
                await cache.set_json(cache_key, result, CacheService.RAG_CACHE_TTL)
                logger.debug(f"RAG cache set: {query[:20]}...")
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")
    
    # ===== 路由决策缓存 =====
    
    @staticmethod
    async def get_route_decision(query: str) -> Optional[Dict[str, Any]]:
        """获取路由决策缓存"""
        cache_key = f"route:{CacheService._hash_key(query)}"
        
        # L1: 内存缓存
        if cache_key in CacheService._route_cache:
            logger.debug(f"Route cache hit (memory): {query[:20]}...")
            return CacheService._route_cache[cache_key]
        
        # L2: Redis 缓存
        try:
            redis = await get_redis()
            if redis:
                cache = RedisCache(redis)
                result = await cache.get_json(cache_key)
                if result:
                    logger.debug(f"Route cache hit (redis): {query[:20]}...")
                    CacheService._route_cache[cache_key] = result
                    return result
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")
        
        return None
    
    @staticmethod
    async def set_route_decision(query: str, decision: Dict[str, Any]):
        """设置路由决策缓存"""
        cache_key = f"route:{CacheService._hash_key(query)}"
        
        # L1: 内存缓存
        CacheService._check_memory_cache_size(CacheService._route_cache)
        CacheService._route_cache[cache_key] = decision
        
        # L2: Redis 缓存
        try:
            redis = await get_redis()
            if redis:
                cache = RedisCache(redis)
                await cache.set_json(cache_key, decision, CacheService.ROUTE_CACHE_TTL)
                logger.debug(f"Route cache set: {query[:20]}...")
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")
    
    # ===== 缓存管理 =====
    
    @staticmethod
    async def clear_all():
        """清空所有缓存"""
        CacheService._rag_cache.clear()
        CacheService._route_cache.clear()
        
        try:
            # 使用 SCAN 替代 KEYS（生产安全，不阻塞 Redis）
            rag_keys = await CacheService._scan_keys("rag:*")
            route_keys = await CacheService._scan_keys("route:*")
            
            redis = await get_redis()
            if redis:
                if rag_keys:
                    await redis.delete(*rag_keys)
                if route_keys:
                    await redis.delete(*route_keys)
        except Exception as e:
            logger.warning(f"Redis cache clear error: {e}")
        
        logger.info("All caches cleared")
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "memory_cache": {
                "rag_count": len(CacheService._rag_cache),
                "route_count": len(CacheService._route_cache),
                "max_size": CacheService.MAX_MEMORY_CACHE_SIZE
            },
            "config": {
                "rag_ttl": CacheService.RAG_CACHE_TTL,
                "route_ttl": CacheService.ROUTE_CACHE_TTL
            }
        }
