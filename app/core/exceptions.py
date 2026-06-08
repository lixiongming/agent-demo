"""自定义异常"""
from fastapi import HTTPException, status


class AgentException(Exception):
    """Agent基础异常"""
    def __init__(self, message: str, code: str = "AGENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class LLMException(AgentException):
    """LLM调用异常"""
    def __init__(self, message: str):
        super().__init__(message, "LLM_ERROR")


class ToolException(AgentException):
    """工具执行异常"""
    def __init__(self, message: str, tool_name: str = ""):
        self.tool_name = tool_name
        super().__init__(message, "TOOL_ERROR")


class MemoryException(AgentException):
    """记忆管理异常"""
    def __init__(self, message: str):
        super().__init__(message, "MEMORY_ERROR")


class DatabaseException(AgentException):
    """数据库异常"""
    def __init__(self, message: str):
        super().__init__(message, "DB_ERROR")


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