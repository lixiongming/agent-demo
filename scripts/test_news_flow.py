"""测试"热门的新闻"查询流程

验证完整流程：
1. 智能路由识别
2. 工具决策
3. 工具执行
4. 数据库查询
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
from app.agent.nodes import tool_decision_node, tool_execute_node
from app.agent.state import ChatState
from app.tools.news_query import news_query_tool
from app.tools.registry import get_registry
from app.core.logger import get_logger
from app.db.database import AsyncSessionLocal
from app.db.repositories.news import NewsRepository

logger = get_logger(__name__)


async def test_smart_route():
    """测试智能路由识别"""
    print("\n" + "="*60)
    print("测试 1: 智能路由识别")
    print("="*60)
    
    test_queries = [
        "热门的新闻",
        "推荐最热的新闻",
        "查看热门新闻",
        "最近有什么新闻",
    ]
    
    for query in test_queries:
        print(f"\n【问题】{query}")
        
        # 智能路由决策
        decision = await smart_route(query)
        
        print(f"   路由决策:")
        print(f"      - needs_retrieval: {decision.get('needs_retrieval')}")
        print(f"      - needs_tool: {decision.get('needs_tool')}")
        print(f"      - tool_name: {decision.get('tool_name')}")
        print(f"      - method: {decision.get('method')}")
        print(f"      - reason: {decision.get('reason')}")
        
        # 验证结果
        if decision.get("needs_tool") and decision.get("tool_name") == "news_query":
            print(f"   ✅ 正确：识别为新闻查询")
        else:
            print(f"   ❌ 错误：未识别为新闻查询")


async def test_tool_registry():
    """测试工具注册"""
    print("\n" + "="*60)
    print("测试 2: 工具注册检查")
    print("="*60)
    
    registry = get_registry()
    
    # 检查工具是否注册
    tools = registry.list_tools()
    print(f"\n已注册工具数量: {len(tools)}")
    
    for tool in tools:
        print(f"   - {tool.name}: {tool.description[:50]}...")
    
    # 检查 news_query 工具
    news_tool = registry.get_tool("news_query")
    if news_tool:
        print(f"\n✅ news_query 工具已注册")
        print(f"   名称: {news_tool.name}")
        print(f"   描述: {news_tool.description}")
    else:
        print(f"\n❌ news_query 工具未注册")


async def test_tool_decision():
    """测试工具决策节点"""
    print("\n" + "="*60)
    print("测试 3: 工具决策节点")
    print("="*60)
    
    # 模拟状态
    state = ChatState(
        current_input="热门的新闻",
        route_decision={
            "needs_tool": True,
            "tool_name": "news_query",
            "reason": "包含新闻查询关键词: 热门",
            "method": "keyword"
        },
        messages=[]
    )
    
    print(f"\n【输入状态】")
    print(f"   current_input: {state['current_input']}")
    print(f"   route_decision: {state['route_decision']}")
    
    # 执行工具决策节点
    result = await tool_decision_node(state)
    
    print(f"\n【输出结果】")
    print(f"   tool_decision: {result.get('tool_decision')}")
    
    # 验证结果
    tool_decision = result.get("tool_decision", {})
    if tool_decision.get("needs_tool") and tool_decision.get("tool_name") == "news_query":
        print(f"\n✅ 工具决策正确")
    else:
        print(f"\n❌ 工具决策错误")


async def test_tool_execute():
    """测试工具执行节点"""
    print("\n" + "="*60)
    print("测试 4: 工具执行节点")
    print("="*60)
    
    # 模拟状态
    state = ChatState(
        current_input="热门的新闻",
        tool_decision={
            "needs_tool": True,
            "tool_name": "news_query",
            "tool_args": {"question": "热门的新闻"},
            "reason": "路由决策指定",
            "method": "route_decision"
        },
        messages=[]
    )
    
    print(f"\n【输入状态】")
    print(f"   tool_name: {state['tool_decision']['tool_name']}")
    print(f"   tool_args: {state['tool_decision']['tool_args']}")
    
    # 执行工具执行节点
    try:
        result = await tool_execute_node(state)
        
        print(f"\n【输出结果】")
        print(f"   tool_used: {result.get('tool_used')}")
        
        # 获取工具结果（注意：返回的是 tool_results 列表）
        tool_results = result.get("tool_results", [])
        if tool_results:
            tool_result = tool_results[0].get("result", {})
            print(f"   tool_result: {tool_result}")
            
            if result.get("tool_used"):
                if tool_result.get("success"):
                    print(f"\n✅ 工具执行成功")
                    print(f"   新闻数量: {tool_result.get('news_count', 0)}")
                    if tool_result.get('news_list'):
                        print(f"   新闻列表:")
                        for news in tool_result['news_list'][:3]:
                            print(f"      - {news['title']} (浏览量: {news['views']})")
                else:
                    print(f"\n❌ 工具执行失败: {tool_result.get('error')}")
            else:
                print(f"\n❌ 工具未执行")
        else:
            print(f"   tool_results: []")
            print(f"\n❌ 工具未执行")
    
    except Exception as e:
        print(f"\n❌ 工具执行异常: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_news_query_directly():
    """直接测试新闻查询工具"""
    print("\n" + "="*60)
    print("测试 5: 直接调用新闻查询工具")
    print("="*60)
    
    try:
        # 直接调用工具
        result = await news_query_tool(
            query_type="hot",
            limit=5
        )
        
        print(f"\n【查询结果】")
        print(f"   success: {result.get('success')}")
        print(f"   news_count: {result.get('news_count', 0)}")
        
        if result.get("success"):
            print(f"\n✅ 查询成功")
            if result.get('news_list'):
                print(f"   热门新闻:")
                for news in result['news_list']:
                    print(f"      - {news['title']} (浏览量: {news['views']})")
        else:
            print(f"\n❌ 查询失败: {result.get('error')}")
    
    except Exception as e:
        print(f"\n❌ 查询异常: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_database_connection():
    """测试数据库连接"""
    print("\n" + "="*60)
    print("测试 6: 数据库连接检查")
    print("="*60)
    
    try:
        # 测试数据库连接
        async with AsyncSessionLocal() as session:
            repo = NewsRepository(session)
            
            # 查询新闻总数
            total = await repo.get_total_count()
            print(f"\n✅ 数据库连接成功")
            print(f"   新闻总数: {total}")
            
            # 查询热门新闻
            hot_news = await repo.get_hot_news(limit=3)
            print(f"   热门新闻数量: {len(hot_news)}")
            
            if hot_news:
                print(f"   热门新闻:")
                for news in hot_news:
                    print(f"      - {news.title} (浏览量: {news.views})")
    
    except Exception as e:
        print(f"\n❌ 数据库连接失败: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_full_flow():
    """测试完整流程"""
    print("\n" + "="*60)
    print("测试 7: 完整流程（智能路由 → 工具决策 → 工具执行）")
    print("="*60)
    
    query = "热门的新闻"
    print(f"\n【用户问题】{query}")
    
    # 1. 智能路由
    print(f"\n步骤 1: 智能路由")
    route_decision = await smart_route(query)
    print(f"   needs_tool: {route_decision.get('needs_tool')}")
    print(f"   tool_name: {route_decision.get('tool_name')}")
    
    # 2. 工具决策
    print(f"\n步骤 2: 工具决策")
    state = ChatState(
        current_input=query,
        route_decision=route_decision,
        messages=[]
    )
    tool_decision_result = await tool_decision_node(state)
    tool_decision = tool_decision_result.get("tool_decision", {})
    print(f"   needs_tool: {tool_decision.get('needs_tool')}")
    print(f"   tool_name: {tool_decision.get('tool_name')}")
    
    # 3. 工具执行
    print(f"\n步骤 3: 工具执行")
    state["tool_decision"] = tool_decision
    tool_execute_result = await tool_execute_node(state)
    
    # 获取工具结果（注意：返回的是 tool_results 列表）
    tool_results = tool_execute_result.get("tool_results", [])
    if tool_results:
        tool_result = tool_results[0].get("result", {})
        print(f"   success: {tool_result.get('success')}")
        print(f"   news_count: {tool_result.get('news_count', 0)}")
    else:
        tool_result = {}
        print(f"   success: None")
        print(f"   news_count: 0")
    
    # 4. 最终结果
    print(f"\n【最终结果】")
    if tool_result.get("success"):
        print(f"✅ 查询成功！")
        if tool_result.get('news_list'):
            print(f"   热门新闻:")
            for news in tool_result['news_list'][:5]:
                print(f"      - {news['title']} (浏览量: {news['views']})")
    else:
        print(f"❌ 查询失败: {tool_result.get('error')}")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("新闻查询完整流程测试")
    print("="*60)
    
    # 测试 1: 智能路由识别
    await test_smart_route()
    
    # 测试 2: 工具注册检查
    await test_tool_registry()
    
    # 测试 3: 工具决策节点
    await test_tool_decision()
    
    # 测试 4: 工具执行节点（需要数据库）
    await test_tool_execute()

    # 测试 5: 直接调用工具（需要数据库）
    await test_news_query_directly()

    # 测试 6: 数据库连接（需要数据库）
    await test_database_connection()

    # 测试 7: 完整流程（需要数据库）
    await test_full_flow()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    print("\n提示：")
    print("1. 如果数据库已配置，取消注释测试 4-7")
    print("2. 如果数据库未配置，请先配置数据库连接")
    print("3. 检查 news 表是否存在")


if __name__ == "__main__":
    asyncio.run(main())