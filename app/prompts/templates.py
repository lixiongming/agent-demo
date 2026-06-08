"""提示词模板管理

功能：
- 模板化管理
- 参数化配置
- 多场景支持
- 版本控制
"""
from typing import Dict, Any, Optional, List
from string import Template
import json
from pathlib import Path


class PromptTemplates:
    """提示词模板管理类
    
    功能：
    - 统一管理
    - 动态生成
    - 参数验证
    """
    
    # 系统提示词模板
    SYSTEM_PROMPTS = {
        "chat": """你是一个智能助手，名叫"通义千问"。
你的职责是：
- 回答用户的问题
- 提供准确、有用的信息
- 保持友好、专业的态度

请根据用户的问题给出清晰的回答。""",
        
        "rag": """你是一个知识检索助手。
你的职责是：
- 基于提供的文档内容回答问题
- 如果文档中没有相关信息，请明确说明
- 回答要准确、详细，并引用来源

请根据以下文档内容回答用户的问题。""",
        
        "code": """你是一个编程助手。
你的职责是：
- 帮助用户编写、调试代码
- 解释代码逻辑
- 提供最佳实践建议

请用清晰、简洁的方式回答编程相关问题。""",
        
        "analysis": """你是一个数据分析助手。
你的职责是：
- 分析数据趋势
- 提供数据洞察
- 给出数据建议

请基于数据给出专业的分析结果。"""
    }
    
    # RAG提示词模板
    RAG_PROMPTS = {
        "default": Template("""基于以下文档内容回答问题。

文档内容：
$context

问题：$question

请根据文档内容给出准确、详细的回答。如果文档中没有相关信息，请说明。"找不到相关信息"。"""),
        
        "concise": Template("""根据以下内容回答问题（简洁版）：

内容：$context

问题：$question

请用简洁的语言回答。"""),
        
        "detailed": Template("""请详细分析以下文档内容并回答问题。

文档内容：
$context

问题：$question

要求：
1. 详细分析文档内容
2. 给出完整的回答
3. 引用相关段落
4. 如果信息不足，请说明""")
    }
    
    # Agent提示词模板
    AGENT_PROMPTS = {
        "react": Template("""你是一个智能Agent，可以使用工具完成任务。

可用工具：
$tools

当前任务：$task

请按以下格式思考和行动：
思考：分析当前情况
行动：选择工具执行
观察：查看执行结果
...重复直到完成任务

最终答案：给出最终结果"""),
        
        "planning": Template("""你是一个规划Agent，需要分解任务并执行。

任务：$task

请按以下步骤执行：
1. 分析任务需求
2. 制定执行计划
3. 逐步执行
4. 验证结果

当前步骤：$current_step""")
    }
    
    # 工具调用提示词
    TOOL_PROMPTS = {
        "search": Template("""搜索工具使用提示：

搜索关键词：$query
搜索范围：$scope

请返回相关搜索结果。"""),
        
        "calculator": Template("""计算工具使用提示：

计算表达式：$expression

请计算并返回结果。""")
    }
    
    # 对话提示词模板
    CONVERSATION_PROMPTS = {
        "greeting": """你好！我是智能助手，很高兴为你服务。
有什么我可以帮助你的吗？""",
        
        "clarification": Template("""我需要更多信息来准确回答你的问题。

当前问题：$question

请提供以下信息：
$clarification_points"""),
        
        "follow_up": Template("""基于之前的对话，我有以下补充问题：

历史对话：
$history

请继续回答或提供更多信息。""")
    }
    
    @classmethod
    def get_system_prompt(cls, prompt_type: str) -> str:
        """获取系统提示词
        
        Args:
            prompt_type: 提示词类型
            
        Returns:
            系统提示词
        """
        return cls.SYSTEM_PROMPTS.get(prompt_type, cls.SYSTEM_PROMPTS["chat"])
    
    @classmethod
    def get_rag_prompt(
        cls,
        context: str,
        question: str,
        style: str = "default"
    ) -> str:
        """获取RAG提示词
        
        Args:
            context: 上下文内容
            question: 问题
            style: 风格
            
        Returns:
            RAG提示词
        """
        template = cls.RAG_PROMPTS.get(style, cls.RAG_PROMPTS["default"])
        return template.substitute(context=context, question=question)
    
    @classmethod
    def get_agent_prompt(
        cls,
        task: str,
        tools: str = "",
        current_step: str = "",
        agent_type: str = "react"
    ) -> str:
        """获取Agent提示词
        
        Args:
            task: 任务
            tools: 工具列表
            current_step: 当前步骤
            agent_type: Agent类型
            
        Returns:
            Agent提示词
        """
        template = cls.AGENT_PROMPTS.get(agent_type, cls.AGENT_PROMPTS["react"])
        return template.substitute(
            task=task,
            tools=tools,
            current_step=current_step
        )
    
    @classmethod
    def get_tool_prompt(
        cls,
        tool_name: str,
        **kwargs
    ) -> str:
        """获取工具提示词
        
        Args:
            tool_name: 工具名称
            **kwargs: 参数
            
        Returns:
            工具提示词
        """
        template = cls.TOOL_PROMPTS.get(tool_name)
        if template:
            return template.substitute(**kwargs)
        return ""
    
    @classmethod
    def get_conversation_prompt(
        cls,
        prompt_type: str,
        **kwargs
    ) -> str:
        """获取对话提示词
        
        Args:
            prompt_type: 提示词类型
            **kwargs: 参数
            
        Returns:
            对话提示词
        """
        if prompt_type == "greeting":
            return cls.CONVERSATION_PROMPTS["greeting"]
        
        template = cls.CONVERSATION_PROMPTS.get(prompt_type)
        if template:
            return template.substitute(**kwargs)
        return ""
    
    @classmethod
    def list_available_prompts(cls) -> Dict[str, List[str]]:
        """列出所有可用提示词"""
        return {
            "system": list(cls.SYSTEM_PROMPTS.keys()),
            "rag": list(cls.RAG_PROMPTS.keys()),
            "agent": list(cls.AGENT_PROMPTS.keys()),
            "tool": list(cls.TOOL_PROMPTS.keys()),
            "conversation": list(cls.CONVERSATION_PROMPTS.keys())
        }


def get_prompt(
    prompt_type: str,
    **kwargs
) -> str:
    """快捷获取提示词
    
    Args:
        prompt_type: 提示词类型
        **kwargs: 参数
        
    Returns:
        提示词
    """
    templates = PromptTemplates()
    
    if prompt_type in PromptTemplates.SYSTEM_PROMPTS:
        return PromptTemplates.get_system_prompt(prompt_type)
    elif prompt_type == "rag":
        return PromptTemplates.get_rag_prompt(**kwargs)
    elif prompt_type in PromptTemplates.AGENT_PROMPTS:
        return PromptTemplates.get_agent_prompt(prompt_type, **kwargs)
    elif prompt_type in PromptTemplates.CONVERSATION_PROMPTS:
        return PromptTemplates.get_conversation_prompt(prompt_type, **kwargs)
    
    return ""


# 预定义的常用提示词
COMMON_PROMPTS = {
    # 聊天场景
    "chat_default": PromptTemplates.get_system_prompt("chat"),
    
    # RAG场景
    "rag_default": PromptTemplates.RAG_PROMPTS["default"].template,
    
    # Agent场景
    "agent_react": PromptTemplates.AGENT_PROMPTS["react"].template,
    
    # 问候语
    "greeting": PromptTemplates.CONVERSATION_PROMPTS["greeting"]
}