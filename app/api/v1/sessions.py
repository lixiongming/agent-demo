"""会话管理接口

功能：
- 会话创建、查询、删除
- 会话状态管理
- 限流保护
- 链路追踪
- 统一错误处理
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_db, get_session_repo, get_optional_user
from app.schemas.session import SessionCreate, SessionInfo, SessionList
from app.schemas.common import SuccessResponse
from app.services.session import SessionService
from app.core.exceptions import SessionNotFoundException
from app.core.logger import get_logger
from app.core.rate_limit import rate_limit
from app.core.tracing import tracer
from app.core.error_codes import ErrorCode, APIError

logger = get_logger(__name__)
router = APIRouter()


@router.post("/create", response_model=SuccessResponse)
@rate_limit(key="session_create", limit=30, period=60)  # 每分钟 30 次
async def create_session(
    request: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """创建会话"""
    async with tracer.span("session_create"):
        try:
            service = SessionService(db)
            
            session = await service.create(
                agent_type=request.agent_type,
                model_name=request.model_name,
                user_id=user.get("user_id"),
                title=request.title,
                system_prompt=request.system_prompt,
                config=request.config
            )
            
            await db.commit()
            
            return SuccessResponse(
                message="会话创建成功",
                data=session
            )
            
        except APIError:
            raise
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            raise APIError(
                code=ErrorCode.SESSION_CREATE_FAILED,
                message="创建会话失败",
                details={"error": str(e)}
            )


@router.get("/list", response_model=SuccessResponse)
@rate_limit(key="session_list", limit=100, period=60)  # 每分钟 100 次
async def list_sessions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """获取会话列表"""
    async with tracer.span("session_list"):
        service = SessionService(db)
        
        sessions = await service.list(
            user_id=user.get("user_id"),
            status=status,
            page=page,
            page_size=page_size
        )
        
        return SuccessResponse(
            message="获取成功",
            data=sessions
        )


@router.get("/{session_id}", response_model=SuccessResponse)
@rate_limit(key="session_get", limit=200, period=60)  # 每分钟 200 次
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取会话详情 - 大厂标准实现"""
    async with tracer.span("session_get"):
        service = SessionService(db)
        
        session = await service.get(session_id)
        if not session:
            raise APIError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message="会话不存在",
                details={"session_id": session_id}
            )
        
        return SuccessResponse(
            message="获取成功",
            data=session
        )


@router.delete("/{session_id}", response_model=SuccessResponse)
@rate_limit(key="session_delete", limit=30, period=60)  # 每分钟 30 次
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除会话"""
    async with tracer.span("session_delete"):
        service = SessionService(db)
        
        success = await service.delete(session_id)
        if not success:
            raise APIError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message="会话不存在",
                details={"session_id": session_id}
            )
        
        await db.commit()
        
        return SuccessResponse(
            message="删除成功",
            data={"session_id": session_id}
        )


@router.post("/{session_id}/pause", response_model=SuccessResponse)
@rate_limit(key="session_update", limit=50, period=60)  # 每分钟 50 次
async def pause_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """暂停会话"""
    async with tracer.span("session_pause"):
        service = SessionService(db)
        
        session = await service.update_status(session_id, "paused")
        await db.commit()
        
        return SuccessResponse(
            message="会话已暂停",
            data=session
        )


@router.post("/{session_id}/resume", response_model=SuccessResponse)
@rate_limit(key="session_update", limit=50, period=60)  # 每分钟 50 次
async def resume_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """恢复会话"""
    async with tracer.span("session_resume"):
        service = SessionService(db)
        
        session = await service.update_status(session_id, "active")
        await db.commit()
        
        return SuccessResponse(
            message="会话已恢复",
            data=session
        )