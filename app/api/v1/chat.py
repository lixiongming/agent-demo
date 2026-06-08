"""聊天接口"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import json

from app.api.deps import get_db, get_session_repo, get_message_repo, get_optional_user
from app.schemas.chat import ChatRequest, ChatResponse, StreamChatRequest
from app.schemas.common import SuccessResponse
from app.services.chat_service import ChatService
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/message", response_model=SuccessResponse)
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """发送消息（非流式）"""
    service = ChatService(db)
    
    result = await service.chat(
        session_id=request.session_id,
        message=request.message,
        user_id=user.get("user_id")
    )
    
    # 提交事务，保存到数据库
    await db.commit()
    
    return SuccessResponse(
        message="回复成功",
        data=result
    )


@router.post("/message/stream")
async def send_message_stream(
    request: StreamChatRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user)
):
    """发送消息（流式）"""
    service = ChatService(db)
    
    async def generate():
        try:
            async for chunk in service.chat_stream(
                session_id=request.session_id,
                message=request.message,
                user_id=user.get("user_id")
            ):
                # ensure_ascii=False 直接输出中文
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            # 流结束后提交事务
            await db.commit()
        except Exception as e:
            await db.rollback()
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


@router.get("/history/{session_id}", response_model=SuccessResponse)
async def get_history(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取聊天历史"""
    from app.db import SessionRepository, MessageRepository
    
    session_repo = SessionRepository(db)
    message_repo = MessageRepository(db)
    
    # 先获取会话（通过字符串session_id找到整数id）
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