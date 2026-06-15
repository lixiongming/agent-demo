"""聊天请求/响应 - 标准实现

功能：
- 输入验证
- 消息长度限制
- 字段描述
"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str = Field(
        ...,
        description="会话ID",
        min_length=1,
        max_length=64
    )
    message: str = Field(
        ...,
        description="用户消息",
        min_length=1,
        max_length=4000
    )
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """验证消息内容"""
        if not v or not v.strip():
            raise ValueError('消息不能为空')
        return v.strip()


class StreamChatRequest(BaseModel):
    """流式聊天请求"""
    session_id: str = Field(
        ...,
        description="会话ID",
        min_length=1,
        max_length=64
    )
    message: str = Field(
        ...,
        description="用户消息",
        min_length=1,
        max_length=4000
    )
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """验证消息内容"""
        if not v or not v.strip():
            raise ValueError('消息不能为空')
        return v.strip()


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    response: str
    message_count: int
    rag_used: bool = False
    rag_strategy: Optional[str] = None
    rag_score: float = 0.0


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