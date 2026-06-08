"""计算工具"""
from typing import Union
from langchain_core.tools import Tool
from app.tools.registry import register_tool
import math


def calculator(expression: str) -> Union[float, str]:
    """计算器
    
    Args:
        expression: 数学表达式
    
    Returns:
        计算结果
    """
    try:
        # 安全计算
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "sqrt": math.sqrt,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "log10": math.log10, "exp": math.exp,
            "pi": math.pi, "e": math.e
        }
        
        # 替换数学函数
        code = expression
        for name, func in allowed_names.items():
            code = code.replace(name, f"allowed_names['{name}']")
        
        # 计算
        result = eval(code, {"__builtins__": {}, "allowed_names": allowed_names})
        
        return result
    
    except Exception as e:
        return f"计算错误: {str(e)}"


def calculator_tool():
    """创建计算器工具"""
    tool = Tool(
        name="calculator",
        func=calculator,
        description="数学计算器。输入数学表达式，返回计算结果。支持基本运算和数学函数如sqrt, sin, cos, log等。"
    )
    register_tool(tool)
    return tool


# 自动注册
calculator_tool()