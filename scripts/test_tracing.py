"""测试链路追踪功能

运行方式：
    python scripts/test_tracing.py
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.tracing import tracer, PerformanceAnalyzer, traced
from app.core.logger import set_request_context, clear_request_context


async def test_basic_tracing():
    """测试基础追踪功能"""
    print("\n" + "="*60)
    print("测试 1: 基础追踪")
    print("="*60)
    
    # 设置请求上下文
    set_request_context("test-001", "user-123")
    
    # 创建 Span
    async with tracer.span("operation_1") as span:
        span.set_attribute("key1", "value1")
        span.set_attribute("count", 100)
        await asyncio.sleep(0.1)  # 模拟耗时
        
        # 嵌套 Span
        async with tracer.span("sub_operation") as sub_span:
            sub_span.set_attribute("nested", True)
            await asyncio.sleep(0.05)
    
    # 获取追踪链
    trace = tracer.get_trace("test-001")
    print(f"\n追踪链长度: {len(trace)}")
    
    for t in trace:
        print(f"  - {t['name']}: {t['duration_ms']:.2f}ms")
    
    # 获取统计
    stats = tracer.get_stats()
    print(f"\n统计信息: {stats}")
    
    clear_request_context()


async def test_error_tracing():
    """测试错误追踪"""
    print("\n" + "="*60)
    print("测试 2: 错误追踪")
    print("="*60)
    
    set_request_context("test-002")
    
    try:
        async with tracer.span("error_operation") as span:
            span.set_attribute("will_fail", True)
            await asyncio.sleep(0.05)
            raise ValueError("模拟错误")
    except ValueError:
        pass
    
    # 检查追踪链
    trace = tracer.get_trace("test-002")
    for t in trace:
        print(f"  - {t['name']}: status={t['status']}, message={t.get('status_message', '')}")
    
    clear_request_context()


async def test_decorator():
    """测试装饰器"""
    print("\n" + "="*60)
    print("测试 3: 装饰器")
    print("="*60)
    
    set_request_context("test-003")
    
    @traced("my_function")
    async def my_function(x: int, y: int):
        await asyncio.sleep(0.03)
        return x + y
    
    result = await my_function(1, 2)
    print(f"函数结果: {result}")
    
    # 检查追踪
    trace = tracer.get_trace("test-003")
    for t in trace:
        print(f"  - {t['name']}: {t['duration_ms']:.2f}ms, attrs={t['attributes']}")
    
    clear_request_context()


async def test_performance_analysis():
    """测试性能分析"""
    print("\n" + "="*60)
    print("测试 4: 性能分析")
    print("="*60)
    
    set_request_context("test-004")
    
    # 模拟一个完整的请求链路
    async with tracer.span("route_decision") as span:
        span.set_attribute("method", "keyword")
        span.set_attribute("needs_retrieval", True)
        await asyncio.sleep(0.005)  # 5ms
    
    async with tracer.span("rag_retrieve") as span:
        span.set_attribute("doc_count", 5)
        await asyncio.sleep(0.15)  # 150ms - 慢操作
        
        async with tracer.span("vector_search") as sub_span:
            sub_span.set_attribute("top_k", 10)
            await asyncio.sleep(0.12)  # 120ms
    
    async with tracer.span("chat") as span:
        span.set_attribute("rag_used", True)
        await asyncio.sleep(0.8)  # 800ms - LLM 调用
        
        async with tracer.span("llm_invoke") as sub_span:
            sub_span.set_attribute("model", "gpt-4")
            await asyncio.sleep(0.75)
    
    # 分析追踪链
    trace = tracer.get_trace("test-004")
    analysis = PerformanceAnalyzer.analyze_trace(trace)
    
    print(f"\n总耗时: {analysis['total_duration_ms']:.2f}ms")
    print(f"Span 数量: {analysis['span_count']}")
    
    print("\n慢操作 (>100ms):")
    for slow in analysis['slow_spans']:
        print(f"  - {slow['name']}: {slow['duration_ms']:.2f}ms")
    
    print("\n各阶段耗时:")
    for name, data in analysis['span_breakdown'].items():
        print(f"  - {name}: avg={data['avg_ms']:.2f}ms, total={data['total_ms']:.2f}ms, count={data['count']}")
    
    clear_request_context()


async def test_multiple_requests():
    """测试多请求追踪"""
    print("\n" + "="*60)
    print("测试 5: 多请求追踪")
    print("="*60)
    
    async def simulate_request(req_id: str, duration: float):
        set_request_context(req_id)
        async with tracer.span("request") as span:
            span.set_attribute("duration", duration)
            await asyncio.sleep(duration)
        clear_request_context()
    
    # 并发多个请求
    await asyncio.gather(
        simulate_request("req-001", 0.1),
        simulate_request("req-002", 0.15),
        simulate_request("req-003", 0.08),
    )
    
    # 获取统计
    stats = tracer.get_stats()
    print(f"\n总 Span 数: {stats['total_spans']}")
    print(f"已完成请求数: {stats['completed_request_count']}")


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("链路追踪功能测试")
    print("="*60)
    
    await test_basic_tracing()
    await test_error_tracing()
    await test_decorator()
    await test_performance_analysis()
    await test_multiple_requests()
    
    print("\n" + "="*60)
    print("所有测试完成!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
