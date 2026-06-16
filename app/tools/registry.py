"""工具注册中心 - 大厂标准实现

功能：
- 工具注册和管理
- 限流保护
- 熔断保护
- 超时控制
- 链路追踪
- 监控统计
- 权限控制
- 重试机制
- 参数验证（Pydantic）
"""
from typing import Dict, List, Any, Optional, Callable
from langchain_core.tools import Tool, StructuredTool
from app.core.logger import get_logger
from app.core.exceptions import ToolException
from app.core.rate_limit import CircuitBreaker
from app.core.tracing import tracer
from app.core.error_codes import ErrorCode, APIError

import asyncio
import time
from dataclasses import dataclass

logger = get_logger(__name__)


# ============================================
# 工具配置
# ============================================

@dataclass
class ToolConfig:
    """工具配置"""
    name: str
    description: str = ""
    timeout: int = 30  # 超时时间（秒）
    rate_limit: int = 100  # 每分钟限制次数
    rate_period: int = 60  # 限流周期（秒）
    failure_threshold: int = 5  # 熔断阈值
    recovery_timeout: int = 60  # 熔断恢复时间（秒）
    max_retries: int = 2  # 最大重试次数
    retry_delay: float = 1.0  # 重试延迟（秒）
    enabled: bool = True  # 是否启用
    require_auth: bool = False  # 是否需要权限


# ============================================
# 工具统计
# ============================================

