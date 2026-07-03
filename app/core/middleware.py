"""中间件"""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import time
import logging
from app.core.logger import get_logger, set_request_context, clear_request_context

logger = get_logger(__name__)

# 性能日志（单例）
_perf_logger = None


def get_perf_logger():
    """获取性能日志单例"""
    global _perf_logger
    if _perf_logger is None:
        from app.core.logger import get_performance_logger
        _perf_logger = get_performance_logger()
    return _perf_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件 - 增强版
    
    - 请求ID追踪
    - 性能监控
    - 请求/响应记录
    """
    
    async def dispatch(self, request: Request, call_next):
        # 设置请求上下文
        request_id = request.headers.get("X-Request-ID", None)
        user_id = request.headers.get("X-User-ID", None)
        
        set_request_context(request_id, user_id)
        
        # 记录请求
        start_time = time.time()
        logger.info(f"Request: {request.method} {request.url.path}")
        
        # 执行请求
        response: Response = await call_next(request)
        
        # 记录响应
        process_time = time.time() - start_time
        
        # 性能日志
        perf_logger = get_perf_logger()
        perf_logger.log_request_time(
            endpoint=request.url.path,
            duration=process_time,
            method=request.method
        )
        
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"Status: {response.status_code} "
            f"Time: {process_time:.3f}s"
        )
        
        # 添加响应头
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_id or ""
        
        # 清除请求上下文
        clear_request_context()
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件
    
    基于 Redis 滑动窗口算法，按客户端 IP 限流。
    默认每分钟 60 次请求。
    Redis 不可用时放行所有请求。
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._limiter = None
    
    def _get_limiter(self):
        """获取限流器实例（延迟初始化）"""
        if self._limiter is None:
            from app.core.rate_limit import RateLimiter
            self._limiter = RateLimiter(default_limit=self.requests_per_minute, default_period=60)
        return self._limiter
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
    
    async def dispatch(self, request: Request, call_next):
        limiter = self._get_limiter()
        client_ip = self._get_client_ip(request)
        key = f"ip:{client_ip}"
        
        try:
            allowed, count, remaining = await limiter.is_allowed(
                key, limit=self.requests_per_minute, period=60
            )
        except Exception:
            # Redis 不可用时放行所有请求
            logger.warning("Rate limiter unavailable, allowing request")
            response = await call_next(request)
            return response
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "code": "4290",
                    "message": "请求过于频繁，请稍后再试",
                    "details": {
                        "limit": self.requests_per_minute,
                        "period": 60,
                        "current_count": count,
                    },
                },
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60",
                },
            )
        
        response = await call_next(request)
        
        # 添加限流信息到响应头
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response


def setup_middlewares(app):
    """配置中间件"""
    from app.config import get_settings
    settings = get_settings()

    # CORS（通过环境变量 CORS_ORIGINS 配置）
    cors_origins = settings.cors_origins_list
    allow_credentials = cors_origins != ["*"]  # 生产环境指定域名时可启用 credentials

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 日志
    app.add_middleware(LoggingMiddleware)

    # 速率限制
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)