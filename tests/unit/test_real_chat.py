"""测试实际的聊天响应

检查是否使用了工具返回的数据
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置输出编码为 UTF-8
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.services.chat import ChatService
from app.core.container import DIContainer
from app.db.database import get_db
from app.core.logger import get_logger

logger = get_logger(__name__)


async def test_real_chat():
    """测试实际的聊天服务"""
    print("\n" + "="*60)
    print("测试实际的聊天服务")
    print("="*60)
    
    # 创建容器和数据库
    container = DIContainer()
    db = await get_db()
    
    # 注册服务
    container.register_singleton(ChatService, lambda: ChatService(db))
    
    # 获取 ChatService
    chat_service = container.get(ChatService)
    
    # 创建会话
    session_id = await chat_service.create_session()
    print(f"\n【会话ID】{session_id}")
    
    # 发送消息
    question = "热点新闻"
    print(f"\n【用户问题】{question}")
    
    # 获取响应
    print(f"\n【开始获取响应】")
    
    response_text = ""
    try:
        # 使用流式响应
        async for chunk in chat_service.chat_stream(
            session_id=session_id,
            question=question,
            user_id=None
        ):
            if chunk:
                response_text += chunk
                print(chunk, end="", flush=True)
        
        print(f"\n\n【完整响应】")
        print(response_text)
        
        # 检查是否使用了工具数据
        print(f"\n【验证】")
        if "费德勒" in response_text or "中国女足" in response_text or "羽毛球" in response_text:
            print(f"✅ 成功：使用了数据库查询的真实新闻")
        elif "特朗普" in response_text or "巴黎奥运会" in response_text:
            print(f"❌ 失败：使用了LLM虚构的新闻，没有使用工具数据")
        else:
            print(f"⚠️  未知：无法确定是否使用了工具数据")
        
        return response_text
    
    except Exception as e:
        print(f"\n❌ 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("测试实际的聊天服务")
    print("="*60)
    
    await test_real_chat()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())