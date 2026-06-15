"""测试智能路由V2系统

验证LLM Function Calling自动决策是否正常工作
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.smart_router_v2 import smart_route_v2, smart_router_v2
from app.tools.tool_registry import tool_registry
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_tool_registry():
    """测试工具注册中心"""
    print("\n" + "="*60)
    print("测试工具注册中心")
    print("="*60)
    
    # 获取所有工具
    tools = tool_registry.get_all_tools()
    
    print(f"\n已注册工具数量: {len(tools)}")
    
    for tool in tools:
        print(f"\n【工具】{tool.name}")
        print(f"   类别: {tool.category}")
        print(f"   描述: {tool.description[:50]}...")
        print(f"   参数: {list(tool.parameters.keys())}")
        print(f"   示例: {tool.examples[:2]}")
    
    # 测试工具描述格式
    print(f"\n【工具描述（供LLM决策）】")
    print(tool_registry.get_tools_description()[:500] + "...")
    
    # 测试OpenAI格式
    print(f"\n【OpenAI Function Calling格式】")
    openai_tools = tool_registry.get_openai_tools()
    print(f"工具数量: {len(openai_tools)}")
    print(f"示例: {openai_tools[0]}")


async def test_smart_router_v2():
    """测试智能路由V2"""
    print("\n" + "="*60)
    print("测试智能路由V2（LLM Function Calling）")
    print("="*60)
    
    # 测试各种问题
    test_queries = [
        # 天气查询
        ("北京天气怎么样", "get_weather"),
        ("上海天气如何", "get_weather"),
        ("广州的气温", "get_weather"),
        
        # 新闻查询
        ("热门新闻", "news_query"),
        ("最近有什么新闻", "news_query"),
        ("搜索科技新闻", "news_query"),
        
        # 数据库查询
        ("查询订单数据", "mysql_query"),
        ("最近一周的用户数量", "mysql_query"),
        
        # 知识库检索
        ("产品功能介绍", "knowledge_search"),
        ("API接口文档", "knowledge_search"),
        
        # 计算器
        ("计算1+2等于几", "calculator"),
        
        # 闲聊（不需要工具）
        ("你好", None),
        ("谢谢", None),
        ("再见", None)
    ]
    
    for query, expected_tool in test_queries:
        print(f"\n【测试问题】{query}")
        print(f"   预期工具: {expected_tool or '无'}")
        
        # 路由决策
        result = await smart_route_v2(query)
        
        print(f"   路由结果:")
        print(f"      - needs_tool: {result.get('needs_tool')}")
        print(f"      - tool_name: {result.get('tool_name')}")
        print(f"      - tool_args: {result.get('tool_args')}")
        print(f"      - reason: {result.get('reason')}")
        print(f"      - confidence: {result.get('confidence')}")
        print(f"      - method: {result.get('method')}")
        print(f"      - latency_ms: {result.get('latency_ms')}ms")
        
        # 验证结果
        actual_tool = result.get('tool_name')
        if expected_tool is None:
            if not result.get('needs_tool'):
                print(f"      ✅ 正确：识别为不需要工具")
            else:
                print(f"      ❌ 错误：应该不需要工具")
        elif actual_tool == expected_tool:
            print(f"      ✅ 正确：识别为{expected_tool}")
        else:
            print(f"      ⚠️  部分正确：识别为{actual_tool}（预期{expected_tool})")


async def test_router_stats():
    """测试路由统计"""
    print("\n" + "="*60)
    print("测试路由统计")
    print("="*60)
    
    stats = smart_router_v2.get_stats()
    
    print(f"\n【统计数据】")
    print(f"   总请求: {stats['total_requests']}")
    print(f"   缓存命中: {stats['cache_hits']}")
    print(f"   LLM调用: {stats['llm_calls']}")
    print(f"   工具调用: {stats['tool_calls']}")
    print(f"   无工具调用: {stats['no_tool_calls']}")
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
    result1 = await smart_route_v2(query)
    print(f"   method: {result1.get('method')}")
    print(f"   latency_ms: {result1.get('latency_ms')}ms")
    
    # 第二次查询（会使用缓存）
    print(f"\n【第二次查询】{query}")
    result2 = await smart_route_v2(query)
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
    print("智能路由V2系统测试")
    print("="*60)
    
    await test_tool_registry()
    await test_smart_router_v2()
    await test_router_stats()
    await test_cache()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())