"""FastAPI 入口"""
import sys
import os

# Windows下设置UTF-8编码（必须在最前面）
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import json

from app.config import get_settings
from app.core import setup_logging, setup_middlewares
from app.db import init_db, close_db, init_redis, close_redis
from app.api import api_router
from app.core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


# 自定义JSON响应类（直接显示中文）
class UnicodeJSONResponse(JSONResponse):
    """支持中文的JSON响应"""
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # 生产环境配置校验
    warnings = settings.validate_production_config()
    for w in warnings:
        logger.warning(f"[配置警告] {w}")
    
    # 配置依赖注入容器
    from app.core.container import setup_container
    setup_container()
    logger.info("DI Container configured")
    
    await init_db()
    await init_redis()
    
    logger.info("Application started")
    
    yield
    
    # 关闭
    await close_db()
    await close_redis()
    
    # 关闭 RerankService HTTP 客户端
    from app.services.rerank import shutdown_rerank_service
    await shutdown_rerank_service()

    # 关闭 Embedding 服务 HTTP 客户端
    from app.core.container import DIContainer
    from app.core.interfaces import IEmbeddingService
    if DIContainer.has(IEmbeddingService):
        embedding_service = DIContainer.get(IEmbeddingService)
        if hasattr(embedding_service, 'close'):
            await embedding_service.close()

    # 关闭 Qdrant 客户端
    from app.core.interfaces import IVectorStore
    if DIContainer.has(IVectorStore):
        vs = DIContainer.get(IVectorStore)
        if hasattr(vs, 'close'):
            await asyncio.to_thread(vs.close)
    
    DIContainer.clear()
    
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    """创建应用"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="LangGraph + FastAPI Agent Service",
        lifespan=lifespan,
        default_response_class=UnicodeJSONResponse,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # 注册全局异常处理器
    _register_exception_handlers(app)
    
    # 配置中间件
    setup_middlewares(app)
    
    # 注册路由
    app.include_router(api_router, prefix=settings.API_PREFIX)
    
    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "health": f"{settings.API_PREFIX}/health/health",
            "docs": "/docs",
        }
    
    return app


def _register_exception_handlers(app: FastAPI):
    """注册全局异常处理器
    
    将领域异常统一转换为 HTTP 响应，遵循分层原则：
    - 异常层不耦合 HTTP 框架
    - API 层负责异常 → HTTP 响应的转换
    """
    from app.core.exceptions import AgentException
    from app.core.error_codes import APIError
    
    @app.exception_handler(AgentException)
    async def agent_exception_handler(request, exc: AgentException):
        """处理所有业务异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details if exc.details else None
            }
        )
    
    @app.exception_handler(APIError)
    async def api_error_handler(request, exc: APIError):
        """处理 API 错误码异常"""
        logger.error(f"APIError: {exc.to_internal_dict()}")
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict()
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc: Exception):
        """处理未捕获的异常（不泄露内部信息）"""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "服务内部错误，请稍后重试"
            }
        )


# 创建应用实例
app = create_app()


# 启动命令:
# uvicorn app.main:app --reload
# uvicorn app.main:app --host 0.0.0.0 --port 8888