"""消息仓库"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.models import Message, Session
from app.core.logger import get_logger

logger = get_logger(__name__)


class MessageRepository:
    """消息数据访问"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        session_id: int,
        role: str,
        content: str,
        token_count: int = 0,
        model_name: Optional[str] = None,
        tool_calls: Optional[dict] = None,
        tool_results: Optional[dict] = None
    ) -> Message:
        """创建消息"""
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            token_count=token_count,
            model_name=model_name,
            tool_calls=tool_calls,
            tool_results=tool_results
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message
    
    async def get_by_session(
        self,
        session_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """获取会话消息列表"""
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_recent(
        self,
        session_id: int,
        limit: int = 20
    ) -> List[Message]:
        """获取最近消息"""
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return list(reversed(messages))
    
    async def delete_by_session(self, session_id: int) -> int:
        """删除会话所有消息"""
        result = await self.db.execute(
            delete(Message).where(Message.session_id == session_id)
        )
        await self.db.flush()
        return result.rowcount
    
    async def count_by_session(self, session_id: int) -> int:
        """统计会话消息数"""
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count(Message.id))
            .where(Message.session_id == session_id)
        )
        return result.scalar()
    
    async def count_by_sessions(self, session_ids: List[int]) -> dict:
        """批量统计多个会话的消息数（避免 N+1 查询）"""
        from sqlalchemy import func
        if not session_ids:
            return {}
        result = await self.db.execute(
            select(Message.session_id, func.count(Message.id))
            .where(Message.session_id.in_(session_ids))
            .group_by(Message.session_id)
        )
        return {row[0]: row[1] for row in result.all()}
    
    async def search(
        self,
        session_id: int,
        keyword: str,
        limit: int = 10
    ) -> List[Message]:
        """搜索消息"""
        result = await self.db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.content.ilike(f"%{keyword}%")
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
