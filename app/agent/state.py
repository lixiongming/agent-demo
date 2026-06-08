"""LangGraph State 定义"""
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph.message import add_messages
from operator import add


class AgentState(TypedDict):
    """Agent状态
    
    LangGraph的核心状态定义，用于在节点间传递数据
    """
    
    # 消息历史（自动累加）
    messages: Annotated[List[dict], add_messages]
    
    # 当前输入
    input: str
    
    # Agent决策
    agent_outcome: Optional[dict]  # {"action": "tool_call" | "finish", "data": ...}
    
    # 工具调用结果
    tool_results: Annotated[List[dict], add]
    
    # 执行步骤
    steps: Annotated[List[str], add]
    
    # 错误信息
    errors: Annotated[List[str], add]
    
    # 会话信息
    session_id: str
    
    # 用户信息
    user_id: Optional[int]
    
    # 配置
    model_name: str
    temperature: float
    
    # 计数
    iteration_count: int
    
    # 最终输出
    final_response: Optional[str]


class ChatState(TypedDict):
    """聊天状态 - 简化版"""
    
    messages: Annotated[List[dict], add_messages]
    session_id: str
    current_input: str
    response: Optional[str]


class ToolState(TypedDict):
    """工具执行状态"""
    
    tool_name: str
    tool_input: dict
    tool_output: Optional[dict]
    error: Optional[str]
    success: bool