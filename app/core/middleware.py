"""中间件"""
from fastapi import Request, Response
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
    
    改进：
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
    """速率限制中间件"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}
    
    async def dispatch(self, request: Request, call_next):
        # TODO: 实现速率限制逻辑
        response = await call_next(request)
        return response


def setup_middlewares(app):
    """配置中间件"""
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 日志
    app.add_middleware(LoggingMiddleware)