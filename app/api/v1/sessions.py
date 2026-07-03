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

from app.api.deps import get_db, get_session_repo, get_current_user
from app.api.v1.admin import verify_admin_token
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


@router.post(
    "/create",
    response_model=SuccessResponse,
    summary="创建会话",
    description="""
创建新的对话会话。会话自动绑定当前登录用户。

**认证要求：** Bearer Token

**请求参数：**
- `agent_type`: Agent类型（如 "chat"）
- `model_name`: 模型名称（如 "qwen3-max"）
- `title`: 可选，会话标题
- `system_prompt`: 可选，系统提示词
- `config`: 可选，会话配置

**限流：** 每分钟30次

**请求示例：**
```json
{
    "agent_type": "chat",
    "model_name": "qwen3-max",
    "title": "新对话"
}
```

**错误码：**
- `UNAUTHORIZED`: 未登录
- `SESSION_CREATE_FAILED`: 创建失败
"""
)
@rate_limit(key="session_create", limit=30, period=60)
async def create_session(
    request: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """创建会话（需登录）"""
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


@router.get(
    "/list",
    response_model=SuccessResponse,
    summary="获取会话列表",
    description="""
获取当前用户的会话列表，支持分页和状态过滤。

**认证要求：** Bearer Token

**查询参数：**
- `page`: 页码，默认1
- `page_size`: 每页数量，默认20
- `status`: 可选，按状态过滤（active/paused/ended）

**限流：** 每分钟100次

**错误码：**
- `UNAUTHORIZED`: 未登录
"""
)
@rate_limit(key="session_list", limit=100, period=60)
async def list_sessions(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """获取会话列表（需登录，仅返回当前用户的会话）"""
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


@router.get(
    "/{session_id}",
    response_model=SuccessResponse,
    summary="获取会话详情",
    description="""
获取指定会话的详细信息。仅返回当前用户拥有的会话。

**认证要求：** Bearer Token

**安全措施：**
- 验证会话归属，只能查看自己的会话

**限流：** 每分钟200次

**错误码：**
- `UNAUTHORIZED`: 未登录
- `SESSION_NOT_FOUND`: 会话不存在或不属于当前用户
"""
)
@rate_limit(key="session_get", limit=200, period=60)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """获取会话详情（需登录+验证归属）"""
    async with tracer.span("session_get"):
        service = SessionService(db)
        
        session = await service.get(session_id)
        if not session:
            raise APIError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message="会话不存在",
                details={"session_id": session_id}
            )
        
        # 验证会话归属：只能查看自己的会话（管理员除外）
        if session.get("user_id") and session["user_id"] != user.get("user_id"):
            raise APIError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message="会话不存在",
                details={"session_id": session_id}
            )
        
        return SuccessResponse(
            message="获取成功",
            data=session
        )


@router.delete(
    "/{session_id}",
    response_model=SuccessResponse,
    summary="删除会话",
    description="""
删除指定会话及其所有消息。此操作不可恢复。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**限流：** 每分钟30次

**错误码：**
- `SESSION_NOT_FOUND`: 会话不存在
""",
    dependencies=[Depends(verify_admin_token)]
)
@rate_limit(key="session_delete", limit=30, period=60)
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


@router.post(
    "/{session_id}/pause",
    response_model=SuccessResponse,
    summary="暂停会话",
    description="""
暂停指定会话，暂停后该会话不再接收新消息。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**限流：** 每分钟50次
""",
    dependencies=[Depends(verify_admin_token)]
)
@rate_limit(key="session_update", limit=50, period=60)
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


@router.post(
    "/{session_id}/resume",
    response_model=SuccessResponse,
    summary="恢复会话",
    description="""
恢复已暂停的会话，恢复后可继续对话。

**认证要求：** Admin Token（X-Admin-Token 请求头）

**限流：** 每分钟50次
""",
    dependencies=[Depends(verify_admin_token)]
)
@rate_limit(key="session_update", limit=50, period=60)
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