"""测试 MySQL 查询工具

演示：
- Text-to-SQL 自动生成
- 安全防护
- 工具调用流程
"""
import asyncio
from app.tools.mysql_query import mysql_query_tool, execute_sql_query, generate_sql_from_question
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_text_to_sql():
    """测试 Text-to-SQL 生成"""
    print("\n" + "="*60)
    print("测试 1: Text-to-SQL 自动生成")
    print("="*60)
    
    questions = [
        "查询最近10个用户",
        "统计订单总数",
        "查询销售额超过100万的订单",
        "搜索商品名称包含'手机'的产品"
    ]
    
    for question in questions:
        print(f"\n问题: {question}")
        sql = await generate_sql_from_question(question)
        print(f"生成的 SQL: {sql}")


async def test_sql_validation():
    """测试 SQL 安全验证"""
    print("\n" + "="*60)
    print("测试 2: SQL 安全验证")
    print("="*60)
    
    from app.tools.mysql_query import validate_sql
    
    test_cases = [
        ("SELECT * FROM users LIMIT 10", True, "安全查询"),
        ("SELECT * FROM users", False, "缺少 LIMIT"),
        ("DROP TABLE users", False, "包含危险关键词"),
        ("SELECT * FROM unknown_table LIMIT 10", False, "表不在白名单"),
        ("DELETE FROM users WHERE id = 1", False, "不允许 DELETE"),
    ]
    
    for sql, expected_safe, reason in test_cases:
        is_safe, error_msg = validate_sql(sql)
        status = "✅" if is_safe == expected_safe else "❌"
        print(f"{status} {reason}: {sql}")
        if not is_safe:
            print(f"   错误: {error_msg}")


async def test_mysql_query_tool():
    """测试 MySQL 查询工具"""
    print("\n" + "="*60)
    print("测试 3: MySQL 查询工具调用")
    print("="*60)
    
    questions = [
        "查询最近5个用户",
        "统计今天的消息数量",
    ]
    
    for question in questions:
        print(f"\n问题: {question}")
        result = await mysql_query_tool(question)
        
        if result.get("success"):
            print(f"✅ 查询成功")
            print(f"   SQL: {result.get('sql')}")
            print(f"   行数: {result.get('rows_count')}")
            if result.get("summary"):
                print(f"   总结: {result.get('summary')}")
        else:
            print(f"❌ 查询失败: {result.get('error')}")


async def test_integration():
    """测试完整流程"""
    print("\n" + "="*60)
    print("测试 4: 完整流程（智能路由 + 工具调用）")
    print("="*60)
    
    from app.agent.smart_router import smart_route
    
    questions = [
        "查询最近一周的订单数据",
        "统计用户总数",
        "你好",  # 通用问题，不需要工具
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
            
            if tool_name == "mysql_query":
                result = await mysql_query_tool(question)
                print(f"工具结果: {result.get('success')}")
        else:
            print("不需要调用工具")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("MySQL 查询工具测试")
    print("="*60)
    
    # 测试 1: Text-to-SQL
    await test_text_to_sql()
    
    # 测试 2: SQL 安全验证
    await test_sql_validation()
    
    # 测试 3: MySQL 查询工具（需要数据库连接）
    # await test_mysql_query_tool()  # 如果数据库已配置，可以启用
    
    # 测试 4: 完整流程
    await test_integration()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())