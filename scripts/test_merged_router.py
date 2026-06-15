"""测试合并后的智能路由系统

验证合并后的路由系统是否正常工作
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.smart_router import smart_route, get_router
from app.tools.tool_registry import tool_registry
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_merged_router():
    """测试合并后的路由系统"""
    print("\n" + "="*60)
    print("测试合并后的智能路由系统")
    print("="*60)
    
    # 测试各种问题
    test_queries = [
        # 规则引擎匹配（正则表达式）
        ("你好", "pattern", None),
        ("谢谢", "pattern", None),
        ("计算1+2等于几", "pattern", "calculator"),
        ("现在几点", "pattern", None),
        
        # LLM决策（天气查询）
        ("北京天气怎么样", "llm", "get_weather"),
        ("上海天气如何", "llm", "get_weather"),
        
        # LLM决策（新闻查询）
        ("热门新闻", "llm", "news_query"),
        ("最近有什么新闻", "llm", "news_query"),
        
        # LLM决策（数据库查询）
        ("查询订单数据", "llm", "mysql_query"),
        ("最近一周的用户数量", "llm", "mysql_query"),
        
        # LLM决策（知识库检索）
        ("产品功能介绍", "llm", "knowledge_search"),
        ("API接口文档", "llm", "knowledge_search"),
        
        # LLM决策（闲聊）
        ("今天心情不错", "llm", None),
    ]
    
    for query, expected_method, expected_tool in test_queries:
        print(f"\n【测试问题】{query}")
        print(f"   预期方法: {expected_method}")
        print(f"   预期工具: {expected_tool or '无'}")
        
        # 路由决策
        result = await smart_route(query)
        
        print(f"   路由结果:")
        print(f"      - method: {result.get('method')}")
        print(f"      - needs_tool: {result.get('needs_tool')}")
        print(f"      - tool_name: {result.get('tool_name')}")
        print(f"      - tool_args: {result.get('tool_args')}")
        print(f"      - reason: {result.get('reason')}")
        print(f"      - confidence: {result.get('confidence')}")
        print(f"      - latency_ms: {result.get('latency_ms')}ms")
        
        # 验证结果
        actual_method = result.get('method')
        actual_tool = result.get('tool_name')
        
        if actual_method == expected_method:
            print(f"      ✅ 方法正确：{actual_method}")
        else:
            print(f"      ⚠️  方法不符：{actual_method}（预期{expected_method})")
        
        if expected_tool is None:
            if not result.get('needs_tool'):
                print(f"      ✅ 工具正确：不需要工具")
            else:
                print(f"      ⚠️  工具不符：应该不需要工具")
        elif actual_tool == expected_tool:
            print(f"      ✅ 工具正确：{actual_tool}")
        else:
            print(f"      ⚠️  工具不符：{actual_tool}（预期{expected_tool})")


async def test_router_stats():
    """测试路由统计"""
    print("\n" + "="*60)
    print("测试路由统计")
    print("="*60)
    
    router = get_router()
    stats = router.get_stats()
    
    print(f"\n【统计数据】")
    print(f"   总请求: {stats['total_requests']}")
    print(f"   规则引擎命中: {stats['pattern_hits']}")
    print(f"   缓存命中: {stats['cache_hits']}")
    print(f"   LLM调用: {stats['llm_calls']}")
    print(f"   工具调用: {stats['tool_calls']}")
    print(f"   无工具调用: {stats['no_tool_calls']}")
    print(f"   规则引擎率: {stats['pattern_rate']:.2%}")
    print(f"   缓存率: {stats['cache_rate']:.2%}")
    print(f"   工具调用率: {stats['tool_rate']:.2%}")


async def test_cache():
    """测试缓存机制"""
    print("\n" + "="*60)
    print("测试缓存机制")
    print("="*60)
    
    # 第一次查询（会调用LLM）
    query = "北京天气怎么样"
    print(f"\n【第一次查询】{query}")
    result1 = await smart_route(query)
    print(f"   method: {result1.get('method')}")
    print(f"   latency_ms: {result1.get('latency_ms')}ms")
    
    # 第二次查询（会使用缓存）
    print(f"\n【第二次查询】{query}")
    result2 = await smart_route(query)
    print(f"   method: {result2.get('method')}")
    print(f"   latency_ms: {result2.get('latency_ms')}ms")
    
    # 验证缓存
    if result2.get('method') == 'cache':
        print(f"   ✅ 缓存机制正常工作")
    else:
        print(f"   ❌ 缓存机制未生效")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("合并后的智能路由系统测试")
    print("="*60)
    
    await test_merged_router()
    await test_router_stats()
    await test_cache()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())