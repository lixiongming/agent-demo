"""统一异常体系

设计原则：
1. 所有业务异常继承 AgentException（领域异常）
2. 不在异常层耦合 HTTP 框架
3. API 层负责将领域异常转换为 HTTP 响应
4. 全局异常处理器统一处理
"""
from typing import Optional, Dict, Any


class AgentException(Exception):
    """Agent 基础异常（所有业务异常的基类）"""
    
    def __init__(
        self,
        message: str,
        code: str = "AGENT_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于日志和响应）"""
        result = {
            "code": self.code,
            "message": self.message
        }
        if self.details:
            result["details"] = self.details
        return result


class LLMException(AgentException):
    """LLM 调用异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "LLM_ERROR", 502, details)


class ToolException(AgentException):
    """工具执行异常"""
    def __init__(self, message: str, tool_name: str = "", details: Optional[Dict[str, Any]] = None):
        self.tool_name = tool_name
        if details is None:
            details = {}
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(message, "TOOL_ERROR", 500, details)


class MemoryException(AgentException):
    """记忆管理异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MEMORY_ERROR", 500, details)


class DatabaseException(AgentException):
    """数据库异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DB_ERROR", 500, details)


class SessionNotFoundException(AgentException):
    """会话不存在（不再继承 HTTPException）"""
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session {session_id} not found",
            code="SESSION_NOT_FOUND",
            status_code=404,
            details={"session_id": session_id}
        )


class InvalidRequestException(AgentException):
    """无效请求（不再继承 HTTPException）"""
    def __init__(self, detail: str):
        super().__init__(
            message=detail,
            code="INVALID_REQUEST",
            status_code=400
        )


class UnauthorizedException(AgentException):
    """未授权"""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, "UNAUTHORIZED", 401)


class ForbiddenException(AgentException):
    """禁止访问"""
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, "FORBIDDEN", 403)


class RateLimitException(AgentException):
    """限流异常"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMITED", 429)
