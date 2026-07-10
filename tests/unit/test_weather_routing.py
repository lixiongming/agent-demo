"""测试天气工具在聊天中的调用

验证智能路由是否能识别天气查询
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.smart_router import SmartRouter
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_weather_routing():
    """测试天气路由"""
    print("\n" + "="*60)
    print("测试天气工具路由")
    print("="*60)
    
    router = SmartRouter()
    
    # 测试天气查询
    test_queries = [
        "北京天气怎么样",
        "上海天气如何",
        "广州天气",
        "深圳的气温",
        "今天下雨吗",
        "晴天还是多云"
    ]
    
    for query in test_queries:
        print(f"\n【测试问题】{query}")
        
        result = await router.route(query)
        
        print(f"路由结果:")
        print(f"  - needs_retrieval: {result.get('needs_retrieval')}")
        print(f"  - needs_tool: {result.get('needs_tool')}")
        print(f"  - tool_name: {result.get('tool_name')}")
        print(f"  - method: {result.get('method')}")
        print(f"  - reason: {result.get('reason')}")
        print(f"  - confidence: {result.get('confidence')}")
        
        # 验证结果
        if result.get('tool_name') == 'get_weather':
            print(f"  ✅ 正确：识别为天气查询")
        else:
            print(f"  ❌ 错误：应该识别为天气查询")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("天气工具路由测试")
    print("="*60)
    
    await test_weather_routing()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())