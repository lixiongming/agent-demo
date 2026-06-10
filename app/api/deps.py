"""依赖注入"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db import get_async_session, SessionRepository, MessageRepository, UserRepository
from app.db.cache import get_redis, RedisCache
from app.config import get_settings
import redis.asyncio as redis

settings = get_settings()
security = HTTPBearer(auto_error=False)


# 数据库依赖
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async for session in get_async_session():
        yield session


# Redis依赖
async def get_redis_cache() -> RedisCache:
    """获取Redis缓存"""
    redis_client = await get_redis()
    return RedisCache(redis_client)


# 仓库依赖
def get_session_repo(db: AsyncSession = Depends(get_db)) -> SessionRepository:
    """获取会话仓库"""
    return SessionRepository(db)


def get_message_repo(db: AsyncSession = Depends(get_db)) -> MessageRepository:
    """获取消息仓库"""
    return MessageRepository(db)


def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepository:
    """获取用户仓库"""
    return UserRepository(db)


# 用户认证依赖
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_repo: UserRepository = Depends(get_user_repo)
) -> dict:
    """获取当前用户"""
    if not credentials:
        # 未认证用户，返回默认
        return {"user_id": None, "username": "anonymous"}
    
    token = credentials.credentials
    
    # TODO: 实现真实的token验证
    # 这里简化处理
    try:
        # 验证token并获取用户
        user_id = int(token)  # 示例
        user = await user_repo.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return {"user_id": user.id, "username": user.username}
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_repo: UserRepository = Depends(get_user_repo)
) -> dict:
    """获取可选用户（允许未认证）"""
    if not credentials:
        return {"user_id": None, "username": "anonymous"}
    
    try:
        return await get_current_user(credentials, user_repo)
    except HTTPException:
        return {"user_id": None, "username": "anonymous"}