"""工具注册中心"""
from typing import Dict, List, Any, Optional, Callable
from langchain_core.tools import Tool, StructuredTool
from app.core.logger import get_logger
from app.core.exceptions import ToolException

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册中心
    
    管理所有可用工具的注册和执行
    """
    
    _instance = None
    _tools: Dict[str, Tool] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance
    
    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"Tool registered: {tool.name}")
    
    def register_function(
        self,
        name: str,
        func: Callable,
        description: str,
        args_schema: Optional[Any] = None
    ):
        """注册函数为工具"""
        if args_schema:
            tool = StructuredTool(
                name=name,
                func=func,
                description=description,
                args_schema=args_schema
            )
        else:
            tool = Tool(
                name=name,
                func=func,
                description=description
            )
        self.register(tool)
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())
    
    async def execute(self, name: str, args: dict) -> Any:
        """执行工具"""
        tool = self.get_tool(name)
        if not tool:
            raise ToolException(f"Tool not found: {name}", name)
        
        try:
            logger.info(f"Executing tool: {name} with args: {args}")
            
            # 同步工具
            if not hasattr(tool.func, "__call__"):
                raise ToolException(f"Tool function not callable: {name}", name)
            
            # 执行
            result = tool.func(**args) if args else tool.func()
            
            logger.info(f"Tool {name} executed successfully")
            return result
        
        except Exception as e:
            logger.error(f"Tool execution error: {name} - {e}")
            raise ToolException(str(e), name)
    
    def to_langchain_tools(self) -> List[Tool]:
        """转换为LangChain工具列表"""
        return self.list_tools()
    
    def get_tool_info(self, name: str) -> dict:
        """获取工具信息"""
        tool = self.get_tool(name)
        if not tool:
            return {}
        
        return {
            "name": tool.name,
            "description": tool.description,
            "args_schema": str(tool.args_schema) if hasattr(tool, "args_schema") else None
        }


# 全局注册中心
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """获取全局工具注册中心"""
    return _registry


def register_tool(tool: Tool):
    """注册工具到全局中心"""
    _registry.register(tool)