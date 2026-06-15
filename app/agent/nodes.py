"""LangGraph 节点实现"""
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from app.agent.state import AgentState, ChatState
from app.llm.factory import get_llm
from app.tools.registry import ToolRegistry
from app.core.logger import get_logger
from app.core.container import DIContainer
from app.core.interfaces import IRAGService
from app.core.tracing import tracer, SpanStatus
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


def get_rag_service():
    """获取 RAG 服务（容器单例）
    
    标准：
    - 使用容器获取单例
    - 只初始化一次
    - 后续请求直接获取
    """
    return DIContainer.get(IRAGService)


async def route_decision_node(state: ChatState) -> Dict[str, Any]:
    """智能路由决策节点
    
    使用三级路由策略：
    1. 关键词快速路径（毫秒级）
    2. 规则引擎匹配（毫秒级）
    3. LLM 智能决策（带缓存，秒级）
    
    Returns:
        route_decision: {"needs_retrieval": bool, "method": str, "reason": str, "confidence": float}
    """
    async with tracer.span("route_decision") as span:
        logger.info("Route decision node executing")
        
        current_input = state.get("current_input", "")
        span.set_attribute("query_length", len(current_input))
        
        if not current_input:
            span.set_attribute("result", "no_input")
            return {"route_decision": {"needs_retrieval": False, "reason": "无输入", "confidence": 1.0, "method": "default"}}
        
        try:
            # 使用智能路由器
            from app.agent.smart_router import smart_route
            
            decision = await smart_route(current_input)
            
            # 记录追踪信息
            span.set_attribute("needs_retrieval", decision.get("needs_retrieval"))
            span.set_attribute("method", decision.get("method"))
            span.set_attribute("confidence", decision.get("confidence"))
            span.set_attribute("latency_ms", decision.get("latency_ms", 0))
            
            logger.info(
                f"Route decision: needs_retrieval={decision.get('needs_retrieval')}, "
                f"method={decision.get('method')}, "
                f"reason={decision.get('reason')}, "
                f"confidence={decision.get('confidence')}, "
                f"latency_ms={decision.get('latency_ms', 0)}"
            )
            
            return {"route_decision": decision}
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"Route decision error: {e}")
            # 降级策略：默认检索
            return {
                "route_decision": {
                    "needs_retrieval": True,
                    "reason": f"路由决策失败，降级为默认检索: {str(e)}",
                    "confidence": 0.5,
                    "method": "fallback"
                }
            }


async def rag_retrieve_node(state: ChatState) -> Dict[str, Any]:
    """RAG 检索节点
    
    根据路由决策，仅在需要时检索知识库
    """
    async with tracer.span("rag_retrieve") as span:
        logger.info("RAG retrieve node executing")
        
        # 检查路由决策
        route_decision = state.get("route_decision", {})
        needs_retrieval = route_decision.get("needs_retrieval", False)
        
        span.set_attribute("needs_retrieval", needs_retrieval)
        
        if not needs_retrieval:
            logger.info("RAG retrieval skipped (route decision: not needed)")
            span.set_attribute("result", "skipped")
            return state
        
        current_input = state.get("current_input", "")
        span.set_attribute("query_length", len(current_input))
        
        if not current_input:
            span.set_attribute("result", "no_input")
            return state
        
        try:
            # 检索知识库
            rag_service = get_rag_service()
            
            # 嵌套 Span：向量检索
            async with tracer.span("vector_search") as search_span:
                result = await rag_service.query(
                    question=current_input,
                    top_k=5,
                    threshold=0.3
                )
                search_span.set_attribute("top_k", 5)
                search_span.set_attribute("threshold", 0.3)
            
            sources = result.get("sources", [])
            span.set_attribute("doc_count", len(sources))
            
            if sources:
                # 构建知识上下文
                context_parts = []
                for i, source in enumerate(sources):
                    context_parts.append(f"[知识{i+1}] {source.get('content', '')}")
                
                knowledge_context = "\n".join(context_parts)
                
                logger.info(f"RAG retrieved {len(sources)} documents")
                span.set_attribute("result", "success")
                
                return {
                    "rag_context": knowledge_context,
                    "rag_sources": sources,
                    "rag_used": True
                }
            else:
                logger.info("RAG: 知识库中没有找到相关内容")
                span.set_attribute("result", "no_match")
                return {"rag_used": False}
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"RAG retrieve error: {e}")
            return {"rag_used": False}


