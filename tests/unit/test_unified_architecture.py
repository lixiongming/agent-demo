"""测试统一架构（大厂标准 Agent 图模式）

运行方式：
    python scripts/test_unified_architecture.py
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent import get_chat_app
from app.core.logger import set_request_context, clear_request_context
from app.core.tracing import tracer, PerformanceAnalyzer


async def test_agent_graph_flow():
    """测试 Agent 图完整流程"""
    print("\n" + "="*60)
    print("测试 1: Agent 图完整流程")
    print("="*60)
    
    # 设置请求上下文
    set_request_context("test-unified-001", "user-123")
    
    # 准备初始状态
    initial_state = {
        "session_id": "test-session-001",
        "current_input": "你好",
        "user_id": 123,
        "model_name": "gpt-4o-mini",
        "messages": [],
        "history_loaded": False,
        "history_count": 0,
        "rag_used": False,
        "rag_strategy": None,
        "rag_score": 0.0,
        "user_message_saved": False,
        "assistant_message_saved": False
    }
    
    # 调用 Agent 图
    app = get_chat_app()
    result = await app.ainvoke(initial_state)
    
    print(f"\n响应: {result.get('response', '')[:100]}...")
    print(f"历史加载: {result.get('history_loaded')}")
    print(f"历史数量: {result.get('history_count')}")
    print(f"RAG 使用: {result.get('rag_used')}")
    print(f"消息保存: {result.get('assistant_message_saved')}")
    
    # 获取追踪链
    trace = tracer.get_trace("test-unified-001")
    print(f"\n追踪链长度: {len(trace)}")
    
    for t in trace:
        print(f"  - {t['name']}: {t['duration_ms']:.2f}ms, status={t['status']}")
    
    clear_request_context()


async def test_smart_routing():
    """测试智能路由"""
    print("\n" + "="*60)
    print("测试 2: 智能路由")
    print("="*60)
    
    test_cases = [
        ("你好", "通用问题，不应检索"),
        ("产品功能有哪些", "知识库问题，应检索"),
        ("1+1等于几", "数学运算，不应检索"),
        ("如何使用API", "知识库问题，应检索"),
    ]
    
    app = get_chat_app()
    
    for query, expected in test_cases:
        set_request_context(f"test-route-{query[:5]}", "user-123")
        
        initial_state = {
            "session_id": f"test-session-{query[:5]}",
            "current_input": query,
            "user_id": 123,
            "messages": [],
            "history_loaded": False,
            "history_count": 0,
            "rag_used": False,
            "rag_strategy": None,
            "rag_score": 0.0,
            "user_message_saved": False,
            "assistant_message_saved": False
        }
        
        result = await app.ainvoke(initial_state)
        
        route_decision = result.get("route_decision", {})
        needs_retrieval = route_decision.get("needs_retrieval", False)
        method = route_decision.get("method", "unknown")
        
        print(f"\n问题: {query}")
        print(f"  预期: {expected}")
        print(f"  实际: needs_retrieval={needs_retrieval}, method={method}")
        
        clear_request_context()


async def test_performance_analysis():
    """测试性能分析"""
    print("\n" + "="*60)
    print("测试 3: 性能分析")
    print("="*60)
    
    set_request_context("test-perf-001", "user-123")
    
    # 模拟一个完整请求
    initial_state = {
        "session_id": "test-session-perf",
        "current_input": "产品功能有哪些",
        "user_id": 123,
        "messages": [],
        "history_loaded": False,
        "history_count": 0,
        "rag_used": False,
        "rag_strategy": None,
        "rag_score": 0.0,
        "user_message_saved": False,
        "assistant_message_saved": False
    }
    
    app = get_chat_app()
    result = await app.ainvoke(initial_state)
    
    # 分析追踪链
    trace = tracer.get_trace("test-perf-001")
    analysis = PerformanceAnalyzer.analyze_trace(trace)
    
    print(f"\n总耗时: {analysis.get('total_duration_ms', 0):.2f}ms")
    print(f"Span 数量: {analysis.get('span_count', 0)}")
    
    print("\n各阶段耗时:")
    for name, data in analysis.get('span_breakdown', {}).items():
        print(f"  - {name}: avg={data['avg_ms']:.2f}ms, count={data['count']}")
    
    if analysis.get('slow_spans'):
        print("\n慢操作 (>100ms):")
        for slow in analysis['slow_spans']:
            print(f"  - {slow['name']}: {slow['duration_ms']:.2f}ms")
    
    clear_request_context()


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("统一架构测试（大厂标准 Agent 图模式）")
    print("="*60)
    
    await test_agent_graph_flow()
    await test_smart_routing()
    await test_performance_analysis()
    
    print("\n" + "="*60)
    print("所有测试完成!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
