"""错误码定义

功能：
- 统一错误码定义
- 错误分类（业务/系统/第三方）
- 错误详情和解决方案
- 国际化支持

使用示例：
    raise APIError(
        code=ErrorCode.SESSION_NOT_FOUND,
        message="会话不存在",
        details={"session_id": "xxx"}
    )
"""
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel


# ============================================
# 错误码定义
# ============================================

class ErrorCode(str, Enum):
    """错误码枚举
    
    格式：模块_错误类型
    - 1000-1999: 通用错误
    - 2000-2999: 会话相关
    - 3000-3999: 聊天相关
    - 4000-4999: RAG 相关
    - 5000-5999: LLM 相关
    - 6000-6999: 数据库相关
    - 7000-7999: 限流/熔断
    - 8000-8999: 第三方服务
    """
    
    # ===== 通用错误 (1000-1999) =====
    SUCCESS = "1000"                    # 成功
    UNKNOWN_ERROR = "1001"              # 未知错误
    INVALID_REQUEST = "1002"            # 请求参数无效
    MISSING_PARAMETER = "1003"          # 缺少必要参数
    INVALID_PARAMETER = "1004"          # 参数格式错误
    UNAUTHORIZED = "1005"               # 未授权
    FORBIDDEN = "1006"                  # 禁止访问
    NOT_FOUND = "1007"                  # 资源不存在
    INTERNAL_ERROR = "1008"             # 内部错误
    SERVICE_UNAVAILABLE = "1009"        # 服务不可用
    
    # ===== 会话相关 (2000-2999) =====
    SESSION_NOT_FOUND = "2001"          # 会话不存在
    SESSION_EXPIRED = "2002"            # 会话已过期
    SESSION_LIMIT_EXCEEDED = "2003"     # 会话数量超限
    SESSION_CREATE_FAILED = "2004"      # 创建会话失败
    SESSION_DELETE_FAILED = "2005"      # 删除会话失败
    
    # ===== 聊天相关 (3000-3999) =====
    MESSAGE_TOO_LONG = "3001"           # 消息过长
    MESSAGE_EMPTY = "3002"              # 消息为空
    MESSAGE_SAVE_FAILED = "3003"        # 消息保存失败
    HISTORY_NOT_FOUND = "3004"          # 历史消息不存在
    CONTEXT_OVERFLOW = "3005"           # 上下文溢出
    
    # ===== RAG 相关 (4000-4999) =====
    RAG_SEARCH_FAILED = "4001"          # RAG 检索失败
    RAG_NO_RESULT = "4002"              # 无检索结果
    RAG_INDEX_NOT_FOUND = "4003"        # 索引不存在
    RAG_EMBEDDING_FAILED = "4004"       # 向量化失败
    RAG_DOCUMENT_NOT_FOUND = "4005"     # 文档不存在
    RAG_UPLOAD_FAILED = "4006"          # 文档上传失败
    
    # ===== LLM 相关 (5000-5999) =====
    LLM_CALL_FAILED = "5001"            # LLM 调用失败
    LLM_TIMEOUT = "5002"                # LLM 超时
    LLM_RESPONSE_EMPTY = "5003"         # LLM 响应为空
    LLM_API_KEY_INVALID = "5004"        # API Key 无效
    LLM_RATE_LIMITED = "5005"           # LLM API 限流
    LLM_MODEL_NOT_FOUND = "5006"        # 模型不存在
    
    # ===== 数据库相关 (6000-6999) =====
    DB_CONNECTION_FAILED = "6001"       # 数据库连接失败
    DB_QUERY_FAILED = "6002"            # 查询失败
    DB_INSERT_FAILED = "6003"           # 插入失败
    DB_UPDATE_FAILED = "6004"           # 更新失败
    DB_DELETE_FAILED = "6005"           # 删除失败
    DB_TIMEOUT = "6006"                 # 数据库超时
    
    # ===== 限流/熔断 (7000-7999) =====
    RATE_LIMIT_EXCEEDED = "7001"        # 请求限流
    CIRCUIT_BREAKER_OPEN = "7002"       # 熔断器打开
    TOO_MANY_REQUESTS = "7003"          # 请求过多
    
    # ===== 第三方服务 (8000-8999) =====
    REDIS_ERROR = "8001"                # Redis 错误
    QDRANT_ERROR = "8002"               # Qdrant 错误
    EXTERNAL_API_ERROR = "8003"         # 外部 API 错误
    NETWORK_ERROR = "8004"              # 网络错误


