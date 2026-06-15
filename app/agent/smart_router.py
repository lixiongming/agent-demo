"""智能路由服务

功能：
- 关键词快速路径（毫秒级）
- LLM 智能决策（带缓存）
- 多级降级策略
- 性能监控

标准：
- OpenAI: 关键词 + 意图分类 + LLM 决策
- Google: 规则引擎 + 语义理解
- 阿里: 多级路由策略
"""
from typing import Dict, Any, Optional
import hashlib
import re
from app.core.logger import get_logger
from app.llm.factory import get_llm
from app.config import get_settings
from app.prompts.templates import PromptTemplates
from langchain_core.messages import HumanMessage
import json

logger = get_logger(__name__)
settings = get_settings()


class SmartRouter:
    """智能路由器
    
    三级路由策略：
    1. 关键词快速路径（毫秒级）
    2. 规则引擎匹配（毫秒级）
    3. LLM 智能决策（带缓存，秒级）
    """
    
    # 知识库相关关键词
    KNOWLEDGE_KEYWORDS = [
        # 产品相关
        "产品", "功能", "特性", "版本", "更新", "发布",
        # 技术相关
        "API", "接口", "文档", "SDK", "开发", "集成",
        # 业务相关
        "规则", "流程", "政策", "协议", "条款", "规定",
        # 帮助相关
        "如何", "怎么", "怎样", "操作", "使用", "教程",
        # 问题相关
        "问题", "错误", "故障", "异常", "报错", "解决"
    ]
    
    # 通用问题关键词（不需要检索）
    GENERAL_KEYWORDS = [
        "你好", "您好", "早上好", "晚上好",
        "谢谢", "感谢", "再见",
        "天气", "时间", "日期",
        "计算", "算数", "数学"
    ]
    
    # 正则规则（优化版）
    PATTERNS = {
        # 数学运算（支持中文前缀和后缀）
        "math": r'^(计算|算一下|帮我算)?[\s]*[\d\s\+\-\*\/\(\)\.]+[\s]*(等于几|等于多少|是多少)?$',
        # 问候语（支持后缀）
        "greeting": r'^(你好|您好|hi|hello|hey)[\s,，。！!]*(.*)?$',
        # 感谢
        "thanks": r'(谢谢|感谢|thank|多谢)',
        # 天气查询
        "weather": r'(.*)天气(怎么样|如何|怎样)',
        # 时间查询
        "time": r'(现在|今天|当前)?(几点|几点钟|什么时间)',
        # 日期查询
        "date": r'(今天|明天|昨天)?(星期几|几号|日期)',
    }
    
    def __init__(self):
        self.llm_cache = {}  # LLM 决策缓存
        self.stats = {
            "keyword_hits": 0,
            "pattern_hits": 0,
            "llm_hits": 0,
            "cache_hits": 0
        }
    
    async def route(self, query: str) -> Dict[str, Any]:
        """智能路由决策
        
        Args:
            query: 用户问题
            
        Returns:
            {
                "needs_retrieval": bool,
                "method": str,  # keyword, pattern, llm, cache
                "reason": str,
                "confidence": float,
                "latency_ms": int
            }
        """
        import time
        start_time = time.time()
        
        # 1. 尝试关键词快速路径
        result = self._keyword_route(query)
        if result:
            self.stats["keyword_hits"] += 1
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"Route by keyword: {result}")
            return result
        
        # 2. 尝试规则引擎匹配
        result = self._pattern_route(query)
        if result:
            self.stats["pattern_hits"] += 1
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"Route by pattern: {result}")
            return result
        
        # 3. 尝试内存缓存
        cache_key = self._get_cache_key(query)
        if cache_key in self.llm_cache:
            self.stats["cache_hits"] += 1
            result = self.llm_cache[cache_key].copy()
            result["method"] = "cache"
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"Route by cache: {result}")
            return result
        
        # 3.5 尝试 Redis 缓存
        try:
            from app.services.cache import CacheService
            cached = await CacheService.get_route_decision(query)
            if cached:
                self.stats["cache_hits"] += 1
                cached["method"] = "redis_cache"
                cached["latency_ms"] = int((time.time() - start_time) * 1000)
                logger.info(f"Route by redis cache: {cached}")
                return cached
        except Exception as e:
            logger.warning(f"Redis cache check failed: {e}")
        
        # 4. LLM 智能决策（带降级）
        try:
            result = await self._llm_route(query)
            self.stats["llm_hits"] += 1
            
            # 缓存结果（内存）
            self.llm_cache[cache_key] = result.copy()
            
            # 缓存结果（Redis）
            try:
                from app.services.cache import CacheService
                await CacheService.set_route_decision(query, result)
            except Exception as e:
                logger.warning(f"Redis cache set failed: {e}")
            
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"Route by LLM: {result}")
            return result
        
        except Exception as e:
            logger.error(f"LLM route failed: {e}")
            # 降级策略：默认检索
            result = {
                "needs_retrieval": True,
                "method": "fallback",
                "reason": f"LLM 路由失败，降级为默认检索: {str(e)}",
                "confidence": 0.5,
                "latency_ms": int((time.time() - start_time) * 1000)
            }
            return result
    
    def _keyword_route(self, query: str) -> Optional[Dict[str, Any]]:
        """关键词快速路由（毫秒级）"""
        # 检查是否包含知识库关键词
        for keyword in self.KNOWLEDGE_KEYWORDS:
            if keyword in query:
                return {
                    "needs_retrieval": True,
                    "method": "keyword",
                    "reason": f"包含知识库关键词: {keyword}",
                    "confidence": 0.9
                }
        
        # 检查是否是通用问题
        for keyword in self.GENERAL_KEYWORDS:
            if keyword in query:
                return {
                    "needs_retrieval": False,
                    "method": "keyword",
                    "reason": f"通用问题关键词: {keyword}",
                    "confidence": 0.95
                }
        
        return None
    
    def _pattern_route(self, query: str) -> Optional[Dict[str, Any]]:
        """规则引擎匹配（毫秒级）- 优化版"""
        query_stripped = query.strip()
        
        # 数学运算（支持中文前缀和后缀）
        if re.match(self.PATTERNS["math"], query_stripped):
            return {
                "needs_retrieval": False,
                "method": "pattern",
                "reason": "数学运算表达式",
                "confidence": 1.0
            }
        
        # 问候语（支持后缀）
        if re.match(self.PATTERNS["greeting"], query_stripped, re.IGNORECASE):
            return {
                "needs_retrieval": False,
                "method": "pattern",
                "reason": "问候语",
                "confidence": 1.0
            }
        
        # 感谢
        if re.search(self.PATTERNS["thanks"], query_stripped, re.IGNORECASE):
            return {
                "needs_retrieval": False,
                "method": "pattern",
                "reason": "感谢语",
                "confidence": 1.0
            }
        
        # 天气查询
        if re.search(self.PATTERNS["weather"], query_stripped):
            return {
                "needs_retrieval": False,
                "method": "pattern",
                "reason": "天气查询",
                "confidence": 1.0
            }
        
        # 时间查询
        if re.search(self.PATTERNS["time"], query_stripped):
            return {
                "needs_retrieval": False,
                "method": "pattern",
                "reason": "时间查询",
                "confidence": 1.0
            }
        
        # 日期查询
        if re.search(self.PATTERNS["date"], query_stripped):
            return {
                "needs_retrieval": False,
                "method": "pattern",
                "reason": "日期查询",
                "confidence": 1.0
            }
        
        return None
    
    async def _llm_route(self, query: str) -> Dict[str, Any]:
        """LLM 智能决策（带缓存）"""
        # 获取 LLM
        llm = get_llm(settings.DEFAULT_MODEL)
        
        # 构建路由决策提示词
        route_prompt = PromptTemplates.get_agent_prompt(
            task=query,
            agent_type="route_decision"
        )
        
        # 调用 LLM
        response = await llm.ainvoke([HumanMessage(content=route_prompt)])
        
        # 解析 JSON 响应
        response_text = response.content.strip()
        
        # 提取 JSON
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text
        
        decision = json.loads(json_str)
        
        return {
            "needs_retrieval": decision.get("needs_retrieval", False),
            "method": "llm",
            "reason": decision.get("reason", ""),
            "confidence": decision.get("confidence", 0.5)
        }
    
    def _get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(query.encode()).hexdigest()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        total = (
            self.stats["keyword_hits"] +
            self.stats["pattern_hits"] +
            self.stats["llm_hits"] +
            self.stats["cache_hits"]
        )
        
        return {
            "total_requests": total,
            "keyword_hits": self.stats["keyword_hits"],
            "pattern_hits": self.stats["pattern_hits"],
            "llm_hits": self.stats["llm_hits"],
            "cache_hits": self.stats["cache_hits"],
            "keyword_rate": self.stats["keyword_hits"] / total if total > 0 else 0,
            "pattern_rate": self.stats["pattern_hits"] / total if total > 0 else 0,
            "llm_rate": self.stats["llm_hits"] / total if total > 0 else 0,
            "cache_rate": self.stats["cache_hits"] / total if total > 0 else 0,
            "cache_size": len(self.llm_cache)
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.llm_cache.clear()
        logger.info("Router cache cleared")


# 全局路由器实例
_router = None


def get_router() -> SmartRouter:
    """获取全局路由器实例"""
    global _router
    if _router is None:
        _router = SmartRouter()
    return _router


async def smart_route(query: str) -> Dict[str, Any]:
    """快捷路由函数"""
    router = get_router()
    return await router.route(query)
