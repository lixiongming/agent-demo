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
        
        # 调用 Agent 图
        app = _get_chat_app()
        result = await app.ainvoke(initial_state)
        
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
        """聊天（流式）- 智能路由 + RAG + 流式输出
        
        流程：
        1. 智能路由决策
        2. RAG 检索（按需）
        3. 流式生成响应
        4. 保存消息
        """
        logger.info(f"ChatService.chat_stream called: session={session_id}, user={user_id}")

        from app.agent.smart_router import smart_route
        from app.llm import get_llm
        from langchain_core.messages import HumanMessage
        from app.db import AsyncSessionLocal, SessionRepository, MessageRepository
        from app.core.tracing import tracer

        db_session_id = None
        rag_used = False
        rag_strategy = None
        rag_score = 0.0
        
        # ===== 1. 加载会话和历史 =====
        async with tracer.span("load_history"):
            async with AsyncSessionLocal() as db:
                session_repo = SessionRepository(db)

                session = await session_repo.get_by_id(session_id)
                if not session:
                    session = await session_repo.create(
                        session_id=session_id,
                        agent_type="chat",
                        model_name=model_name or settings.DEFAULT_MODEL,
                        user_id=user_id
                    )

                db_session_id = session.id

                # 使用历史管理服务加载消息
                from app.services.history import HistoryManager
                history_manager = HistoryManager(db)
                messages = await history_manager.get_history(
                    session_id=session.id,
                    system_prompt=session.system_prompt
                )
        
        # ===== 2. 智能路由决策 =====
        async with tracer.span("route_decision"):
            decision = await smart_route(message)
            needs_retrieval = decision.get("needs_retrieval", False)
            rag_strategy = decision.get("method")
        
        # ===== 3. RAG 检索（按需）=====
        if needs_retrieval:
            async with tracer.span("rag_retrieve"):
                try:
                    from app.core.container import DIContainer
                    from app.core.interfaces import IRAGService
                    from app.services.cache import CacheService
                    from app.services.rerank import get_rerank_service
                    
                    # 先尝试缓存
                    cached_result = await CacheService.get_rag_result(message)
                    if cached_result:
                        sources = cached_result.get("sources", [])
                        logger.info(f"RAG cache hit for: {message[:20]}...")
                    else:
                        # 缓存未命中，执行检索
                        rag_service = DIContainer.get(IRAGService)
                        
                        # 检索更多候选（用于 Rerank）
                        result = await rag_service.query(
                            question=message,
                            top_k=20,  # 召回更多候选
                            threshold=0.2  # 降低阈值，召回更多
                        )
                        
                        sources = result.get("sources", [])
                        
                        # Rerank 重排序
                        if sources and len(sources) > 5:
                            async with tracer.span("rerank"):
                                reranker = get_rerank_service()
                                
                                # 提取文档内容
                                documents = [s.get("content", "") for s in sources]
                                
                                # Rerank
                                rerank_results = await reranker.rerank(
                                    query=message,
                                    documents=documents,
                                    top_k=5
                                )
                                
                                # 按重排序结果重新排列
                                reranked_sources = []
                                for item in rerank_results:
                                    idx = item["index"]
                                    if idx < len(sources):
                                        source = sources[idx].copy()
                                        source["rerank_score"] = item["relevance_score"]
                                        reranked_sources.append(source)
                                
                                sources = reranked_sources
                                logger.info(f"Rerank 完成: {len(sources)} documents")
                        
                        # 缓存结果
                        if sources:
                            await CacheService.set_rag_result(message, {"sources": sources})
                    
                    if sources:
                        rag_used = True
                        rag_score = sources[0].get("rerank_score") or sources[0].get("score", 0)
                        
                        context_parts = []
                        for i, source in enumerate(sources):
                            context_parts.append(f"[知识{i+1}] {source.get('content', '')}")
                        
                        knowledge_context = "\n".join(context_parts)
                        
                        messages.insert(0, SystemMessage(
                            content=f"""以下是知识库中检索到的相关内容，请参考这些内容回答用户问题：

{knowledge_context}

请基于以上知识库内容回答用户问题。如果知识库中没有相关信息，请根据你的知识回答。"""
                        ))
                except Exception as e:
                    logger.warning(f"RAG retrieve failed: {e}")
        
        # ===== 4. 流式生成响应 =====
        messages.append(HumanMessage(content=message))

        # 打印发送给模型的消息摘要（详细日志只在 DEBUG 模式）
        logger.info(f"🚀 发送给模型的消息总数: {len(messages)}")
        if settings.DEBUG:
            for i, msg in enumerate(messages):
                content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                logger.debug(f"  [{i}] {msg.type}: {content_preview}")

        # 保存用户消息
        async with AsyncSessionLocal() as db:
            message_repo = MessageRepository(db)
            await message_repo.create(
                session_id=db_session_id,
                role="user",
                content=message
            )
            await db.commit()  # 提交事务
        
        # 流式调用 LLM
        llm = get_llm(model_name or settings.DEFAULT_MODEL)
        full_response = []
        
        async with tracer.span("llm_stream"):
            async for chunk in llm.astream(messages):
                content = chunk.content
                if content and content.strip():
                    full_response.append(content)
                    yield {"content": content}
        
        # ===== 5. 保存助手消息 =====
        complete_response = "".join(full_response)
        
        async with AsyncSessionLocal() as db:
            session_repo = SessionRepository(db)
            message_repo = MessageRepository(db)
            
            await message_repo.create(
                session_id=db_session_id,
                role="assistant",
                content=complete_response,
                model_name=model_name or settings.DEFAULT_MODEL
            )
            
            await session_repo.increment_message_count(session_id)
            
            await db.commit()  # 提交事务
        
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
