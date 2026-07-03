"""测试天气查询问题

检查智能路由是否正确识别天气查询
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.smart_router import smart_route
from app.tools.tool_definitions import tool_registry


async def test_weather_query():
    """测试天气查询"""
    print("\n" + "="*60)
    print("测试天气查询问题")
    print("="*60)
    
    # 测试问题
    query = "北京天气怎么样?"
    
    print(f"\n【测试问题】{query}")
    
    # 1. 检查工具注册
    print(f"\n【检查工具注册】")
    weather_tool = tool_registry.get_tool("get_weather")
    if weather_tool:
        print(f"   ✅ 天气工具已注册")
        print(f"   工具名称: {weather_tool.name}")
        print(f"   工具描述: {weather_tool.description[:50]}...")
        print(f"   工具参数: {list(weather_tool.parameters.keys())}")
    else:
        print(f"   ❌ 天气工具未注册")
    
    # 2. 检查智能路由
    print(f"\n【检查智能路由】")
    result = await smart_route(query)
    
    print(f"   路由结果:")
    print(f"      - method: {result.get('method')}")
    print(f"      - needs_tool: {result.get('needs_tool')}")
    print(f"      - tool_name: {result.get('tool_name')}")
    print(f"      - tool_args: {result.get('tool_args')}")
    print(f"      - reason: {result.get('reason')}")
    print(f"      - confidence: {result.get('confidence')}")
    print(f"      - latency_ms: {result.get('latency_ms')}ms")
    
    # 3. 验证结果
    if result.get('tool_name') == 'get_weather':
        print(f"   ✅ 正确识别为天气查询")
        
        # 4. 检查工具参数
        tool_args = result.get('tool_args', {})
        if 'city' in tool_args:
            print(f"   ✅ 工具参数正确: city={tool_args['city']}")
        else:
            print(f"   ⚠️  工具参数缺少: city")
    else:
        print(f"   ❌ 未识别为天气查询")
        print(f"   实际识别为: {result.get('tool_name')}")
    
    # 5. 测试其他天气问题
    print(f"\n【测试其他天气问题】")
    test_queries = [
        "上海天气如何",
        "广州的气温",
        "深圳天气",
        "今天下雨吗"
    ]
    
    for q in test_queries:
        print(f"\n   问题: {q}")
        r = await smart_route(q)
        print(f"      tool_name: {r.get('tool_name')}")
        print(f"      tool_args: {r.get('tool_args')}")
        
        if r.get('tool_name') == 'get_weather':
            print(f"      ✅ 正确")
        else:
            print(f"      ❌ 错误")


if __name__ == "__main__":
    asyncio.run(test_weather_query())