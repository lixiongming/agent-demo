"""聊天接口

功能：
- 限流保护
- 熔断保护
- 链路追踪
- 统一错误处理
- 输入验证
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import json

from app.api.deps import get_db, get_session_repo, get_message_repo, get_optional_user
from app.schemas.chat import ChatRequest, ChatResponse, StreamChatRequest
from app.schemas.common import SuccessResponse
from app.services.chat import ChatService
from app.core.logger import get_logger
from app.core.rate_limit import rate_limit, llm_breaker
from app.core.tracing import tracer
from app.core.error_codes import ErrorCode, APIError

logger = get_logger(__name__)
router = APIRouter()


@router.post("/message", response_model=SuccessResponse)
@rate_limit(key="chat", limit=50, period=60)  # 每分钟 50 次
async def send_message(
    request: ChatRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """发送消息（非流式）
    
    功能：
    - 限流保护（每分钟 50 次）
    - 熔断保护（LLM 调用失败 5 次熔断）
    - 链路追踪
    - 统一错误处理
    """
    async with tracer.span("chat_api"):
        try:
            service = ChatService(db)
            
            # 熔断保护
            with llm_breaker:
                result = await service.chat(
                    session_id=request.session_id,
                    message=request.message,
                    user_id=user.get("user_id")
                )
            
            # 提交事务
            await db.commit()
            
            return SuccessResponse(
                message="回复成功",
                data=result
            )
            
        except APIError:
            # 已知错误，直接抛出
            raise
        except Exception as e:
            # 未知错误，转换为统一格式
            logger.error(f"Chat error: {e}")
            raise APIError(
                code=ErrorCode.INTERNAL_ERROR,
                message="对话处理失败",
                details={"error": str(e)}
            )


@router.post("/message/stream")
@rate_limit(key="chat_stream", limit=30, period=60)  # 每分钟 30 次
async def send_message_stream(
    request: StreamChatRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """发送消息（流式）
    
    功能：
    - 限流保护（每分钟 30 次）
    - 熔断保护
    - 链路追踪
    - 统一错误处理
    """
    async with tracer.span("chat_stream_api"):
        service = ChatService(db)
        
        async def generate():
            try:
                # 熔断检查
                if llm_breaker.state.value == "open":
                    yield f"data: {json.dumps({'error': '服务暂时不可用，请稍后重试'}, ensure_ascii=False)}\n\n"
                    return
                
                async for chunk in service.chat_stream(
                    session_id=request.session_id,
                    message=request.message,
                    user_id=user.get("user_id")
                ):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                
                # 流结束后提交事务
                await db.commit()
                
            except APIError as e:
                await db.rollback()
                yield f"data: {json.dumps({'error': e.message, 'code': e.code}, ensure_ascii=False)}\n\n"
            except Exception as e:
                await db.rollback()
                logger.error(f"Stream chat error: {e}")
                yield f"data: {json.dumps({'error': '对话处理失败'}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )


@router.get("/history/{session_id}", response_model=SuccessResponse)
@rate_limit(key="chat_history", limit=100, period=60)  # 每分钟 100 次
async def get_history(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取聊天历史"""
    async with tracer.span("chat_history_api"):
        from app.db import SessionRepository, MessageRepository
        
        session_repo = SessionRepository(db)
        message_repo = MessageRepository(db)
        
        # 先获取会话
        session = await session_repo.get_by_id(session_id)
        if not session:
            return SuccessResponse(
                message="会话不存在",
                data={"session_id": session_id, "messages": []}
            )
        
        # 使用整数id查询消息
        messages = await message_repo.get_by_session(session.id, limit)
        
        # 格式化消息
        message_list = []
        for msg in messages:
            message_list.append({
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            })
        
        return SuccessResponse(
            message="获取成功",
            data={
                "session_id": session_id,
                "messages": message_list
            }
        )