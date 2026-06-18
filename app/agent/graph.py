"""LangGraph 图定义 + 编译 - 大厂标准

核心改进：
1. 合并工具决策流程
2. 使用原生 Function Calling
3. ToolMessage 回传机制
4. ReAct 循环支持
"""
import threading
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agent.state import AgentState, ChatState
from app.agent.nodes import (
    agent_node, tool_node, chat_node, error_handler_node,
    route_decision_node, rag_retrieve_node,
    load_history_node, save_message_node,
    tool_decision_node, tool_execute_node,
    react_agent_node, react_tool_execute_node,
    memory_retrieve_node, memory_integrate_node
)
from app.agent.router import route_agent, route_after_tools, route_error, route_chat, route_tool, route_react
from app.core.logger import get_logger

logger = get_logger(__name__)

# 线程安全的全局实例
_agent_app = None
_chat_app = None
_react_app = None
_lock = threading.Lock()


def create_agent_graph():
    """创建Agent图（旧版兼容）
    
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
    """创建聊天图 - 大厂标准
    
    完整流程：
    1. load_history: 加载历史消息
    2. memory_retrieve: 记忆检索（长期记忆上下文）
    3. route_decision: 智能路由（Function Calling）
    4. rag_retrieve: RAG 检索（按需）
    5. tool_decision: 工具决策（直接使用路由结果）
    6. tool_execute: 工具执行（ToolMessage 回传）
    7. chat: LLM 整合结果
    8. save_message: 保存消息
    9. memory_integrate: 记忆整合（提取关键事实）
    
    核心改进：
    - 合并工具决策流程
    - 使用原生 Function Calling
    - ToolMessage 回传机制
    - 记忆检索与整合
    """
    workflow = StateGraph(ChatState)
    
    # ===== 添加节点 =====
    workflow.add_node("load_history", load_history_node)
    workflow.add_node("memory_retrieve", memory_retrieve_node)
    workflow.add_node("route_decision", route_decision_node)
    workflow.add_node("rag_retrieve", rag_retrieve_node)
    workflow.add_node("tool_decision", tool_decision_node)
    workflow.add_node("tool_execute", tool_execute_node)
    workflow.add_node("chat", chat_node)
    workflow.add_node("save_message", save_message_node)
    workflow.add_node("memory_integrate", memory_integrate_node)
    
    # ===== 设置入口 =====
    workflow.set_entry_point("load_history")
    
    # ===== 添加边 =====
    workflow.add_edge("load_history", "memory_retrieve")
    workflow.add_edge("memory_retrieve", "route_decision")
    
    # route_decision -> rag_retrieve 或 tool_decision
    workflow.add_conditional_edges(
        "route_decision",
        route_chat,
        {
            "retrieve": "rag_retrieve",
            "chat": "tool_decision"
        }
    )
    
    workflow.add_edge("rag_retrieve", "tool_decision")
    
    # tool_decision -> tool_execute 或 chat
    workflow.add_conditional_edges(
        "tool_decision",
        route_tool,
        {
            "tool": "tool_execute",
            "chat": "chat"
        }
    )
    
    workflow.add_edge("tool_execute", "chat")
    workflow.add_edge("chat", "save_message")
    workflow.add_edge("save_message", "memory_integrate")
    workflow.add_edge("memory_integrate", END)
    
    # ===== 编译 =====
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("Chat graph compiled (大厂标准: Function Calling + ToolMessage + Memory)")
    return app


def create_react_graph():
    """创建 ReAct 循环图 - 大厂标准
    
    ReAct 循环流程：
    1. load_history: 加载历史消息
    2. react_agent: LLM 决策（bind_tools）
    3. react_tool_execute: 执行工具（ToolMessage 回传）
    4. 循环: react_agent -> react_tool_execute -> react_agent
    5. chat: 最终回答
    6. save_message: 保存消息
    
    大厂标准：
    - OpenAI: ReAct + Function Calling
    - Google: Agent 循环 + 工具执行
    - 阿里: 多轮对话 + 工具编排
    """
    workflow = StateGraph(ChatState)
    
    # ===== 添加节点 =====
    workflow.add_node("load_history", load_history_node)
    workflow.add_node("react_agent", react_agent_node)
    workflow.add_node("react_tool_execute", react_tool_execute_node)
    workflow.add_node("chat", chat_node)
    workflow.add_node("save_message", save_message_node)
    
    # ===== 设置入口 =====
    workflow.set_entry_point("load_history")
    
    # ===== 添加边 =====
    workflow.add_edge("load_history", "react_agent")
    
    # react_agent -> react_tool_execute 或 chat（条件边）
    workflow.add_conditional_edges(
        "react_agent",
        route_react,
        {
            "tool": "react_tool_execute",
            "chat": "chat",
            "end": END  # 达到最大轮次
        }
    )
    
    # react_tool_execute -> react_agent（循环）
    workflow.add_edge("react_tool_execute", "react_agent")
    
    workflow.add_edge("chat", "save_message")
    workflow.add_edge("save_message", END)
    
    # ===== 编译 =====
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("ReAct graph compiled (大厂标准: 多轮工具调用)")
    return app


# 全局图实例（线程安全）
_agent_app = None
_chat_app = None
_react_app = None
_lock = threading.Lock()


def get_agent_app():
    """获取Agent应用（线程安全）"""
    global _agent_app
    if _agent_app is None:
        with _lock:
            if _agent_app is None:
                _agent_app = create_agent_graph()
    return _agent_app


def get_chat_app():
    """获取聊天应用（线程安全）"""
    global _chat_app
    if _chat_app is None:
        with _lock:
            if _chat_app is None:
                _chat_app = create_chat_graph()
    return _chat_app


def get_react_app():
    """获取 ReAct 应用（线程安全）"""
    global _react_app
    if _react_app is None:
        with _lock:
            if _react_app is None:
                _react_app = create_react_graph()
    return _react_app