async def agent_node(state: AgentState) -> Dict[str, Any]:
    """Agent决策节点
    
    分析当前状态，决定下一步行动
    """
    logger.info(f"Agent node executing, iteration: {state.get('iteration_count', 0)}")
    
    # 获取LLM
    llm = get_llm(state.get("model_name", settings.DEFAULT_MODEL))
    
    # 构建消息
    messages = state.get("messages", [])
    
    # 调用LLM
    try:
        response = await llm.ainvoke(messages)
        
        # 检查是否需要工具调用
        if hasattr(response, "tool_calls") and response.tool_calls:
            return {
                "agent_outcome": {
                    "action": "tool_call",
                    "data": response.tool_calls
                },
                "messages": [response],
                "iteration_count": state.get("iteration_count", 0) + 1
            }
        
        # 完成
        return {
            "agent_outcome": {
                "action": "finish",
                "data": response.content
            },
            "messages": [response],
            "final_response": response.content,
            "iteration_count": state.get("iteration_count", 0) + 1
        }
    
    except Exception as e:
        logger.error(f"Agent node error: {e}")
        return {
            "errors": [str(e)],
            "iteration_count": state.get("iteration_count", 0) + 1
        }


async def tool_node(state: AgentState) -> Dict[str, Any]:
    """工具执行节点
    
    执行Agent决策的工具调用
    """
    logger.info("Tool node executing")
    
    outcome = state.get("agent_outcome")
    if not outcome or outcome.get("action") != "tool_call":
        return state
    
    tool_calls = outcome.get("data", [])
    tool_registry = ToolRegistry()
    
    results = []
    messages = []
    
    for tool_call in tool_calls:
        tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
        tool_args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", {})
        
        try:
            # 执行工具
            result = await tool_registry.execute(tool_name, tool_args)
            
            results.append({
                "tool_name": tool_name,
                "result": result,
                "success": True
            })
            
            # 添加工具消息
            messages.append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call.get("id", "")
                )
            )
        
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            results.append({
                "tool_name": tool_name,
                "result": None,
                "error": str(e),
                "success": False
            })
            messages.append(
                ToolMessage(
                    content=f"Error: {str(e)}",
                    tool_call_id=tool_call.get("id", "")
                )
            )
    
    return {
        "tool_results": results,
        "messages": messages,
        "agent_outcome": None  # 清除决策，重新进入agent节点
    }


