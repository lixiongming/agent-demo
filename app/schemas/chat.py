"""聊天请求/响应"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="用户消息")


class StreamChatRequest(BaseModel):
    """流式聊天请求"""
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="用户消息")


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    response: str
    message_count: int


class MessageItem(BaseModel):
    """消息项"""
    id: int
    role: str
    content: str
    created_at: datetime
    token_count: int = 0
    
    class Config:
        from_attributes = True


class MessageList(BaseModel):
    """消息列表"""
    session_id: str
    messages: List[MessageItem]