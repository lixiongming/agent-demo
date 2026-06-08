"""测试数据"""
import asyncio
from app.db import get_async_session, SessionRepository, MessageRepository
from app.config import get_settings
from app.core.logger import setup_logging, get_logger
import uuid

logger = get_logger(__name__)
settings = get_settings()


async def main():
    """创建测试数据"""
    setup_logging()
    
    logger.info("Creating test data...")
    
    async for db in get_async_session():
        session_repo = SessionRepository(db)
        message_repo = MessageRepository(db)
        
        # 创建测试会话
        session = await session_repo.create(
            session_id=str(uuid.uuid4()),
            agent_type="chat",
            model_name=settings.DEFAULT_MODEL,
            title="测试会话",
            system_prompt="你是一个友好的AI助手"
        )
        
        logger.info(f"Created test session: {session.session_id}")
        
        # 创建测试消息
        await message_repo.create(
            session_id=session.id,
            role="user",
            content="你好！"
        )
        
        await message_repo.create(
            session_id=session.id,
            role="assistant",
            content="你好！我是AI助手，有什么可以帮助你的吗？",
            model_name=settings.DEFAULT_MODEL
        )
        
        logger.info("Test data created successfully")
        break


if __name__ == "__main__":
    asyncio.run(main())