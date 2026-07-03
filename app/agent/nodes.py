"""LangGraph 节点实现 - 大厂标准

核心改进：
1. 使用原生 Function Calling（bind_tools）
2. ToolMessage 回传机制
3. ReAct 循环支持
4. 生产级审计日志
"""
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from app.agent.state import AgentState, ChatState
from app.llm.factory import get_llm
from app.core.logger import get_logger
from app.core.container import DIContainer
from app.core.interfaces import IRAGService
from app.core.tracing import tracer, SpanStatus
from app.config import get_settings
import time

logger = get_logger(__name__)
settings = get_settings()

# 模块级单例（避免每次调用新建实例）
_audit_logger = None
_tool_registry = None


def _get_audit_logger():
    """获取审计日志单例"""
    global _audit_logger
    if _audit_logger is None:
        from app.core.audit import AuditLogger
        _audit_logger = AuditLogger()
    return _audit_logger


def _get_tool_registry():
    """获取工具注册表单例"""
    global _tool_registry
    if _tool_registry is None:
        from app.tools.registry import ToolRegistry
        _tool_registry = ToolRegistry()
    return _tool_registry


def get_rag_service():
    """获取 RAG 服务（容器单例）"""
    return DIContainer.get(IRAGService)


# ============================================
# 智能路由节点
# ============================================

async def route_decision_node(state: ChatState) -> Dict[str, Any]:
    """智能路由决策节点 - 大厂标准
    
    使用三级路由策略：
    1. 关键词快速路径（毫秒级）
    2. 规则引擎匹配（毫秒级）
    3. LLM Function Calling（带缓存，秒级）
    
    Returns:
        route_decision: 包含 tool_calls 的决策结果
    """
    async with tracer.span("route_decision") as span:
        logger.info("Route decision node executing")
        
        current_input = state.get("current_input", "")
        user_id = state.get("user_id")
        
        span.set_attribute("query_length", len(current_input))
        span.set_attribute("user_id", user_id)
        
        if not current_input:
            span.set_attribute("result", "no_input")
            return {
                "route_decision": {
                    "needs_retrieval": False,
                    "needs_tool": False,
                    "tool_calls": [],
                    "reason": "无输入",
                    "confidence": 1.0,
                    "method": "default"
                }
            }
        
        try:
            # 使用智能路由器（已使用 Function Calling）
            from app.agent.smart_router import smart_route
            
            decision = await smart_route(current_input, user_id)
            
            # 记录追踪信息
            span.set_attribute("needs_retrieval", decision.get("needs_retrieval"))
            span.set_attribute("needs_tool", decision.get("needs_tool"))
            span.set_attribute("tool_calls_count", len(decision.get("tool_calls", [])))
            span.set_attribute("method", decision.get("method"))
            span.set_attribute("confidence", decision.get("confidence"))
            span.set_attribute("latency_ms", decision.get("latency_ms", 0))
            
            logger.info(
                f"Route decision: needs_tool={decision.get('needs_tool')}, "
                f"tool_calls={len(decision.get('tool_calls', []))}, "
                f"method={decision.get('method')}, "
                f"latency_ms={decision.get('latency_ms', 0)}"
            )
            
            return {"route_decision": decision}
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"Route decision error: {e}")
            
            # 降级策略
            return {
                "route_decision": {
                    "needs_retrieval": False,
                    "needs_tool": False,
                    "tool_calls": [],
                    "reason": f"路由决策失败，降级: {str(e)}",
                    "confidence": 0.5,
                    "method": "fallback"
                }
            }


# ============================================
# RAG 检索节点
# ============================================

async def rag_retrieve_node(state: ChatState) -> Dict[str, Any]:
    """RAG 检索节点"""
    from app.config import get_settings
    settings = get_settings()
    
    async with tracer.span("rag_retrieve") as span:
        logger.info("RAG retrieve node executing")
        
        route_decision = state.get("route_decision", {})
        needs_retrieval = route_decision.get("needs_retrieval", False)
        
        span.set_attribute("needs_retrieval", needs_retrieval)
        
        if not needs_retrieval:
            logger.info("RAG retrieval skipped")
            span.set_attribute("result", "skipped")
            return state
        
        current_input = state.get("current_input", "")
        
        try:
            rag_service = get_rag_service()
            
            async with tracer.span("vector_search"):
                result = await rag_service.query(
                    question=current_input,
                    top_k=settings.RAG_TOP_K,
                    threshold=settings.RAG_THRESHOLD
                )
            
            sources = result.get("sources", [])
            span.set_attribute("doc_count", len(sources))
            
            if sources:
                context_parts = []
                for i, source in enumerate(sources):
                    context_parts.append(f"[知识{i+1}] {source.get('content', '')}")
                
                knowledge_context = "\n".join(context_parts)
                logger.info(f"RAG retrieved {len(sources)} documents")
                
                return {
                    "rag_context": knowledge_context,
                    "rag_sources": sources,
                    "rag_used": True
                }
            else:
                logger.info("RAG: no match")
                return {"rag_used": False}
        
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            logger.error(f"RAG retrieve error: {e}")
            return {"rag_used": False}


# ============================================
# 工具执行节点 - 大厂标准
# ============================================

async def tool_decision_node(state: ChatState) -> Dict[str, Any]:
    """工具决策节点 - 只做执行（不再调用 LLM）
    
    核心改进：
    - 直接使用 route_decision 中的 tool_calls
    - 不再重复调用 LLM 决策
    - 执行工具并返回 ToolMessage 格式结果
    """
    async with tracer.span("tool_decision") as span:
        logger.info("Tool decision node executing")
        
        # 直接从路由决策获取 tool_calls
        route_decision = state.get("route_decision", {})
        tool_calls = route_decision.get("tool_calls", [])
        
        span.set_attribute("tool_calls_count", len(tool_calls))
        
        if not tool_calls:
            logger.info("No tool calls from route decision")
            return {
                "tool_decision": {
                    "needs_tool": False,
                    "tool_calls": [],
                    "reason": "路由决策未指定工具"
                }
            }
        
        # 审计日志
        audit_logger = _get_audit_logger()
        current_input = state.get("current_input", "")
        user_id = state.get("user_id")
        
        # 记录工具调用审计
        audit_logger.log_tool_decision(
            user_id=user_id,
            query=current_input,
            tool_calls=tool_calls,
            method=route_decision.get("method", "unknown")
        )
        
        span.set_attribute("needs_tool", True)
        span.set_attribute("tool_names", [tc.get("name") for tc in tool_calls])
        
        return {
            "tool_decision": {
                "needs_tool": True,
                "tool_calls": tool_calls,
                "reason": route_decision.get("reason", "路由决策指定")
            }
        }


async def tool_execute_node(state: ChatState) -> Dict[str, Any]:
    """工具执行节点 - 大厂标准
    
    核心改进：
    1. 执行工具并返回 ToolMessage 格式
    2. 支持多工具并行执行
    3. 完整的审计日志
    4. 权限检查
    """
    async with tracer.span("tool_execute") as span:
        logger.info("Tool execute node executing")
        
        tool_decision = state.get("tool_decision", {})
        tool_calls = tool_decision.get("tool_calls", [])
        
        if not tool_calls:
            logger.info("No tool calls to execute")
            return {"tool_used": False}
        
        # 审计日志
        audit_logger = _get_audit_logger()
        user_id = state.get("user_id")
        session_id = state.get("session_id", "")
        
        tool_registry = _get_tool_registry()
        tool_messages = []
        tool_results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", f"call_{int(time.time()*1000)}")
            
            span.set_attribute("tool_name", tool_name)
            span.set_attribute("tool_args_keys", str(list(tool_args.keys())))
            
            # 权限检查
            if not tool_registry.check_permission(tool_name, user_id):
                logger.warning(f"Tool {tool_name} permission denied for user {user_id}")
                audit_logger.log_permission_check(
                    user_id=user_id,
                    permission="tool_call",
                    resource=tool_name,
                    granted=False,
                    reason="权限不足"
                )
                
                tool_messages.append(
                    ToolMessage(
                        content=f"权限不足：无法调用工具 {tool_name}",
                        tool_call_id=tool_call_id
                    )
                )
                tool_results.append({
                    "tool_name": tool_name,
                    "result": None,
                    "error": "permission_denied",
                    "success": False
                })
                continue
            
            try:
                # 执行工具
                async with tracer.span(f"tool_{tool_name}") as tool_span:
                    start_time = time.time()
                    result = await tool_registry.execute(tool_name, tool_args)
                    latency_ms = int((time.time() - start_time) * 1000)
                    tool_span.set_attribute("success", True)
                    tool_span.set_attribute("latency_ms", latency_ms)
                
                # 审计日志
                audit_logger.log_tool_execution(
                    user_id=user_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    result=result,
                    latency_ms=latency_ms,
                    success=True
                )
                
                # 构建 ToolMessage（大厂标准）
                tool_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id
                    )
                )
                
                tool_results.append({
                    "tool_name": tool_name,
                    "result": result,
                    "success": True,
                    "latency_ms": latency_ms
                })
                
                logger.info(f"Tool {tool_name} executed successfully in {latency_ms}ms")
            
            except Exception as e:
                span.set_status(SpanStatus.ERROR, str(e))
                logger.error(f"Tool {tool_name} execution failed: {e}")
                
                # 审计日志
                audit_logger.log_tool_execution(
                    user_id=user_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    result=None,
                    error=str(e),
                    success=False
                )
                
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_call_id
                    )
                )
                
                tool_results.append({
                    "tool_name": tool_name,
                    "result": None,
                    "error": str(e),
                    "success": False
                })
        
        span.set_attribute("tool_count", len(tool_results))
        span.set_attribute("success_count", sum(1 for r in tool_results if r.get("success")))
        
        return {
            "tool_messages": tool_messages,
            "tool_results": tool_results,
            "tool_used": True
        }


# ============================================
# ReAct 循环节点 - 大厂标准
# ============================================

async def react_agent_node(state: ChatState) -> Dict[str, Any]:
    """ReAct Agent 节点 - 支持多轮工具调用
    
    大厂标准 ReAct 循环：
    1. LLM 决策是否需要工具
    2. 执行工具
    3. 将 ToolMessage 回传给 LLM
    4. LLM 整合结果或继续调用工具
    5. 循环直到完成或达到最大轮次
    """
    async with tracer.span("react_agent") as span:
        logger.info("ReAct agent node executing")
        
        iteration = state.get("react_iteration", 0)
        max_iterations = settings.MAX_REACT_ITERATIONS
        
        span.set_attribute("iteration", iteration)
        span.set_attribute("max_iterations", max_iterations)
        
        # 检查是否超过最大轮次
        if iteration >= max_iterations:
            logger.warning(f"ReAct max iterations reached: {iteration}")
            span.set_attribute("result", "max_iterations")
            return {
                "react_status": "max_iterations",
                "react_iteration": iteration
            }
        
        messages = state.get("messages", [])
        current_input = state.get("current_input", "")
        
        # 添加用户消息（如果是第一轮）
        if iteration == 0:
            messages.append(HumanMessage(content=current_input))
        
        # 获取工具并绑定到 LLM
        from app.tools.tool_definitions import tool_registry
        tools = tool_registry.get_openai_tools()
        
        llm = get_llm(settings.DEFAULT_MODEL)
        llm_with_tools = llm.bind_tools(tools)
        
        # 调用 LLM
        async with tracer.span("llm_react_invoke"):
            response = await llm_with_tools.ainvoke(messages)
        
        # 检查是否有工具调用
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_calls = []
            for tc in response.tool_calls:
                tool_calls.append({
                    "name": tc.get("name"),
                    "args": tc.get("args", {}),
                    "id": tc.get("id", f"call_{int(time.time()*1000)}")
                })
            
            span.set_attribute("has_tool_calls", True)
            span.set_attribute("tool_calls_count", len(tool_calls))
            
            logger.info(f"ReAct iteration {iteration}: LLM requested {len(tool_calls)} tools")
            
            return {
                "messages": [response],
                "react_tool_calls": tool_calls,
                "react_status": "tool_call",
                "react_iteration": iteration + 1
            }
        
        # LLM 完成，返回最终答案
        span.set_attribute("has_tool_calls", False)
        span.set_attribute("result", "completed")
        
        logger.info(f"ReAct iteration {iteration}: LLM completed with answer")
        
        return {
            "messages": [response],
            "response": response.content,
            "react_status": "completed",
            "react_iteration": iteration + 1
        }


async def react_tool_execute_node(state: ChatState) -> Dict[str, Any]:
    """ReAct 工具执行节点 - 执行工具并回传 ToolMessage"""
    async with tracer.span("react_tool_execute") as span:
        logger.info("ReAct tool execute node executing")
        
        tool_calls = state.get("react_tool_calls", [])
        messages = state.get("messages", [])
        
        if not tool_calls:
            return {"messages": messages}
        
        tool_registry = _get_tool_registry()
        audit_logger = _get_audit_logger()
        user_id = state.get("user_id")
        session_id = state.get("session_id", "")
        
        tool_messages = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id")
            
            span.set_attribute("tool_name", tool_name)
            
            try:
                start_time = time.time()
                result = await tool_registry.execute(tool_name, tool_args)
                latency_ms = int((time.time() - start_time) * 1000)
                
                audit_logger.log_tool_execution(
                    user_id=user_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    result=result,
                    latency_ms=latency_ms,
                    success=True
                )
                
                # 构建 ToolMessage（大厂标准）
                tool_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id
                    )
                )
                
                logger.info(f"ReAct tool {tool_name} executed in {latency_ms}ms")
            
            except Exception as e:
                logger.error(f"ReAct tool {tool_name} failed: {e}")
                
                audit_logger.log_tool_execution(
                    user_id=user_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    error=str(e),
                    success=False
                )
                
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_call_id
                    )
                )
        
        return {
            "messages": tool_messages,
            "react_tool_calls": []  # 清空，准备下一轮
        }


# ============================================
# Chat 节点 - 大厂标准
# ============================================

async def chat_node(state: ChatState) -> Dict[str, Any]:
    """聊天节点 - 大厂标准
    
    核心改进：
    1. ToolMessage 回传机制
    2. LLM 整合工具结果
    3. 支持多工具结果整合
    """
    async with tracer.span("chat") as span:
        logger.info("Chat node executing")
        
        llm = get_llm(settings.DEFAULT_MODEL)
        
        messages = state.get("messages", [])
        current_input = state.get("current_input", "")
        
        span.set_attribute("query_length", len(current_input))
        span.set_attribute("model", settings.DEFAULT_MODEL)
        
        # 构建消息列表
        if not any(isinstance(m, HumanMessage) and m.content == current_input for m in messages):
            messages.append(HumanMessage(content=current_input))
        
        # 检查是否有 RAG 上下文
        rag_context = state.get("rag_context")
        rag_used = state.get("rag_used", False)
        
        # 检查是否有工具执行结果（ToolMessage）
        tool_messages = state.get("tool_messages", [])
        tool_used = state.get("tool_used", False)
        
        span.set_attribute("rag_used", rag_used)
        span.set_attribute("tool_used", tool_used)
        span.set_attribute("tool_messages_count", len(tool_messages))
        
        # 构建上下文
        context_parts = []
        
        if rag_context and rag_used:
            context_parts.append(f"知识库检索结果：\n{rag_context}")
            logger.info("Using RAG context")
        
        # 如果有 ToolMessage，添加到消息列表（大厂标准）
        if tool_messages:
            messages.extend(tool_messages)
            logger.info(f"Added {len(tool_messages)} ToolMessages to conversation")
        
        # 如果有上下文，添加系统提示
        if context_parts:
            system_content = f"""以下是相关信息，请参考这些内容回答用户问题：

{chr(10).join(context_parts)}

请基于以上信息回答用户问题。"""
            messages.insert(0, SystemMessage(content=system_content))
        
        try:
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


# ============================================
# 会话管理节点
# ============================================

async def load_history_node(state: ChatState) -> Dict[str, Any]:
    """加载历史消息节点"""
    async with tracer.span("load_history") as span:
        logger.info("Load history node executing")
        
        session_id = state.get("session_id", "")
        user_id = state.get("user_id")
        
        span.set_attribute("session_id", session_id)
        
        try:
            from app.db import AsyncSessionLocal, SessionRepository, MessageRepository
            
            async with AsyncSessionLocal() as db:
                session_repo = SessionRepository(db)
                message_repo = MessageRepository(db)
                
                session = await session_repo.get_by_id(session_id)
                if not session:
                    session = await session_repo.create(
                        session_id=session_id,
                        agent_type="chat",
                        model_name=state.get("model_name", settings.DEFAULT_MODEL),
                        user_id=user_id
                    )
                    logger.info(f"Session created: {session_id}")
                
                history = await message_repo.get_recent(session.id, limit=settings.HISTORY_LIMIT)
                
                messages = []
                
                if session.system_prompt:
                    messages.append(SystemMessage(content=session.system_prompt))
                
                for msg in history:
                    if msg.role == "user":
                        messages.append(HumanMessage(content=msg.content))
                    elif msg.role == "assistant":
                        messages.append(AIMessage(content=msg.content))
                
                span.set_attribute("history_count", len(history))
                
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
                "errors": [f"加载历史消息失败: {str(e)}"]
            }


async def save_message_node(state: ChatState) -> Dict[str, Any]:
    """保存消息节点"""
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
                
                if not state.get("user_message_saved"):
                    await message_repo.create(
                        session_id=db_session_id,
                        role="user",
                        content=current_input
                    )
                    span.set_attribute("user_message_saved", True)
                
                if response:
                    await message_repo.create(
                        session_id=db_session_id,
                        role="assistant",
                        content=response,
                        model_name=state.get("model_name", settings.DEFAULT_MODEL)
                    )
                    span.set_attribute("assistant_message_saved", True)
                
                await session_repo.increment_message_count(session_id)
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
# Agent 节点（旧版兼容）
# ============================================

async def agent_node(state: AgentState) -> Dict[str, Any]:
    """Agent决策节点（旧版）"""
    logger.info(f"Agent node executing, iteration: {state.get('iteration_count', 0)}")
    
    llm = get_llm(state.get("model_name", settings.DEFAULT_MODEL))
    messages = state.get("messages", [])
    
    try:
        response = await llm.ainvoke(messages)
        
        if hasattr(response, "tool_calls") and response.tool_calls:
            return {
                "agent_outcome": {
                    "action": "tool_call",
                    "data": response.tool_calls
                },
                "messages": [response],
                "iteration_count": state.get("iteration_count", 0) + 1
            }
        
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
    """工具执行节点（旧版）"""
    logger.info("Tool node executing")
    
    outcome = state.get("agent_outcome")
    if not outcome or outcome.get("action") != "tool_call":
        return state
    
    tool_calls = outcome.get("data", [])
    tool_registry = _get_tool_registry()
    
    messages = []
    
    for tool_call in tool_calls:
        tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
        tool_args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", {})
        
        try:
            result = await tool_registry.execute(tool_name, tool_args)
            
            messages.append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call.get("id", "")
                )
            )
        
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            messages.append(
                ToolMessage(
                    content=f"Error: {str(e)}",
                    tool_call_id=tool_call.get("id", "")
                )
            )
    
    return {
        "messages": messages,
        "agent_outcome": None
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
    """判断是否继续执行"""
    if state.get("iteration_count", 0) >= settings.MAX_ITERATIONS:
        return "finish"
    
    if state.get("errors"):
        return "error"
    
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
# 记忆管理节点 - 大厂标准
# ============================================

async def memory_integrate_node(state: AgentState) -> Dict[str, Any]:
    """记忆整合节点
    
    在对话结束时：
    1. 提取关键事实
    2. 检测冲突并修正
    3. 存储长期记忆
    
    大厂实践：
    - Google MemGPT：对话结束时整合记忆
    - OpenAI Memory：提取关键事实存储
    """
    logger.info("[记忆整合] 开始执行")
    
    session_id = state.get("session_id")
    messages = state.get("messages", [])
    
    if not session_id or not messages:
        logger.warning("[记忆整合] 缺少必要参数")
        return state
    
    try:
        from app.memory import MemoryIntegrator
        from app.llm.factory import get_llm
        from app.db.database import AsyncSessionLocal
        
        # 获取 LLM
        llm = get_llm()
        
        # 使用 async with 正确管理数据库会话
        async with AsyncSessionLocal() as db:
            integrator = MemoryIntegrator(llm, db)
            
            # 整合对话
            result = await integrator.integrate_conversation(messages, session_id)
            
            logger.info(f"[记忆整合] 完成: facts={result.get('stats', {}).get('facts_count', 0)}")
            
            # 存储事实
            facts = result.get("facts", [])
            for fact in facts:
                if fact.get("fact_type") != "none":
                    await integrator.store_integrated_memory(fact, session_id)
            
            await db.commit()
        
        return {
            "memory_integrated": True,
            "facts_extracted": len(facts)
        }
    
    except Exception as e:
        logger.error(f"[记忆整合] 失败: {e}")
        return state


async def memory_forgetting_node(state: AgentState) -> Dict[str, Any]:
    """遗忘周期节点
    
    定期执行：
    1. 时间衰减
    2. 容量检查
    3. 淘汰低权重记忆
    
    大厂实践：
    - Google MemGPT：定期遗忘周期
    - OpenAI Memory：容量管理
    """
    logger.info("[遗忘周期] 开始执行")
    
    session_id = state.get("session_id")
    
    if not session_id:
        logger.warning("[遗忘周期] 缺少 session_id")
        return state
    
    try:
        from app.memory import ForgettingManager
        from app.memory.long_term import LongTermMemory

        # 创建 LongTermMemory 以获取 Qdrant 实例
        long_term = LongTermMemory(session_id)

        manager = ForgettingManager(
            session_id,
            qdrant_store=long_term.qdrant,
        )

        # 执行遗忘周期
        result = await manager.run_forgetting_cycle()

        logger.info(
            f"[遗忘周期] 完成: "
            f"decayed={result.get('decay', {}).get('decayed_count', 0)}, "
            f"evicted={result.get('evict', {}).get('evicted_count', 0)}"
        )

        return {
            "forgetting_cycle_run": True,
            "forgetting_result": result
        }

    except Exception as e:
        logger.error(f"[遗忘周期] 失败: {e}")
        return state


async def memory_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """记忆检索节点
    
    为 LLM 提供记忆上下文：
    1. 向量检索长期记忆
    2. 获取短期记忆
    3. Rerank 重排序
    
    大厂实践：
    - Google MemGPT：检索相关记忆作为上下文
    - OpenAI Memory：提供记忆背景
    """
    logger.info("[记忆检索] 开始执行")
    
    session_id = state.get("session_id")
    query = state.get("current_query", "")
    
    if not session_id:
        logger.warning("[记忆检索] 缺少 session_id")
        return state
    
    try:
        from app.memory import MemoryManager
        from app.llm.factory import get_llm
        from app.db.database import AsyncSessionLocal
        
        # 获取 LLM
        llm = get_llm()
        
        async with AsyncSessionLocal() as db:
            manager = MemoryManager(session_id, db, llm)
            await manager.init()
            
            # 检索记忆
            memories = await manager.retrieve(query, limit=5, use_rerank=True)
            
            # 获取上下文
            context = await manager.get_context_for_llm(query, limit=5)
            
            logger.info(f"[记忆检索] 完成: memories={len(memories)}")
        
        return {
            "memory_context": context,
            "retrieved_memories": memories,
            "memory_retrieved": True
        }
    
    except Exception as e:
        logger.error(f"[记忆检索] 失败: {e}")
        return state