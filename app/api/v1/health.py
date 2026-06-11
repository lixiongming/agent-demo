"""健康检查接口

功能：
- 基础健康检查
- 详细依赖检查（数据库、Redis、Qdrant）
- 系统指标
- 熔断器状态
"""
from fastapi import APIRouter
from app.schemas.common import SuccessResponse
from app.config import get_settings
from app.core.logger import get_logger
from app.core.metrics import Metrics
from app.core.rate_limit import CircuitBreakerManager
import time
import asyncio

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

# 本地常量定义
API_PREFIX = "/api/v1"


@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """基础健康检查"""
    return SuccessResponse(
        message="healthy",
        data={
            "status": "ok",
            "timestamp": time.time()
        }
    )


@router.get("/info", response_model=SuccessResponse)
async def app_info():
    """应用信息"""
    return SuccessResponse(
        message="success",
        data={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "api_prefix": API_PREFIX,
            "default_model": settings.DEFAULT_MODEL
        }
    )


@router.get("/ready", response_model=SuccessResponse)
async def readiness_check():
    """就绪检查 - 详细依赖状态"""
    checks = {}
    all_healthy = True
    
    # 检查数据库
    try:
        from app.db.database import async_engine
        # 简单查询测试
        async with async_engine.connect() as conn:
            await conn.execute("SELECT 1")
        checks["database"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)[:100]}
        all_healthy = False
    
    # 检查 Redis
    try:
        from app.db.cache import get_redis
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)[:100]}
        all_healthy = False
    
    # 检查 Qdrant
    try:
        from app.embeddings.qdrant_store import get_qdrant_adapter
        store = get_qdrant_adapter()
        info = store.get_stats()
        checks["qdrant"] = {
            "status": "healthy",
            "collection": info.get("collection_name"),
            "documents": info.get("total_documents", 0)
        }
    except Exception as e:
        checks["qdrant"] = {"status": "unhealthy", "error": str(e)[:100]}
        all_healthy = False
    
    return SuccessResponse(
        message="ready" if all_healthy else "degraded",
        data={
            "status": "ready" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": time.time()
        }
    )


@router.get("/metrics", response_model=SuccessResponse)
async def get_metrics():
    """获取系统指标"""
    stats = Metrics.get_all_stats()
    
    return SuccessResponse(
        message="success",
        data={
            "metrics": stats,
            "timestamp": time.time()
        }
    )


@router.get("/circuit-breakers", response_model=SuccessResponse)
async def get_circuit_breakers():
    """获取熔断器状态"""
    stats = CircuitBreakerManager.get_all_stats()
    
    return SuccessResponse(
        message="success",
        data={
            "circuit_breakers": stats,
            "timestamp": time.time()
        }
    )


@router.post("/circuit-breakers/reset", response_model=SuccessResponse)
async def reset_circuit_breakers(name: str = None):
    """重置熔断器"""
    CircuitBreakerManager.reset(name)
    
    return SuccessResponse(
        message="circuit breaker reset",
        data={
            "reset_name": name or "all",
            "timestamp": time.time()
        }
    )