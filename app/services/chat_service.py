"""聊天服务"""
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.db import SessionRepository, MessageRepository
from app.agent import get_chat_app, AgentState
from app.llm import get_llm
from app.memory import ShortTermMemory
from app.config import get_settings
from app.core.logger import get_logger
import uuid

logger = get_logger(__name__)
settings = get_settings()


class ChatService:
    """聊天服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.message_repo = MessageRepository(db)
    
    async def chat(
        self,
        session_id: str,
        message: str,
        user_id: Optional[int] = None
    ) -> dict:
        """聊天（非流式）"""
        # 获取或创建会话
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            session = await self.session_repo.create(
                session_id=session_id,
                agent_type="chat",
                model_name=settings.DEFAULT_MODEL,
                user_id=user_id
            )
        
        # 获取历史消息
        history = await self.message_repo.get_recent(session.id, limit=20)
        
        # 构建消息列表
        messages = []
        if session.system_prompt:
            messages.append(SystemMessage(content=session.system_prompt))
        
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
        # 添加当前消息
        messages.append(HumanMessage(content=message))
        
        # 保存用户消息
        await self.message_repo.create(
            session_id=session.id,
            role="user",
            content=message
        )
        
        # 调用LLM
        llm = get_llm(session.model_name)
        response = await llm.ainvoke(messages)
        
        # 保存助手消息
        await self.message_repo.create(
            session_id=session.id,
            role="assistant",
            content=response.content,
            model_name=session.model_name
        )
        
        # 更新会话统计
        await self.session_repo.increment_message_count(session_id)
        
        return {
            "session_id": session_id,
            "response": response.content,
            "message_count": session.message_count + 1
        }
    
    async def chat_stream(
        self,
        session_id: str,
        message: str,
        user_id: Optional[int] = None
    ) -> AsyncGenerator[dict, None]:
        """聊天（流式）"""
        # 获取或创建会话
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            session = await self.session_repo.create(
                session_id=session_id,
                agent_type="chat",
                model_name=settings.DEFAULT_MODEL,
                user_id=user_id
            )
        
        # 获取历史
        history = await self.message_repo.get_recent(session.id, limit=20)
        
        # 构建消息
        messages = []
        if session.system_prompt:
            messages.append(SystemMessage(content=session.system_prompt))
        
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
        messages.append(HumanMessage(content=message))
        
        # 保存用户消息
        await self.message_repo.create(
            session_id=session.id,
            role="user",
            content=message
        )
        
        # 流式调用LLM
        llm = get_llm(session.model_name)
        full_response = []
        
        async for chunk in llm.astream(messages):
            content = chunk.content
            full_response.append(content)
            yield {"content": content}
        
        # 保存完整响应
        complete_response = "".join(full_response)
        await self.message_repo.create(
            session_id=session.id,
            role="assistant",
            content=complete_response,
            model_name=session.model_name
        )
        
        await self.session_repo.increment_message_count(session_id)
        
        yield {"done": True}
    
    async def create_session(
        self,
        agent_type: str = "chat",
        model_name: str = None,
        user_id: Optional[int] = None,
        system_prompt: Optional[str] = None
    ) -> dict:
        """创建会话"""
        session_id = str(uuid.uuid4())
        
        session = await self.session_repo.create(
            session_id=session_id,
            agent_type=agent_type,
            model_name=model_name or settings.DEFAULT_MODEL,
            user_id=user_id,
            system_prompt=system_prompt
        )
        
        return {
            "session_id": session.session_id,
            "agent_type": session.agent_type,
            "model_name": session.model_name,
            "created_at": session.created_at
        }