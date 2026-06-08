"""提示词模块

功能：
- 提示词模板管理
- 动态提示词生成
- 提示词版本控制

功能：
- 模板化管理
- 参数化配置
- 多场景支持
"""
from .templates import PromptTemplates, get_prompt

__all__ = ["PromptTemplates", "get_prompt"]