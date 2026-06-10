"""用户仓库"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import User
from datetime import datetime
from app.core.logger import get_logger

logger = get_logger(__name__)


class UserRepository:
    """用户数据访问"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        username: str,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_admin: bool = False
    ) -> User:
        """创建用户"""
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            is_admin=is_admin
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        logger.info(f"User created: {username}")
        return user
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """根据ID获取"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取"""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def list_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        """获取所有用户"""
        result = await self.db.execute(
            select(User)
            .where(User.is_active == True)
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def update_last_login(self, user_id: int):
        """更新最后登录时间"""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.utcnow())
        )
        await self.db.flush()
    
    async def deactivate(self, user_id: int) -> bool:
        """停用用户"""
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.is_active = False
        await self.db.flush()
        return True