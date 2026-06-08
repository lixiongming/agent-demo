"""工具函数"""
from typing import Optional
import uuid
import hashlib
from datetime import datetime


def generate_session_id() -> str:
    """生成会话ID"""
    return str(uuid.uuid4())


def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == hash


def format_datetime(dt: datetime) -> str:
    """格式化时间"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def estimate_tokens(text: str) -> int:
    """估算token数量"""
    # 简单估算：中文约1.5字符/token，英文约4字符/token
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    
    return int(chinese_chars / 1.5 + other_chars / 4)