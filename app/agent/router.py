"""条件路由"""
from typing import Literal
from app.agent.state import AgentState
from app.agent.nodes import should_continue


def route_agent(state: AgentState) -> Literal["tools", "end", "error"]:
    """Agent路由
    
    根据Agent决策路由到不同节点
    """
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
    # 检查是否有错误
    tool_results = state.get("tool_results", [])
    
    for result in tool_results:
        if not result.get("success"):
            return "error"
    
    return "agent"


def route_error(state: AgentState) -> Literal["agent", "end"]:
    """错误路由"""
    errors = state.get("errors", [])
    
    # 如果错误太多，直接结束
    if len(errors) > 3:
        return "end"
    
    # 尝试恢复
    return "agent"