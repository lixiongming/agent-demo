"""健康检查接口（K8s 探针用）

仅保留最小化的健康探针端点，不暴露任何内部信息。
生产标准：
- /health: 存活探针（Liveness Probe）
- /ready:  就绪探针（Readiness Probe）
"""
import asyncio
from fastapi import APIRouter
from sqlalchemy import text
from app.schemas.common import SuccessResponse
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """存活探针 - K8s Liveness Probe
    
    只要服务进程存活就返回 OK，不检查依赖。
    K8s 根据此探针决定是否重启容器。
    """
    return SuccessResponse(
        message="healthy",
        data={"status": "ok"}
    )


@router.get("/ready", response_model=SuccessResponse)
async def readiness_check():
    """就绪探针 - K8s Readiness Probe
    
    检查所有关键依赖是否可用，决定是否接收流量。
    不暴露内部错误细节，只返回 healthy/unhealthy。
    """
    checks = {}
    all_healthy = True

    # 检查数据库
    try:
        from app.db.database import async_engine
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"
        all_healthy = False

    # 检查 Redis
    try:
        from app.db.redis_client import get_redis
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"
        all_healthy = False

    # 检查 Qdrant
    try:
        from app.embeddings.qdrant_store import get_qdrant_adapter
        store = get_qdrant_adapter()
        await asyncio.to_thread(store.get_stats)
        checks["qdrant"] = "healthy"
    except Exception:
        checks["qdrant"] = "unhealthy"
        all_healthy = False

    return SuccessResponse(
        message="ready" if all_healthy else "degraded",
        data={
            "status": "ready" if all_healthy else "degraded",
            "checks": checks
        }
    )
