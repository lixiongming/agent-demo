"""管理接口（需 Admin Token 认证）

生产标准：
- 独立路由前缀 /admin
- 所有接口需要 Admin Token 认证
- 不暴露测试接口
- 操作接口有审计日志
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
import hmac
from app.schemas.common import SuccessResponse
from app.config import get_settings
from app.core.logger import get_logger
from app.core.metrics import Metrics
from app.core.rate_limit import CircuitBreakerManager
from app.core.tracing import tracer, PerformanceAnalyzer
from app.services.cache import CacheService
from app.services.rerank import get_rerank_service

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


# ===== 认证依赖 =====

async def verify_admin_token(x_admin_token: Optional[str] = Header(None)) -> bool:
    """验证 Admin Token

    Admin Token 通过环境变量 ADMIN_TOKEN 配置。
    使用 hmac.compare_digest 防止时序攻击。
    """
    admin_token = settings.ADMIN_TOKEN
    if not admin_token:
        raise HTTPException(status_code=403, detail="未配置 ADMIN_TOKEN 环境变量")
    if not hmac.compare_digest(x_admin_token or "", admin_token):
        logger.warning("Admin API 访问被拒绝: 无效的 Token")
        raise HTTPException(status_code=401, detail="无效的管理员 Token")
    return True


# ===== 系统信息 =====

@router.get(
    "/info",
    response_model=SuccessResponse,
    summary="获取应用信息",
    description="""
获取应用基本信息，包括名称、版本、环境、默认模型等。

**认证要求：** Admin Token（X-Admin-Token 请求头）
""",
    dependencies=[Depends(verify_admin_token)],
)
async def app_info():
    """获取应用信息"""
    return SuccessResponse(
        message="获取成功",
        data={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "default_model": settings.DEFAULT_MODEL,
        },
    )


# ===== 系统指标 =====

@router.get(
    "/metrics",
    response_model=SuccessResponse,
    summary="获取系统指标",
    description="""
获取系统运行指标，包括请求统计、延迟分布等。

**认证要求：** Admin Token（X-Admin-Token 请求头）
""",
    dependencies=[Depends(verify_admin_token)],
)
async def get_metrics():
    """获取系统指标"""
    stats = Metrics.get_all_stats()
    return SuccessResponse(message="获取成功", data={"metrics": stats})


# ===== 熔断器管理 =====

@router.get(
    "/circuit-breakers",
    response_model=SuccessResponse,
    summary="获取熔断器状态",
    description="""
获取所有熔断器的当前状态（开路/半开/闭路）及失败计数。

**认证要求：** Admin Token（X-Admin-Token 请求头）
""",
    dependencies=[Depends(verify_admin_token)],
)
async def get_circuit_breakers():
    """获取熔断器状态"""
    stats = CircuitBreakerManager.get_all_stats()
    return SuccessResponse(message="获取成功", data={"circuit_breakers": stats})


@router.post(
    "/circuit-breakers/reset",
    response_model=SuccessResponse,
    summary="重置熔断器",
    description="""
重置指定熔断器到闭路状态。不传 name 则重置所有熔断器。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**查询参数：**
- `name`: 可选，熔断器名称，不传则重置全部
""",
    dependencies=[Depends(verify_admin_token)],
)
async def reset_circuit_breakers(name: Optional[str] = None):
    """重置熔断器"""
    logger.warning(f"管理员操作: 重置熔断器 [{name or '全部'}]")
    CircuitBreakerManager.reset(name)
    return SuccessResponse(
        message="熔断器已重置",
        data={"reset_name": name or "all"},
    )


# ===== 链路追踪 =====

@router.get(
    "/tracing/stats",
    response_model=SuccessResponse,
    summary="获取追踪统计",
    description="""
获取链路追踪的统计信息，包括请求数量、平均延迟等。

**认证要求：** Admin Token（X-Admin-Token 请求头）
""",
    dependencies=[Depends(verify_admin_token)],
)
async def get_tracing_stats():
    """获取追踪统计"""
    stats = tracer.get_stats()
    return SuccessResponse(message="获取成功", data={"tracing": stats})


@router.get(
    "/tracing/trace/{request_id}",
    response_model=SuccessResponse,
    summary="获取请求追踪链",
    description="""
根据请求ID获取完整的调用链路及性能分析。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**路径参数：**
- `request_id`: 请求ID
""",
    dependencies=[Depends(verify_admin_token)],
)
async def get_trace(request_id: str):
    """获取请求追踪链"""
    trace = tracer.get_trace(request_id)
    if not trace:
        return SuccessResponse(message="追踪记录不存在", data={"request_id": request_id, "trace": []})
    analysis = PerformanceAnalyzer.analyze_trace(trace)
    return SuccessResponse(message="获取成功", data={"request_id": request_id, "trace": trace, "analysis": analysis})


@router.delete(
    "/tracing/clear",
    response_model=SuccessResponse,
    summary="清理追踪数据",
    description="""
清理追踪数据。可指定 request_id 清理单条，不传则清理全部。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**查询参数：**
- `request_id`: 可选，指定请求ID，不传则清理全部
""",
    dependencies=[Depends(verify_admin_token)],
)
async def clear_tracing(request_id: Optional[str] = None):
    """清理追踪数据"""
    logger.warning(f"管理员操作: 清理追踪数据 [{request_id or '全部'}]")
    if request_id:
        tracer.clear_request(request_id)
    else:
        tracer.clear_all()
    return SuccessResponse(message="追踪数据已清理", data={"cleared_request": request_id})


# ===== 缓存管理 =====

@router.get(
    "/cache/stats",
    response_model=SuccessResponse,
    summary="获取缓存统计",
    description="""
