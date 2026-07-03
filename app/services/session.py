"""会话服务"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db import SessionRepository, MessageRepository
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class SessionService:
    """会话服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.message_repo = MessageRepository(db)
    
    async def create(
        self,
        agent_type: str,
        model_name: str,
        user_id: Optional[int] = None,
        title: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[dict] = None
    ) -> dict:
        """创建会话"""
        session_id = str(uuid.uuid4())
        
        session = await self.session_repo.create(
            session_id=session_id,
            agent_type=agent_type,
            model_name=model_name,
            user_id=user_id,
            title=title,
            system_prompt=system_prompt,
            config=config
        )
        
        logger.info(f"Session created: {session_id}")
        
        return {
            "session_id": session.session_id,
            "agent_type": session.agent_type,
            "model_name": session.model_name,
            "title": session.title,
            "status": session.status,
            "created_at": session.created_at
        }
    
    async def get(self, session_id: str) -> Optional[dict]:
        """获取会话"""
        session = await self.session_repo.get_by_id(session_id)
        
        if not session:
            return None
        
        # 获取消息数量
        message_count = await self.message_repo.count_by_session(session.id)
        
        return {
            "session_id": session.session_id,
            "agent_type": session.agent_type,
            "model_name": session.model_name,
            "title": session.title,
            "status": session.status,
            "system_prompt": session.system_prompt,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": message_count,
            "token_count": session.token_count
        }
    
    async def list(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """获取会话列表"""
        skip = (page - 1) * page_size
        
        if user_id:
            sessions = await self.session_repo.get_by_user(
                user_id=user_id,
                status=status,
                limit=page_size
            )
        else:
            sessions = await self.session_repo.list_all(
                status=status,
                skip=skip,
                limit=page_size
            )
        
        # 统计总数
        total = await self.session_repo.count(status)
        
        # 批量获取消息数量（避免 N+1 查询）
        session_ids = [session.id for session in sessions]
        message_counts = await self.message_repo.count_by_sessions(session_ids)

        items = []
        for session in sessions:
            items.append({
                "session_id": session.session_id,
                "agent_type": session.agent_type,
                "title": session.title,
                "status": session.status,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "message_count": message_counts.get(session.id, 0)
            })
        
        return {
            "list": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": total > page * page_size
        }
    
    async def update_status(self, session_id: str, status: str) -> Optional[dict]:
        """更新会话状态"""
        session = await self.session_repo.update(session_id, status=status)
        
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "status": session.status
        }
    
    async def delete(self, session_id: str) -> bool:
        """删除会话（事务保证一致性）"""
        session = await self.session_repo.get_by_id(session_id)
        
        if not session:
            return False
        
        try:
            # 在同一事务中删除消息和会话
            await self.message_repo.delete_by_session(session.id)
            success = await self.session_repo.delete(session_id)
            
            if success:
                logger.info(f"Session deleted: {session_id}")
            
            return success
        except Exception as e:
            logger.error(f"Session delete failed: {e}")
            raise