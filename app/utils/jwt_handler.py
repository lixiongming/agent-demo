"""JWT 认证服务 - 生产级实现

功能：
- Access Token / Refresh Token 双令牌机制
- Token 黑名单（基于 Redis）
- 密码哈希（bcrypt）
- 统一异常体系（不耦合 HTTPException）
"""
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from passlib.context import CryptContext

from app.config import get_settings
from app.core.logger import get_logger
from app.core.exceptions import UnauthorizedException, InvalidRequestException

logger = get_logger(__name__)
settings = get_settings()

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================
# 密码工具
# ============================================

def hash_password(password: str) -> str:
    """密码哈希"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """密码验证（常量时间比较，防时序攻击）"""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================
# JWT 工具
# ============================================

def _get_secret_key() -> str:
    """获取 JWT 密钥"""
    secret = settings.JWT_SECRET_KEY
    if not secret:
        raise UnauthorizedException("JWT_SECRET_KEY not configured")
    return secret


def create_access_token(user_id: int, username: str, extra: Optional[Dict] = None) -> str:
    """创建 Access Token

    Args:
        user_id: 用户ID
        username: 用户名
        extra: 额外声明

    Returns:
        JWT 字符串
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _get_secret_key(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int, username: str) -> str:
    """创建 Refresh Token

    Args:
        user_id: 用户ID
        username: 用户名

    Returns:
        JWT 字符串
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=settings.JWT_ALGORITHM)


def create_token_pair(user_id: int, username: str) -> Dict[str, str]:
    """创建 Token 对（Access + Refresh）

    Returns:
        {"access_token": ..., "refresh_token": ..., "token_type": "Bearer"}
    """
    access_token = create_access_token(user_id, username)
    refresh_token = create_refresh_token(user_id, username)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    }


def decode_token(token: str, token_type: str = "access") -> Dict:
    """解码并验证 Token

    Args:
        token: JWT 字符串
        token_type: 期望的 token 类型（access/refresh）

    Returns:
        Token payload

    Raises:
        UnauthorizedException: Token 无效或过期
    """
    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[settings.JWT_ALGORITHM]
        )

        # 验证 token 类型
        if payload.get("type") != token_type:
            raise UnauthorizedException(f"Invalid token type, expected {token_type}")

        # 验证 sub 存在
        if "sub" not in payload:
            raise UnauthorizedException("Token missing subject")

        return payload

    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Token 已过期，请重新登录")
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException(f"Token 无效: {str(e)}")


# ============================================
# Token 黑名单（基于 Redis）
# ============================================

async def revoke_token(token: str, ttl_seconds: Optional[int] = None) -> bool:
    """将 Token 加入黑名单

    Args:
        token: JWT 字符串
        ttl_seconds: 黑名单保留时间（默认取 token 剩余有效期）
    """
    try:
        from app.db.cache import get_redis
        redis_client = await get_redis()

        # 解码获取过期时间（不验证过期，允许已过期 token 加入黑名单）
        try:
            payload = jwt.decode(
                token,
                _get_secret_key(),
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False}
            )
            exp = payload.get("exp", 0)
            now = datetime.now(timezone.utc).timestamp()
            remaining = max(int(exp - now), 0)
        except jwt.InvalidTokenError:
            remaining = 3600  # 无法解析时默认1小时

        ttl = ttl_seconds or remaining
        if ttl > 0:
            await redis_client.set(f"token_blacklist:{token}", "1", ex=ttl)
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to revoke token: {e}")
        return False


async def is_token_revoked(token: str) -> bool:
    """检查 Token 是否已被撤销"""
    try:
        from app.db.cache import get_redis
        redis_client = await get_redis()
        return await redis_client.exists(f"token_blacklist:{token}")
    except Exception:
        return False
