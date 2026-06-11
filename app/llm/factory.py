"""LLM 工厂 - 多模型支持"""
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from app.config import get_settings
from app.core.logger import get_logger
from app.core.exceptions import LLMException

logger = get_logger(__name__)
settings = get_settings()


class LLMFactory:
    """LLM工厂
    
    支持多种LLM模型的创建和管理
    """
    
    _instances: Dict[str, BaseChatModel] = {}
    
    @classmethod
    def create(
        cls,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> BaseChatModel:
        """创建LLM实例
        
        Args:
            model_name: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
        
        Returns:
            LLM实例
        """
        model = model_name or settings.DEFAULT_MODEL
        temp = temperature or settings.TEMPERATURE
        tokens = max_tokens or settings.MAX_TOKENS
        
        # 检查缓存
        cache_key = f"{model}_{temp}_{tokens}"
        if cache_key in cls._instances:
            return cls._instances[cache_key]
        
        # 创建实例
        try:
            llm = ChatOpenAI(
                model=model,
                temperature=temp,
                max_tokens=tokens,
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.DASHSCOPE_BASE_URL,
                **kwargs
            )
            
            cls._instances[cache_key] = llm
            logger.info(f"LLM created: {model}")
            
            return llm
        
        except Exception as e:
            logger.error(f"LLM creation error: {e}")
            raise LLMException(f"Failed to create LLM: {e}")
    
    @classmethod
    def get_available_models(cls) -> list:
        """获取可用模型列表"""
        return [
            "qwen3-max",
            "qwen3.7-lite",
            "qwen-plus",
            "qwen-turbo",
            "gpt-4",
            "gpt-3.5-turbo"
        ]
    
    @classmethod
    def clear_cache(cls):
        """清除缓存"""
        cls._instances.clear()
        logger.info("LLM cache cleared")


def get_llm(
    model_name: Optional[str] = None,
    **kwargs
) -> BaseChatModel:
    """获取LLM实例"""
    return LLMFactory.create(model_name, **kwargs)


def get_llm_with_tools(
    model_name: Optional[str] = None,
    tools: list = None
) -> BaseChatModel:
    """获取带工具绑定的LLM"""
    llm = get_llm(model_name)
    
    if tools:
        llm = llm.bind_tools(tools)
    
    return llm