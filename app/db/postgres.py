"""MySQL 数据库连接"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# 异步引擎
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 同步引擎（用于Alembic迁移）
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=settings.DEBUG,
    pool_recycle=3600
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
)

# 基类
Base = declarative_base()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话"""
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database error: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()


def get_sync_session():
    """获取同步数据库会话"""
    session = SyncSessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


async def init_db():
    """初始化数据库"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("MySQL Database initialized")


async def close_db():
    """关闭数据库连接"""
    await async_engine.dispose()
    logger.info("MySQL connection closed")