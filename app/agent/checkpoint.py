"""Checkpointer 配置"""
from typing import Optional
from langgraph.checkpoint.memory import MemorySaver
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def get_memory_checkpointer() -> MemorySaver:
    """内存Checkpointer
    
    用于开发和测试
    """
    return MemorySaver()


def get_checkpointer(
    checkpoint_type: str = "memory",
    db_path: Optional[str] = None
):
    """获取Checkpointer
    
    Args:
        checkpoint_type: memory | sqlite
        db_path: SQLite数据库路径
    """
    # 目前只支持memory
    return get_memory_checkpointer()


class CheckpointManager:
    """Checkpointer管理器"""
    
    def __init__(self, checkpointer_type: str = "memory"):
        self.checkpointer = get_checkpointer(checkpointer_type)
    
    async def save_state(self, thread_id: str, state: dict):
        """保存状态"""
        # LangGraph自动处理
        pass
    
    async def load_state(self, thread_id: str) -> Optional[dict]:
        """加载状态"""
        # LangGraph自动处理
        pass
    
    async def list_checkpoints(self, thread_id: str) -> list:
        """列出所有checkpoint"""
        return list(self.checkpointer.list(thread_id))
    
    async def clear_checkpoints(self, thread_id: str):
        """清除checkpoint"""
        # 实现清除逻辑
        pass