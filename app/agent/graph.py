"""LangGraph 图定义 + 编译"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agent.state import AgentState, ChatState
from app.agent.nodes import agent_node, tool_node, chat_node, error_handler_node
from app.agent.router import route_agent, route_after_tools, route_error
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
    """创建聊天图
    
    简化的聊天图，不使用工具
    """
    workflow = StateGraph(ChatState)
    
    # 添加节点
    workflow.add_node("chat", chat_node)
    
    # 设置入口和出口
    workflow.set_entry_point("chat")
    workflow.add_edge("chat", END)
    
    # 编译
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("Chat graph compiled")
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