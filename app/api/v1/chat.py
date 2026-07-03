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

from app.api.deps import get_db, get_session_repo, get_message_repo, get_current_user
from app.schemas.chat import ChatRequest, ChatResponse, StreamChatRequest
from app.schemas.common import SuccessResponse
from app.services.chat import ChatService
from app.core.logger import get_logger
from app.core.rate_limit import rate_limit, llm_breaker
from app.core.tracing import tracer
from app.core.error_codes import ErrorCode, APIError

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/message",
    response_model=SuccessResponse,
    summary="发送消息（非流式）",
    description="""
发送消息并等待完整回复。适用于不需要流式输出的场景。

**认证要求：** Bearer Token

**请求参数：**
- `session_id`: 会话ID，若不存在会自动创建
- `message`: 用户消息内容

**处理流程：**
1. 智能路由决策（关键词→规则→LLM）
2. 按需执行工具调用（新闻/天气/计算器等）
3. 按需进行RAG检索
4. LLM生成完整回复

**限流：** 每分钟50次

**请求示例：**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "深圳今天天气怎么样"
}
```

**错误码：**
- `UNAUTHORIZED`: 未登录
- `INTERNAL_ERROR`: 对话处理失败
"""
)
@rate_limit(key="chat", limit=50, period=60)
async def send_message(
    request: ChatRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """发送消息（非流式）
    
    需要登录认证。
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
            # 未知错误，转换为统一格式（不泄露内部异常信息）
            logger.error(f"Chat error: {e}")
            raise APIError(
                code=ErrorCode.INTERNAL_ERROR,
                message="对话处理失败，请稍后重试"
            )


@router.post(
    "/message/stream",
    response_model=None,
    summary="发送消息（流式SSE）",
    description="""
发送消息并以 Server-Sent Events (SSE) 流式返回回复。适用于需要实时显示生成过程的场景。

**认证要求：** Bearer Token

**请求参数：**
- `session_id`: 会话ID，若不存在会自动创建
- `message`: 用户消息内容

**SSE 数据格式：**
```
data: {"type": "content", "content": "你"}
data: {"type": "content", "content": "好"}
data: {"type": "done", "session_id": "..."}
```

**错误SSE格式：**
```
data: {"error": "对话处理失败", "code": "INTERNAL_ERROR"}
```

**限流：** 每分钟30次

**curl 示例：**
```bash
curl -N -X POST http://localhost:8888/api/v1/chat/message/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "你好"}'
```

**错误码：**
- `UNAUTHORIZED`: 未登录
- `INTERNAL_ERROR`: 对话处理失败
"""
)
@rate_limit(key="chat_stream", limit=30, period=60)
async def send_message_stream(
    request: StreamChatRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """发送消息（流式）
    
    需要登录认证。
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


@router.get(
    "/history/{session_id}",
    response_model=SuccessResponse,
    summary="获取聊天历史",
    description="""
获取指定会话的聊天历史记录。仅返回当前用户拥有的会话。

**认证要求：** Bearer Token

**路径参数：**
- `session_id`: 会话ID

**查询参数：**
- `limit`: 返回消息数量，默认50

**安全措施：**
- 验证会话归属，只能查看自己的会话

**限流：** 每分钟100次

**响应示例：**
```json
{
    "session_id": "550e8400...",
    "messages": [
        {"id": 1, "role": "user", "content": "你好", "created_at": "2026-01-01T00:00:00"},
        {"id": 2, "role": "assistant", "content": "你好！有什么可以帮你的？", "created_at": "2026-01-01T00:00:01"}
    ]
}
```

**错误码：**
- `UNAUTHORIZED`: 未登录
"""
)
@rate_limit(key="chat_history", limit=100, period=60)
async def get_history(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """获取聊天历史（需登录+验证会话归属）"""
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
        
        # 验证会话归属：只能查看自己的会话
        if session.user_id and session.user_id != user.get("user_id"):
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