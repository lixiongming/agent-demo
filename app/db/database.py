"""数据库连接管理

支持：
- MySQL 异步连接
- 连接池管理
- 会话管理
- 延迟初始化（避免启动时数据库不可用导致失败）
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

# 延迟初始化的引擎和会话工厂
_async_engine: Optional[create_async_engine] = None
_AsyncSessionLocal: Optional[async_sessionmaker] = None
_sync_engine: Optional[create_engine] = None
_SyncSessionLocal: Optional[sessionmaker] = None


class Base(DeclarativeBase):
    """ORM 基类（SQLAlchemy 2.0 标准写法）"""
    pass


def _get_settings():
    """延迟获取配置，避免模块级导入时配置未就绪"""
    from app.config import get_settings
    return get_settings()


def _ensure_async_engine():
    """确保异步引擎已初始化"""
    global _async_engine, _AsyncSessionLocal
    if _async_engine is None:
        settings = _get_settings()
        _async_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        _AsyncSessionLocal = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    return _async_engine, _AsyncSessionLocal


def _ensure_sync_engine():
    """确保同步引擎已初始化"""
    global _sync_engine, _SyncSessionLocal
    if _sync_engine is None:
        settings = _get_settings()
        _sync_engine = create_engine(
            settings.DATABASE_URL_SYNC,
            echo=settings.DEBUG,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=10
        )
        _SyncSessionLocal = sessionmaker(
            bind=_sync_engine,
            autocommit=False,
            autoflush=False
        )
    return _sync_engine, _SyncSessionLocal


# 为了兼容旧代码中直接访问 async_engine 和 AsyncSessionLocal 的情况，
# 提供 __getattr__ 模块级别代理
import sys


class _DbModule(sys.modules[__name__].__class__):
    """模块代理，支持延迟初始化的属性访问"""

    @property
    def async_engine(self):
        return _ensure_async_engine()[0]

    @property
    def AsyncSessionLocal(self):
        return _ensure_async_engine()[1]

    @property
    def sync_engine(self):
        return _ensure_sync_engine()[0]

    @property
    def SyncSessionLocal(self):
        return _ensure_sync_engine()[1]


sys.modules[__name__].__class__ = _DbModule


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话"""
    _, session_local = _ensure_async_engine()
    session = session_local()
    try:
        yield session
    except Exception as e:
        from sqlalchemy.exc import SQLAlchemyError
        if isinstance(e, SQLAlchemyError):
            logger.error(f"Database error: {e}")
            await session.rollback()
        raise
    finally:
        await session.close()


def get_sync_session():
    """获取同步数据库会话"""
    _, session_local = _ensure_sync_engine()
    session = session_local()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


async def init_db():
    """初始化数据库

    注意：生产环境应使用 Alembic 进行数据库迁移，而非 create_all。
    开发环境可使用 create_all 快速创建表结构。
    """
    engine, _ = _ensure_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def close_db():
    """关闭数据库连接"""
    global _async_engine, _AsyncSessionLocal, _sync_engine, _SyncSessionLocal

    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _AsyncSessionLocal = None

    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
        _SyncSessionLocal = None

    logger.info("Database connection closed")
