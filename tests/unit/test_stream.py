"""测试流式响应"""
import httpx
import json


async def test_stream_chat():
    """测试流式聊天"""
    url = "http://localhost:8001/api/v1/chat/message/stream"
    
    # 先创建会话
    create_url = "http://localhost:8001/api/v1/sessions/create"
    async with httpx.AsyncClient() as client:
        resp = await client.post(create_url, json={"agent_type": "chat"})
        session_id = resp.json()["data"]["session_id"]
        print(f"会话ID: {session_id}")
    
    # 发送流式消息
    payload = {
        "session_id": session_id,
        "message": "你好"
    }
    
    print("\n流式响应:")
    print("-" * 40)
    
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload) as response:
            full_content = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    try:
                        data = json.loads(data_str)
                        if "content" in data:
                            content = data["content"]
                            full_content.append(content)
                            print(content, end="", flush=True)
                        if data.get("done"):
                            print("\n\n[完成]")
                    except json.JSONDecodeError:
                        pass
    
    print("-" * 40)
    print(f"完整内容: {''.join(full_content)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_stream_chat())