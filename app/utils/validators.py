"""验证器"""
from typing import Optional
import re


def validate_session_id(session_id: str) -> bool:
    """验证会话ID格式"""
    # UUID格式
    pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    return bool(re.match(pattern, session_id))


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username: str) -> bool:
    """验证用户名"""
    # 3-50字符，字母数字下划线
    if len(username) < 3 or len(username) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_]+$', username))


def validate_model_name(model_name: str) -> bool:
    """验证模型名称"""
    valid_models = [
        "qwen3.7-plus", "qwen3.7-lite",
        "qwen-max", "qwen-plus", "qwen-turbo",
        "gpt-4", "gpt-3.5-turbo"
    ]
    return model_name in valid_models


def validate_agent_type(agent_type: str) -> bool:
    """验证Agent类型"""
    valid_types = ["chat", "react", "multi"]
    return agent_type in valid_types


def sanitize_input(text: str) -> str:
    """清理输入"""
    # 移除危险字符
    text = text.strip()
    text = re.sub(r'<[^>]*>', '', text)  # 移除HTML标签
    return text