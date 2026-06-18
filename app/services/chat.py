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
        from langchain_core.messages import HumanMessage, SystemMessage
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

                # 提交事务（确保 session 被保存）
                await db.commit()

                # 使用历史管理服务加载消息
                from app.services.history import HistoryManager
                history_manager = HistoryManager(db)
                messages = await history_manager.get_history(
                    session_id=session.id,
                    system_prompt=session.system_prompt
                )
        
        # ===== 2. 智能路由决策（使用LLM Function Calling） =====
        async with tracer.span("route_decision"):
            # 使用智能路由（符合大厂标准）
            decision = await smart_route(message)
            
            logger.info(f"[路由决策] 完整结果: {decision}")
            
            needs_retrieval = decision.get("needs_retrieval", False)
            needs_tool = decision.get("needs_tool", False)
            
            # 解析 tool_calls（大厂标准格式）
            tool_calls = decision.get("tool_calls", [])
            if tool_calls:
                # 取第一个工具调用（当前只支持单工具）
                first_call = tool_calls[0]
                tool_name = first_call.get("name")
                tool_args = first_call.get("args", {})
                logger.info(f"[路由决策] 工具调用: name={tool_name}, args={tool_args}")
            else:
                tool_name = None
                tool_args = {}
            
            rag_strategy = decision.get("method")
            confidence = decision.get("confidence", 0.0)
            
            logger.info(f"[路由决策] 最终结果: needs_tool={needs_tool}, tool_name={tool_name}, confidence={confidence}")
        
        # ===== 3. 工具执行（按需）=====
        tool_used = False
        tool_result = None
        
        logger.info(f"[工具执行] 开始判断: needs_tool={needs_tool}, tool_name={tool_name}")
        
        if needs_tool and tool_name:
            async with tracer.span("tool_execute"):
                try:
                    from app.tools.registry import get_registry
                    
                    logger.info(f"[工具执行] 开始执行工具: {tool_name}")
                    logger.info(f"[工具执行] 原始参数: {tool_args}")
                    
                    # 使用全局工具注册中心（单例模式）
                    tool_registry = get_registry()
                    
                    # 检查工具是否存在
                    tool = tool_registry.get_tool(tool_name)
                    if not tool:
                        logger.error(f"[工具执行] 工具不存在: {tool_name}")
                        tool_used = False
                    else:
                        logger.info(f"[工具执行] 工具已找到: {tool_name}")
                        logger.info(f"[工具执行] 工具描述: {tool.description[:100]}...")

                        # 强制使用 question 参数（确保调用 smart_news_query）
                        # 智能路由器可能返回错误的参数，需要覆盖
                        if tool_name == "news_query":
                            tool_args = {"question": message}
                            logger.info(f"[工具执行] 参数已修正为: {tool_args}")

                        logger.info(f"[工具执行] 最终参数: {tool_args}")
                        
                        tool_result = await tool_registry.execute(tool_name, tool_args)
                        
                        logger.info(f"[工具执行] 执行完成: {tool_name}")
                        logger.info(f"[工具执行] 结果: success={tool_result.get('success')}")
                        logger.info(f"[工具执行] 结果详情: {str(tool_result)[:500]}...")
                        
                        if tool_result and tool_result.get("success"):
                            tool_used = True
                            logger.info(f"[工具执行] 执行成功: {tool_name}")
                        else:
                            logger.warning(f"[工具执行] 执行失败: {tool_result}")
                except Exception as e:
                    logger.error(f"[工具执行] 异常: {e}")
                    import traceback
                    logger.error(f"[工具执行] 异常堆栈: {traceback.format_exc()}")
        else:
            logger.info(f"[工具执行] 跳过执行: needs_tool={needs_tool}, tool_name={tool_name}")
        
        # ===== 4. RAG 检索（按需）=====
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
                            content=f"""以下是知识库中检索到的相关内容，请参考这些内容回答用户问题：{knowledge_context}请基于以上知识库内容回答用户问题。如果知识库中没有相关信息，请根据你的知识回答。"""))
                except Exception as e:
                    logger.warning(f"RAG retrieve failed: {e}")
        
        # ===== 5. 准备消息 =====
        messages.append(HumanMessage(content=message))
        
        # 如果有工具结果，添加到消息中
        if tool_used and tool_result:
            # 特殊处理新闻查询结果
            if tool_name == "news_query" and tool_result.get("news_list"):
                news_list = tool_result.get('news_list', [])
                if news_list:
                    news_info = []
                    news_info.append(f"查询类型: {tool_result.get('result_type', '新闻')}")
                    news_info.append(f"新闻数量: {tool_result.get('news_count', 0)}")
                    news_info.append("\n新闻列表:")
                    for i, news in enumerate(news_list[:10], 1):  # 最多显示10条
                        title = news.get('title', '无标题')
                        views = news.get('views', 0)
                        author = news.get('author', '未知')
                        news_info.append(f"{i}. {title} (作者: {author}, 浏览量: {views})")
                    
                    tool_context = "\n".join(news_info)
                    
                    messages.insert(0, SystemMessage(
                        content=f"""以下是工具查询返回的新闻数据，请基于这些真实数据回答用户问题：{tool_context}请基于以上真实新闻数据回答用户问题。"""
                    ))
            # 特殊处理知识库检索结果
            elif tool_name == "knowledge_search":
                # 检查是否成功
                if tool_result.get("success") and tool_result.get("found"):
                    knowledge_content = tool_result.get("knowledge", "")
                    total_results = tool_result.get("total_results", 0)
                    
                    messages.insert(0, SystemMessage(
                        content=f"""以下是知识库中检索到的 {total_results} 条相关内容，请参考这些内容回答用户问题：

{knowledge_content}

请基于以上知识库内容回答用户问题。"""
                    ))
                    logger.info(f"知识库检索结果已注入上下文: {total_results} 条内容")
                else:
                    # 检索失败或无结果，使用降级策略
                    error_msg = tool_result.get("error", tool_result.get("message", "未知错误"))
                    logger.warning(f"知识库检索失败: {error_msg}")
                    # 不注入错误信息，让 LLM 使用自己的知识回答
                    logger.info("降级策略：LLM 将使用自身知识回答")
            # 特殊处理天气查询结果
            elif tool_name == "get_weather" and tool_result.get("success"):
                weather_desc = tool_result.get("description", "")
                
                messages.insert(0, SystemMessage(
                    content=f"""以下是工具查询返回的天气数据，请基于这些真实数据回答用户问题：{weather_desc}请基于以上真实天气数据回答用户问题，用友好的语言描述天气情况。"""
                ))
            else:
                # 其他工具，直接显示结果
                messages.insert(0, SystemMessage(
                    content=f"""以下是工具查询返回的数据，请基于这些数据回答用户问题：{tool_result}请基于以上数据回答用户问题。"""
                ))

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
        
        # ===== 6. 流式生成响应 =====
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
