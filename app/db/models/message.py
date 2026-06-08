"""消息表模型"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.postgres import Base
from datetime import datetime


class Message(Base):
    """消息表"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    
    # 消息内容
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    
    # 元数据
    token_count = Column(Integer, default=0)
    model_name = Column(String(100), nullable=True)
    tool_calls = Column(JSON, nullable=True)  # 工具调用记录
    tool_results = Column(JSON, nullable=True)  # 工具返回结果
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 关系
    session = relationship("Session", back_populates="messages")
    
    def __repr__(self):
        return f"<Message {self.id} role={self.role}>"