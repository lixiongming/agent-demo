"""测试优化后的智能路由功能

验证：
1. 关键词快速路径（毫秒级）
2. 规则引擎匹配（毫秒级）
3. LLM 智能决策（带缓存）
4. 降级策略
"""
import asyncio
import time
from app.agent.smart_router import get_router
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_smart_router():
    """测试智能路由器"""
    
    router = get_router()
    
    # 测试用例
    test_cases = [
        # 关键词快速路径
        {
            "question": "这个产品的功能是什么？",
            "expected_method": "keyword",
            "expected_retrieval": True,
            "category": "关键词-产品"
        },
        {
            "question": "如何使用API接口？",
            "expected_method": "keyword",
            "expected_retrieval": True,
            "category": "关键词-API"
        },
        {
            "question": "你好",
            "expected_method": "keyword",
            "expected_retrieval": False,
            "category": "关键词-问候"
        },
        {
            "question": "今天天气怎么样？",
            "expected_method": "keyword",
            "expected_retrieval": False,
            "category": "关键词-通用"
        },
        
        # 规则引擎匹配
        {
            "question": "1 + 1",
            "expected_method": "pattern",
            "expected_retrieval": False,
            "category": "规则-数学"
        },
        {
            "question": "3 * 5 + 2",
            "expected_method": "pattern",
            "expected_retrieval": False,
            "category": "规则-数学"
        },
        {
            "question": "你好，请问有什么可以帮助我的？",
            "expected_method": "pattern",
            "expected_retrieval": False,
            "category": "规则-问候"
        },
        {
            "question": "谢谢你的帮助",
            "expected_method": "pattern",
            "expected_retrieval": False,
            "category": "规则-感谢"
        },
        
        # LLM 智能决策
        {
            "question": "英雄联盟的游戏规则是什么？",
            "expected_method": "llm",
            "expected_retrieval": True,
            "category": "LLM-游戏知识"
        },
        {
            "question": "请帮我分析一下这个问题",
            "expected_method": "llm",
            "expected_retrieval": False,
            "category": "LLM-通用分析"
        },
        
        # 缓存测试（重复问题）
        {
            "question": "英雄联盟的游戏规则是什么？",
            "expected_method": "cache",
            "expected_retrieval": True,
            "category": "缓存-重复问题"
        }
    ]
    
    print("=" * 80)
    print("智能路由测试 - 生产级实现")
    print("=" * 80)
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试 {i}: {test_case['question']}")
        print(f"分类: {test_case['category']}")
        print(f"预期: method={test_case['expected_method']}, retrieval={test_case['expected_retrieval']}")
        
        start_time = time.time()
        decision = await router.route(test_case['question'])
        elapsed = time.time() - start_time
        
        print(f"\n实际结果:")
        print(f"  - 方法: {decision.get('method')}")
        print(f"  - 需要检索: {decision.get('needs_retrieval')}")
        print(f"  - 原因: {decision.get('reason')}")
        print(f"  - 置信度: {decision.get('confidence')}")
        print(f"  - 延迟: {decision.get('latency_ms', 0)} ms")
        print(f"  - 总耗时: {elapsed*1000:.2f} ms")
        
        # 验证结果
        method_match = decision.get('method') == test_case['expected_method']
        retrieval_match = decision.get('needs_retrieval') == test_case['expected_retrieval']
        
        if method_match and retrieval_match:
            print("✅ 测试通过")
            status = "PASS"
        else:
            print(f"❌ 测试失败 (method: {method_match}, retrieval: {retrieval_match})")
            status = "FAIL"
        
        results.append({
            "test": i,
            "question": test_case['question'],
            "category": test_case['category'],
            "expected_method": test_case['expected_method'],
            "actual_method": decision.get('method'),
            "expected_retrieval": test_case['expected_retrieval'],
            "actual_retrieval": decision.get('needs_retrieval'),
            "latency_ms": decision.get('latency_ms', 0),
            "status": status
        })
    
    # 打印统计信息
    print("\n" + "=" * 80)
    print("路由统计")
    print("=" * 80)
    stats = router.get_stats()
    print(f"总请求数: {stats['total_requests']}")
    print(f"关键词命中: {stats['keyword_hits']} ({stats['keyword_rate']*100:.1f}%)")
    print(f"规则命中: {stats['pattern_hits']} ({stats['pattern_rate']*100:.1f}%)")
    print(f"LLM 调用: {stats['llm_hits']} ({stats['llm_rate']*100:.1f}%)")
    print(f"缓存命中: {stats['cache_hits']} ({stats['cache_rate']*100:.1f}%)")
    print(f"缓存大小: {stats['cache_size']}")
    
    # 打印测试结果汇总
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    pass_count = sum(1 for r in results if r['status'] == 'PASS')
    fail_count = len(results) - pass_count
    
    print(f"通过: {pass_count}/{len(results)}")
    print(f"失败: {fail_count}/{len(results)}")
    print(f"通过率: {pass_count/len(results)*100:.1f}%")
    
    # 性能分析
    print("\n" + "=" * 80)
    print("性能分析")
    print("=" * 80)
    
    keyword_latencies = [r['latency_ms'] for r in results if r['actual_method'] == 'keyword']
    pattern_latencies = [r['latency_ms'] for r in results if r['actual_method'] == 'pattern']
    llm_latencies = [r['latency_ms'] for r in results if r['actual_method'] == 'llm']
    cache_latencies = [r['latency_ms'] for r in results if r['actual_method'] == 'cache']
    
    if keyword_latencies:
        print(f"关键词路径平均延迟: {sum(keyword_latencies)/len(keyword_latencies):.2f} ms")
    if pattern_latencies:
        print(f"规则引擎平均延迟: {sum(pattern_latencies)/len(pattern_latencies):.2f} ms")
    if llm_latencies:
        print(f"LLM 决策平均延迟: {sum(llm_latencies)/len(llm_latencies):.2f} ms")
    if cache_latencies:
        print(f"缓存命中平均延迟: {sum(cache_latencies)/len(cache_latencies):.2f} ms")
    
    # 性能提升计算
    if llm_latencies and keyword_latencies:
        improvement = (sum(llm_latencies)/len(llm_latencies) - sum(keyword_latencies)/len(keyword_latencies)) / (sum(llm_latencies)/len(llm_latencies)) * 100
        print(f"\n关键词路径相比 LLM 决策性能提升: {improvement:.1f}%")


if __name__ == "__main__":
    asyncio.run(test_smart_router())
