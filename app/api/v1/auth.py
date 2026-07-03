"""用户认证接口 - 注册/登录/刷新/登出

大厂生产模式：
- bcrypt 密码哈希
- Access + Refresh 双令牌
- Redis Token 黑名单
- 登录失败计数 + 账号锁定（防暴力破解）
- IP 维度限流（防批量注册/撞库）
- 统一错误信息（不泄露用户状态）
- 审计日志
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
import re

from app.db import get_async_session, UserRepository
from app.utils.jwt_handler import (
    hash_password, verify_password,
    create_token_pair, decode_token,
    revoke_token, is_token_revoked,
)
from app.api.deps import get_current_user
from app.core.exceptions import InvalidRequestException, UnauthorizedException
from app.core.logger import get_logger
from app.core.audit import AuditLogger

logger = get_logger(__name__)
audit = AuditLogger()
router = APIRouter()

# 登录安全配置 - 渐进式锁定（大厂标准）
# 失败次数 → 锁定时长（秒）
LOGIN_LOCKOUT_STEPS = [
    (3, 5 * 60),       # 3次失败 → 锁定5分钟
    (5, 15 * 60),      # 5次失败 → 锁定15分钟
    (10, 60 * 60),     # 10次失败 → 锁定60分钟
]
LOGIN_MAX_ATTEMPTS = 10     # 超过此次数后不再允许尝试
LOGIN_LOCKOUT_MAX_TTL = 7200  # 锁定计数器最大TTL（2小时后自动重置）

# 注册限流配置
REGISTER_IP_LIMIT = 5           # 同一IP每小时最大注册数
REGISTER_IP_WINDOW = 3600       # 窗口：1小时（比每天更合理）


# ============================================
# 请求/响应模型
# ============================================

class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    email: str | None = Field(None, max_length=100, description="邮箱")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("密码必须包含字母")
        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含数字")
        return v


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class RefreshRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str = Field(..., description="Refresh Token")


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    user_id: int
    username: str
    email: str | None
    is_admin: bool


# ============================================
# 安全辅助函数
# ============================================

async def _check_register_ip_limit(ip: str):
    """检查同一 IP 注册频率（防批量注册）"""
    try:
        from app.db.cache import get_redis
        redis = await get_redis()
        key = f"register_ip:{ip}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, REGISTER_IP_WINDOW)
        if count > REGISTER_IP_LIMIT:
            raise InvalidRequestException("注册过于频繁，请稍后再试")
    except InvalidRequestException:
        raise
    except Exception:
        pass  # Redis 不可用时放行


async def _check_ip_login_limit(ip: str):
    """检查同一 IP 登录频率（防分布式撞库）"""
    try:
        from app.db.cache import get_redis
        redis = await get_redis()
        key = f"login_ip:{ip}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 300)  # 5分钟窗口
        if count > 20:  # 同一IP 5分钟内最多20次登录尝试
            raise UnauthorizedException("登录尝试过于频繁，请稍后再试")
    except UnauthorizedException:
        raise
    except Exception:
        pass


def _get_lockout_duration(attempts: int) -> int | None:
    """根据失败次数获取锁定时长（渐进式）

    Returns:
        锁定秒数，None 表示不锁定
    """
    lockout_seconds = None
    for threshold, duration in LOGIN_LOCKOUT_STEPS:
        if attempts >= threshold:
            lockout_seconds = duration
    return lockout_seconds


async def _get_login_attempts(username: str) -> int:
    """获取登录失败次数"""
    try:
        from app.db.cache import get_redis
        redis = await get_redis()
        count = await redis.get(f"login_fail:{username}")
        return int(count) if count else 0
    except Exception:
        return 0


async def _record_login_failure(username: str):
    """记录登录失败（渐进式TTL）"""
    try:
        from app.db.cache import get_redis
        redis = await get_redis()
        key = f"login_fail:{username}"
        count = await redis.incr(key)
        if count == 1:
            # 首次失败，设置最大TTL
            await redis.expire(key, LOGIN_LOCKOUT_MAX_TTL)
        else:
            # 根据当前失败次数调整TTL（渐进式延长）
            lockout = _get_lockout_duration(count)
            if lockout:
                current_ttl = await redis.ttl(key)
                if current_ttl < lockout:
                    await redis.expire(key, lockout)
    except Exception:
        pass


async def _clear_login_failure(username: str):
    """清除登录失败计数"""
    try:
        from app.db.cache import get_redis
        redis = await get_redis()
        await redis.delete(f"login_fail:{username}")
    except Exception:
        pass


# ============================================
# 接口
# ============================================

@router.post(
    "/register",
    response_model=TokenResponse,
    summary="用户注册",
    description="""
