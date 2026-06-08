"""会话表模型"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from app.db.postgres import Base
from datetime import datetime


class Session(Base):
    """会话表"""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    agent_type = Column(String(50), nullable=False)
    status = Column(String(20), default="active")  # active, paused, ended
    title = Column(String(200), nullable=True)
    
    # 配置
    model_name = Column(String(100), nullable=False)
    system_prompt = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # 统计
    message_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    
    # 关系
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Session {self.session_id}>"