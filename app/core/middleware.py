"""中间件"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import time
import logging
from app.core.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next):
        # 记录请求
        start_time = time.time()
        logger.info(f"Request: {request.method} {request.url}")
        
        # 执行请求
        response: Response = await call_next(request)
        
        # 记录响应
        process_time = time.time() - start_time
        logger.info(
            f"Response: {request.method} {request.url} "
            f"Status: {response.status_code} "
            f"Time: {process_time:.3f}s"
        )
        
        # 添加处理时间头
        response.headers["X-Process-Time"] = str(process_time)
        
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