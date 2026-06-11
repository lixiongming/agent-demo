"""会话请求/响应"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class SessionCreate(BaseModel):
    """创建会话请求"""
    agent_type: str = Field(default="chat", description="Agent类型")
    model_name: str = Field(default="qwen3-max", description="模型名称")
    title: Optional[str] = Field(None, description="会话标题")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    config: Optional[dict] = Field(None, description="配置")


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    agent_type: str
    model_name: str
    title: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    class Config:
        from_attributes = True


class SessionList(BaseModel):
    """会话列表项"""
    session_id: str
    agent_type: str
    title: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    class Config:
        from_attributes = True


class SessionPaginate(BaseModel):
    """会话分页响应"""
    list: List[SessionList]
    total: int
    page: int
    page_size: int
    has_more: bool