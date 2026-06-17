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
    """聊天状态 -（标准 Agent 图模式）

    统一架构：
    - 所有业务逻辑在 Agent 图中处理
    - ChatService 只做入口适配
    - 支持完整的会话生命周期
    - 支持工具调用
    - 支持 ReAct 循环
    """

    # ===== 消息相关 =====
    messages: Annotated[List[dict], add_messages]
    current_input: str
    response: Optional[str]

    # ===== 会话相关 =====
    session_id: str
    user_id: Optional[int]
    db_session_id: Optional[int]  # 数据库会话 ID
    system_prompt: Optional[str]
    model_name: Optional[str]

    # ===== 历史消息 =====
    history_loaded: bool
    history_count: int

    # ===== 智能路由 =====
    route_decision: Optional[dict]  # {"needs_retrieval": bool, "tool_calls": list, "method": str}

    # ===== RAG 检索 =====
    rag_context: Optional[str]
    rag_sources: Annotated[List[dict], add]
    rag_used: bool
    rag_strategy: Optional[str]
    rag_score: float

    # ===== 工具调用 =====
    tool_decision: Optional[dict]  # {"needs_tool": bool, "tool_calls": list}
    tool_results: Annotated[List[dict], add]
    tool_messages: Annotated[List[dict], add]  # ToolMessage 格式
    tool_used: bool

    # ===== ReAct 循环 =====
    react_iteration: int  # 当前迭代次数
    react_status: str  # tool_call / completed / max_iterations
    react_tool_calls: List[dict]  # 当前轮次的工具调用

    # ===== 消息保存 =====
    user_message_saved: bool
    assistant_message_saved: bool

    # ===== 错误处理 =====
    errors: Annotated[List[str], add]


class ToolState(TypedDict):
    """工具执行状态"""
    
    tool_name: str
    tool_input: dict
    tool_output: Optional[dict]
    error: Optional[str]
    success: bool