async def chat_node(state: ChatState) -> Dict[str, Any]:
    """聊天节点 - 智能路由版（支持工具调用）
    
    根据路由决策决定是否使用 RAG 检索结果
    根据工具决策决定是否使用工具执行结果
    """
    async with tracer.span("chat") as span:
        logger.info("Chat node executing")
        
        llm = get_llm(settings.DEFAULT_MODEL)
        
        messages = state.get("messages", [])
        current_input = state.get("current_input", "")
        
        span.set_attribute("query_length", len(current_input))
        span.set_attribute("model", settings.DEFAULT_MODEL)
        
        # 添加用户消息
        messages.append(HumanMessage(content=current_input))
        
        try:
            # 检查是否有 RAG 上下文
            rag_context = state.get("rag_context")
            rag_used = state.get("rag_used", False)
            
            # 检查是否有工具执行结果
            tool_results = state.get("tool_results", [])
            tool_used = state.get("tool_used", False)
            
            span.set_attribute("rag_used", rag_used)
            span.set_attribute("tool_used", tool_used)
            
            # 构建上下文
            context_parts = []
            
            # 如果有检索结果，添加到上下文
            if rag_context and rag_used:
                context_parts.append(f"""知识库检索结果：{rag_context}""")
                logger.info("Using RAG context for response")
            
            # 如果有工具执行结果，添加到上下文
            if tool_results and tool_used:
                tool_info = []
                for result in tool_results:
                    if result.get("success"):
                        tool_name = result['tool_name']
                        tool_result = result['result']
                        
                        # 特殊处理新闻查询结果
                        if tool_name == "news_query" and tool_result:
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
                                
                                tool_info.append(f"- {tool_name}:\n{chr(10).join(news_info)}")
                            else:
                                tool_info.append(f"- {tool_name}: 没有找到相关新闻")
                        else:
                            # 其他工具，直接显示结果
                            tool_info.append(f"- {tool_name}: {tool_result}")
                    else:
                        tool_info.append(f"- {result['tool_name']}: 执行失败 - {result.get('error')}")
                
                context_parts.append(f"""工具调用结果：
{chr(10).join(tool_info)}""")
                logger.info(f"Using tool results: {len(tool_results)} tools")
            
            # 如果有上下文，添加系统提示
            if context_parts:
                system_content = f"""以下是相关信息，请参考这些内容回答用户问题：

{chr(10).join(context_parts)}

请基于以上信息回答用户问题。如果没有相关信息，请根据你的知识回答。"""
                messages.insert(0, SystemMessage(content=system_content))
            else:
                logger.info("No context, using general knowledge")
            
            # 嵌套 Span：LLM 调用
            async with tracer.span("llm_invoke") as llm_span:
                response = await llm.ainvoke(messages)
                llm_span.set_attribute("response_length", len(response.content))
            
            span.set_attribute("result", "success")
            
            return {
                "messages": [AIMessage(content=response.content)],
                "response": response.content,
                "rag_used": rag_used,
                "tool_used": tool_used
            }
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"Chat node error: {e}")
            return {
                "response": f"Error: {str(e)}",
                "errors": [str(e)]
            }


async def error_handler_node(state: AgentState) -> Dict[str, Any]:
    """错误处理节点"""
    errors = state.get("errors", [])
    
    if errors:
        logger.warning(f"Handling errors: {errors}")
        return {
            "final_response": f"执行过程中发生错误: {errors[-1]}",
            "agent_outcome": {"action": "finish", "data": None}
        }
    
    return state


async def should_continue(state: AgentState) -> str:
    """判断是否继续执行
    
    Returns:
        "continue": 继续执行工具
        "finish": 完成
        "error": 错误处理
    """
    # 检查迭代次数
    if state.get("iteration_count", 0) >= settings.MAX_ITERATIONS:
        return "finish"
    
    # 检查错误
    if state.get("errors"):
        return "error"
    
    # 检查决策
    outcome = state.get("agent_outcome")
    if not outcome:
        return "continue"
    
    action = outcome.get("action")
    if action == "tool_call":
        return "continue"
    elif action == "finish":
        return "finish"
    
    return "continue"


# ============================================
# 会话管理节点（标准 Agent 图模式）
# ============================================