# ============================================
# 错误详情定义
# ============================================

ERROR_DETAILS: Dict[str, Dict[str, Any]] = {
    # 通用错误
    ErrorCode.SUCCESS: {
        "level": "info",
        "solution": "无需处理"
    },
    ErrorCode.UNKNOWN_ERROR: {
        "level": "error",
        "solution": "请联系技术支持"
    },
    ErrorCode.INVALID_REQUEST: {
        "level": "warning",
        "solution": "请检查请求参数格式"
    },
    
    # 会话错误
    ErrorCode.SESSION_NOT_FOUND: {
        "level": "warning",
        "solution": "请创建新会话或检查会话ID"
    },
    ErrorCode.SESSION_EXPIRED: {
        "level": "warning",
        "solution": "请创建新会话"
    },
    
    # RAG 错误
    ErrorCode.RAG_SEARCH_FAILED: {
        "level": "error",
        "solution": "请检查向量数据库连接"
    },
    ErrorCode.RAG_NO_RESULT: {
        "level": "info",
        "solution": "请尝试其他关键词或上传相关文档"
    },
    
    # LLM 错误
    ErrorCode.LLM_CALL_FAILED: {
        "level": "error",
        "solution": "请稍后重试或联系技术支持"
    },
    ErrorCode.LLM_TIMEOUT: {
        "level": "warning",
        "solution": "请稍后重试"
    },
    ErrorCode.LLM_API_KEY_INVALID: {
        "level": "error",
        "solution": "请检查 API Key 配置"
    },
    
    # 限流/熔断
    ErrorCode.RATE_LIMIT_EXCEEDED: {
        "level": "warning",
        "solution": "请降低请求频率，稍后重试"
    },
    ErrorCode.CIRCUIT_BREAKER_OPEN: {
        "level": "warning",
        "solution": "服务正在恢复，请稍后重试"
    },
}


# ============================================
# API 错误类
# ============================================

