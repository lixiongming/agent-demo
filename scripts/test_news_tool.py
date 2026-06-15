"""测试新闻查询工具

演示：
- 新闻搜索
- 热门新闻
- 最近新闻
- 作者新闻
- 新闻统计
- 智能查询
"""
import asyncio
from app.tools.news_query import news_query_tool, smart_news_query
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_basic_queries():
    """测试基础查询"""
    print("\n" + "="*60)
    print("测试 1: 基础查询")
    print("="*60)
    
    # 1. 搜索新闻
    print("\n【搜索新闻】关键词: 科技")
    result = await news_query_tool(query_type="search", keyword="科技", limit=5)
    print(f"结果: {result.get('news_count')} 条新闻")
    if result.get('news_list'):
        for news in result['news_list'][:3]:
            print(f"  - {news['title']} (浏览量: {news['views']})")
    
    # 2. 热门新闻
    print("\n【热门新闻】")
    result = await news_query_tool(query_type="hot", limit=5)
    print(f"结果: {result.get('news_count')} 条新闻")
    if result.get('news_list'):
        for news in result['news_list'][:3]:
            print(f"  - {news['title']} (浏览量: {news['views']})")
    
    # 3. 最近新闻
    print("\n【最近新闻】")
    result = await news_query_tool(query_type="recent", limit=5)
    print(f"结果: {result.get('news_count')} 条新闻")
    if result.get('news_list'):
        for news in result['news_list'][:3]:
            print(f"  - {news['title']}")
    
    # 4. 作者新闻
    print("\n【作者新闻】作者: 新华社")
    result = await news_query_tool(query_type="author", author="新华社", limit=5)
    print(f"结果: {result.get('news_count')} 条新闻")
    if result.get('news_list'):
        for news in result['news_list'][:3]:
            print(f"  - {news['title']}")
    
    # 5. 新闻统计
    print("\n【新闻统计】")
    result = await news_query_tool(query_type="stats")
    if result.get('stats'):
        stats = result['stats']
        print(f"  - 新闻总数: {stats['total_count']}")
        print(f"  - 总浏览量: {stats['total_views']}")
        print(f"  - 平均浏览量: {stats['avg_views']}")
        print(f"  - 作者数量: {stats['authors_count']}")


async def test_time_range_queries():
    """测试时间范围查询"""
    print("\n" + "="*60)
    print("测试 2: 时间范围查询")
    print("="*60)
    
    # 1. 今天新闻
    print("\n【今天新闻】")
    result = await news_query_tool(query_type="today", limit=5)
    print(f"结果: {result.get('news_count')} 条新闻")
    
    # 2. 本周新闻
    print("\n【本周新闻】")
    result = await news_query_tool(query_type="week", limit=5)
    print(f"结果: {result.get('news_count')} 条新闻")
    
    # 3. 本月新闻
    print("\n【本月新闻】")
    result = await news_query_tool(query_type="month", limit=5)
    print(f"结果: {result.get('news_count')} 条新闻")


async def test_smart_query():
    """测试智能查询"""
    print("\n" + "="*60)
    print("测试 3: 智能查询（LLM 决策）")
    print("="*60)
    
    questions = [
        "最近有什么新闻",
        "查看热门新闻",
        "搜索关于科技的新闻",
        "新华社发布了什么新闻",
        "统计新闻数据"
    ]
    
    for question in questions:
        print(f"\n问题: {question}")
        result = await smart_news_query(question)
        
        if result.get('success'):
            print(f"✅ 查询成功")
            print(f"   查询类型: {result.get('query_type')}")
            print(f"   新闻数量: {result.get('news_count', 0)}")
            
            if result.get('news_list'):
                for news in result['news_list'][:2]:
                    print(f"   - {news['title']}")
            
            if result.get('stats'):
                print(f"   统计: {result.get('summary')}")
        else:
            print(f"❌ 查询失败: {result.get('error')}")


async def test_integration():
    """测试完整流程"""
    print("\n" + "="*60)
    print("测试 4: 完整流程（智能路由 + 工具调用）")
    print("="*60)
    
    from app.agent.smart_router import smart_route
    
    questions = [
        "最近有什么新闻",
        "查看热门新闻",
        "搜索科技新闻"
    ]
    
    for question in questions:
        print(f"\n问题: {question}")
        
        # 1. 智能路由决策
        decision = await smart_route(question)
        print(f"路由决策: {decision}")
        
        # 2. 如果需要工具，调用工具
        if decision.get("needs_tool"):
            tool_name = decision.get("tool_name")
            print(f"调用工具: {tool_name}")
            
            if tool_name == "news_query":
                result = await smart_news_query(question)
                print(f"工具结果: {result.get('success')}")
        else:
            print("不需要调用工具")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("新闻查询工具测试")
    print("="*60)
    
    # 测试 1: 基础查询（需要数据库连接）
    # await test_basic_queries()  # 如果数据库已配置，可以启用
    
    # 测试 2: 时间范围查询（需要数据库连接）
    # await test_time_range_queries()  # 如果数据库已配置，可以启用
    
    # 测试 3: 智能查询（需要 LLM）
    # await test_smart_query()  # 如果 LLM 已配置，可以启用
    
    # 测试 4: 完整流程
    await test_integration()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())