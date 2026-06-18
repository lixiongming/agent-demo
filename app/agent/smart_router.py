"""智能路由服务 - 大厂标准实现

使用 LLM Function Calling 自动决策工具调用
符合 OpenAI、Google、阿里等大厂标准

标准：
- OpenAI: bind_tools() + tool_calls 属性
- Google: 工具注册 + LLM 自动决策
- 阿里: 智能路由 + 缓存机制
"""
import time
import re
import threading
from typing import Dict, Any, Optional, List
from collections import OrderedDict
from langchain_core.messages import HumanMessage, AIMessage
from app.llm import get_llm
from app.tools.tool_registry import tool_registry
from app.core.logger import get_logger
from app.core.tracing import tracer
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class SmartRouter:
    """智能路由器 - 大厂标准实现
    
    核心改进：
    1. 使用 bind_tools() 原生 Function Calling
    2. 直接返回 tool_calls，无需手动 JSON 解析
    3. 支持多工具并行调用
    4. LRU 缓存 + TTL 过期
    5. 规则引擎快速路径
    
    流程：
    1. 规则引擎匹配（毫秒级）
    2. 缓存命中（毫秒级）
    3. LLM Function Calling（秒级）
    """
    
    # 正则规则（用于快速处理简单问题）
    PATTERNS = {
        "math": r'^(计算|算一下|帮我算)?[\s]*[\d\s\+\-\*\/\(\)\.]+[\s]*(等于几|等于多少|是多少)?$',
        "greeting": r'^(你好|您好|hi|hello|hey)[\s,，。！!]*(.*)?$',
        "thanks": r'(谢谢|感谢|thank|多谢)',
        "time": r'(现在|今天|当前)?(几点|几点钟|什么时间)',
        "date": r'(今天|明天|昨天)?(星期几|几号|日期)',
    }
    
    def __init__(self):
        self.llm = get_llm()
        
        # 缓存配置
        self.cache = OrderedDict()
        self.cache_timestamps = {}
        self.cache_max_size = 1000
        self.cache_ttl = 3600
        
        # 统计
        self.stats = {
            "total_requests": 0,
            "pattern_hits": 0,
            "cache_hits": 0,
            "cache_expired": 0,
            "cache_evicted": 0,
            "llm_calls": 0,
            "tool_calls": 0,
            "multi_tool_calls": 0,
            "no_tool_calls": 0
        }
    
    async def route(self, query: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """智能路由决策 - 大厂标准
        
        Args:
            query: 用户问题
            user_id: 用户ID（用于权限控制）
        
        Returns:
            {
                "needs_retrieval": bool,
                "needs_tool": bool,
                "tool_calls": List[dict],  # 原生 tool_calls 格式
                "reason": str,
                "confidence": float,
                "method": str,
                "latency_ms": int
            }
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        # 1. 规则引擎快速路径
        result = self._pattern_route(query)
        if result:
            self.stats["pattern_hits"] += 1
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"Route by pattern: {result}")
            return result
        
        # 2. 缓存命中
        cache_key = query.strip().lower()
        if cache_key in self.cache:
            cache_age = time.time() - self.cache_timestamps.get(cache_key, 0)
            if cache_age > self.cache_ttl:
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
                self.stats["cache_expired"] += 1
            else:
                self.stats["cache_hits"] += 1
                self.cache.move_to_end(cache_key)
                result = self.cache[cache_key].copy()
                result["method"] = "cache"
                result["latency_ms"] = int((time.time() - start_time) * 1000)
                logger.info(f"Route by cache: {result}")
                return result
        
        # 3. LLM Function Calling
        async with tracer.span("llm_function_call"):
            result = await self._llm_function_call(query, user_id)
        
        # 4. 缓存结果
        if len(self.cache) >= self.cache_max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            del self.cache_timestamps[oldest_key]
            self.stats["cache_evicted"] += 1
        
        self.cache[cache_key] = result.copy()
        self.cache_timestamps[cache_key] = time.time()
        self.cache.move_to_end(cache_key)
        
        # 5. 更新统计
        tool_calls = result.get("tool_calls", [])
        if tool_calls:
            self.stats["tool_calls"] += 1
            if len(tool_calls) > 1:
                self.stats["multi_tool_calls"] += 1
        else:
            self.stats["no_tool_calls"] += 1
        
        result["latency_ms"] = int((time.time() - start_time) * 1000)
        logger.info(f"Route by LLM: tool_calls={len(tool_calls)}, latency={result['latency_ms']}ms")
        
        return result
    
    def _pattern_route(self, query: str) -> Optional[Dict[str, Any]]:
        """规则引擎匹配（毫秒级）"""
        query_stripped = query.strip()
        
        # 数学运算
        if re.match(self.PATTERNS["math"], query_stripped):
            return {
                "needs_retrieval": False,
                "needs_tool": True,
                "tool_calls": [{
                    "name": "calculator",
                    "args": {"expression": query_stripped},
                    "id": f"call_pattern_{int(time.time()*1000)}"
                }],
                "method": "pattern",
                "reason": "数学运算表达式",
                "confidence": 1.0
            }
        
        # 问候语
        if re.match(self.PATTERNS["greeting"], query_stripped, re.IGNORECASE):
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_calls": [],
                "method": "pattern",
                "reason": "问候语",
                "confidence": 1.0
            }
        
        # 感谢
        if re.search(self.PATTERNS["thanks"], query_stripped, re.IGNORECASE):
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_calls": [],
                "method": "pattern",
                "reason": "感谢语",
                "confidence": 1.0
            }
        
        # 时间/日期查询
        if re.search(self.PATTERNS["time"], query_stripped) or re.search(self.PATTERNS["date"], query_stripped):
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_calls": [],
                "method": "pattern",
                "reason": "时间/日期查询",
                "confidence": 1.0
            }
        
        return None
    
    async def _llm_function_call(self, query: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """使用 LLM Function Calling 决策 - 大厂标准
        
        核心改进：
        1. 使用 bind_tools() 绑定工具
        2. 直接使用 tool_calls 属性
        3. 无需手动 JSON 解析
        4. 支持多工具并行调用
        """
        self.stats["llm_calls"] += 1
        
        try:
            # 获取 OpenAI 格式的工具定义
            tools = tool_registry.get_openai_tools()
            
            logger.info(f"[LLM Function Call] 可用工具数量: {len(tools)}")
            logger.info(f"[LLM Function Call] 工具列表: {[t['function']['name'] for t in tools]}")
            
            # 权限过滤（如果有 user_id）
            if user_id:
                tools = self._filter_tools_by_permission(tools, user_id)
            
            # 绑定工具到 LLM
            llm_with_tools = self.llm.bind_tools(tools)
            
            logger.info(f"[LLM Function Call] 用户问题: {query}")
            logger.info(f"[LLM Function Call] 开始调用 LLM...")
            
            # 构建消息（添加系统提示）
            messages = [
                HumanMessage(content=f"""你是一个智能助手，可以使用工具来回答用户问题。

可用工具及使用场景：
1. knowledge_search: 知识库检索（优先使用）
   - 用户询问游戏攻略、英雄技能、装备信息、玩法技巧等游戏相关问题
   - 用户询问产品信息、技术文档、业务规则、FAQ等内部知识
   - 示例："亚索怎么玩"、"无尽之刃属性"、"产品功能介绍"

2. news_query: 新闻查询
   - 用户询问热门新闻、最新新闻、搜索新闻、作者新闻
   - 示例："热门新闻"、"最近的科技新闻"

3. get_weather: 天气查询
   - 用户询问某地的天气情况
   - 示例："北京天气"、"上海今天天气"

4. calculator: 数学计算
   - 用户需要计算数学表达式
   - 示例："计算 123+456"、"1+2等于几"

5. mysql_query: 数据库查询
   - 用户需要查询数据库中的业务数据
   - 示例："查询用户列表"、"统计订单数量"

6. web_search: 网络搜索（最后选择）
   - 只有当其他工具都无法满足时才使用
   - 需要搜索互联网上的实时信息
   - 示例："最新科技动态"、"今日热搜"

决策规则：
- 游戏相关问题 → 优先使用 knowledge_search
- 内部知识问题 → 优先使用 knowledge_search
- 实时新闻 → 使用 news_query
- 天气查询 → 使用 get_weather
- 数学计算 → 使用 calculator
- 数据库查询 → 使用 mysql_query
- 其他实时信息 → 使用 web_search

用户问题：{query}

请根据以上规则选择最合适的工具。""")
            ]
            
            # 调用 LLM
            response = await llm_with_tools.ainvoke(messages)
            
            logger.info(f"[LLM Function Call] LLM 响应类型: {type(response)}")
            logger.info(f"[LLM Function Call] LLM 响应内容: {response.content[:200] if response.content else 'None'}...")
            
            # 直接使用 tool_calls 属性（大厂标准）
            tool_calls = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                logger.info(f"[LLM Function Call] tool_calls 数量: {len(response.tool_calls)}")
                for tc in response.tool_calls:
                    logger.info(f"[LLM Function Call] tool_call: name={tc.get('name')}, args={tc.get('args')}")
                    tool_calls.append({
                        "name": tc.get("name"),
                        "args": tc.get("args", {}),
                        "id": tc.get("id", f"call_{int(time.time()*1000)}")
                    })
            else:
                logger.warning(f"[LLM Function Call] 没有 tool_calls，hasattr={hasattr(response, 'tool_calls')}")
                if hasattr(response, "tool_calls"):
                    logger.warning(f"[LLM Function Call] tool_calls 值: {response.tool_calls}")
            
            # 构建结果
            result = {
                "needs_retrieval": False,
                "needs_tool": len(tool_calls) > 0,
                "tool_calls": tool_calls,
                "reason": f"LLM Function Calling: {len(tool_calls)} tools",
                "confidence": 0.9 if tool_calls else 0.8,
                "method": "llm_function_call"
            }
            
            logger.info(f"[LLM Function Call] 最终结果: needs_tool={result['needs_tool']}, tool_calls={tool_calls}")
            
            return result
        
        except Exception as e:
            logger.error(f"[LLM Function Call] 异常: {e}")
            import traceback
            logger.error(f"[LLM Function Call] 异常堆栈: {traceback.format_exc()}")
            
            # 降级策略
            return {
                "needs_retrieval": False,
                "needs_tool": False,
                "tool_calls": [],
                "reason": f"LLM 路由失败，降级: {str(e)}",
                "confidence": 0.5,
                "method": "fallback"
            }
    
    def _filter_tools_by_permission(self, tools: List[Dict], user_id: int) -> List[Dict]:
        """权限过滤工具
        
        生产级权限控制：
        - 根据用户角色过滤工具
        - 支持工具级别的权限配置
        """
        # TODO: 实现基于用户角色的权限过滤
        # 当前：返回所有工具（后续可接入权限系统）
        return tools
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        total = max(self.stats["total_requests"], 1)
        return {
            "total_requests": self.stats["total_requests"],
            "pattern_hits": self.stats["pattern_hits"],
            "cache_hits": self.stats["cache_hits"],
            "cache_expired": self.stats["cache_expired"],
            "cache_evicted": self.stats["cache_evicted"],
            "llm_calls": self.stats["llm_calls"],
            "tool_calls": self.stats["tool_calls"],
            "multi_tool_calls": self.stats["multi_tool_calls"],
            "no_tool_calls": self.stats["no_tool_calls"],
            "cache_size": len(self.cache),
            "cache_max_size": self.cache_max_size,
            "cache_ttl": self.cache_ttl,
            "pattern_rate": round(self.stats["pattern_hits"] / total, 3),
            "cache_rate": round(self.stats["cache_hits"] / total, 3),
            "tool_rate": round(self.stats["tool_calls"] / total, 3),
            "multi_tool_rate": round(self.stats["multi_tool_calls"] / total, 3)
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("路由缓存已清空")
    
    def cleanup_expired_cache(self) -> int:
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, ts in self.cache_timestamps.items()
            if current_time - ts > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
            del self.cache_timestamps[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)


# 全局路由器实例（线程安全）
_router = None
_router_lock = threading.Lock()


def get_router() -> SmartRouter:
    """获取全局路由器实例（线程安全）"""
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                _router = SmartRouter()
    return _router


async def smart_route(query: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """快捷路由函数"""
    router = get_router()
    return await router.route(query, user_id)