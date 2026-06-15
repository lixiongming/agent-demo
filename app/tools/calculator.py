"""计算工具 - 安全实现（生产标准）

使用 ast.parse() 安全解析数学表达式，避免 eval() 的代码注入风险

安全特性：
- 只允许数学运算（加减乘除、幂、括号）
- 只允许数学函数（sin, cos, sqrt, log 等）
- 禁止任何代码执行（import, exec, eval 等）
- 禁止变量赋值和函数定义
"""
from typing import Union
import ast
import math
import operator
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.tools.registry import register_tool, ToolConfig
from app.core.logger import get_logger

logger = get_logger(__name__)


# ============================================
# 安全的数学运算映射
# ============================================

# 允许的运算符
ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,  # 负号
    ast.UAdd: operator.pos,  # 正号
}

# 允许的数学函数
ALLOWED_FUNCTIONS = {
    'abs': abs,
    'round': round,
    'min': min,
    'max': max,
    'sum': sum,
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log,
    'log10': math.log10,
    'log2': math.log2,
    'exp': math.exp,
    'floor': math.floor,
    'ceil': math.ceil,
    'pow': pow,
    'factorial': math.factorial,
}

# 允许的数学常量
ALLOWED_CONSTANTS = {
    'pi': math.pi,
    'e': math.e,
    'inf': math.inf,
}


# ============================================
# 安全表达式解析器
# ============================================

class SafeExpressionEvaluator(ast.NodeVisitor):
    """安全的数学表达式解析器
    
    使用 ast.NodeVisitor 遍历表达式树，只允许数学运算
    禁止任何代码执行操作
    
    生产标准：
    - 白名单机制（只允许特定运算符和函数）
    - 深度限制（防止递归攻击）
    - 异常处理（返回友好错误信息）
    """
    
    def __init__(self, max_depth: int = 100):
        self.max_depth = max_depth
        self.current_depth = 0
    
    def evaluate(self, expression: str) -> Union[float, str]:
        """安全计算数学表达式
        
        Args:
            expression: 数学表达式（如 "1+2*3", "sqrt(16)", "sin(pi/2)"）
        
        Returns:
            计算结果或错误信息
        """
        try:
            # 1. 预处理表达式
            expression = expression.strip()
            
            # 2. 解析为 AST
            tree = ast.parse(expression, mode='eval')
            
            # 3. 遍历 AST 并计算
            result = self.visit(tree.body)
            
            # 4. 返回结果
            return result
        
        except SyntaxError as e:
            return f"表达式语法错误: {str(e)}"
        except ValueError as e:
            return f"计算错误: {str(e)}"
        except TypeError as e:
            return f"类型错误: {str(e)}"
        except ZeroDivisionError:
            return "计算错误: 除数不能为零"
        except OverflowError:
            return "计算错误: 结果超出范围"
        except RecursionError:
            return "计算错误: 表达式过于复杂"
        except Exception as e:
            logger.error(f"Calculator error: {e}")
            return f"计算错误: {str(e)}"
    
    def visit(self, node):
        """遍历 AST 节点
        
        Args:
            node: AST 节点
        
        Returns:
            计算结果
        
        Raises:
            ValueError: 不允许的操作
        """
        # 深度检查（防止递归攻击）
        self.current_depth += 1
        if self.current_depth > self.max_depth:
            raise ValueError("表达式嵌套深度超出限制")
        
        try:
            result = super().visit(node)
        finally:
            self.current_depth -= 1
        
        return result
    
    def visit_BinOp(self, node):
        """处理二元运算（加减乘除等）"""
        left = self.visit(node.left)
        right = self.visit(node.right)
        
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise ValueError(f"不允许的运算符: {op_type.__name__}")
        
        return ALLOWED_OPERATORS[op_type](left, right)
    
    def visit_UnaryOp(self, node):
        """处理一元运算（正负号）"""
        operand = self.visit(node.operand)
        
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise ValueError(f"不允许的运算符: {op_type.__name__}")
        
        return ALLOWED_OPERATORS[op_type](operand)
    
    def visit_Call(self, node):
        """处理函数调用"""
        # 检查函数名
        if not isinstance(node.func, ast.Name):
            raise ValueError("只允许调用简单函数")
        
        func_name = node.func.id
        if func_name not in ALLOWED_FUNCTIONS:
            raise ValueError(f"不允许的函数: {func_name}")
        
        # 计算参数
        args = [self.visit(arg) for arg in node.args]
        
        # 调用函数
        return ALLOWED_FUNCTIONS[func_name](*args)
    
    def visit_Name(self, node):
        """处理变量名（常量）"""
        name = node.id
        
        if name in ALLOWED_CONSTANTS:
            return ALLOWED_CONSTANTS[name]
        
        raise ValueError(f"不允许的变量: {name}")
    
    def visit_Constant(self, node):
        """处理常量（数字）"""
        # Python 3.8+ 使用 Constant 节点
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不允许的常量类型: {type(node.value)}")
    
    def visit_Num(self, node):
        """处理数字（Python 3.7 兼容）"""
        return node.n
    
    def visit_Expression(self, node):
        """处理表达式"""
        return self.visit(node.body)
    
    def generic_visit(self, node):
        """处理未知节点（拒绝）"""
        raise ValueError(f"不允许的操作: {type(node).__name__}")


# ============================================
# 计算器函数
# ============================================

def calculator(expression: str) -> Union[float, str]:
    """安全计算器
    
    使用 ast.parse() 安全解析数学表达式，避免代码注入
    
    Args:
        expression: 数学表达式（如 "1+2", "sqrt(16)", "sin(pi/2)"）
    
    Returns:
        计算结果或错误信息
    
    示例:
        >>> calculator("1+2*3")
        7
        >>> calculator("sqrt(16)")
        4.0
        >>> calculator("sin(pi/2)")
        1.0
        >>> calculator("__import__('os').system('rm -rf /')")  # 安全拒绝
        "计算错误: 不允许的变量: __import__"
    """
    evaluator = SafeExpressionEvaluator()
    return evaluator.evaluate(expression)


# ============================================
# 工具注册
# ============================================

class CalculatorInput(BaseModel):
    """计算器输入参数"""
    expression: str = Field(
        ...,
        description="数学表达式（如：1+2、sqrt(16)、sin(pi/2)、2**10）"
    )


def calculator_tool():
    """创建计算器工具（生产标准）"""
    tool = StructuredTool(
        name="calculator",
        func=calculator,  # 同步函数
        description="""数学计算器（安全实现）。

功能：
- 基本运算：加减乘除、幂、取余
- 数学函数：sqrt, sin, cos, tan, log, exp, floor, ceil
- 数学常量：pi, e
- 括号运算

安全特性：
- 只允许数学运算，禁止代码执行
- 白名单机制，防止代码注入

示例：
- "1+2*3" → 7
- "sqrt(16)" → 4.0
- "sin(pi/2)" → 1.0
- "2**10" → 1024
- "log(100, 10)" → 2.0
""",
        args_schema=CalculatorInput
    )
    
    # 配置：超时5秒，每分钟200次，失败10次熔断
    config = ToolConfig(
        name="calculator",
        description="数学计算器（安全实现）",
        timeout=5,
        rate_limit=200,
        rate_period=60,
        failure_threshold=10,
        recovery_timeout=30,
        max_retries=1
    )
    
    register_tool(tool, config)
    return tool


# 自动注册
calculator_tool()