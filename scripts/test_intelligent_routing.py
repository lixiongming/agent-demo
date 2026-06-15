"""测试智能路由功能

验证：
1. 简单问题不检索知识库
2. 复杂问题检索知识库
"""
import asyncio
from app.agent.graph import get_chat_app
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_intelligent_routing():
    """测试智能路由"""
    
    # 获取聊天应用
    chat_app = get_chat_app()
    
    # 测试用例
    test_cases = [
        {
            "question": "今天天气怎么样？",
            "expected_retrieval": False,
            "reason": "通用问题，不需要知识库"
        },
        {
            "question": "1+1等于几？",
            "expected_retrieval": False,
            "reason": "简单数学，不需要知识库"
        },
        {
            "question": "你好",
            "expected_retrieval": False,
            "reason": "问候语，不需要知识库"
        },
        {
            "question": "英雄联盟的游戏规则是什么？",
            "expected_retrieval": True,
            "reason": "特定游戏知识，需要知识库"
        },
        {
            "question": "如何使用这个产品的API？",
            "expected_retrieval": True,
            "reason": "技术文档，需要知识库"
        }
    ]
    
    print("=" * 60)
    print("智能路由测试")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test_case['question']}")
        print(f"预期: {'需要检索' if test_case['expected_retrieval'] else '不需要检索'}")
        print(f"原因: {test_case['reason']}")
        
        # 初始化状态
        initial_state = {
            "messages": [],
            "session_id": f"test_{i}",
            "current_input": test_case["question"],
            "response": None,
            "route_decision": None,
            "rag_context": None,
            "rag_sources": [],
            "rag_used": False
        }
        
        try:
            # 执行图
            result = await chat_app.ainvoke(initial_state)
            
            # 检查路由决策
            route_decision = result.get("route_decision", {})
            needs_retrieval = route_decision.get("needs_retrieval", False)
            reason = route_decision.get("reason", "")
            confidence = route_decision.get("confidence", 0.0)
            
            print(f"\n实际路由决策:")
            print(f"  - 需要检索: {needs_retrieval}")
            print(f"  - 原因: {reason}")
            print(f"  - 置信度: {confidence}")
            
            # 检查是否使用了 RAG
            rag_used = result.get("rag_used", False)
            print(f"  - 实际使用RAG: {rag_used}")
            
            # 验证结果
            if needs_retrieval == test_case["expected_retrieval"]:
                print("✅ 测试通过")
            else:
                print("❌ 测试失败")
            
            # 显示响应
            response = result.get("response", "")
            print(f"\n响应: {response[:200]}...")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            logger.error(f"Test failed: {e}", exc_info=True)
        
        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(test_intelligent_routing())