注册新用户并返回 Access Token + Refresh Token。

**认证要求：** 无需认证

**请求参数：**
- `username`: 3-50字符，仅支持字母、数字、下划线、连字符
- `password`: 8-128字符，必须包含字母和数字
- `email`: 可选，邮箱地址

**安全措施：**
- 同一IP每小时最多注册5次
- 密码使用 bcrypt 哈希存储

**请求示例：**
```json
{
    "username": "zhangsan",
    "password": "Test1234",
    "email": "zhangsan@example.com"
}
```

**响应示例：**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer"
}
```

**错误码：**
- `INVALID_REQUEST`: 用户名已存在 / 邮箱已被注册 / 注册过于频繁
- `VALIDATION_ERROR`: 参数格式不合法
"""
)
async def register(
    req: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """注册新用户，返回 Token 对"""
    # IP 维度限流
    client_ip = request.client.host if request.client else "unknown"
    await _check_register_ip_limit(client_ip)

    user_repo = UserRepository(db)

    # 检查用户名是否已存在
    existing = await user_repo.get_by_username(req.username)
    if existing:
        raise InvalidRequestException("用户名已存在")

    # 检查邮箱是否已存在
    if req.email:
        existing = await user_repo.get_by_email(req.email)
        if existing:
            raise InvalidRequestException("邮箱已被注册")

    # 创建用户
    password_hash = hash_password(req.password)
    user = await user_repo.create(
        username=req.username,
        email=req.email,
        password_hash=password_hash,
    )
    await db.commit()

    logger.info(f"User registered: {req.username}, ip={client_ip}")
    audit.log_operation(
        operation="user_register",
        user_id=user.id,
        details={"username": req.username, "ip": client_ip},
    )

    tokens = create_token_pair(user.id, user.username)
    return TokenResponse(**tokens)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
    description="""
用户名密码登录，返回 Access Token + Refresh Token。

**认证要求：** 无需认证

**渐进式锁定策略：**
| 失败次数 | 锁定时长 |
|---------|---------|
| 3次 | 5分钟 |
| 5次 | 15分钟 |
| 10次 | 60分钟 |

**其他安全措施：**
- 同一IP 5分钟内最多20次登录尝试（防分布式撞库）
- 统一错误信息，不泄露用户是否存在或是否停用
- 2小时后自动重置失败计数

**请求示例：**
```json
{
    "username": "zhangsan",
    "password": "Test1234"
}
```

**错误码：**
- `UNAUTHORIZED`: 用户名或密码错误 / 登录失败次数过多
"""
)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """用户名密码登录，返回 Token 对

    安全措施：
    - 渐进式锁定：3次→5分钟，5次→15分钟，10次→60分钟
    - IP维度限流：同一IP 5分钟内最多20次尝试（防分布式撞库）
    - 统一错误信息（不泄露用户是否存在、是否停用）
    - 审计日志记录
    """
    client_ip = request.client.host if request.client else "unknown"

    # IP 维度限流（防分布式撞库）
    await _check_ip_login_limit(client_ip)

    # 检查账号是否被锁定（渐进式）
    attempts = await _get_login_attempts(req.username)
    lockout = _get_lockout_duration(attempts)
    if lockout and attempts >= LOGIN_MAX_ATTEMPTS:
        audit.log_security(
            event="login_locked",
            severity="high",
            details={"username": req.username, "ip": client_ip, "attempts": attempts},
        )
        raise UnauthorizedException("登录失败次数过多，请稍后重试")
    if lockout:
        minutes = lockout // 60
        audit.log_security(
            event="login_locked",
            severity="medium",
            details={"username": req.username, "ip": client_ip, "attempts": attempts, "lockout_minutes": minutes},
        )
        raise UnauthorizedException(f"登录失败次数过多，请{minutes}分钟后重试")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(req.username)

    # 统一验证：用户不存在、停用、密码错误 → 同一错误信息
    authenticated = False
    if user and user.is_active and user.password_hash:
        authenticated = verify_password(req.password, user.password_hash)

    if not authenticated:
        # 记录失败（渐进式TTL）
        await _record_login_failure(req.username)
        new_attempts = attempts + 1

        audit.log_security(
            event="login_failed",
            severity="low",
            details={"username": req.username, "ip": client_ip, "attempts": new_attempts},
        )

        # 检查是否触发锁定
        lockout = _get_lockout_duration(new_attempts)
        if lockout:
            minutes = lockout // 60
            raise UnauthorizedException(f"登录失败次数过多，请{minutes}分钟后重试")
        if new_attempts >= 3:
            # 距离下一级锁定还剩几次
            next_threshold = 5
            for threshold, _ in LOGIN_LOCKOUT_STEPS:
                if threshold > new_attempts:
                    next_threshold = threshold
                    break
            remaining = next_threshold - new_attempts
            raise UnauthorizedException(f"用户名或密码错误，还剩{remaining}次尝试机会")
        raise UnauthorizedException("用户名或密码错误")

    # 登录成功：清除失败计数
    await _clear_login_failure(req.username)

    # 更新最后登录时间
    await user_repo.update_last_login(user.id)
    await db.commit()

    logger.info(f"User logged in: {req.username}")
    audit.log_operation(
        operation="user_login",
        user_id=user.id,
        details={"username": req.username},
    )

    tokens = create_token_pair(user.id, user.username)
    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="刷新令牌",
    description="""
使用 Refresh Token 获取新的 Token 对。旧 Refresh Token 一次性使用，刷新后自动撤销。

**认证要求：** 无需认证（需提供有效的 Refresh Token）

**Token 有效期：**
- Access Token: 30分钟
- Refresh Token: 7天

**安全措施：**
- 旧 Refresh Token 用后即焚（防重放攻击）
- 验证用户仍然活跃（已停用用户无法刷新）

**请求示例：**
```json
{
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**错误码：**
- `UNAUTHORIZED`: Refresh Token 已被撤销 / 已过期 / 用户已停用
"""
)
async def refresh_token(
    req: RefreshRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """使用 Refresh Token 获取新的 Token 对

    安全措施：
    - 旧 Refresh Token 一次性使用（用后即焚）
    - 验证用户仍然活跃
    """
    # 解码 Refresh Token
    payload = decode_token(req.refresh_token, token_type="refresh")

    # 检查是否已被撤销
    if await is_token_revoked(req.refresh_token):
        raise UnauthorizedException("Refresh Token 已被撤销，请重新登录")

    # 验证用户仍然活跃（统一错误信息，不泄露状态）
    user_id = int(payload["sub"])
    username = payload["username"]
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedException("Token 无效，请重新登录")

    # 撤销旧 Refresh Token（防止重放）
    await revoke_token(req.refresh_token)

    # 生成新 Token 对
    tokens = create_token_pair(user.id, user.username)

    logger.info(f"Token refreshed for user: {username}")
    return TokenResponse(**tokens)


@router.post(
    "/logout",
    summary="用户登出",
    description="""
登出当前用户，将 Access Token 加入黑名单使其立即失效。

**认证要求：** Bearer Token

**说明：**
- 服务端将当前 Access Token 加入 Redis 黑名单
- Token 在过期前无法再次使用
- 前端应在调用此接口后删除本地存储的 Token

**请求头：**
```
Authorization: Bearer <access_token>
```

**错误码：**
- `UNAUTHORIZED`: Token 无效或已过期
"""
)
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """登出当前用户

    从请求头提取 Access Token 并加入黑名单，
    确保 Token 在过期前无法再次使用。
    """
    # 从请求头提取原始 Token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[7:]
        await revoke_token(raw_token)

    logger.info(f"User logged out: {current_user.get('username')}")
    return {"message": "登出成功"}


@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="获取当前用户信息",
    description="""
获取当前登录用户的基本信息。

**认证要求：** Bearer Token

**请求头：**
```
Authorization: Bearer <access_token>
```

**响应示例：**
```json
{
    "user_id": 1,
    "username": "zhangsan",
    "email": "zhangsan@example.com",
    "is_admin": false
}
```

**错误码：**
- `UNAUTHORIZED`: 未登录 / Token 无效
"""
)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """获取当前登录用户信息"""
    user_id = current_user.get("user_id")
    if not user_id:
        raise UnauthorizedException("未登录")

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedException("用户不存在")

    return UserInfoResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
    )
