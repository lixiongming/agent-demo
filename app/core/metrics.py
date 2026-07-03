"""监控指标模块

功能：
- Prometheus 指标收集
- 请求计数、延迟、错误率
- LLM/RAG/DB 性能指标
- 自定义业务指标

使用示例：
    from app.core.metrics import Metrics
    
    # 记录请求
    Metrics.record_request("chat", latency=0.5, success=True)
    
    # 记录 LLM 调用
    Metrics.record_llm_call(model="qwen", tokens=1000, latency=2.5)
"""
import time
from typing import Optional, Dict, Any
from functools import wraps
from contextvars import ContextVar

from app.core.logger import get_logger

logger = get_logger(__name__)

# 请求上下文
request_start_time: ContextVar[float] = ContextVar("request_start_time", default=0)


# ============================================
# 指标收集器（简化版，不依赖 Prometheus）
# ============================================

class MetricsCollector:
    """指标收集器
    
    收集各类指标，支持：
    - 内存存储（简化版）
    - Prometheus 导出（可选）
    """

    MAX_LATENCY_SAMPLES = 1000

    def __init__(self):
        # 请求指标
        self._request_counts: Dict[str, int] = {}
        self._request_latencies: Dict[str, list] = {}
        self._request_errors: Dict[str, int] = {}
        
        # LLM 指标
        self._llm_calls: Dict[str, int] = {}
        self._llm_tokens: Dict[str, int] = {}
        self._llm_latencies: Dict[str, list] = {}
        self._llm_errors: Dict[str, int] = {}
        
        # RAG 指标
        self._rag_searches: int = 0
        self._rag_hits: int = 0
        self._rag_misses: int = 0
        self._rag_latencies: list = []  # 使用 _append_latency_list 管理
        
        # DB 指标
        self._db_queries: Dict[str, int] = {}
        self._db_latencies: Dict[str, list] = {}
        self._db_errors: Dict[str, int] = {}
        
        # 系统指标
        self._active_sessions: int = 0
        self._total_messages: int = 0

    def _append_latency(self, storage: Dict[str, list], key: str, value: float):
        """向字典中的延迟列表追加值，超出上限时裁剪"""
        if key not in storage:
            storage[key] = []
        storage[key].append(value)
        if len(storage[key]) > self.MAX_LATENCY_SAMPLES:
            storage[key] = storage[key][-self.MAX_LATENCY_SAMPLES:]

    def _append_latency_list(self, latencies: list, value: float):
        """向延迟列表追加值，超出上限时裁剪"""
        latencies.append(value)
        if len(latencies) > self.MAX_LATENCY_SAMPLES:
            del latencies[:-self.MAX_LATENCY_SAMPLES]

    @staticmethod
    def _percentile(sorted_data: list, p: float) -> float:
        """计算百分位数"""
        if not sorted_data:
            return 0
        sorted_data = sorted(sorted_data)
        k = (len(sorted_data) - 1) * p / 100
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[f]
        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f)
        return d0 + d1

    # ===== 请求指标 =====
    
    def record_request(
        self,
        endpoint: str,
        latency: float,
        success: bool = True,
        error_code: str = None
    ):
        """记录请求
        
        Args:
            endpoint: API 端点（如 "chat", "rag_search"）
            latency: 响应延迟（秒）
            success: 是否成功
            error_code: 错误码（失败时）
        """
        # 计数
        self._request_counts[endpoint] = self._request_counts.get(endpoint, 0) + 1
        
        # 延迟
        self._append_latency(self._request_latencies, endpoint, latency)
        
        # 错误
        if not success:
            error_key = f"{endpoint}:{error_code or 'unknown'}"
            self._request_errors[error_key] = self._request_errors.get(error_key, 0) + 1
        
        logger.debug(f"Request recorded: {endpoint}, latency={latency:.3f}s, success={success}")
    
    def get_request_stats(self, endpoint: str = None) -> Dict[str, Any]:
        """获取请求统计"""
        if endpoint:
            latencies = self._request_latencies.get(endpoint, [])
            return {
                "endpoint": endpoint,
                "count": self._request_counts.get(endpoint, 0),
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
                "max_latency": max(latencies) if latencies else 0,
                "min_latency": min(latencies) if latencies else 0,
                "p50_latency": self._percentile(latencies, 50),
                "p95_latency": self._percentile(latencies, 95),
                "p99_latency": self._percentile(latencies, 99),
            }
        
        # 所有端点
        stats = {}
        for ep, count in self._request_counts.items():
            latencies = self._request_latencies.get(ep, [])
            stats[ep] = {
                "count": count,
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
                "p50_latency": self._percentile(latencies, 50),
                "p95_latency": self._percentile(latencies, 95),
                "errors": sum(v for k, v in self._request_errors.items() if k.startswith(ep))
            }
        return stats
    
    # ===== LLM 指标 =====
    
    def record_llm_call(
        self,
        model: str,
        tokens: int = 0,
        latency: float = 0,
        success: bool = True
    ):
        """记录 LLM 调用"""
        self._llm_calls[model] = self._llm_calls.get(model, 0) + 1
        self._llm_tokens[model] = self._llm_tokens.get(model, 0) + tokens

        self._append_latency(self._llm_latencies, model, latency)
        
        if not success:
            self._llm_errors[model] = self._llm_errors.get(model, 0) + 1
        
        logger.debug(f"LLM call recorded: {model}, tokens={tokens}, latency={latency:.3f}s")
    
    def get_llm_stats(self, model: str = None) -> Dict[str, Any]:
        """获取 LLM 统计"""
        if model:
            latencies = self._llm_latencies.get(model, [])
            return {
                "model": model,
                "calls": self._llm_calls.get(model, 0),
                "tokens": self._llm_tokens.get(model, 0),
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
                "p50_latency": self._percentile(latencies, 50),
                "p95_latency": self._percentile(latencies, 95),
                "errors": self._llm_errors.get(model, 0),
            }
        
        stats = {}
        for m, calls in self._llm_calls.items():
            latencies = self._llm_latencies.get(m, [])
            stats[m] = {
                "calls": calls,
                "tokens": self._llm_tokens.get(m, 0),
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
                "p50_latency": self._percentile(latencies, 50),
                "p95_latency": self._percentile(latencies, 95),
                "errors": self._llm_errors.get(m, 0),
            }
        return stats
    
    # ===== RAG 指标 =====
    
    def record_rag_search(
        self,
        latency: float,
        hits: int = 0,
        success: bool = True
    ):
        """记录 RAG 检索"""
        self._rag_searches += 1
        
        if success and hits > 0:
            self._rag_hits += 1
        else:
            self._rag_misses += 1
        
        self._append_latency_list(self._rag_latencies, latency)
        
        logger.debug(f"RAG search recorded: latency={latency:.3f}s, hits={hits}")
    
    def get_rag_stats(self) -> Dict[str, Any]:
        """获取 RAG 统计"""
        avg_latency = sum(self._rag_latencies) / len(self._rag_latencies) if self._rag_latencies else 0
        return {
            "searches": self._rag_searches,
            "hits": self._rag_hits,
            "misses": self._rag_misses,
            "hit_rate": self._rag_hits / self._rag_searches if self._rag_searches > 0 else 0,
            "avg_latency": avg_latency,
            "p50_latency": self._percentile(self._rag_latencies, 50),
            "p95_latency": self._percentile(self._rag_latencies, 95),
        }
    
    # ===== DB 指标 =====
    
    def record_db_query(
        self,
        operation: str,
        latency: float,
        success: bool = True
    ):
        """记录数据库查询"""
        self._db_queries[operation] = self._db_queries.get(operation, 0) + 1

        self._append_latency(self._db_latencies, operation, latency)
        
        if not success:
            self._db_errors[operation] = self._db_errors.get(operation, 0) + 1
    
    def get_db_stats(self) -> Dict[str, Any]:
        """获取数据库统计"""
        stats = {}
        for op, count in self._db_queries.items():
            latencies = self._db_latencies.get(op, [])
            stats[op] = {
                "count": count,
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
                "errors": self._db_errors.get(op, 0),
            }
        return stats
    
    # ===== 系统指标 =====
    
    def update_active_sessions(self, count: int):
        """更新活跃会话数"""
        self._active_sessions = count
    
    def increment_messages(self):
        """增加消息计数"""
        self._total_messages += 1
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计"""
        return {
            "active_sessions": self._active_sessions,
            "total_messages": self._total_messages,
        }
    
    # ===== 综合统计 =====
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有统计"""
        return {
            "requests": self.get_request_stats(),
            "llm": self.get_llm_stats(),
            "rag": self.get_rag_stats(),
            "db": self.get_db_stats(),
            "system": self.get_system_stats(),
        }
    
    def reset(self):
        """重置所有指标"""
        self._request_counts.clear()
        self._request_latencies.clear()
        self._request_errors.clear()
        self._llm_calls.clear()
        self._llm_tokens.clear()
        self._llm_latencies.clear()
        self._llm_errors.clear()
        self._rag_searches = 0
        self._rag_hits = 0
        self._rag_misses = 0
        self._rag_latencies.clear()
        self._db_queries.clear()
        self._db_latencies.clear()
        self._db_errors.clear()
        logger.info("All metrics reset")


# ============================================
# 全局指标实例
# ============================================

Metrics = MetricsCollector()


# ============================================
# 指标装饰器
# ============================================

def track_request(endpoint: str):
    """请求追踪装饰器
    
    Args:
        endpoint: API 端点名称
        
    使用示例：
        @track_request("chat")
        async def chat_endpoint():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_code = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_code = getattr(e, 'code', 'unknown')
                raise
            finally:
                latency = time.time() - start_time
                Metrics.record_request(endpoint, latency, success, error_code)
        
        return wrapper
    return decorator


def track_llm_call(model: str):
    """LLM 调用追踪装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            tokens = 0
            
            try:
                result = await func(*args, **kwargs)
                # 尝试获取 token 数
                if hasattr(result, 'usage'):
                    tokens = getattr(result.usage, 'total_tokens', 0)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                latency = time.time() - start_time
                Metrics.record_llm_call(model, tokens, latency, success)
        
        return wrapper
    return decorator


def track_rag_search(func):
    """RAG 检索追踪装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        success = True
        hits = 0
        
        try:
            result = await func(*args, **kwargs)
            # 尝试获取命中数
            if isinstance(result, dict):
                hits = len(result.get('sources', []))
            return result
        except Exception as e:
            success = False
            raise
        finally:
            latency = time.time() - start_time
            Metrics.record_rag_search(latency, hits, success)
    
    return wrapper


# ============================================
# 性能监控上下文
# ============================================

class PerformanceMonitor:
    """性能监控上下文"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        latency = time.time() - self.start_time
        
        if exc_type is None:
            logger.info(f"Performance: {self.name} completed in {latency:.3f}s")
        else:
            logger.warning(f"Performance: {self.name} failed after {latency:.3f}s")
        
        return False  # 不抑制异常
    
    @property
    def elapsed(self) -> float:
        """已耗时"""
        return time.time() - self.start_time