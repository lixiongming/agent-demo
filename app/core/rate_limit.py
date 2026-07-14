
"""限流和熔断模块
# 功能：
# - 基于 Redis 的分布式限流（滑动窗口算法）
# - 熔断器模式（防止级联故障）
# - IP/用户/API 多维度限流
# - 自动恢复机制

# 使用示例：
#     # 限流
#     @rate_limit(key="api_chat", limit=100, period=60)
#     async def chat_endpoint():
#         ...

#     # 熔断器
#     circuit_breaker = CircuitBreaker(name="llm_call", threshold=5, timeout=30)
#     async def call_llm():
#         with circuit_breaker:
#             return await llm.invoke()
"""

import time
import uuid
import asyncio
from functools import wraps
from enum import Enum
from typing import Optional, Callable, Any

from app.config import get_settings
from app.core.logger import get_logger
from app.core.error_codes import ErrorCode, APIError

logger = get_logger(__name__)
settings = get_settings()


# ============================================
# 限流器（基于 Redis 滑动窗口）
# ============================================

class RateLimiter:
    """分布式限流器
    
    使用 Redis 滑动窗口算法，支持：
    - IP 限流
    - 用户限流
    - API 限流
    """
    
    _REDIS_SENTINEL = object()

    def __init__(
        self,
        redis_client: Any = None,
        default_limit: int = 100,
        default_period: int = 60
    ):
        """
        Args:
            redis_client: Redis 客户端
            default_limit: 默认限制次数
            default_period: 默认时间窗口（秒）
        """
        self.redis = redis_client
        self.default_limit = default_limit
        self.default_period = default_period
    
    async def _get_redis(self):
        """获取 Redis 连接"""
        if self.redis is None:
            from app.db.redis_client import get_redis
            redis_client = await get_redis()
            if redis_client is None:
                self.redis = self._REDIS_SENTINEL
                return None
            self.redis = redis_client
        if self.redis is self._REDIS_SENTINEL:
            return None
        return self.redis
    
    async def is_allowed(
        self,
        key: str,
        limit: int = None,
        period: int = None
    ) -> tuple[bool, int, int]:
        """检查是否允许请求
        
        Args:
            key: 限流键（如 "ip:192.168.1.1"）
            limit: 限制次数
            period: 时间窗口（秒）
            
        Returns:
            (是否允许, 当前计数, 剩余次数)
        """
        limit = limit or self.default_limit
        period = period or self.default_period
        
        redis = await self._get_redis()
        if redis is None:
            # Redis 不可用时放行所有请求
            return True, 0, limit
        
        current_time = time.time()
        window_start = current_time - period
        
        redis_key = f"rate_limit:{key}"
        
        # 滑动窗口算法
        # 1. 移除窗口外的记录
        await redis.zremrangebyscore(redis_key, 0, window_start)
        
        # 2. 获取当前窗口内的计数
        count = await redis.zcard(redis_key)
        
        if count >= limit:
            # 获取最早的请求时间，计算等待时间
            earliest = await redis.zrange(redis_key, 0, 0, withscores=True)
            if earliest:
                wait_time = earliest[0][1] - window_start
                logger.warning(f"Rate limit exceeded: key={key}, count={count}, wait={wait_time}s")
            return False, count, 0
        
        # 3. 添加当前请求
        await redis.zadd(redis_key, {str(uuid.uuid4()): current_time})
        await redis.expire(redis_key, period)
        
        return True, count + 1, limit - count - 1
    
    async def get_remaining(self, key: str, limit: int = None, period: int = None) -> int:
        """获取剩余次数"""
        limit = limit or self.default_limit
        redis = await self._get_redis()
        redis_key = f"rate_limit:{key}"
        
        current_time = time.time()
        window_start = current_time - (period or self.default_period)
        
        await redis.zremrangebyscore(redis_key, 0, window_start)
        count = await redis.zcard(redis_key)
        
        return max(0, limit - count)


# 模块级别限流器实例
_default_limiter = None


def _get_default_limiter():
    """获取模块级别限流器实例"""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter()
    return _default_limiter


