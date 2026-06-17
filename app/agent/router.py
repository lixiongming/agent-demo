"""条件路由 - 大厂标准"""
from typing import Literal
from app.agent.state import AgentState, ChatState
from app.agent.nodes import should_continue
from app.core.logger import get_logger

logger = get_logger(__name__)


def route_agent(state: AgentState) -> Literal["tools", "end", "error"]:
    """Agent路由"""
    outcome = state.get("agent_outcome")
    
    if not outcome:
        return "tools"
    
    action = outcome.get("action")
    
    if action == "tool_call":
        return "tools"
    elif action == "finish":
        return "end"
    
    return "end"


def route_after_tools(state: AgentState) -> Literal["agent", "error"]:
    """工具执行后路由"""
    tool_results = state.get("tool_results", [])
    
    for result in tool_results:
        if not result.get("success"):
            return "error"
    
    return "agent"


def route_error(state: AgentState) -> Literal["agent", "end"]:
    """错误路由"""
    errors = state.get("errors", [])
    
    if len(errors) > 3:
        return "end"
    
    return "agent"


def route_chat(state: ChatState) -> Literal["retrieve", "chat"]:
    """聊天路由 - 根据路由决策"""
    route_decision = state.get("route_decision", {})
    needs_retrieval = route_decision.get("needs_retrieval", False)
    
    logger.info(f"route_chat: needs_retrieval={needs_retrieval}")
    
    if needs_retrieval:
        return "retrieve"
    else:
        return "chat"


def route_tool(state: ChatState) -> Literal["tool", "chat"]:
    """工具路由 - 根据工具决策"""
    tool_decision = state.get("tool_decision", {})
    needs_tool = tool_decision.get("needs_tool", False)
    
    logger.info(f"route_tool: needs_tool={needs_tool}")
    
    if needs_tool:
        return "tool"
    else:
        return "chat"


def route_react(state: ChatState) -> Literal["tool", "chat", "end"]:
    """ReAct 循环路由 - 大厂标准
    
    根据 react_status 决定下一步：
    - tool_call: 继续执行工具
    - completed: 完成，生成回答
    - max_iterations: 达到最大轮次，结束
    """
    react_status = state.get("react_status", "completed")
    
    logger.info(f"route_react: react_status={react_status}")
    
    if react_status == "tool_call":
        return "tool"
    elif react_status == "completed":
        return "chat"
    elif react_status == "max_iterations":
        return "end"
    
    return "chat"