"""健康检查接口

功能：
- 基础健康检查
- 详细依赖检查（数据库、Redis、Qdrant）
- 系统指标
- 熔断器状态
- 链路追踪
"""
from fastapi import APIRouter
from app.schemas.common import SuccessResponse
from app.config import get_settings
from app.core.logger import get_logger
from app.core.metrics import Metrics
from app.core.rate_limit import CircuitBreakerManager
from app.core.tracing import tracer, PerformanceAnalyzer
from app.services.cache import CacheService
from app.services.rerank import get_rerank_service
import time

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


# ============================================
# 链路追踪接口
# ============================================

@router.get("/tracing/stats", response_model=SuccessResponse)
async def get_tracing_stats():
    """获取追踪统计信息"""
    stats = tracer.get_stats()
    
    return SuccessResponse(
        message="success",
        data={
            "tracing": stats,
            "timestamp": time.time()
        }
    )


@router.get("/tracing/trace/{request_id}", response_model=SuccessResponse)
async def get_trace(request_id: str):
    """获取某个请求的追踪链"""
    trace = tracer.get_trace(request_id)
    
    if not trace:
        return SuccessResponse(
            message="trace not found",
            data={
                "request_id": request_id,
                "trace": []
            }
        )
    
    # 分析追踪链
    analysis = PerformanceAnalyzer.analyze_trace(trace)
    
    return SuccessResponse(
        message="success",
        data={
            "request_id": request_id,
            "trace": trace,
            "analysis": analysis,
            "timestamp": time.time()
        }
    )


@router.get("/tracing/active", response_model=SuccessResponse)
async def get_active_spans():
    """获取当前活跃的 Span"""
    spans = tracer.get_active_spans()
    
    return SuccessResponse(
        message="success",
        data={
            "active_count": len(spans),
            "spans": [
                {
                    "name": s.name,
                    "request_id": s.request_id,
                    "start_time": s.start_time,
                    "attributes": s.attributes
                }
                for s in spans
            ],
            "timestamp": time.time()
        }
    )


@router.delete("/tracing/clear", response_model=SuccessResponse)
async def clear_tracing(request_id: str = None):
    """清理追踪数据"""
    if request_id:
        tracer.clear_request(request_id)
        message = f"trace cleared for request: {request_id}"
    else:
        tracer.clear_all()
        message = "all traces cleared"
    
    return SuccessResponse(
        message=message,
        data={
            "cleared_request": request_id,
            "timestamp": time.time()
        }
    )


# ============================================
# 缓存接口
# ============================================

@router.get("/cache/stats", response_model=SuccessResponse)
async def get_cache_stats():
    """获取缓存统计信息"""
    stats = CacheService.get_stats()
    
    return SuccessResponse(
        message="success",
        data={
            "cache": stats,
            "timestamp": time.time()
        }
    )


@router.delete("/cache/clear", response_model=SuccessResponse)
async def clear_cache():
    """清空所有缓存"""
    await CacheService.clear_all()
    
    return SuccessResponse(
        message="all caches cleared",
        data={
            "timestamp": time.time()
        }
    )


# ============================================
# Rerank 接口
# ============================================

@router.get("/rerank/stats", response_model=SuccessResponse)
async def get_rerank_stats():
    """获取 Rerank 统计信息"""
    reranker = get_rerank_service()
    stats = reranker.get_stats()
    
    return SuccessResponse(
        message="success",
        data={
            "rerank": stats,
            "config": {
                "enabled": settings.RERANK_ENABLED,
                "model": settings.RERANK_MODEL,
                "top_k": settings.RERANK_TOP_K,
                "final_k": settings.RERANK_FINAL_K
            },
            "timestamp": time.time()
        }
    )


@router.post("/rerank/test", response_model=SuccessResponse)
async def test_rerank(query: str, documents: list[str], top_k: int = 5):
    """测试 Rerank 功能
    
    Args:
        query: 查询文本
        documents: 文档列表
        top_k: 返回前 K 个结果
    """
    reranker = get_rerank_service()
    results = await reranker.rerank(query, documents, top_k)
    
    return SuccessResponse(
        message="success",
        data={
            "query": query,
            "input_count": len(documents),
            "results": results,
            "timestamp": time.time()
        }
    )


# ============================================
# 工具统计接口
# ============================================

@router.get("/tools/stats", response_model=SuccessResponse)
async def get_tools_stats():
    """获取所有工具统计信息"""
    from app.tools.registry import get_registry
    
    registry = get_registry()
    stats = registry.get_all_stats()
    
    return SuccessResponse(
        message="success",
        data={
            "tools": stats,
            "total_tools": len(stats),
            "timestamp": time.time()
        }
    )


@router.get("/tools/{tool_name}", response_model=SuccessResponse)
async def get_tool_info(tool_name: str):
    """获取单个工具详细信息"""
    from app.tools.registry import get_registry
    
    registry = get_registry()
    info = registry.get_tool_info(tool_name)
    
    if not info:
        return SuccessResponse(
            message="工具不存在",
            data={"tool_name": tool_name}
        )
    
    return SuccessResponse(
        message="success",
        data=info
    )


@router.post("/tools/{tool_name}/enable", response_model=SuccessResponse)
async def enable_tool(tool_name: str):
    """启用工具"""
    from app.tools.registry import get_registry
    
    registry = get_registry()
    registry.enable_tool(tool_name)
    
    return SuccessResponse(
        message=f"工具已启用: {tool_name}",
        data={"tool_name": tool_name}
    )


@router.post("/tools/{tool_name}/disable", response_model=SuccessResponse)
async def disable_tool(tool_name: str):
    """禁用工具"""
    from app.tools.registry import get_registry
    
    registry = get_registry()
    registry.disable_tool(tool_name)
    
    return SuccessResponse(
        message=f"工具已禁用: {tool_name}",
        data={"tool_name": tool_name}
    )


@router.delete("/tools/stats/reset", response_model=SuccessResponse)
async def reset_tools_stats(tool_name: str = None):
    """重置工具统计信息"""
    from app.tools.registry import get_registry
    
    registry = get_registry()
    registry.reset_stats(tool_name)
    
    return SuccessResponse(
        message=f"工具统计已重置: {tool_name or 'all'}",
        data={"tool_name": tool_name}
    )