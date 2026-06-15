"""LangGraph 图定义 + 编译"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agent.state import AgentState, ChatState
from app.agent.nodes import (
    agent_node, tool_node, chat_node, error_handler_node,
    route_decision_node, rag_retrieve_node,
    load_history_node, save_message_node,
    tool_decision_node, tool_execute_node
)
from app.agent.router import route_agent, route_after_tools, route_error, route_chat, route_tool
from app.core.logger import get_logger

logger = get_logger(__name__)


def create_agent_graph():
    """创建Agent图
    
    ReAct模式的Agent图
    """
    # 创建图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # 设置入口
    workflow.set_entry_point("agent")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "agent",
        route_agent,
        {
            "tools": "tools",
            "end": END,
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "agent": "agent",
            "error": "error_handler"
        }
    )
    
    workflow.add_conditional_edges(
        "error_handler",
        route_error,
        {
            "agent": "agent",
            "end": END
        }
    )
    
    # 编译图（带checkpointer）
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("Agent graph compiled")
    return app


def create_chat_graph():
    """创建聊天图 -（标准 Agent 图模式）

    完整流程：
    1. load_history: 加载历史消息和会话信息
    2. route_decision: 智能路由决策（是否检索知识库）
    3. rag_retrieve: RAG 检索（按需）
    4. tool_decision: 工具决策（是否调用工具）
    5. tool_execute: 工具执行（按需）
    6. chat: 生成响应
    7. save_message: 保存消息

    架构优势：
    - 统一入口，逻辑清晰
    - 每个节点职责单一
    - 支持链路追踪
    - 支持工具调用
    - 易于扩展和测试
    """
    workflow = StateGraph(ChatState)

    # ===== 添加节点 =====
    workflow.add_node("load_history", load_history_node)
    workflow.add_node("route_decision", route_decision_node)
    workflow.add_node("rag_retrieve", rag_retrieve_node)
    workflow.add_node("tool_decision", tool_decision_node)
    workflow.add_node("tool_execute", tool_execute_node)
    workflow.add_node("chat", chat_node)
    workflow.add_node("save_message", save_message_node)

    # ===== 设置入口 =====
    workflow.set_entry_point("load_history")

    # ===== 添加边 =====
    # load_history -> route_decision
    workflow.add_edge("load_history", "route_decision")

    # route_decision -> rag_retrieve 或 tool_decision（条件边）
    workflow.add_conditional_edges(
        "route_decision",
        route_chat,
        {
            "retrieve": "rag_retrieve",
            "chat": "tool_decision"
        }
    )

    # rag_retrieve -> tool_decision
    workflow.add_edge("rag_retrieve", "tool_decision")

    # tool_decision -> tool_execute 或 chat（条件边）
    workflow.add_conditional_edges(
        "tool_decision",
        route_tool,
        {
            "tool": "tool_execute",
            "chat": "chat"
        }
    )

    # tool_execute -> chat
    workflow.add_edge("tool_execute", "chat")

    # chat -> save_message
    workflow.add_edge("chat", "save_message")

    # save_message -> END
    workflow.add_edge("save_message", END)

    # ===== 编译 =====
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)

    logger.info("Chat graph compiled (production mode with tools support)")
    return app


# 全局图实例
_agent_app = None
_chat_app = None


def get_agent_app():
    """获取Agent应用"""
    global _agent_app
    if _agent_app is None:
        _agent_app = create_agent_graph()
    return _agent_app


def get_chat_app():
    """获取聊天应用"""
    global _chat_app
    if _chat_app is None:
        _chat_app = create_chat_graph()
    return _chat_app