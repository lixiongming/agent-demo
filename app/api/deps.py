"""依赖注入"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db import get_async_session, SessionRepository, MessageRepository, UserRepository
from app.db.redis_client import get_redis, RedisCache
from app.config import get_settings
from app.core.exceptions import UnauthorizedException
from app.core.logger import get_logger
from app.utils.jwt_handler import decode_token, is_token_revoked
import jwt as jwt_lib

settings = get_settings()
security = HTTPBearer(auto_error=False)
logger = get_logger(__name__)


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


# ============================================
# 用户认证依赖（JWT）
# ============================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """获取当前用户（必须登录）

    验证流程：
    1. 提取 Bearer Token
    2. JWT 解码验证签名和过期
    3. 检查 Token 黑名单
    4. 返回用户信息

    Raises:
        UnauthorizedException: 未认证或 Token 无效
    """
    if not credentials:
        raise UnauthorizedException("未提供认证凭证")

    token = credentials.credentials

    # JWT 解码验证
    try:
        payload = decode_token(token, token_type="access")
    except jwt_lib.ExpiredSignatureError:
        raise UnauthorizedException("Token 已过期")
    except jwt_lib.InvalidTokenError:
        raise UnauthorizedException("Token 无效")
    except (KeyError, ValueError):
        raise UnauthorizedException("Token 格式错误")
    except Exception:
        raise UnauthorizedException("认证失败")

    # 检查黑名单
    if await is_token_revoked(token):
        raise UnauthorizedException("Token 已被撤销")

    return {
        "user_id": int(payload["sub"]),
        "username": payload.get("username", ""),
    }


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """获取可选用户（允许未认证）

    Token 有效时返回用户信息，无效时返回匿名用户。
    用于同时支持登录和未登录用户的接口。
    """
    if not credentials:
        return {"user_id": None, "username": "anonymous"}

    try:
        return await get_current_user(credentials)
    except UnauthorizedException:
        logger.debug("Optional auth failed, using anonymous user")
        return {"user_id": None, "username": "anonymous"}
