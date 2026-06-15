"""完整端到端测试：模拟真实聊天流程

测试流程：
1. 用户发送"热门的新闻"
2. 智能路由识别
3. 工具决策
4. 工具执行（查询数据库）
5. Chat节点生成响应（使用工具返回的数据）
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.agent.graph import create_chat_graph
from app.agent.state import ChatState
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_chat_endpoint():
    """测试完整的聊天流程"""
    print("\n" + "="*60)
    print("完整端到端测试：模拟真实聊天流程")
    print("="*60)
    
    # 创建聊天图
    chat_app = create_chat_graph()
    
    # 模拟用户输入
    user_input = "热门的新闻"
    print(f"\n【用户输入】{user_input}")
    
    # 创建初始状态
    initial_state = ChatState(
        current_input=user_input,
        messages=[],
        session_id="test_session_001",
        user_id="test_user_001"
    )
    
    print(f"\n【开始执行聊天流程】")
    
    # 执行聊天图
    try:
        # 添加配置参数（checkpointer 需要 thread_id）
        config = {
            "configurable": {
                "thread_id": "test_thread_001"
            }
        }
        
        result = await chat_app.ainvoke(initial_state, config=config)
        
        print(f"\n【执行完成】")
        
        # 检查路由决策
        route_decision = result.get("route_decision", {})
        print(f"\n步骤 1: 智能路由")
        print(f"   needs_tool: {route_decision.get('needs_tool')}")
        print(f"   tool_name: {route_decision.get('tool_name')}")
        print(f"   reason: {route_decision.get('reason')}")
        
        # 检查工具决策
        tool_decision = result.get("tool_decision", {})
        print(f"\n步骤 2: 工具决策")
        print(f"   needs_tool: {tool_decision.get('needs_tool')}")
        print(f"   tool_name: {tool_decision.get('tool_name')}")
        
        # 检查工具执行结果
        tool_results = result.get("tool_results", [])
        print(f"\n步骤 3: 工具执行")
        if tool_results:
            tool_result = tool_results[0]
            print(f"   success: {tool_result.get('success')}")
            if tool_result.get('success'):
                result_data = tool_result.get('result', {})
                print(f"   news_count: {result_data.get('news_count', 0)}")
                if result_data.get('news_list'):
                    print(f"   新闻列表:")
                    for news in result_data['news_list'][:3]:
                        print(f"      - {news['title']} (浏览量: {news['views']})")
        else:
            print(f"   没有工具执行结果")
        
        # 检查最终响应
        response = result.get("response", "")
        print(f"\n步骤 4: Chat节点生成响应")
        print(f"   响应长度: {len(response)}")
        print(f"\n【最终响应】")
        print(response[:500] if len(response) > 500 else response)
        
        # 检查是否使用了工具数据
        print(f"\n【验证】")
        if "费德勒" in response or "中国女足" in response or "羽毛球" in response:
            print(f"✅ 成功：使用了数据库查询的真实新闻")
        elif "特朗普" in response or "巴黎奥运会" in response:
            print(f"❌ 失败：使用了LLM虚构的新闻，没有使用工具数据")
        else:
            print(f"⚠️  未知：无法确定是否使用了工具数据")
        
        return result
    
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_multiple_queries():
    """测试多个查询"""
    print("\n" + "="*60)
    print("测试多个查询")
    print("="*60)
    
    queries = [
        "热门的新闻",
        "最近有什么新闻",
        "推荐最热的新闻",
    ]
    
    chat_app = create_chat_graph()
    
    for query in queries:
        print(f"\n【查询】{query}")
        
        initial_state = ChatState(
            current_input=query,
            messages=[],
            session_id="test_session_001",
            user_id="test_user_001"
        )
        
        try:
            result = await chat_app.ainvoke(initial_state)
            response = result.get("response", "")
            
            print(f"\n【响应】")
            print(response[:300] if len(response) > 300 else response)
            
            # 验证
            if "费德勒" in response or "中国女足" in response or "羽毛球" in response:
                print(f"✅ 成功：使用了数据库数据")
            else:
                print(f"⚠️  可能使用了LLM虚构数据")
        
        except Exception as e:
            print(f"❌ 失败: {str(e)}")


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("完整端到端测试")
    print("="*60)
    
    # 测试 1: 完整聊天流程
    await test_chat_endpoint()
    
    # 测试 2: 多个查询
    # await test_multiple_queries()  # 可以启用
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())