获取各层缓存的统计信息，包括命中率、大小等。

**认证要求：** Admin Token（X-Admin-Token 请求头）
""",
    dependencies=[Depends(verify_admin_token)],
)
async def get_cache_stats():
    """获取缓存统计"""
    stats = CacheService.get_stats()
    return SuccessResponse(message="获取成功", data={"cache": stats})


@router.delete(
    "/cache/clear",
    response_model=SuccessResponse,
    summary="清空所有缓存",
    description="""
清空所有层级的缓存数据。此操作不可恢复。

**认证要求：** Admin Token（X-Admin-Token 请求头）
""",
    dependencies=[Depends(verify_admin_token)],
)
async def clear_cache():
    """清空所有缓存"""
    logger.warning("管理员操作: 清空所有缓存")
    await CacheService.clear_all()
    return SuccessResponse(message="所有缓存已清空")


# ===== Rerank 管理 =====

@router.get(
    "/rerank/stats",
    response_model=SuccessResponse,
    summary="获取 Rerank 统计",
    description="""
获取 Rerank 重排序服务的统计信息及当前配置。

**认证要求：** Admin Token（X-Admin-Token 请求头）
""",
    dependencies=[Depends(verify_admin_token)],
)
async def get_rerank_stats():
    """获取 Rerank 统计"""
    reranker = get_rerank_service()
    stats = reranker.get_stats()
    return SuccessResponse(
        message="获取成功",
        data={
            "rerank": stats,
            "config": {
                "enabled": settings.RERANK_ENABLED,
                "model": settings.RERANK_MODEL,
                "top_k": settings.RERANK_TOP_K,
                "final_k": settings.RERANK_FINAL_K,
            },
        },
    )


# ===== 工具管理 =====

@router.get(
    "/tools/stats",
    response_model=SuccessResponse,
    summary="获取工具统计",
    description="""
获取所有已注册工具的执行统计，包括调用次数、成功率、平均耗时等。

**认证要求：** Admin Token（X-Admin-Token 请求头）
""",
    dependencies=[Depends(verify_admin_token)],
)
async def get_tools_stats():
    """获取工具统计"""
    from app.tools.registry import get_registry
    registry = get_registry()
    stats = registry.get_all_stats()
    return SuccessResponse(message="获取成功", data={"tools": stats, "total_tools": len(stats)})


@router.get(
    "/tools/{tool_name}",
    response_model=SuccessResponse,
    summary="获取工具详情",
    description="""
获取指定工具的详细信息，包括参数定义、限流配置、熔断状态等。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**路径参数：**
- `tool_name`: 工具名称
""",
    dependencies=[Depends(verify_admin_token)],
)
async def get_tool_info(tool_name: str):
    """获取工具详情"""
    from app.tools.registry import get_registry
    registry = get_registry()
    info = registry.get_tool_info(tool_name)
    if not info:
        return SuccessResponse(message="工具不存在", data={"tool_name": tool_name})
    return SuccessResponse(message="获取成功", data=info)


@router.post(
    "/tools/{tool_name}/enable",
    response_model=SuccessResponse,
    summary="启用工具",
    description="""
启用指定工具，启用后该工具可被 Agent 调用。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**路径参数：**
- `tool_name`: 工具名称
""",
    dependencies=[Depends(verify_admin_token)],
)
async def enable_tool(tool_name: str):
    """启用工具"""
    logger.warning(f"管理员操作: 启用工具 [{tool_name}]")
    from app.tools.registry import get_registry
    registry = get_registry()
    registry.enable_tool(tool_name)
    return SuccessResponse(message=f"工具已启用: {tool_name}", data={"tool_name": tool_name})


@router.post(
    "/tools/{tool_name}/disable",
    response_model=SuccessResponse,
    summary="禁用工具",
    description="""
禁用指定工具，禁用后该工具不会被 Agent 调用。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**路径参数：**
- `tool_name`: 工具名称
""",
    dependencies=[Depends(verify_admin_token)],
)
async def disable_tool(tool_name: str):
    """禁用工具"""
    logger.warning(f"管理员操作: 禁用工具 [{tool_name}]")
    from app.tools.registry import get_registry
    registry = get_registry()
    registry.disable_tool(tool_name)
    return SuccessResponse(message=f"工具已禁用: {tool_name}", data={"tool_name": tool_name})


@router.delete(
    "/tools/stats/reset",
    response_model=SuccessResponse,
    summary="重置工具统计",
    description="""
重置工具的执行统计数据。可指定工具名重置单个，不传则重置全部。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**查询参数：**
- `tool_name`: 可选，工具名称，不传则重置全部
""",
    dependencies=[Depends(verify_admin_token)],
)
async def reset_tools_stats(tool_name: Optional[str] = None):
    """重置工具统计"""
    logger.warning(f"管理员操作: 重置工具统计 [{tool_name or '全部'}]")
    from app.tools.registry import get_registry
    registry = get_registry()
    registry.reset_stats(tool_name)
    return SuccessResponse(message=f"工具统计已重置: {tool_name or '全部'}")
