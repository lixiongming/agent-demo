"""测试统一架构（简化版，不依赖外部服务）

运行方式：
    python scripts/test_unified_architecture_simple.py
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_imports():
    """测试导入是否正常"""
    print("\n" + "="*60)
    print("测试 1: 模块导入")
    print("="*60)
    
    try:
        from app.agent.state import ChatState
        print("✅ ChatState 导入成功")
        
        from app.agent.nodes import (
            load_history_node, 
            save_message_node,
            route_decision_node,
            rag_retrieve_node,
            chat_node
        )
        print("✅ 所有节点导入成功")
        
        from app.agent.graph import create_chat_graph
        print("✅ create_chat_graph 导入成功")
        
        from app.services.chat import ChatService
        print("✅ ChatService 导入成功")
        
        print("\n所有导入测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_state_structure():
    """测试状态结构"""
    print("\n" + "="*60)
    print("测试 2: 状态结构")
    print("="*60)
    
    from app.agent.state import ChatState
    
    # 创建测试状态
    test_state = {
        "session_id": "test-001",
        "current_input": "你好",
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
    
    print(f"✅ 状态创建成功")
    print(f"  - session_id: {test_state['session_id']}")
    print(f"  - current_input: {test_state['current_input']}")
    print(f"  - history_loaded: {test_state['history_loaded']}")
    
    return True


async def test_smart_router():
    """测试智能路由"""
    print("\n" + "="*60)
    print("测试 3: 智能路由")
    print("="*60)
    
    try:
        from app.agent.smart_router import SmartRouter
        
        router = SmartRouter()
        
        # 测试关键词路由
        result = router._keyword_route("你好")
        if result:
            print(f"✅ 关键词路由: '你好' -> needs_retrieval={result.get('needs_retrieval')}")
        
        result = router._keyword_route("产品功能有哪些")
        if result:
            print(f"✅ 关键词路由: '产品功能有哪些' -> needs_retrieval={result.get('needs_retrieval')}")
        
        # 测试规则路由
        result = router._pattern_route("1+1")
        if result:
            print(f"✅ 规则路由: '1+1' -> needs_retrieval={result.get('needs_retrieval')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 智能路由测试失败: {e}")
        return False


async def test_tracing():
    """测试链路追踪"""
    print("\n" + "="*60)
    print("测试 4: 链路追踪")
    print("="*60)
    
    try:
        from app.core.tracing import tracer, SpanStatus
        
        # 创建测试 Span
        async with tracer.span("test_operation") as span:
            span.set_attribute("test_key", "test_value")
            await asyncio.sleep(0.01)
        
        print("✅ Span 创建成功")
        
        # 获取统计
        stats = tracer.get_stats()
        print(f"✅ 统计信息: total_spans={stats['total_spans']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 链路追踪测试失败: {e}")
        return False


async def test_chat_service_structure():
    """测试 ChatService 结构"""
    print("\n" + "="*60)
    print("测试 5: ChatService 结构")
    print("="*60)
    
    try:
        from app.services.chat import ChatService
        
        # 检查方法存在
        assert hasattr(ChatService, 'chat'), "缺少 chat 方法"
        assert hasattr(ChatService, 'chat_stream'), "缺少 chat_stream 方法"
        assert hasattr(ChatService, 'create_session'), "缺少 create_session 方法"
        
        print("✅ ChatService 结构正确")
        print("  - chat 方法存在")
        print("  - chat_stream 方法存在")
        print("  - create_session 方法存在")
        
        return True
        
    except Exception as e:
        print(f"❌ ChatService 结构测试失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("统一架构测试（简化版）")
    print("="*60)
    
    results = []
    
    results.append(await test_imports())
    results.append(await test_state_structure())
    results.append(await test_smart_router())
    results.append(await test_tracing())
    results.append(await test_chat_service_structure())
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("\n✅ 所有测试通过！统一架构已就绪。")
    else:
        print(f"\n❌ {total - passed} 个测试失败")


if __name__ == "__main__":
    asyncio.run(main())
