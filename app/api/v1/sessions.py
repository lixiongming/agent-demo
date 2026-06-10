"""会话管理接口"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_db, get_session_repo, get_optional_user
from app.schemas.session import SessionCreate, SessionInfo, SessionList
from app.schemas.common import SuccessResponse
from app.services.session import SessionService
from app.core.exceptions import SessionNotFoundException
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/create", response_model=SuccessResponse)
async def create_session(
    request: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """创建会话"""
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


@router.get("/list", response_model=SuccessResponse)
async def list_sessions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """获取会话列表"""
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
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取会话详情"""
    service = SessionService(db)
    
    session = await service.get(session_id)
    if not session:
        raise SessionNotFoundException(session_id)
    
    return SuccessResponse(
        message="获取成功",
        data=session
    )


@router.delete("/{session_id}", response_model=SuccessResponse)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除会话"""
    service = SessionService(db)
    
    success = await service.delete(session_id)
    if not success:
        raise SessionNotFoundException(session_id)
    
    await db.commit()
    
    return SuccessResponse(
        message="删除成功",
        data={"session_id": session_id}
    )


@router.post("/{session_id}/pause", response_model=SuccessResponse)
async def pause_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """暂停会话"""
    service = SessionService(db)
    
    session = await service.update_status(session_id, "paused")
    await db.commit()
    
    return SuccessResponse(
        message="会话已暂停",
        data=session
    )


@router.post("/{session_id}/resume", response_model=SuccessResponse)
async def resume_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """恢复会话"""
    service = SessionService(db)
    
    session = await service.update_status(session_id, "active")
    await db.commit()
    
    return SuccessResponse(
        message="会话已恢复",
        data=session
    )