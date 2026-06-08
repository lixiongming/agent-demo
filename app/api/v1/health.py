"""健康检查接口"""
from fastapi import APIRouter
from app.schemas.common import SuccessResponse
from app.config import get_settings
import time

router = APIRouter()


@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """健康检查"""
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
    settings = get_settings()
    
    return SuccessResponse(
        message="success",
        data={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG
        }
    )


@router.get("/ready", response_model=SuccessResponse)
async def readiness_check():
    """就绪检查"""
    # TODO: 检查数据库、Redis等连接状态
    
    return SuccessResponse(
        message="ready",
        data={
            "database": "connected",
            "redis": "connected"
        }
    )