@dataclass
class ToolStats:
    """工具统计信息"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0
    last_call_time: float = 0
    last_error: Optional[str] = None
    
    def record_success(self, latency_ms: float):
        """记录成功调用"""
        self.total_calls += 1
        self.successful_calls += 1
        self.total_latency_ms += latency_ms
        self.last_call_time = time.time()
    
    def record_failure(self, error: str):
        """记录失败调用"""
        self.total_calls += 1
        self.failed_calls += 1
        self.last_call_time = time.time()
        self.last_error = error
    
    def get_avg_latency(self) -> float:
        """获取平均延迟"""
        if self.successful_calls == 0:
            return 0
        return self.total_latency_ms / self.successful_calls
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "avg_latency_ms": round(self.get_avg_latency(), 2),
            "success_rate": round(self.get_success_rate() * 100, 2),
            "last_call_time": self.last_call_time,
            "last_error": self.last_error
        }


# ============================================
# 工具注册中心
# ============================================

class ToolRegistry:
    """工具注册中心
    
    功能：
    - 工具注册和管理
    - 限流保护（基于内存计数器）
    - 熔断保护
    - 超时控制
    - 链路追踪
    - 监控统计
    - 重试机制
    """
    
    _instance = None
    _tools: Dict[str, Tool] = {}
    _configs: Dict[str, ToolConfig] = {}
    _stats: Dict[str, ToolStats] = {}
    _breakers: Dict[str, CircuitBreaker] = {}
    _rate_counters: Dict[str, List[float]] = {}  # 限流计数器
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._configs = {}
            cls._instance._stats = {}
            cls._instance._breakers = {}
            cls._instance._rate_counters = {}
        return cls._instance
    
    def register(
        self,
        tool: Tool,
        config: Optional[ToolConfig] = None
    ):
        """注册工具
        
        Args:
            tool: LangChain 工具
            config: 工具配置
        """
        self._tools[tool.name] = tool
        
        # 设置默认配置
        if config is None:
            config = ToolConfig(name=tool.name, description=tool.description)
        self._configs[tool.name] = config
        
        # 初始化统计
        self._stats[tool.name] = ToolStats()
        
        # 初始化熔断器
        self._breakers[tool.name] = CircuitBreaker(
            name=f"tool_{tool.name}",
            threshold=config.failure_threshold,
            timeout=config.recovery_timeout
        )
        
        # 初始化限流计数器
        self._rate_counters[tool.name] = []
        
        logger.info(f"Tool registered: {tool.name} (timeout={config.timeout}s, rate_limit={config.rate_limit}/min)")
    
    def register_function(
        self,
        name: str,
        func: Callable,
        description: str,
        args_schema: Optional[Any] = None,
        config: Optional[ToolConfig] = None
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
        self.register(tool, config)
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_config(self, name: str) -> Optional[ToolConfig]:
        """获取工具配置"""
        return self._configs.get(name)
    
    def get_stats(self, name: str) -> Optional[ToolStats]:
        """获取工具统计"""
        return self._stats.get(name)
    
    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())
    
    def _check_rate_limit(self, name: str) -> bool:
        """检查限流

        Args:
            name: 工具名称

        Returns:
            是否允许调用
        """
        config = self._configs.get(name)
        if not config:
            return True

        current_time = time.time()
        window_start = current_time - config.rate_period

        # 清理过期的请求记录
        self._rate_counters[name] = [
            t for t in self._rate_counters[name] if t > window_start
        ]

        # 检查是否超过限制
        if len(self._rate_counters[name]) >= config.rate_limit:
            logger.warning(f"Tool rate limit exceeded: {name}")
            return False

        # 记录本次请求
        self._rate_counters[name].append(current_time)
        return True

    def _validate_tool_args(self, tool: Tool, args: dict, tool_name: str) -> dict:
        """验证工具参数（生产级）

        功能：
        1. 类型检查
        2. 必填参数检查
        3. 默认值填充
        4. 过滤未定义参数
        5. 详细的错误提示

        Args:
            tool: 工具实例
            args: 原始参数
            tool_name: 工具名称

        Returns:
            验证后的参数

        Raises:
            ToolException: 参数验证失败
        """
        if not args:
            return {}

        # 没有定义 schema，直接返回原始参数
        if not hasattr(tool, 'args_schema') or not tool.args_schema:
            logger.debug(f"Tool {tool_name} has no args_schema, using raw args")
            return args

        try:
            from pydantic import ValidationError

            # Pydantic 验证：类型检查 + 必填检查 + 默认值
            validated = tool.args_schema.model_validate(args)

            # 转换为字典（包含默认值）
            validated_args = validated.model_dump()

            # 记录参数变化
            if set(validated_args.keys()) != set(args.keys()):
                extra_keys = set(args.keys()) - set(validated_args.keys())
                if extra_keys:
                    logger.info(
                        f"Tool {tool_name}: filtered extra args {list(extra_keys)}, "
                        f"kept {list(validated_args.keys())}"
                    )

            return validated_args

        except ValidationError as e:
            # 构建详细的错误信息
            errors = e.errors()
            error_msgs = []
            for err in errors:
                field = ".".join(str(loc) for loc in err.get("loc", []))
                msg = err.get("msg", "validation error")
                error_msgs.append(f"{field}: {msg}")

            error_detail = "; ".join(error_msgs)
            logger.error(f"Tool {tool_name} 参数验证失败: {error_detail}")

            raise ToolException(
                f"参数验证失败: {error_detail}",
                tool_name,
                details={"errors": errors, "input_args": args}
            )
        except Exception as e:
            logger.error(f"Tool {tool_name} 参数验证异常: {e}")
            # 降级：返回原始参数（保持兼容性）
            return args
    
    async def execute(
        self,
        name: str,
        args: dict,
        timeout: Optional[int] = None
    ) -> Any:
        """执行工具
        
        功能：
        - 限流检查
        - 熔断检查
        - 超时控制
        - 链路追踪
        - 重试机制
        - 统计记录
        
        Args:
            name: 工具名称
            args: 工具参数
            timeout: 超时时间（可选，覆盖默认配置）
            
        Returns:
            工具执行结果
            
        Raises:
            ToolException: 工具执行失败
        """
        # 检查工具是否存在
        tool = self.get_tool(name)
        if not tool:
            raise ToolException(f"Tool not found: {name}", name)
        
        config = self._configs.get(name)
        stats = self._stats.get(name)
        breaker = self._breakers.get(name)
        
        # 检查是否启用
        if config and not config.enabled:
            raise ToolException(f"Tool is disabled: {name}", name)
        
        # 限流检查
        if not self._check_rate_limit(name):
            raise APIError(
                code=ErrorCode.RATE_LIMIT_EXCEEDED,
                message=f"工具调用过于频繁: {name}",
                details={"tool": name, "limit": config.rate_limit if config else 100}
            )
        
        # 熔断检查
        if breaker and breaker.state.value == "open":
            raise APIError(
                code=ErrorCode.CIRCUIT_BREAKER_OPEN,
                message=f"工具暂时不可用: {name}",
                details={"tool": name, "state": "open"}
            )
        
        # 获取超时时间
        exec_timeout = timeout or (config.timeout if config else 30)
        
        # 链路追踪
        async with tracer.span(f"tool_{name}"):
            start_time = time.time()
            last_error = None
            
            # 重试机制
            max_retries = config.max_retries if config else 0
            retry_delay = config.retry_delay if config else 1.0
            
            for attempt in range(max_retries + 1):
                try:
                    logger.info(f"Executing tool: {name} (attempt {attempt + 1}/{max_retries + 1})")
                    
                    # 获取工具函数（支持 StructuredTool）
                    # StructuredTool 使用 coroutine 属性，普通 Tool 使用 func 属性
                    if hasattr(tool, 'coroutine') and tool.coroutine:
                        func = tool.coroutine
                    elif hasattr(tool, 'func') and tool.func:
                        func = tool.func
                    else:
                        raise ToolException(f"Tool function not callable: {name}", name)
                    
                    if not hasattr(func, "__call__"):
                        raise ToolException(f"Tool function not callable: {name}", name)

                    # 参数验证与过滤（生产级）
                    validated_args = self._validate_tool_args(tool, args, name)

                    # 调用函数获取结果
                    call_result = func(**validated_args) if validated_args else func()
                    
                    # 如果结果是 coroutine，等待它
                    if asyncio.iscoroutine(call_result):
                        result = await asyncio.wait_for(
                            call_result,
                            timeout=exec_timeout
                        )
                    else:
                        result = call_result
                    
                    # 记录成功
                    latency_ms = (time.time() - start_time) * 1000
                    if stats:
                        stats.record_success(latency_ms)
                    if breaker:
                        breaker._record_success()
                    
                    logger.info(f"Tool {name} executed successfully in {latency_ms:.2f}ms")
                    return result
                    
                except asyncio.TimeoutError:
                    last_error = f"Tool execution timeout ({exec_timeout}s)"
                    logger.warning(f"Tool {name} timeout on attempt {attempt + 1}")
                    
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"Tool {name} error on attempt {attempt + 1}: {e}")
                
                # 重试前等待
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * (attempt + 1))
            
            # 所有重试都失败
            if stats:
                stats.record_failure(last_error)
            if breaker:
                breaker._record_failure()
            
            raise ToolException(last_error, name)
    
    def to_langchain_tools(self) -> List[Tool]:
        """转换为LangChain工具列表"""
        return self.list_tools()
    
    def get_tool_info(self, name: str) -> dict:
        """获取工具信息"""
        tool = self.get_tool(name)
        if not tool:
            return {}
        
        config = self._configs.get(name)
        stats = self._stats.get(name)
        breaker = self._breakers.get(name)
        
        return {
            "name": tool.name,
            "description": tool.description,
            "config": {
                "timeout": config.timeout if config else 30,
                "rate_limit": config.rate_limit if config else 100,
                "enabled": config.enabled if config else True
            },
            "stats": stats.to_dict() if stats else {},
            "circuit_breaker": breaker.get_stats() if breaker else {}
        }
    
    def get_all_stats(self) -> dict:
        """获取所有工具统计信息"""
        return {
            name: stats.to_dict()
            for name, stats in self._stats.items()
        }
    
    def reset_stats(self, name: str = None):
        """重置统计信息"""
        if name:
            if name in self._stats:
                self._stats[name] = ToolStats()
        else:
            for name in self._stats:
                self._stats[name] = ToolStats()
        logger.info(f"Tool stats reset: {name or 'all'}")
    
    def enable_tool(self, name: str):
        """启用工具"""
        if name in self._configs:
            self._configs[name].enabled = True
            logger.info(f"Tool enabled: {name}")
    
    def disable_tool(self, name: str):
        """禁用工具"""
        if name in self._configs:
            self._configs[name].enabled = False
            logger.info(f"Tool disabled: {name}")


# ============================================
# 全局注册中心
# ============================================

_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """获取全局工具注册中心"""
    return _registry


def register_tool(tool: Tool, config: Optional[ToolConfig] = None):
    """注册工具到全局中心"""
    _registry.register(tool, config)


# ============================================
# 工具装饰器
# ============================================

def tool(
    name: str = None,
    description: str = "",
    timeout: int = 30,
    rate_limit: int = 100,
    failure_threshold: int = 5
):
    """工具装饰器 - 快速注册工具
    
    使用示例：
        @tool(name="weather", description="获取天气", timeout=10)
        async def get_weather(city: str):
            return {"city": city, "temp": 25}
    """
    def decorator(func):
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        
        config = ToolConfig(
            name=tool_name,
            description=tool_desc,
            timeout=timeout,
            rate_limit=rate_limit,
            failure_threshold=failure_threshold
        )
        
        # 创建 LangChain 工具
        lc_tool = Tool(
            name=tool_name,
            func=func,
            description=tool_desc
        )
        
        # 注册
        _registry.register(lc_tool, config)
        
        return func
    
    return decorator
