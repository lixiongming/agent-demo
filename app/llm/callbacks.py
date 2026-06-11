"""LLM 回调 - 日志、监控、成本"""
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from app.core.logger import get_logger
from app.config import get_settings
import time

logger = get_logger(__name__)
settings = get_settings()


class LLMCallbackHandler(BaseCallbackHandler):
    """LLM回调处理器
    
    用于日志记录、性能监控和成本计算
    """
    
    def __init__(self):
        self.start_time = None
        self.token_count = 0
        self.cost = 0.0
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any
    ) -> None:
        """LLM开始调用"""
        self.start_time = time.time()
        logger.info(f"LLM started: {serialized.get('name', 'unknown')}")
        logger.debug(f"Prompts: {prompts[:1]}")  # 只记录第一个
    
    def on_llm_end(
        self,
        response: Any,
        **kwargs: Any
    ) -> None:
        """LLM结束调用"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        # 计算token
        if hasattr(response, "llm_output"):
            token_usage = response.llm_output.get("token_usage", {})
            self.token_count = token_usage.get("total_tokens", 0)
        
        logger.info(
            f"LLM completed: "
            f"tokens={self.token_count}, "
            f"time={elapsed:.2f}s"
        )
    
    def on_llm_error(
        self,
        error: Exception,
        **kwargs: Any
    ) -> None:
        """LLM调用错误"""
        logger.error(f"LLM error: {error}")
    
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any
    ) -> None:
        """工具开始执行"""
        logger.info(f"Tool started: {serialized.get('name', 'unknown')}")
        logger.debug(f"Input: {input_str}")
    
    def on_tool_end(
        self,
        output: str,
        **kwargs: Any
    ) -> None:
        """工具执行结束"""
        logger.info(f"Tool completed: output={output[:100]}")
    
    def on_tool_error(
        self,
        error: Exception,
        **kwargs: Any
    ) -> None:
        """工具执行错误"""
        logger.error(f"Tool error: {error}")
    
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        """链开始"""
        logger.info(f"Chain started: {serialized.get('name', 'unknown')}")
    
    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        """链结束"""
        logger.info("Chain completed")


class CostTracker(BaseCallbackHandler):
    """成本追踪器"""
    
    # 价格表（每1000 tokens）
    PRICES = {
        "qwen3-max": {"input": 0.04, "output": 0.12},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002}
    }
    
    def __init__(self, model: str = "qwen3-max"):
        self.model = model
        self.total_cost = 0.0
        self.total_tokens = 0
    
    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """计算成本"""
        if hasattr(response, "llm_output"):
            token_usage = response.llm_output.get("token_usage", {})
            input_tokens = token_usage.get("prompt_tokens", 0)
            output_tokens = token_usage.get("completion_tokens", 0)
            
            prices = self.PRICES.get(self.model, {"input": 0.01, "output": 0.01})
            cost = (
                input_tokens * prices["input"] / 1000 +
                output_tokens * prices["output"] / 1000
            )
            
            self.total_cost += cost
            self.total_tokens += input_tokens + output_tokens
            
            logger.info(f"Cost: ${cost:.4f}, Total: ${self.total_cost:.4f}")
    
    def get_report(self) -> dict:
        """获取成本报告"""
        return {
            "model": self.model,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost
        }


def get_callback_handler() -> LLMCallbackHandler:
    """获取回调处理器"""
    return LLMCallbackHandler()


def get_cost_tracker(model: str) -> CostTracker:
    """获取成本追踪器"""
    return CostTracker(model)