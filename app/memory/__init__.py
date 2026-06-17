"""记忆模块 - 大厂标准记忆管理

功能：
- 短期记忆（Redis）：对话上下文，自动过期
- 长期记忆（Qdrant）：关键事实，向量存储
- 遗忘机制：时间衰减 + 容量限制
- 冲突修正：事实检测 + 信息更新
- 记忆整合：事实提取 + 实体识别
- 记忆管理器：统一管理入口

大厂实践：
- Google MemGPT：分层记忆 + 智能遗忘
- OpenAI Memory API：事实提取 + 冲突修正
- 阿里通义：记忆整合 + Rerank 重排序
"""
from .short_term import ShortTermMemory
from .long_term import LongTermMemory
from .forgetting import ForgettingManager
from .conflict import ConflictResolver
from .integration import MemoryIntegrator
from .manager import MemoryManager, get_memory_manager, clear_memory_manager

__all__ = [
    "ShortTermMemory",
    "LongTermMemory",
    "ForgettingManager",
    "ConflictResolver",
    "MemoryIntegrator",
    "MemoryManager",
    "get_memory_manager",
    "clear_memory_manager"
]