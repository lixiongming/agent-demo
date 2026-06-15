"""工具注册中心

管理所有工具的描述、参数和执行逻辑
符合大厂标准：工具描述驱动，LLM自动决策
"""
from typing import Dict, Any, List, Optional
from app.core.logger import get_logger

logger = get_logger(__name__)


class ToolDefinition:
    """工具定义
    
    包含工具的完整描述，供LLM决策使用
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        examples: Optional[List[str]] = None,
        category: Optional[str] = None
    ):
        """
        Args:
            name: 工具名称
            description: 工具描述（LLM决策的关键）
            parameters: 工具参数定义
            examples: 使用示例
            category: 工具类别
        """
        self.name = name
        self.description = description
        self.parameters = parameters
        self.examples = examples or []
        self.category = category or "general"
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI Function Calling格式
        
        Returns:
            OpenAI工具定义格式
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.parameters.keys())
                }
            }
        }
    
    def to_prompt_format(self) -> str:
        """转换为提示词格式
        
        Returns:
            工具描述文本
        """
        params_desc = []
        for param_name, param_info in self.parameters.items():
            param_type = param_info.get("type", "string")
            param_desc = param_info.get("description", "")
            params_desc.append(f"  - {param_name} ({param_type}): {param_desc}")
        
        examples_str = ""
        if self.examples:
            examples_str = "\n示例:\n" + "\n".join([f"  - {ex}" for ex in self.examples])
        
        return f"""
工具名称: {self.name}
描述: {self.description}
参数:
{chr(10).join(params_desc)}
{examples_str}
类别: {self.category}
"""


class ToolRegistry:
    """工具注册中心
    
    管理所有工具，提供工具查询和执行功能
    符合大厂标准：工具注册驱动，LLM自动决策
    """
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具
        
        所有工具的描述都在这里定义，LLM根据描述自动决策
        """
        # 1. 天气查询工具
        self.register(ToolDefinition(
            name="get_weather",
            description="获取城市天气信息，包括温度、湿度、风向、气压、能见度等详细数据。支持城市名称（如：北京、上海）或城市代码查询。",
            parameters={
                "city": {
                    "type": "string",
                    "description": "城市名称（如：北京、上海、广州）或城市代码（如：101010100）"
                }
            },
            examples=[
                "北京天气怎么样",
                "上海天气如何",
                "广州的气温",
                "今天下雨吗"
            ],
            category="weather"
        ))
        
        # 2. 新闻查询工具
        self.register(ToolDefinition(
            name="news_query",
            description="查询新闻信息，支持热门新闻、最近新闻、搜索新闻、作者新闻等多种查询类型。返回新闻标题、作者、浏览量等信息。",
            parameters={
                "query_type": {
                    "type": "string",
                    "description": "查询类型：hot（热门）、recent（最近）、search（搜索）、author（作者）、stats（统计）",
                    "enum": ["hot", "recent", "search", "author", "stats"]
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词（可选）"
                },
                "author": {
                    "type": "string",
                    "description": "作者名称（可选）"
                }
            },
            examples=[
                "热门新闻",
                "最近有什么新闻",
                "搜索科技新闻",
                "新华社的新闻"
            ],
            category="news"
        ))
        
        # 3. 数据库查询工具
        self.register(ToolDefinition(
            name="mysql_query",
            description="查询数据库中的业务数据，支持订单、用户、商品、库存等数据查询。自动生成SQL查询语句，返回数据统计结果。",
            parameters={
                "query": {
                    "type": "string",
                    "description": "查询描述（如：查询最近一周的订单数量）"
                }
            },
            examples=[
                "查询订单数据",
                "最近一周的用户数量",
                "库存统计"
            ],
            category="database"
        ))
        
        # 4. 知识库检索工具
        self.register(ToolDefinition(
            name="knowledge_search",
            description="检索知识库中的文档、FAQ、教程等信息。支持产品功能、API接口、业务规则、常见问题等内容的检索。",
            parameters={
                "query": {
                    "type": "string",
                    "description": "检索关键词或问题"
                }
            },
            examples=[
                "产品功能介绍",
                "API接口文档",
                "如何使用"
            ],
            category="knowledge"
        ))
        
        # 5. 计算器工具
        self.register(ToolDefinition(
            name="calculator",
            description="执行数学计算，支持加减乘除、百分比、平方根等运算。",
            parameters={
                "expression": {
                    "type": "string",
                    "description": "数学表达式（如：1+2、3*4、10%等）"
                }
            },
            examples=[
                "计算1+2等于几",
                "3乘以4是多少",
                "10的平方根"
            ],
            category="math"
        ))
        
        logger.info(f"已注册 {len(self.tools)} 个工具")
    
    def register(self, tool: ToolDefinition):
        """注册工具
        
        Args:
            tool: 工具定义
        """
        self.tools[tool.name] = tool
        logger.info(f"工具已注册: {tool.name} ({tool.category})")
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义
        
        Args:
            name: 工具名称
        
        Returns:
            工具定义，不存在则返回None
        """
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[ToolDefinition]:
        """获取所有工具
        
        Returns:
            工具列表
        """
        return list(self.tools.values())
    
    def get_tools_by_category(self, category: str) -> List[ToolDefinition]:
        """按类别获取工具
        
        Args:
            category: 工具类别
        
        Returns:
            工具列表
        """
        return [tool for tool in self.tools.values() if tool.category == category]
    
    def get_tools_description(self) -> str:
        """获取所有工具的描述（供LLM决策使用）
        
        Returns:
            工具描述文本
        """
        descriptions = []
        for tool in self.tools.values():
            descriptions.append(tool.to_prompt_format())
        
        return "\n".join(descriptions)
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """获取OpenAI Function Calling格式的工具列表
        
        Returns:
            OpenAI工具列表
        """
        return [tool.to_openai_format() for tool in self.tools.values()]


# 全局工具注册中心
tool_registry = ToolRegistry()