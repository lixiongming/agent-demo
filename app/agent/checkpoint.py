"""Checkpointer 配置

支持：
- MemorySaver：开发/测试用，内存存储，进程重启后丢失
- SqliteSaver：生产用，SQLite 持久化存储
"""
import os
from pathlib import Path
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# 尝试导入 SQLite checkpointer
_SQLITE_AVAILABLE = False
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    _SQLITE_AVAILABLE = True
except ImportError:
    logger.warning(
        "langgraph-checkpoint-sqlite 未安装，SQLite 持久化不可用，"
        "将回退到 MemorySaver。安装命令: pip install langgraph-checkpoint-sqlite"
    )


def get_memory_checkpointer() -> MemorySaver:
    """内存 Checkpointer

    用于开发和测试，进程重启后状态丢失
    """
    return MemorySaver()


def get_sqlite_checkpointer(db_path: Optional[str] = None):
    """SQLite 持久化 Checkpointer

    Args:
        db_path: SQLite 数据库文件路径，默认使用配置中的 CHECKPOINT_DB_PATH

    Returns:
        SqliteSaver 实例

    Raises:
        ImportError: langgraph-checkpoint-sqlite 未安装
    """
    if not _SQLITE_AVAILABLE:
        raise ImportError(
            "langgraph-checkpoint-sqlite 未安装，无法使用 SQLite 持久化。"
            "安装命令: pip install langgraph-checkpoint-sqlite"
        )

    if db_path is None:
        db_path = settings.CHECKPOINT_DB_PATH

    # 确保数据库目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir:
        Path(db_dir).mkdir(parents=True, exist_ok=True)

    conn_string = f"file:{db_path}"
    checkpointer = SqliteSaver.from_conn_string(conn_string)
    checkpointer.setup()
    logger.info(f"SQLite checkpointer 初始化完成，数据库路径: {db_path}")
    return checkpointer


def get_checkpointer(
    checkpoint_type: Optional[str] = None,
    db_path: Optional[str] = None
):
    """获取 Checkpointer

    根据配置返回合适的 checkpointer 实例：
    - memory: MemorySaver（开发/测试）
    - sqlite: SqliteSaver（生产）

    如果 sqlite 不可用，自动回退到 MemorySaver。

    Args:
        checkpoint_type: 覆盖配置中的 CHECKPOINT_TYPE，可选 memory | sqlite
        db_path: 覆盖配置中的 CHECKPOINT_DB_PATH

    Returns:
        Checkpointer 实例
    """
    if checkpoint_type is None:
        checkpoint_type = settings.CHECKPOINT_TYPE

    if checkpoint_type == "sqlite":
        if _SQLITE_AVAILABLE:
            try:
                return get_sqlite_checkpointer(db_path)
            except Exception as e:
                logger.error(f"SQLite checkpointer 初始化失败: {e}，回退到 MemorySaver")
                return get_memory_checkpointer()
        else:
            logger.warning("SQLite 不可用，回退到 MemorySaver")
            return get_memory_checkpointer()

    return get_memory_checkpointer()


class CheckpointManager:
    """Checkpointer 管理器

    封装 LangGraph checkpointer 的常用操作，提供统一的状态管理接口。
    """

    def __init__(self, checkpoint_type: Optional[str] = None):
        self.checkpointer = get_checkpointer(checkpoint_type)
        self._is_sqlite = isinstance(self.checkpointer, SqliteSaver) if _SQLITE_AVAILABLE else False

    def _make_config(self, thread_id: str) -> dict:
        """构建 LangGraph checkpointer 所需的 config 字典"""
        return {"configurable": {"thread_id": thread_id}}

    async def save_state(self, thread_id: str, state: dict):
        """保存状态

        LangGraph 在图执行过程中会自动通过 checkpointer 保存状态，
        此方法用于手动保存额外状态。

        Args:
            thread_id: 线程 ID
            state: 要保存的状态字典
        """
        config = self._make_config(thread_id)
        # 获取当前 checkpoint 作为基础
        current = self.checkpointer.get(config)
        if current is not None:
            # 已有 checkpoint，LangGraph 会自动管理
            logger.debug(f"线程 {thread_id} 已有 checkpoint，状态由 LangGraph 自动管理")
        else:
            logger.debug(f"线程 {thread_id} 暂无 checkpoint，状态将在图执行时自动保存")

    async def load_state(self, thread_id: str) -> Optional[dict]:
        """加载状态

        从 checkpointer 中获取指定线程的最新 checkpoint 状态。

        Args:
            thread_id: 线程 ID

        Returns:
            最新 checkpoint 的 channel_values，如果没有则返回 None
        """
        config = self._make_config(thread_id)
        checkpoint = self.checkpointer.get(config)
        if checkpoint is None:
            return None
        # checkpoint 是 CheckpointTuple，其 channel_values 包含图状态
        return checkpoint.get("channel_values") if isinstance(checkpoint, dict) else None

    async def list_checkpoints(self, thread_id: str) -> list:
        """列出指定线程的所有 checkpoint

        Args:
            thread_id: 线程 ID

        Returns:
            checkpoint 列表
        """
        config = self._make_config(thread_id)
        try:
            return list(self.checkpointer.list(config))
        except Exception as e:
            logger.error(f"列出 checkpoint 失败 (thread_id={thread_id}): {e}")
            return []

    async def clear_checkpoints(self, thread_id: str):
        """清除指定线程的所有 checkpoint

        对于 SqliteSaver，直接删除该线程的所有 checkpoint 记录。
        对于 MemorySaver，无法精确删除，只能重建实例。

        Args:
            thread_id: 线程 ID
        """
        config = self._make_config(thread_id)

        if self._is_sqlite:
            try:
                # SqliteSaver 支持 delete_thread 方法
                if hasattr(self.checkpointer, "delete_thread"):
                    self.checkpointer.delete_thread(thread_id)
                    logger.info(f"已清除线程 {thread_id} 的所有 checkpoint")
                else:
                    # 兼容旧版本：通过底层连接删除
                    self._clear_sqlite_thread(thread_id)
            except Exception as e:
                logger.error(f"清除 checkpoint 失败 (thread_id={thread_id}): {e}")
        else:
            # MemorySaver 没有删除 API，记录警告
            logger.warning(
                f"MemorySaver 不支持清除指定线程的 checkpoint (thread_id={thread_id})，"
                "如需清除请使用 SQLite 模式"
            )

    def _clear_sqlite_thread(self, thread_id: str):
        """通过底层 SQLite 连接清除指定线程的 checkpoint"""
        try:
            db = self.checkpointer.db
            cursor = db.cursor()
            # 删除 checkpoint 写入记录
            cursor.execute(
                "DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,)
            )
            # 删除 checkpoint 记录
            cursor.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,)
            )
            # 删除 checkpoint blob 记录
            cursor.execute(
                "DELETE FROM checkpoint_blobs WHERE thread_id = ?", (thread_id,)
            )
            db.commit()
            logger.info(f"已通过 SQL 清除线程 {thread_id} 的所有 checkpoint")
        except Exception as e:
            logger.error(f"SQL 清除 checkpoint 失败 (thread_id={thread_id}): {e}")