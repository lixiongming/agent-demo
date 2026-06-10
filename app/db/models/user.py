"""用户表模型"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.db.database import Base
from datetime import datetime


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    
    # 状态
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # 配置
    preferences = Column(String(500), nullable=True)  # JSON格式用户偏好
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<User {self.username}>"