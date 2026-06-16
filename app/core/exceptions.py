"""自定义异常"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class AgentException(Exception):
    """Agent基础异常"""
    def __init__(self, message: str, code: str = "AGENT_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
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
    """LLM调用异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "LLM_ERROR", details)


class ToolException(AgentException):
    """工具执行异常"""
    def __init__(self, message: str, tool_name: str = "", details: Optional[Dict[str, Any]] = None):
        self.tool_name = tool_name
        # 自动添加 tool_name 到 details
        if details is None:
            details = {}
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(message, "TOOL_ERROR", details)


class MemoryException(AgentException):
    """记忆管理异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "MEMORY_ERROR", details)


class DatabaseException(AgentException):
    """数据库异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DB_ERROR", details)


class SessionNotFoundException(HTTPException):
    """会话不存在"""
    def __init__(self, session_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )


class InvalidRequestException(HTTPException):
    """无效请求"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )