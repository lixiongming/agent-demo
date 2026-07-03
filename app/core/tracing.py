"""链路追踪模块

功能：
- Span 追踪（记录每个节点的耗时、状态）
- 自动关联 request_id
- 支持嵌套 Span
- 性能统计

使用示例：
    from app.core.tracing import tracer, Span

    # 方式1：上下文管理器
    async with tracer.span("rag_retrieve") as span:
        span.set_attribute("query", "产品功能")
        result = await rag_service.query(query)
        span.set_attribute("doc_count", len(result))

    # 方式2：手动控制
    span = tracer.start_span("llm_call")
    try:
        result = await llm.invoke()
        span.set_status("ok")
    except Exception as e:
        span.set_status("error", str(e))
    finally:
        span.end()
"""

import time
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import asynccontextmanager
from functools import wraps
from app.core.logger import get_logger, request_id_var

logger = get_logger(__name__)


# ============================================
# Span 定义
# ============================================

@dataclass
class SpanStatus:
    """Span 状态"""
    OK = "ok"
    ERROR = "error"


@dataclass
class Span:
    """追踪单元

    记录一个操作的开始、结束、属性和状态
    """
    name: str
    request_id: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = SpanStatus.OK
    status_message: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    parent: Optional['Span'] = None

    def set_attribute(self, key: str, value: Any):
        """设置属性"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """添加事件"""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        })

    def set_status(self, status: str, message: str = ""):
        """设置状态"""
        self.status = status
        self.status_message = message

    def end(self):
        """结束 Span"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "request_id": self.request_id,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
            "status": self.status,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "events": self.events
        }


# ============================================
# Tracer 定义
# ============================================

class Tracer:
    """链路追踪器

    功能：
    - 创建和管理 Span
    - 自动关联 request_id
    - 支持嵌套 Span
    - 统计分析
    """

    MAX_COMPLETED_REQUESTS = 1000
    MAX_ACTIVE_SPANS_PER_REQUEST = 50

    def __init__(self):
        # 当前活跃的 Span 栈（支持嵌套）
        self._active_spans: Dict[str, List[Span]] = {}
        # 已完成的 Span 存储
        self._completed_spans: Dict[str, List[Span]] = {}
        # 统计信息
        self._stats = {
            "total_spans": 0,
            "total_requests": 0,
            "error_count": 0
        }

    def start_span(
        self,
        name: str,
        attributes: Dict[str, Any] = None
    ) -> Span:
        """开始一个 Span

        Args:
            name: Span 名称
            attributes: 初始属性

        Returns:
            Span 对象
        """
        # 获取当前 request_id
        request_id = request_id_var.get() or "unknown"

        # 创建 Span
        span = Span(
            name=name,
            request_id=request_id,
            attributes=attributes or {}
        )

        # 设置父 Span
        if request_id in self._active_spans and self._active_spans[request_id]:
            span.parent = self._active_spans[request_id][-1]

        # 添加到活跃列表
        if request_id not in self._active_spans:
            self._active_spans[request_id] = []
        self._active_spans[request_id].append(span)

        # 安全检查：活跃 span 数量过多，可能存在泄漏
        if len(self._active_spans[request_id]) > self.MAX_ACTIVE_SPANS_PER_REQUEST:
            logger.warning(
                f"[{request_id}] Active spans count ({len(self._active_spans[request_id])}) "
                f"exceeds limit ({self.MAX_ACTIVE_SPANS_PER_REQUEST}), possible span leak"
            )

        # 更新统计
        self._stats["total_spans"] += 1

        logger.debug(f"[{request_id}] Span started: {name}")

        return span

    def end_span(self, span: Span):
        """结束 Span"""
        span.end()

        request_id = span.request_id

        # 从活跃列表移除
        if request_id in self._active_spans:
            if span in self._active_spans[request_id]:
                self._active_spans[request_id].remove(span)

        # 添加到已完成列表
        if request_id not in self._completed_spans:
            self._completed_spans[request_id] = []
        self._completed_spans[request_id].append(span)

        # 淘汰过旧的已完成请求数据
        self._evict_completed_spans()

        # 更新统计
        if span.status == SpanStatus.ERROR:
            self._stats["error_count"] += 1

        # 记录日志
        log_msg = f"[{request_id}] Span ended: {span.name} | {span.duration_ms:.2f}ms | {span.status}"
        if span.status == SpanStatus.ERROR:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

    def _evict_completed_spans(self):
        """淘汰过旧的已完成请求数据，保持 _completed_spans 不超过上限"""
        while len(self._completed_spans) > self.MAX_COMPLETED_REQUESTS:
            oldest_key = next(iter(self._completed_spans))
            del self._completed_spans[oldest_key]

    @asynccontextmanager
    async def span(self, name: str, attributes: Dict[str, Any] = None):
        """异步上下文管理器

        使用示例：
            async with tracer.span("operation") as span:
                span.set_attribute("key", "value")
                await do_something()
        """
        s = self.start_span(name, attributes)
        try:
            yield s
            s.set_status(SpanStatus.OK)
        except Exception as e:
            s.set_status(SpanStatus.ERROR, str(e))
            raise
        finally:
            self.end_span(s)

    def get_trace(self, request_id: str) -> List[Dict[str, Any]]:
        """获取某个请求的完整追踪链"""
        spans = self._completed_spans.get(request_id, [])
        return [span.to_dict() for span in spans]

    def get_active_spans(self, request_id: str = None) -> List[Span]:
        """获取活跃的 Span"""
        if request_id:
            return self._active_spans.get(request_id, [])
        else:
            # 返回所有活跃 Span
            all_spans = []
            for spans in self._active_spans.values():
                all_spans.extend(spans)
            return all_spans

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "active_span_count": sum(len(spans) for spans in self._active_spans.values()),
            "completed_request_count": len(self._completed_spans)
        }

    def clear_request(self, request_id: str):
        """清理某个请求的追踪数据"""
        if request_id in self._active_spans:
            del self._active_spans[request_id]
        if request_id in self._completed_spans:
            del self._completed_spans[request_id]

    def clear_all(self):
        """清理所有追踪数据"""
        self._active_spans.clear()
        self._completed_spans.clear()
        logger.info("All tracing data cleared")

    def export_traces(self, format: str = "json") -> str:
        """导出追踪数据

        Args:
            format: 导出格式，支持 json

        Returns:
            导出的数据字符串
        """
        import json

        all_traces = {}
        for request_id, spans in self._completed_spans.items():
            all_traces[request_id] = [span.to_dict() for span in spans]

        if format == "json":
            return json.dumps(all_traces, ensure_ascii=False, indent=2)

        raise ValueError(f"Unsupported export format: {format}")


# ============================================
# 全局 Tracer 实例
# ============================================

tracer = Tracer()


# ============================================
# 便捷函数
# ============================================

def start_span(name: str, attributes: Dict[str, Any] = None) -> Span:
    """开始一个 Span"""
    return tracer.start_span(name, attributes)


def end_span(span: Span):
    """结束 Span"""
    tracer.end_span(span)


@asynccontextmanager
async def trace_span(name: str, attributes: Dict[str, Any] = None):
    """追踪 Span（异步上下文管理器）"""
    async with tracer.span(name, attributes) as span:
        yield span


# ============================================
# 装饰器
# ============================================

def traced(name: str = None):
    """追踪装饰器

    使用示例：
        @traced("my_function")
        async def my_function():
            ...
    """
    def decorator(func):
        span_name = name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with tracer.span(span_name) as span:
                # 记录参数
                span.set_attribute("function", func.__name__)
                if args:
                    span.set_attribute("args_count", len(args))
                if kwargs:
                    span.set_attribute("kwargs", list(kwargs.keys()))

                result = await func(*args, **kwargs)
                return result

        return wrapper
    return decorator


# ============================================
# 性能分析工具
# ============================================

class PerformanceAnalyzer:
    """性能分析器

    分析追踪数据，找出性能瓶颈
    """

    @staticmethod
    def analyze_trace(trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析追踪链

        Returns:
            {
                "total_duration_ms": float,
                "span_count": int,
                "slow_spans": [...],  # 耗时 > 100ms
                "error_spans": [...],
                "span_breakdown": {...}  # 各 Span 耗时占比
            }
        """
        if not trace:
            return {}

        total_duration = 0
        slow_spans = []
        error_spans = []
        span_breakdown = {}

        for span in trace:
            duration = span.get("duration_ms", 0) or 0
            total_duration = max(total_duration, duration)

            # 记录慢 Span
            if duration > 100:
                slow_spans.append({
                    "name": span["name"],
                    "duration_ms": duration
                })

            # 记录错误 Span
            if span.get("status") == SpanStatus.ERROR:
                error_spans.append({
                    "name": span["name"],
                    "message": span.get("status_message", "")
                })

            # 统计各类型耗时
            span_name = span["name"]
            if span_name not in span_breakdown:
                span_breakdown[span_name] = {
                    "count": 0,
                    "total_ms": 0,
                    "avg_ms": 0
                }
            span_breakdown[span_name]["count"] += 1
            span_breakdown[span_name]["total_ms"] += duration

        # 计算平均值
        for name, data in span_breakdown.items():
            data["avg_ms"] = data["total_ms"] / data["count"]

        return {
            "total_duration_ms": round(total_duration, 2),
            "span_count": len(trace),
            "slow_spans": sorted(slow_spans, key=lambda x: x["duration_ms"], reverse=True),
            "error_spans": error_spans,
            "span_breakdown": span_breakdown
        }
