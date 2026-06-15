"""对话历史管理服务

支持两种模式：
1. rounds - 按轮数限制：保留最近 N 轮对话
2. token - 按 Token 限制：在 token 预算内加载尽可能多的历史

大厂标准做法：
- 模型上下文窗口 32K tokens
- 预留一半给输出（16K）
- 历史消息使用另一半（16K）
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.config import get_settings
from app.core.logger import get_logger
from app.db import MessageRepository

logger = get_logger(__name__)
settings = get_settings()

# Token 计算器（延迟加载）
_token_counter = None


def get_token_counter():
    """获取 token 计数器"""
    global _token_counter
    if _token_counter is None:
        try:
            import tiktoken
            # Qwen 使用类似 GPT-4 的分词器
            _token_counter = tiktoken.encoding_for_model("gpt-4")
        except ImportError:
            logger.warning("tiktoken 未安装，使用估算模式")
            _token_counter = None
    return _token_counter


def count_tokens(text: str) -> int:
    """计算文本的 token 数

    优先使用 tiktoken 精确计算，否则使用估算
    """
    if not text:
        return 0

    encoder = get_token_counter()
    if encoder:
        return len(encoder.encode(text))

    # 估算：中文约 1.5 字/token，英文约 4 字/token
    # 取中间值 2 字/token
    return len(text) // 2


class HistoryManager:
    """对话历史管理器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.message_repo = MessageRepository(db)

    async def get_history(
        self,
        session_id: int,
        system_prompt: Optional[str] = None
    ) -> List:
        """获取历史消息

        Args:
            session_id: 会话 ID（数据库整数 ID）
            system_prompt: 系统提示词

        Returns:
            LangChain 消息列表
        """
        if not settings.HISTORY_ENABLED:
            logger.info("📚 历史消息已禁用")
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            return messages

        # 根据模式选择处理方式
        if settings.HISTORY_MODE == "rounds":
            return await self._get_rounds_history(session_id, system_prompt)
        else:
            return await self._get_token_history(session_id, system_prompt)

    async def _get_rounds_history(
        self,
        session_id: int,
        system_prompt: Optional[str] = None
    ) -> List:
        """轮数模式：保留最近 N 轮对话

        1 轮 = 1 问 + 1 答 = 2 条消息
        """
        # 加载足够多的消息
        limit = settings.HISTORY_ROUNDS_LIMIT * 2 + 5  # 多加载几条确保够用
        all_messages = await self.message_repo.get_recent(session_id, limit=limit)

        # 按轮数截取
        rounds_count = 0
        selected_messages = []

        for msg in reversed(all_messages):  # 从最新开始
            selected_messages.insert(0, msg)
            if msg.role == "assistant":
                rounds_count += 1
            if rounds_count >= settings.HISTORY_ROUNDS_LIMIT:
                break

        # 构建消息列表
        messages = []
        total_tokens = 0

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
            total_tokens += count_tokens(system_prompt)

        for msg in selected_messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
            total_tokens += count_tokens(msg.content)

        logger.info(f"� [轮数模式] {len(selected_messages)}条/{rounds_count}轮, token: {total_tokens}")

        return messages

    async def _get_token_history(
        self,
        session_id: int,
        system_prompt: Optional[str] = None
    ) -> List:
        """Token 模式：在 token 预算内加载尽可能多的历史

        大厂标准做法：
        - 计算每条消息的 token 数
        - 从最新开始，累加直到达到预算
        - 确保不超过模型上下文限制
        """
        # 加载所有历史消息
        all_messages = await self.message_repo.get_recent(session_id, limit=100)

        # 计算可用 token 预算
        max_tokens = settings.HISTORY_TOKEN_LIMIT - settings.HISTORY_TOKEN_SAFETY_MARGIN

        # 构建消息列表，从最新开始添加
        messages = []
        used_tokens = 0

        # 先计算系统提示词
        if system_prompt:
            system_tokens = count_tokens(system_prompt)
            used_tokens += system_tokens

        # 从最新消息开始，倒序添加
        selected_messages = []
        for msg in reversed(all_messages):
            msg_tokens = count_tokens(msg.content)

            if used_tokens + msg_tokens > max_tokens:
                # 超出预算，停止添加
                break

            selected_messages.insert(0, msg)
            used_tokens += msg_tokens

        # 构建最终消息列表
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        for msg in selected_messages:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        logger.info(f"📚 [Token模式] {len(selected_messages)}条, token: {used_tokens}/{max_tokens}")

        return messages
