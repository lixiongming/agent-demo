"""测试聊天数据库保存"""
import httpx
import json
import asyncio


async def test_chat_and_db():
    """测试聊天功能并检查数据库保存"""
    
    async with httpx.AsyncClient(timeout=60) as client:
        # 1. 创建会话
        print("=== 1. 创建会话 ===")
        resp = await client.post(
            "http://localhost:8001/api/v1/sessions/create",
            json={"agent_type": "chat"}
        )
        result = resp.json()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if result.get("code") != 200:
            print("创建会话失败!")
            return
        
        session_id = result["data"]["session_id"]
        print(f"\n会话ID: {session_id}")
        
        # 2. 发送消息
        print("\n=== 2. 发送消息 ===")
        resp = await client.post(
            "http://localhost:8001/api/v1/chat/message",
            json={"session_id": session_id, "message": "你好"}
        )
        result = resp.json()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 3. 查看历史
        print("\n=== 3. 查看历史 ===")
        resp = await client.get(
            f"http://localhost:8001/api/v1/chat/history/{session_id}"
        )
        result = resp.json()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 4. 查看会话列表
        print("\n=== 4. 查看会话列表 ===")
        resp = await client.get("http://localhost:8001/api/v1/sessions/list")
        result = resp.json()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(test_chat_and_db())