async def load_history_node(state: ChatState) -> Dict[str, Any]:
    """加载历史消息节点
    
    功能：
    - 获取或创建会话
    - 加载历史消息
    - 加载系统提示词
    """
    async with tracer.span("load_history") as span:
        logger.info("Load history node executing")
        
        session_id = state.get("session_id", "")
        user_id = state.get("user_id")
        
        span.set_attribute("session_id", session_id)
        
        try:
            # 获取数据库会话
            from app.db import AsyncSessionLocal, SessionRepository, MessageRepository
            
            async with AsyncSessionLocal() as db:
                session_repo = SessionRepository(db)
                message_repo = MessageRepository(db)
                
                # 获取或创建会话
                session = await session_repo.get_by_id(session_id)
                if not session:
                    session = await session_repo.create(
                        session_id=session_id,
                        agent_type="chat",
                        model_name=state.get("model_name", settings.DEFAULT_MODEL),
                        user_id=user_id
                    )
                    logger.info(f"Session created: {session_id}")
                
                # 加载历史消息
                history = await message_repo.get_recent(session.id, limit=20)
                
                # 构建消息列表
                messages = []
                
                # 添加系统提示词
                if session.system_prompt:
                    messages.append(SystemMessage(content=session.system_prompt))
                
                # 添加历史消息
                for msg in history:
                    if msg.role == "user":
                        messages.append(HumanMessage(content=msg.content))
                    elif msg.role == "assistant":
                        messages.append(AIMessage(content=msg.content))
                
                span.set_attribute("history_count", len(history))
                span.set_attribute("session_id_db", session.id)
                
                logger.info(f"Loaded {len(history)} history messages for session {session_id}")
                
                # 提交事务（如果有创建会话的操作）
                await db.commit()
                
                return {
                    "messages": messages,
                    "db_session_id": session.id,
                    "system_prompt": session.system_prompt,
                    "model_name": session.model_name,
                    "history_loaded": True,
                    "history_count": len(history)
                }
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"Load history error: {e}")
            return {
                "history_loaded": False,
                "history_count": 0,
                "errors": [f"加载历史消息失败: {str(e)}"]
            }


async def save_message_node(state: ChatState) -> Dict[str, Any]:
    """保存消息节点
    
    功能：
    - 保存用户消息
    - 保存助手消息
    - 更新会话统计
    """
    async with tracer.span("save_message") as span:
        logger.info("Save message node executing")
        
        session_id = state.get("session_id", "")
        db_session_id = state.get("db_session_id")
        current_input = state.get("current_input", "")
        response = state.get("response", "")
        
        span.set_attribute("session_id", session_id)
        
        if not db_session_id:
            span.set_status(SpanStatus.ERROR, "No db_session_id")
            return {"assistant_message_saved": False}
        
        try:
            from app.db import AsyncSessionLocal, SessionRepository, MessageRepository
            
            async with AsyncSessionLocal() as db:
                session_repo = SessionRepository(db)
                message_repo = MessageRepository(db)
                
                # 保存用户消息（如果还没保存）
                if not state.get("user_message_saved"):
                    await message_repo.create(
                        session_id=db_session_id,
                        role="user",
                        content=current_input
                    )
                    span.set_attribute("user_message_saved", True)
                    logger.info(f"User message saved for session {session_id}")
                
                # 保存助手消息
                if response:
                    await message_repo.create(
                        session_id=db_session_id,
                        role="assistant",
                        content=response,
                        model_name=state.get("model_name", settings.DEFAULT_MODEL)
                    )
                    span.set_attribute("assistant_message_saved", True)
                    logger.info(f"Assistant message saved for session {session_id}")
                
                # 更新会话统计
                await session_repo.increment_message_count(session_id)
                
                # 提交事务（关键！）
                await db.commit()
                
                return {
                    "user_message_saved": True,
                    "assistant_message_saved": True
                }
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"Save message error: {e}")
            return {
                "assistant_message_saved": False,
                "errors": [f"保存消息失败: {str(e)}"]
            }


# ============================================
# 工具调用节点
# ============================================

