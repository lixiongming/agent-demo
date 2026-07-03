"""日志配置

功能：
- 结构化日志（JSON）
- 请求追踪（Request ID）
- 日志分类（业务/错误/审计/性能）
- 敏感信息过滤
- 性能监控
- 按日期滚动 + 自动压缩 + 自动清理

- 使用 TimedRotatingFileHandler 按日期滚动
- 历史日志自动压缩（节省存储空间）
- 自动清理过期日志（保留30天）
"""
import logging
import sys
import json
import time
import uuid
import gzip
import shutil
import os
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from contextvars import ContextVar

from app.config import get_settings

settings = get_settings()

# 请求上下文
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


# ============================================
# 按日期滚动的日志处理器（支持压缩）
# ============================================

class CompressedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """按日期滚动的日志处理器（支持压缩）
    
    功能：
    - 每天午夜滚动
    - 自动压缩历史日志（gzip）
    - 自动清理过期日志
    """
    
    def __init__(
        self,
        filename,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8',
        compress_after_days=1,
        **kwargs
    ):
        """
        Args:
            filename: 日志文件名
            when: 滚动时机（midnight=每天午夜）
            interval: 滚动间隔
            backupCount: 保留天数
            encoding: 编码
            compress_after_days: 滚动后多少天开始压缩
        """
        super().__init__(
            filename,
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding=encoding,
            **kwargs
        )
        self.compress_after_days = compress_after_days
        
    def doRollover(self):
        """执行日志滚动"""
        # 先执行父类的滚动
        super().doRollover()
        
        # 压缩历史日志
        self._compress_old_logs()
        
        # 清理过期日志
        self._cleanup_old_logs()
    
    def _compress_old_logs(self):
        """压缩历史日志文件"""
        log_dir = Path(self.baseFilename).parent
        base_name = Path(self.baseFilename).name
        
        # 找到所有未压缩的历史日志
        for log_file in log_dir.glob(f"{base_name}.*"):
            # 跳过已压缩的文件
            if log_file.suffix == '.gz':
                continue
            
            # 跳过当前日志文件
            if log_file.name == base_name:
                continue
            
            # 检查文件是否超过压缩阈值
            file_date_str = log_file.suffix.lstrip('.')
            try:
                file_date = datetime.strptime(file_date_str, '%Y-%m-%d')
                days_old = (datetime.now() - file_date).days
                
                # 超过指定天数则压缩
                if days_old >= self.compress_after_days:
                    compressed_file = log_file.with_suffix(log_file.suffix + '.gz')
                    
                    # 压缩文件
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(compressed_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # 删除原文件
                    log_file.unlink()
                    
            except ValueError:
                # 文件名格式不匹配，跳过
                continue
    
    def _cleanup_old_logs(self):
        """清理过期日志"""
        log_dir = Path(self.baseFilename).parent
        base_name = Path(self.baseFilename).name
        
        cutoff_date = datetime.now() - timedelta(days=self.backupCount)
        
        # 清理所有过期日志（包括压缩的）
        for log_file in log_dir.glob(f"{base_name}.*"):
            # 获取文件日期
            suffix = log_file.suffix.lstrip('.')
            if suffix.endswith('.gz'):
                date_str = suffix.replace('.gz', '')
            else:
                date_str = suffix
            
            try:
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                # 删除过期文件
                if file_date < cutoff_date:
                    log_file.unlink()
                    
            except ValueError:
                continue


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
            "timestamp": datetime.now(timezone.utc).isoformat(),
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


class LogAuditLogger:
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
    """配置日志
    
    特性：
    - 按日期滚动（每天午夜）
    - 自动压缩历史日志（gzip）
    - 自动清理过期日志（保留30天）
    - 结构化 JSON 格式
    - 敏感信息过滤
    """
    
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
    
    # 主日志文件（按日期滚动 + 压缩）
    main_file = CompressedTimedRotatingFileHandler(
        log_dir / "app.json",
        when="midnight",           # 每天午夜滚动
        interval=1,                # 每1天
        backupCount=30,            # 保留30天
        encoding='utf-8',
        compress_after_days=1      # 滚动后1天开始压缩
    )
    main_file.suffix = "%Y-%m-%d"  # 文件名格式: app.json.2026-06-10
    main_file.setFormatter(json_formatter)
    
    # 错误日志文件（单独）
    error_file = CompressedTimedRotatingFileHandler(
        log_dir / "error.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding='utf-8',
        compress_after_days=1
    )
    error_file.suffix = "%Y-%m-%d"
    error_file.setFormatter(json_formatter)
    error_file.setLevel(logging.ERROR)
    
    # 审计日志文件（单独）
    audit_file = CompressedTimedRotatingFileHandler(
        log_dir / "audit.log",
        when="midnight",
        interval=1,
        backupCount=90,            # 审计日志保留90天
        encoding='utf-8',
        compress_after_days=1
    )
    audit_file.suffix = "%Y-%m-%d"
    audit_file.setFormatter(json_formatter)
    
    # 性能日志文件（单独）
    perf_file = CompressedTimedRotatingFileHandler(
        log_dir / "performance.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding='utf-8',
        compress_after_days=1
    )
    perf_file.suffix = "%Y-%m-%d"
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
    
    # 记录日志配置信息
    root_logger.info(
        "Logging configured: rotation=daily, compression=gzip, retention=30days"
    )


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


def get_audit_logger() -> LogAuditLogger:
    """获取审计日志"""
    return LogAuditLogger()


def get_performance_logger(threshold: float = 1.0) -> PerformanceLogger:
    """获取性能日志"""
    return PerformanceLogger(slow_threshold=threshold)