"""聊天服务 - 入口适配器（Agent 图模式）

架构说明：
- ChatService 只做入口适配
- 所有业务逻辑在 Agent 图中处理
- 统一入口，逻辑清晰，易于维护
"""
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _get_chat_app():
    """延迟导入 Agent 图，避免循环导入"""
    from app.agent import get_chat_app
    return get_chat_app()


class ChatService:
    """聊天服务 - 入口适配器
    
    职责：
    - 接收 API 请求
    - 准备初始状态
    - 调用 Agent 图
    - 返回结果
    
    不包含：
    - RAG 检索逻辑（在 Agent 图中）
    - 路由决策逻辑（在 Agent 图中）
    - 消息保存逻辑（在 Agent 图中）
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def chat(
        self,
        session_id: str,
        message: str,
        user_id: Optional[int] = None,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> dict:
        """聊天（非流式）- 调用 Agent 图
        
        Args:
            session_id: 会话 ID
            message: 用户消息
            user_id: 用户 ID
            model_name: 模型名称
            system_prompt: 系统提示词
            
        Returns:
            {
                "session_id": str,
                "response": str,
                "message_count": int,
                "rag_used": bool,
                "rag_strategy": str,
                "rag_score": float
            }
        """
        logger.info(f"ChatService.chat called: session={session_id}, user={user_id}")
        
        # 准备初始状态
        initial_state = {
            "session_id": session_id,
            "current_input": message,
            "user_id": user_id,
            "model_name": model_name or settings.DEFAULT_MODEL,
            "system_prompt": system_prompt,
            "messages": [],
            "history_loaded": False,
            "history_count": 0,
            "rag_used": False,
            "rag_strategy": None,
            "rag_score": 0.0,
            "user_message_saved": False,
            "assistant_message_saved": False
        }
        
        # 调用 Agent 图（需要传递 config 参数给 Checkpointer）
        app = _get_chat_app()
        config = {"configurable": {"thread_id": session_id}}
        result = await app.ainvoke(initial_state, config=config)
        
        # 获取消息数量
        from app.db import AsyncSessionLocal, SessionRepository
        message_count = 0
        try:
            async with AsyncSessionLocal() as db:
                session_repo = SessionRepository(db)
                session = await session_repo.get_by_id(session_id)
                if session:
                    message_count = session.message_count
        except Exception as e:
            logger.warning(f"Failed to get message count: {e}")
        
        # 返回结果（兼容旧接口）
        return {
            "session_id": session_id,
            "response": result.get("response", ""),
            "message_count": message_count,
            "rag_used": result.get("rag_used", False),
            "rag_strategy": result.get("rag_strategy"),
            "rag_score": result.get("rag_score", 0.0),
            "history_count": result.get("history_count", 0)
        }
    
    async def chat_stream(
        self,
        session_id: str,
        message: str,
        user_id: Optional[int] = None,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """聊天（流式）- 通过 Agent 图实现

        使用 LangGraph 的 astream_events 实现流式输出，
        消除与 Agent 图的并行逻辑。
        """
        logger.info(f"ChatService.chat_stream called: session={session_id}, user={user_id}")

        # 准备初始状态（与 chat 方法一致）
        initial_state = {
            "session_id": session_id,
            "current_input": message,
            "user_id": user_id,
            "model_name": model_name or settings.DEFAULT_MODEL,
            "system_prompt": system_prompt,
            "messages": [],
            "history_loaded": False,
            "history_count": 0,
            "rag_used": False,
            "rag_strategy": None,
            "rag_score": 0.0,
            "user_message_saved": False,
            "assistant_message_saved": False
        }

        # 调用 Agent 图（流式）
        app = _get_chat_app()
        config = {"configurable": {"thread_id": session_id}}

        rag_used = False
        rag_strategy = None
        rag_score = 0.0

        try:
            # 使用 astream_events 获取流式输出
            async for event in app.astream_events(
                initial_state,
                config=config,
                version="v2",
                include_types=["on_chat_model_stream"]
            ):
                kind = event.get("event")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        if isinstance(content, str) and content.strip():
                            yield {"content": content}
        except Exception as e:
            logger.error(f"Agent graph stream failed: {e}")
            yield {"content": "抱歉，生成响应时出现错误，请稍后重试。"}
            return

        # 从图状态中获取 RAG 信息
        try:
            state = await app.aget_state(config)
            if state and state.values:
                rag_used = state.values.get("rag_used", False)
                rag_strategy = state.values.get("rag_strategy")
                rag_score = state.values.get("rag_score", 0.0)
        except Exception as e:
            logger.warning(f"Failed to get final state: {e}")

        # 返回最终状态
        yield {
            "done": True,
            "rag_used": rag_used,
            "rag_strategy": rag_strategy,
            "rag_score": rag_score
        }
    
    async def create_session(
        self,
        agent_type: str = "chat",
        model_name: str = None,
        user_id: Optional[int] = None,
        system_prompt: Optional[str] = None
    ) -> dict:
        """创建会话（预创建）
        
        注意：Agent 图会在第一次消息时自动创建会话
        这个方法用于预创建会话或设置系统提示词
        """
        import uuid
        from app.db import AsyncSessionLocal, SessionRepository
        
        session_id = str(uuid.uuid4())
        
        async with AsyncSessionLocal() as db:
            session_repo = SessionRepository(db)
            session = await session_repo.create(
                session_id=session_id,
                agent_type=agent_type,
                model_name=model_name or settings.DEFAULT_MODEL,
                user_id=user_id,
                system_prompt=system_prompt
            )
            await db.commit()
            
            logger.info(f"Session created: {session_id}")
            
            return {
                "session_id": session.session_id,
                "agent_type": session.agent_type,
                "model_name": session.model_name,
                "created_at": session.created_at
            }
