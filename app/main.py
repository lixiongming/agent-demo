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
    
    # 清理容器
    from app.core.container import DIContainer
    DIContainer.clear()
    
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    """创建应用"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="LangGraph + FastAPI Agent Service",
        lifespan=lifespan,
        default_response_class=UnicodeJSONResponse  # 使用自定义JSON响应
    )
    
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
            "docs": "/docs",
            "health": f"{settings.API_PREFIX}/health/health"
        }
    
    return app


# 创建应用实例
app = create_app()


# 启动命令:
# uvicorn app.main:app --reload
# uvicorn app.main:app --host 0.0.0.0 --port 8888