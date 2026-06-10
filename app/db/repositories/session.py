"""会话仓库"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from app.db.models import Session
from app.core.logger import get_logger

logger = get_logger(__name__)


class SessionRepository:
    """会话数据访问"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        session_id: str,
        agent_type: str,
        model_name: str,
        user_id: Optional[int] = None,
        title: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[dict] = None
    ) -> Session:
        """创建会话"""
        session = Session(
            session_id=session_id,
            user_id=user_id,
            agent_type=agent_type,
            model_name=model_name,
            title=title,
            system_prompt=system_prompt,
            config=config
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        logger.info(f"Session created: {session_id}")
        return session
    
    async def get_by_id(self, session_id: str) -> Optional[Session]:
        """根据session_id获取"""
        result = await self.db.execute(
            select(Session).where(Session.session_id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_user(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Session]:
        """获取用户会话列表"""
        query = select(Session).where(Session.user_id == user_id)
        if status:
            query = query.where(Session.status == status)
        query = query.order_by(Session.updated_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def list_all(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Session]:
        """获取所有会话"""
        query = select(Session)
        if status:
            query = query.where(Session.status == status)
        query = query.order_by(Session.updated_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update(
        self,
        session_id: str,
        **kwargs
    ) -> Optional[Session]:
        """更新会话"""
        session = await self.get_by_id(session_id)
        if not session:
            return None
        
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        await self.db.flush()
        await self.db.refresh(session)
        logger.info(f"Session updated: {session_id}")
        return session
    
    async def delete(self, session_id: str) -> bool:
        """删除会话"""
        result = await self.db.execute(
            delete(Session).where(Session.session_id == session_id)
        )
        await self.db.flush()
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Session deleted: {session_id}")
        return deleted
    
    async def increment_message_count(self, session_id: str, token_count: int = 0):
        """增加消息计数"""
        await self.db.execute(
            update(Session)
            .where(Session.session_id == session_id)
            .values(
                message_count=Session.message_count + 1,
                token_count=Session.token_count + token_count
            )
        )
        await self.db.flush()
    
    async def count(self, status: Optional[str] = None) -> int:
        """统计会话数量"""
        query = select(func.count(Session.id))
        if status:
            query = query.where(Session.status == status)
        result = await self.db.execute(query)
        return result.scalar()