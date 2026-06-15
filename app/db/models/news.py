"""新闻表模型

对应数据库表：news
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from app.db.database import Base


class News(Base):
    """新闻表
    
    表结构：
    - id: 新闻ID（主键，自增）
    - title: 新闻标题
    - description: 新闻简介
    - content: 新闻内容
    - image: 封面图片URL
    - author: 作者
    - views: 浏览量
    - created_at: 创建时间
    - updated_at: 更新时间
    """
    __tablename__ = "news"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="新闻ID")
    
    # 基本信息
    title = Column(String(255), nullable=False, comment="新闻标题")
    description = Column(String(500), nullable=True, comment="新闻简介")
    content = Column(Text, nullable=False, comment="新闻内容")
    image = Column(String(255), nullable=True, comment="封面图片URL")
    author = Column(String(50), nullable=True, comment="作者")
    
    # 统计信息
    views = Column(Integer, nullable=False, default=0, comment="浏览量")
    
    # 时间信息
    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间"
    )
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="更新时间"
    )
    
    def __repr__(self):
        return f"<News {self.id} title={self.title[:20]}>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "image": self.image,
            "author": self.author,
            "views": self.views,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_summary_dict(self):
        """转换为摘要字典（不包含完整内容）"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "image": self.image,
            "author": self.author,
            "views": self.views,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }