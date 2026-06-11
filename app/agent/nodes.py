"""LangGraph 节点实现"""
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from app.agent.state import AgentState, ChatState
from app.llm.factory import get_llm
from app.tools.registry import ToolRegistry
from app.core.logger import get_logger
from app.core.container import DIContainer
from app.core.interfaces import IRAGService
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


def get_rag_service():
    """获取 RAG 服务（容器单例）
    
    生产标准：
    - 使用容器获取单例
    - 只初始化一次
    - 后续请求直接获取
    """
    return DIContainer.get(IRAGService)


async def rag_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """RAG 检索节点
    
    在 Agent 决策前，先检索知识库获取相关上下文
    """
    logger.info("RAG retrieve node executing")
    
    # 获取用户问题
    messages = state.get("messages", [])
    current_input = state.get("current_input", "")
    
    # 找到最后一条用户消息
    user_query = current_input
    if not user_query:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_query = msg.content
                break
    
    if not user_query:
        return state
    
    try:
        # 检索知识库
        rag_service = get_rag_service()
        result = await rag_service.query(
            question=user_query,
            top_k=5,
            threshold=0.3
        )
        
        sources = result.get("sources", [])
        
        if sources:
            # 构建知识上下文
            context_parts = []
            for i, source in enumerate(sources):
                context_parts.append(f"[知识{i+1}] {source.get('content', '')}")
            
            knowledge_context = "\n".join(context_parts)
            
            # 添加系统消息，包含知识库内容
            system_msg = SystemMessage(
                content=f"""以下是知识库中检索到的相关内容，请参考这些内容回答用户问题：

{knowledge_context}

请基于以上知识库内容回答用户问题。如果知识库中没有相关信息，请根据你的知识回答。"""
            )
            
            return {
                "messages": [system_msg],
                "rag_context": knowledge_context,
                "rag_sources": sources
            }
        else:
            logger.info("RAG: 知识库中没有找到相关内容")
            return state
            
    except Exception as e:
        logger.error(f"RAG retrieve error: {e}")
        return state


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
    """聊天节点 - 增强版
    
    自动检索知识库，将检索结果作为上下文
    """
    logger.info("Chat node executing")
    
    llm = get_llm(settings.DEFAULT_MODEL)
    
    messages = state.get("messages", [])
    current_input = state.get("current_input", "")
    
    # 添加用户消息
    messages.append(HumanMessage(content=current_input))
    
    try:
        # 先检索知识库
        rag_result = None
        try:
            rag_service = get_rag_service()
            rag_result = await rag_service.query(
                question=current_input,
                top_k=5,
                threshold=0.3
            )
        except Exception as e:
            logger.warning(f"RAG检索失败（继续执行）: {e}")
        
        # 如果有检索结果，添加到消息中
        if rag_result and rag_result.get("sources"):
            sources = rag_result.get("sources", [])
            context_parts = []
            for i, source in enumerate(sources):
                context_parts.append(f"[知识{i+1}] {source.get('content', '')}")
            
            knowledge_context = "\n".join(context_parts)
            
            # 添加系统提示
            messages.insert(0, SystemMessage(
                content=f"""以下是知识库中检索到的相关内容，请参考这些内容回答用户问题：

{knowledge_context}

请基于以上知识库内容回答用户问题。如果知识库中没有相关信息，请根据你的知识回答。"""
            ))
            
            logger.info(f"RAG检索成功，找到 {len(sources)} 条相关知识")
        
        # 调用LLM生成响应
        response = await llm.ainvoke(messages)
        
        return {
            "messages": [AIMessage(content=response.content)],
            "response": response.content,
            "rag_used": rag_result is not None and rag_result.get("sources")
        }
    
    except Exception as e:
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