class APIError(Exception):
    """API 统一错误类
    
    功能：
    - 错误码
    - 错误消息
    - 错误详情
    - 解决方案
    - 堆栈跟踪
    """
    
    def __init__(
        self,
        code: ErrorCode,
        message: str = None,
        details: Dict[str, Any] = None,
        trace_id: str = None
    ):
        """
        Args:
            code: 错误码
            message: 错误消息（可选，默认使用错误码描述）
            details: 错误详情
            trace_id: 请求追踪ID
        """
        self.code = code
        self.message = message or self._get_default_message(code)
        self.details = details or {}
        self.trace_id = trace_id
        
        # 获取错误详情
        error_info = ERROR_DETAILS.get(code, {})
        self.level = error_info.get("level", "error")
        self.solution = error_info.get("solution", "请联系技术支持")
        
        super().__init__(self.message)
    
    def _get_default_message(self, code: ErrorCode) -> str:
        """获取默认错误消息"""
        messages = {
            ErrorCode.SUCCESS: "操作成功",
            ErrorCode.UNKNOWN_ERROR: "未知错误",
            ErrorCode.INVALID_REQUEST: "请求参数无效",
            ErrorCode.MISSING_PARAMETER: "缺少必要参数",
            ErrorCode.INVALID_PARAMETER: "参数格式错误",
            ErrorCode.UNAUTHORIZED: "未授权访问",
            ErrorCode.FORBIDDEN: "禁止访问",
            ErrorCode.NOT_FOUND: "资源不存在",
            ErrorCode.INTERNAL_ERROR: "内部错误",
            ErrorCode.SERVICE_UNAVAILABLE: "服务不可用",
            
            ErrorCode.SESSION_NOT_FOUND: "会话不存在",
            ErrorCode.SESSION_EXPIRED: "会话已过期",
            ErrorCode.SESSION_LIMIT_EXCEEDED: "会话数量超限",
            
            ErrorCode.MESSAGE_TOO_LONG: "消息过长",
            ErrorCode.MESSAGE_EMPTY: "消息为空",
            
            ErrorCode.RAG_SEARCH_FAILED: "知识库检索失败",
            ErrorCode.RAG_NO_RESULT: "知识库无匹配结果",
            ErrorCode.RAG_EMBEDDING_FAILED: "向量化失败",
            
            ErrorCode.LLM_CALL_FAILED: "AI 服务调用失败",
            ErrorCode.LLM_TIMEOUT: "AI 服务响应超时",
            ErrorCode.LLM_API_KEY_INVALID: "API Key 无效",
            
            ErrorCode.DB_CONNECTION_FAILED: "数据库连接失败",
            ErrorCode.DB_QUERY_FAILED: "数据库查询失败",
            
            ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁",
            ErrorCode.CIRCUIT_BREAKER_OPEN: "服务暂时不可用",
            
            ErrorCode.REDIS_ERROR: "缓存服务错误",
            ErrorCode.QDRANT_ERROR: "向量数据库错误",
        }
        return messages.get(code, "未知错误")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 API 响应，不暴露内部信息）"""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "trace_id": self.trace_id
        }

    def to_internal_dict(self) -> Dict[str, Any]:
        """转换为内部字典（包含 level 和 solution，仅用于日志）"""
        return {
            "code": self.code,
            "message": self.message,
            "level": self.level,
            "solution": self.solution,
            "details": self.details,
            "trace_id": self.trace_id
        }

    @property
    def status_code(self) -> int:
        """根据错误码返回 HTTP 状态码"""
        code_int = int(self.code)
        if code_int == 1005:
            return 401
        elif code_int == 1006:
            return 403
        elif code_int == 1007:
            return 404
        elif 7000 <= code_int < 8000:
            return 429
        elif 8000 <= code_int < 9000:
            return 502
        else:
            return 400
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# ============================================
# 错误处理辅助函数
# ============================================

def get_error_info(code: ErrorCode) -> Dict[str, Any]:
    """获取错误信息"""
    return ERROR_DETAILS.get(code, {
        "level": "error",
        "solution": "请联系技术支持"
    })


def create_error_response(
    code: ErrorCode,
    message: str = None,
    details: Dict[str, Any] = None
) -> Dict[str, Any]:
    """创建错误响应"""
    error = APIError(code, message, details)
    return {
        "code": int(code),
        "message": error.message,
        "data": None,
        "error": error.to_dict()
    }


# ============================================
# 常用错误快捷创建
# ============================================

def not_found_error(resource: str, resource_id: str = None) -> APIError:
    """资源不存在错误"""
    return APIError(
        code=ErrorCode.NOT_FOUND,
        message=f"{resource}不存在",
        details={"resource": resource, "resource_id": resource_id}
    )


def invalid_parameter_error(param_name: str, reason: str = None) -> APIError:
    """参数无效错误"""
    return APIError(
        code=ErrorCode.INVALID_PARAMETER,
        message=f"参数 {param_name} 无效",
        details={"parameter": param_name, "reason": reason}
    )


def internal_error_error(operation: str, reason: str = None) -> APIError:
    """内部错误"""
    return APIError(
        code=ErrorCode.INTERNAL_ERROR,
        message=f"{operation}失败",
        details={"operation": operation, "reason": reason}
    )