def rate_limit(
    key: str,
    limit: int = 100,
    period: int = 60,
    key_prefix: str = ""
):
    """限流装饰器
    
    Args:
        key: 限流键
        limit: 限制次数
        period: 时间窗口（秒）
        key_prefix: 键前缀（如 "ip:" 或 "user:"）
        
    使用示例：
        @rate_limit("chat", limit=50, period=60)
        async def chat_endpoint(request, ...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取模块级别限流器实例
            limiter = _get_default_limiter()
            
            # 构建完整键
            full_key = f"{key_prefix}{key}"
            
            # 检查限流
            allowed, count, remaining = await limiter.is_allowed(full_key, limit, period)
            
            if not allowed:
                raise APIError(
                    code=ErrorCode.RATE_LIMIT_EXCEEDED,
                    message=f"请求过于频繁，请稍后再试（限制: {limit}次/{period}秒）",
                    details={"limit": limit, "period": period, "current_count": count}
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================
# 熔断器（Circuit Breaker）
# ============================================

class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态（拒绝请求）
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）


class CircuitBreaker:
    """熔断器
    
    功能：
    - 自动熔断（连续失败达到阈值）
    - 自动恢复（超时后尝试恢复）
    - 状态监控
    
    使用示例：
        breaker = CircuitBreaker("llm_call", threshold=5, timeout=30)
        
        async def call_llm():
            with breaker:
                return await llm.invoke()
    """
    
    def __init__(
        self,
        name: str,
        threshold: int = 5,
        timeout: int = 30,
        half_open_requests: int = 3
    ):
        """
        Args:
            name: 熔断器名称
            threshold: 失败阈值（连续失败次数）
            timeout: 熔断超时时间（秒）
            half_open_requests: 半开状态允许的尝试次数
        """
        self.name = name
        self.threshold = threshold
        self.timeout = timeout
        self.half_open_requests = half_open_requests
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0
        self._half_open_count = 0
        self._lock = asyncio.Lock()

        logger.info(f"Circuit breaker initialized: {name}")
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态（同步版本，无锁保护）

        注意：此属性不提供线程安全保证，仅用于非异步上下文的只读检查。
        在异步环境中，推荐使用 await _get_state() 方法。
        """
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_count = 0
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN")
        return self._state

    async def _get_state(self) -> CircuitState:
        """获取当前状态（线程安全）"""
        async with self._lock:
            # 检查是否需要从 OPEN 转为 HALF_OPEN
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_count = 0
                    logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN")

            return self._state
    
    def _record_success(self):
        """记录成功（同步版本，无锁保护，供 __exit__ 使用）"""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_count += 1
            if self._half_open_count >= self.half_open_requests:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED")
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    async def _async_record_success(self):
        """记录成功（异步版本，线程安全，供 call() 使用）"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_count += 1
                if self._half_open_count >= self.half_open_requests:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _record_failure(self):
        """记录失败（同步版本，无锁保护，供 __exit__ 使用）"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (failure)")
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker {self.name}: CLOSED -> OPEN (threshold={self.threshold})")

    async def _async_record_failure(self):
        """记录失败（异步版本，线程安全，供 call() 使用）"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (failure)")
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(f"Circuit breaker {self.name}: CLOSED -> OPEN (threshold={self.threshold})")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """通过熔断器调用函数
        
        Args:
            func: 要调用的函数
            args, kwargs: 函数参数
            
        Returns:
            函数返回值
            
        Raises:
            CircuitBreakerError: 熔断器处于 OPEN 状态
        """
        state = await self._get_state()

        if state == CircuitState.OPEN:
            raise APIError(
                code=ErrorCode.CIRCUIT_BREAKER_OPEN,
                message=f"服务暂时不可用，请稍后再试（熔断器: {self.name}）",
                details={"breaker": self.name, "state": "open", "timeout": self.timeout}
            )

        try:
            result = await func(*args, **kwargs)
            await self._async_record_success()
            return result
        except Exception:
            await self._async_record_failure()
            raise
    
    def __enter__(self):
        """上下文管理器入口

        注意：同步上下文管理器无法使用 asyncio.Lock 保护状态转换，
        推荐在生产环境中使用 async call() 方法代替。
        """
        if self.state == CircuitState.OPEN:
            raise APIError(
                code=ErrorCode.CIRCUIT_BREAKER_OPEN,
                message=f"服务暂时不可用，请稍后再试（熔断器: {self.name}）",
                details={"breaker": self.name, "state": "open"}
            )
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口

        注意：同步上下文管理器无法使用 asyncio.Lock 保护状态转换，
        推荐在生产环境中使用 async call() 方法代替。
        """
        if exc_type is None:
            self._record_success()
        else:
            self._record_failure()
        
        return False  # 不抑制异常
    
    def get_stats(self) -> dict:
        """获取统计信息（返回快照，非线程安全）"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "threshold": self.threshold,
            "timeout": self.timeout,
            "last_failure_time": self._last_failure_time
        }


# ============================================
# 熔断器管理器
# ============================================

class CircuitBreakerManager:
    """熔断器管理器
    
    管理多个熔断器，提供统一接口
    """
    
    _breakers: dict[str, CircuitBreaker] = {}
    
    @classmethod
    def get_breaker(
        cls,
        name: str,
        threshold: int = 5,
        timeout: int = 30
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in cls._breakers:
            cls._breakers[name] = CircuitBreaker(name, threshold, timeout)
        return cls._breakers[name]
    
    @classmethod
    def get_all_stats(cls) -> dict:
        """获取所有熔断器统计"""
        return {
            name: breaker.get_stats()
            for name, breaker in cls._breakers.items()
        }
    
    @classmethod
    def reset(cls, name: str = None):
        """重置熔断器"""
        if name:
            if name in cls._breakers:
                cls._breakers[name]._state = CircuitState.CLOSED
                cls._breakers[name]._failure_count = 0
                logger.info(f"Circuit breaker {name} reset")
        else:
            for breaker in cls._breakers.values():
                breaker._state = CircuitState.CLOSED
                breaker._failure_count = 0
            logger.info("All circuit breakers reset")


# ============================================
# 预定义熔断器
# ============================================

# LLM 调用熔断器
llm_breaker = CircuitBreakerManager.get_breaker(
    "llm_call",
    threshold=5,    # 连续失败 5 次熔断
    timeout=60      # 60 秒后尝试恢复
)

# RAG 检索熔断器
rag_breaker = CircuitBreakerManager.get_breaker(
    "rag_search",
    threshold=10,
    timeout=30
)

# 数据库熔断器
db_breaker = CircuitBreakerManager.get_breaker(
    "database",
    threshold=5,
    timeout=30
)