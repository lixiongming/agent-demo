"""日志配置 - 生产级别

功能：
- 结构化日志（JSON）
- 请求追踪（Request ID）
- 日志分类（业务/错误/审计/性能）
- 敏感信息过滤
- 性能监控
"""
import logging
import sys
import json
import time
import uuid
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar

from app.config import get_settings

settings = get_settings()

# 请求上下文
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


# ============================================
# 敏感信息过滤
# ============================================

SENSITIVE_KEYS = [
    "password", "passwd", "pwd",
    "api_key", "apikey", "key", "token",
    "secret", "credential", "auth",
    "credit_card", "card_number"
]


def filter_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    """过滤敏感信息"""
    filtered = {}
    for key, value in data.items():
        if any(s in key.lower() for s in SENSITIVE_KEYS):
            filtered[key] = "***FILTERED***"
        elif isinstance(value, dict):
            filtered[key] = filter_sensitive(value)
        else:
            filtered[key] = value
    return filtered


# ============================================
# 结构化日志格式
# ============================================

class StructuredFormatter(logging.Formatter):
    """结构化日志格式器（JSON）"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """文本格式器（带请求ID）"""
    
    def format(self, record: logging.LogRecord) -> str:
        request_id = request_id_var.get()
        user_id = user_id_var.get()
        
        prefix = f"[{request_id}] " if request_id else ""
        user_prefix = f"[user:{user_id}] " if user_id else ""
        
        base_msg = super().format(record)
        return f"{prefix}{user_prefix}{base_msg}"


# ============================================
# 日志分类器
# ============================================

class BusinessLogger:
    """业务日志"""
    
    def __init__(self, name: str = "business"):
        self.logger = logging.getLogger(name)
    
    def log_operation(self, operation: str, details: Dict[str, Any] = None, level: str = "INFO"):
        """记录业务操作"""
        extra_data = {
            "operation": operation,
            "details": filter_sensitive(details or {}),
            "type": "business"
        }
        self.logger.info(operation, extra={"extra_data": extra_data})


class ErrorLogger:
    """错误日志"""
    
    def __init__(self, name: str = "error"):
        self.logger = logging.getLogger(name)
    
    def log_exception(self, exception: Exception, context: Dict[str, Any] = None):
        """记录异常"""
        extra_data = {
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "context": filter_sensitive(context or {}),
            "type": "error"
        }
        self.logger.error(
            f"Exception: {type(exception).__name__}: {str(exception)}",
            exc_info=True,
            extra={"extra_data": extra_data}
        )


class AuditLogger:
    """审计日志"""
    
    def __init__(self, name: str = "audit"):
        self.logger = logging.getLogger(name)
    
    def log_login(self, user_id: str, success: bool, ip_address: str = ""):
        """记录登录"""
        self.logger.info(
            f"Login: user={user_id}, success={success}",
            extra={
                "extra_data": {
                    "type": "audit",
                    "action": "login",
                    "user_id": user_id,
                    "success": success,
                    "ip_address": ip_address
                }
            }
        )


class PerformanceLogger:
    """性能日志"""
    
    def __init__(self, name: str = "performance", slow_threshold: float = 1.0):
        self.logger = logging.getLogger(name)
        self.slow_threshold = slow_threshold
    
    def log_request_time(self, endpoint: str, duration: float, method: str = ""):
        """记录请求时间"""
        level = "WARNING" if duration > self.slow_threshold else "INFO"
        self.logger.log(
            getattr(logging, level),
            f"Request: {method} {endpoint} took {duration:.3f}s",
            extra={
                "extra_data": {
                    "type": "performance",
                    "endpoint": endpoint,
                    "method": method,
                    "duration": duration,
                    "is_slow": duration > self.slow_threshold
                }
            }
        )


# ============================================
# 日志配置
# ============================================

def setup_logging():
    """配置日志 - 生产级别"""
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 文本格式（控制台）
    text_formatter = TextFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # JSON格式（文件）
    json_formatter = StructuredFormatter()
    
    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(text_formatter)
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    # 主日志文件（JSON格式）
    main_file = RotatingFileHandler(
        log_dir / "app.json",
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    main_file.setFormatter(json_formatter)
    
    # 错误日志文件（单独）
    error_file = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_file.setFormatter(json_formatter)
    error_file.setLevel(logging.ERROR)
    
    # 审计日志文件（单独）
    audit_file = RotatingFileHandler(
        log_dir / "audit.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8'
    )
    audit_file.setFormatter(json_formatter)
    
    # 性能日志文件（单独）
    perf_file = RotatingFileHandler(
        log_dir / "performance.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    perf_file.setFormatter(json_formatter)
    
    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(main_file)
    root_logger.addHandler(error_file)
    
    # 配置审计日志
    audit_logger = logging.getLogger("audit")
    audit_logger.addHandler(audit_file)
    audit_logger.propagate = False
    
    # 配置性能日志
    perf_logger = logging.getLogger("performance")
    perf_logger.addHandler(perf_file)
    perf_logger.propagate = False
    
    # 降低第三方库日志级别
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取日志实例"""
    return logging.getLogger(name)


# ============================================
# 请求上下文管理
# ============================================

def set_request_context(request_id: str = None, user_id: str = None):
    """设置请求上下文"""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    
    request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)


def clear_request_context():
    """清除请求上下文"""
    request_id_var.set("")
    user_id_var.set("")


# ============================================
# 便捷获取函数
# ============================================

def get_business_logger() -> BusinessLogger:
    """获取业务日志"""
    return BusinessLogger()


def get_error_logger() -> ErrorLogger:
    """获取错误日志"""
    return ErrorLogger()


def get_audit_logger() -> AuditLogger:
    """获取审计日志"""
    return AuditLogger()


def get_performance_logger(threshold: float = 1.0) -> PerformanceLogger:
    """获取性能日志"""
    return PerformanceLogger(slow_threshold=threshold)