async def tool_decision_node(state: ChatState) -> Dict[str, Any]:
    """工具决策节点
    
    功能：
    1. 分析用户问题，判断是否需要调用工具
    2. 优先检查路由决策（如果路由已指定工具）
    3. 使用 LLM 自主决策（如果路由未指定）
    4. 返回工具调用决策
    
    - OpenAI: LLM 自主决策工具调用
    - Google: 意图分类 + LLM 决策
    - 阿里: 规则引擎 + LLM 决策
    """
    async with tracer.span("tool_decision") as span:
        logger.info("Tool decision node executing")
        
        current_input = state.get("current_input", "")
        messages = state.get("messages", [])
        
        span.set_attribute("query", current_input)
        
        try:
            # 1. 优先检查路由决策（如果路由已指定工具）
            route_decision = state.get("route_decision", {})
            if route_decision.get("needs_tool"):
                tool_name = route_decision.get("tool_name")
                logger.info(f"Tool decision from route: {tool_name}")
                
                span.set_attribute("needs_tool", True)
                span.set_attribute("tool_name", tool_name)
                span.set_attribute("method", "route_decision")
                
                return {
                    "tool_decision": {
                        "needs_tool": True,
                        "tool_name": tool_name,
                        "tool_args": {"question": current_input},
                        "reason": route_decision.get("reason", "路由决策指定"),
                        "method": "route_decision"
                    }
                }
            
            # 2. 如果路由未指定，使用 LLM 自主决策
            # 获取可用工具
            tool_registry = ToolRegistry()
            available_tools = tool_registry.list_tools()
            
            if not available_tools:
                logger.info("No tools available, skipping tool decision")
                return {"tool_decision": {"needs_tool": False, "reason": "no_tools"}}
            
            # 构建工具描述
            tool_descriptions = []
            for tool in available_tools:
                tool_descriptions.append(f"- {tool['name']}: {tool['description']}")
            
            tools_info = "\n".join(tool_descriptions)
            
            # 构建 LLM 提示词
            prompt = f"""你是一个工具调用决策器，需要判断用户问题是否需要调用工具。

可用工具列表：
{tools_info}

用户问题：{current_input}

请分析：
1. 用户问题是否需要调用以上某个工具？
2. 如果需要，应该调用哪个工具？参数是什么？

请以JSON格式返回决策：
{{
    "needs_tool": true/false,
    "tool_name": "工具名称（如果needs_tool为true）",
    "tool_args": {{参数对象}},
    "reason": "决策原因"
}}

只返回JSON，不要其他内容。"""
            
            # 调用 LLM
            llm = get_llm(settings.DEFAULT_MODEL)
            
            async with tracer.span("llm_tool_decision") as llm_span:
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                llm_span.set_attribute("response_length", len(response.content))
            
            # 解析结果
            import json
            try:
                # 尝试提取 JSON
                content = response.content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                decision = json.loads(content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool decision: {response.content}")
                decision = {"needs_tool": False, "reason": "parse_error"}
            
            span.set_attribute("needs_tool", decision.get("needs_tool", False))
            span.set_attribute("tool_name", decision.get("tool_name", ""))
            span.set_attribute("method", "llm")
            
            logger.info(f"Tool decision: {decision}")
            
            return {"tool_decision": decision}
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"Tool decision error: {e}")
            return {
                "tool_decision": {"needs_tool": False, "reason": f"error: {str(e)}"},
                "errors": [f"工具决策失败: {str(e)}"]
            }


async def tool_execute_node(state: ChatState) -> Dict[str, Any]:
    """工具执行节点
    
    功能：
    1. 执行工具调用
    2. 记录执行结果
    3. 支持限流、熔断、追踪
    """
    async with tracer.span("tool_execute") as span:
        logger.info("Tool execute node executing")
        
        tool_decision = state.get("tool_decision", {})
        
        if not tool_decision.get("needs_tool"):
            logger.info("No tool call needed")
            return {"tool_used": False}
        
        tool_name = tool_decision.get("tool_name")
        tool_args = tool_decision.get("tool_args", {})
        
        span.set_attribute("tool_name", tool_name)
        span.set_attribute("tool_args", str(tool_args))
        
        try:
            # 执行工具
            tool_registry = ToolRegistry()
            
            async with tracer.span(f"tool_{tool_name}") as tool_span:
                result = await tool_registry.execute(tool_name, tool_args)
                tool_span.set_attribute("success", True)
            
            span.set_attribute("result", "success")
            logger.info(f"Tool {tool_name} executed successfully: {result}")
            
            return {
                "tool_results": [{
                    "tool_name": tool_name,
                    "result": result,
                    "success": True
                }],
                "tool_used": True
            }
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"Tool execute error: {e}")
            
            return {
                "tool_results": [{
                    "tool_name": tool_name,
                    "result": None,
                    "error": str(e),
                    "success": False
                }],
                "tool_used": True,
                "errors": [f"工具执行失败: {str(e)}"]
            }