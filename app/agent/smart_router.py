"""智能路由服务 - 符合大厂标准

使用LLM Function Calling自动决策工具调用
无需手动维护关键词，LLM根据工具描述自动决策

标准：
- OpenAI: Function Calling + 工具描述驱动
- Google: 工具注册 + LLM自动决策
- 阿里: 智能路由 + 缓存机制
"""
import json
import time
import re
from typing import Dict, Any, Optional
from collections import OrderedDict
from app.llm import get_llm
from app.tools.tool_registry import tool_registry
from app.core.logger import get_logger
from app.core.tracing import tracer

logger = get_logger(__name__)


class SmartRouter:
    """智能路由器
    
    符合大厂标准：
    - 使用LLM Function Calling自动决策
    - 无需手动维护关键词
    - 工具描述驱动
    - 支持缓存机制
    - 保留规则引擎（正则表达式）用于快速处理简单问题
    """
    
    # 正则规则（用于快速处理简单问题）
    PATTERNS = {
        # 数学运算（支持中文前缀和后缀）
        "math": r'^(计算|算一下|帮我算)?[\s]*[\d\s\+\-\*\/\(\)\.]+[\s]*(等于几|等于多少|是多少)?$',
        # 问候语（支持后缀）
        "greeting": r'^(你好|您好|hi|hello|hey)[\s,，。！!]*(.*)?$',
        # 感谢
        "thanks": r'(谢谢|感谢|thank|多谢)',
        # 时间查询
        "time": r'(现在|今天|当前)?(几点|几点钟|什么时间)',
        # 日期查询
        "date": r'(今天|明天|昨天)?(星期几|几号|日期)',
    }
    
    def __init__(self):
        self.llm = get_llm()
        
        # 生产级缓存配置
        self.cache = OrderedDict()  # LRU 缓存（有序字典）
        self.cache_timestamps = {}  # 缓存时间戳
        self.cache_max_size = 1000  # 最大缓存数量
        self.cache_ttl = 3600  # 缓存过期时间（秒），默认 1 小时
        
        self.stats = {
            "total_requests": 0,
            "pattern_hits": 0,
            "cache_hits": 0,
            "cache_expired": 0,  # 缓存过期次数
            "cache_evicted": 0,  # 缓存淘汰次数
            "llm_calls": 0,
            "tool_calls": 0,
            "no_tool_calls": 0
        }
    
    async def route(self, query: str) -> Dict[str, Any]:
        """智能路由决策
        
        Args:
            query: 用户问题
        
        Returns:
            {
                "needs_retrieval": bool,  # 是否需要检索知识库
                "needs_tool": bool,  # 是否需要调用工具
                "tool_name": str,  # 工具名称
                "tool_args": dict,  # 工具参数
                "reason": str,  # 决策原因
                "confidence": float,  # 置信度
                "method": str,  # 决策方法（pattern/cache/llm）
                "latency_ms": int  # 响应时间
            }
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        # 1. 尝试规则引擎匹配（毫秒级，用于简单问题）
        result = self._pattern_route(query)
        if result:
            self.stats["pattern_hits"] += 1
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"Route by pattern: {result}")
            return result
        
        # 2. 检查缓存（带过期时间和 LRU 更新）
        cache_key = query.strip().lower()
        if cache_key in self.cache:
            # 检查缓存是否过期
            cache_age = time.time() - self.cache_timestamps.get(cache_key, 0)
            if cache_age > self.cache_ttl:
                # 缓存过期，删除
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
                self.stats["cache_expired"] += 1
                logger.info(f"Cache expired: {cache_key[:20]} (age: {cache_age:.0f}s)")
            else:
                # 缓存命中，更新 LRU
                self.stats["cache_hits"] += 1
                self.cache.move_to_end(cache_key)  # 移到末尾（最近使用）
                result = self.cache[cache_key].copy()
                result["method"] = "cache"
                result["latency_ms"] = int((time.time() - start_time) * 1000)
                logger.info(f"Route by cache: {result}")
                return result
        
        # 3. 使用LLM Function Calling决策
        async with tracer.span("llm_route"):
            result = await self._llm_route(query)
        
        # 4. 缓存结果（LRU 策略）
        # 检查缓存大小，超过限制则淘汰最旧的
        if len(self.cache) >= self.cache_max_size:
            oldest_key = next(iter(self.cache))  # 获取最旧的键
            del self.cache[oldest_key]
            del self.cache_timestamps[oldest_key]
            self.stats["cache_evicted"] += 1
            logger.info(f"Cache evicted (LRU): {oldest_key[:20]}")
        
        # 添加新缓存
        self.cache[cache_key] = result.copy()
        self.cache_timestamps[cache_key] = time.time()
        self.cache.move_to_end(cache_key)  # 移到末尾（最近使用）
        
        # 5. 更新统计
        if result.get("needs_tool"):
            self.stats["tool_calls"] += 1
        else:
            self.stats["no_tool_calls"] += 1
        
        result["latency_ms"] = int((time.time() - start_time) * 1000)
        logger.info(f"Route by LLM: {result}")
        
        return result
    
    def _pattern_route(self, query: str) -> Optional[Dict[str, Any]]:
        """规则引擎匹配（毫秒级）
        
        用于快速处理简单问题（问候、感谢、时间查询等）
        """
        query_stripped = query.strip()
        
        # 数学运算（支持中文前缀和后缀）
        if re.match(self.PATTERNS["math"], query_stripped):
            return {
                "needs_retrieval": False,
                "needs_tool": True,
                "tool_name": "calculator",
                "tool_args": {"expression": query_stripped},
                "method": "pattern",
                "reason": "数学运算表达式",
                "confidence": 1.0
            }
        
        # 问候语（支持后缀）
        if re.match(self.PATTERNS["greeting"], query_stripped, re.IGNORECASE):
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_name": None,
                "tool_args": {},
                "method": "pattern",
                "reason": "问候语",
                "confidence": 1.0
            }
        
        # 感谢
        if re.search(self.PATTERNS["thanks"], query_stripped, re.IGNORECASE):
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_name": None,
                "tool_args": {},
                "method": "pattern",
                "reason": "感谢语",
                "confidence": 1.0
            }
        
        # 时间查询
        if re.search(self.PATTERNS["time"], query_stripped):
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_name": None,
                "tool_args": {},
                "method": "pattern",
                "reason": "时间查询",
                "confidence": 1.0
            }
        
        # 日期查询
        if re.search(self.PATTERNS["date"], query_stripped):
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_name": None,
                "tool_args": {},
                "method": "pattern",
                "reason": "日期查询",
                "confidence": 1.0
            }
        
        return None
    
    async def _llm_route(self, query: str) -> Dict[str, Any]:
        """使用LLM Function Calling决策
        
        Args:
            query: 用户问题
        
        Returns:
            路由决策结果
        """
        self.stats["llm_calls"] += 1
        
        # 构建提示词
        prompt = self._build_route_prompt(query)
        
        try:
            # 调用LLM
            response = await self.llm.ainvoke(prompt)
            
            # 解析LLM响应
            result = self._parse_llm_response(response.content, query)
            
            return result
        
        except Exception as e:
            logger.error(f"LLM route failed: {e}")
            
            # 降级策略：默认不调用工具
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_name": None,
                "tool_args": {},
                "reason": f"LLM路由失败，降级为不调用工具: {str(e)}",
                "confidence": 0.5,
                "method": "fallback"
            }
    
    def _build_route_prompt(self, query: str) -> str:
        """构建路由决策提示词
        
        Args:
            query: 用户问题
        
        Returns:
            提示词文本
        """
        tools_description = tool_registry.get_tools_description()
        
        # 使用简单的字符串拼接，避免格式化错误
        prompt = """你是一个智能路由决策器，需要判断用户问题是否需要调用工具。

用户问题：""" + query + """

可用工具列表：
""" + tools_description + """

请分析用户问题，判断：
1. 是否需要调用工具？
2. 如果需要，调用哪个工具？
3. 工具参数是什么？

重要规则：
- news_query 工具：参数必须是 {"question": "用户问题"}，不要生成其他参数
- 工具会自动解析用户问题，你只需要传递原始问题

请以JSON格式返回决策结果：
{
    "needs_tool": true或false,
    "tool_name": "工具名称（如果需要调用工具）",
    "tool_args": {"参数名": "参数值"},
    "reason": "决策原因",
    "confidence": 0.0到1.0之间的数字
}

注意：
- 如果用户问题涉及天气、新闻、数据库查询等，应该调用对应的工具
- 如果用户问题是问候、闲聊、简单问题，不需要调用工具
- confidence表示决策的置信度，范围0.0-1.0

请只返回JSON，不要包含其他内容。"""
        
        return prompt
    
    def _parse_llm_response(self, response: str, query: str) -> Dict[str, Any]:
        """解析LLM响应
        
        Args:
            response: LLM响应文本
            query: 用户问题
        
        Returns:
            路由决策结果
        """
        try:
            # 尝试提取JSON
            json_str = response.strip()
            
            # 移除可能的markdown标记
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            
            json_str = json_str.strip()
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 构建结果
            result = {
                "needs_retrieval": False,  # 工具调用优先于知识库检索
                "needs_tool": data.get("needs_tool", False),
                "tool_name": data.get("tool_name"),
                "tool_args": data.get("tool_args", {}),
                "reason": data.get("reason", "LLM决策"),
                "confidence": data.get("confidence", 0.8),
                "method": "llm"
            }
            
            # 验证工具是否存在
            if result["needs_tool"] and result["tool_name"]:
                tool = tool_registry.get_tool(result["tool_name"])
                if not tool:
                    logger.warning(f"LLM决策的工具不存在: {result['tool_name']}")
                    result["needs_tool"] = False
                    result["tool_name"] = None
                    result["reason"] = f"工具不存在: {result['tool_name']}"
            
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}, response: {response[:200]}")
            
            # 降级策略：不调用工具
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_name": None,
                "tool_args": {},
                "reason": f"JSON解析失败: {str(e)}",
                "confidence": 0.5,
                "method": "fallback"
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计
        
        Returns:
            统计数据
        """
        total = max(self.stats["total_requests"], 1)
        return {
            "total_requests": self.stats["total_requests"],
            "pattern_hits": self.stats["pattern_hits"],
            "cache_hits": self.stats["cache_hits"],
            "cache_expired": self.stats["cache_expired"],
            "cache_evicted": self.stats["cache_evicted"],
            "llm_calls": self.stats["llm_calls"],
            "tool_calls": self.stats["tool_calls"],
            "no_tool_calls": self.stats["no_tool_calls"],
            "cache_size": len(self.cache),
            "cache_max_size": self.cache_max_size,
            "cache_ttl": self.cache_ttl,
            "pattern_rate": self.stats["pattern_hits"] / total,
            "cache_rate": self.stats["cache_hits"] / total,
            "tool_rate": self.stats["tool_calls"] / total
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("路由缓存已清空")
    
    def cleanup_expired_cache(self) -> int:
        """清理过期缓存
        
        Returns:
            清理的缓存数量
        """
        current_time = time.time()
        expired_keys = []
        
        # 找出所有过期的缓存
        for key, timestamp in self.cache_timestamps.items():
            if current_time - timestamp > self.cache_ttl:
                expired_keys.append(key)
        
        # 删除过期缓存
        for key in expired_keys:
            del self.cache[key]
            del self.cache_timestamps[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)


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