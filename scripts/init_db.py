"""初始化数据库"""
import asyncio
from app.db import init_db, close_db
from app.core.logger import setup_logging, get_logger

logger = get_logger(__name__)


async def main():
    """初始化数据库"""
    setup_logging()
    
    logger.info("Initializing database...")
    
    await init_db()
    
    logger.info("Database initialized successfully")
    
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())