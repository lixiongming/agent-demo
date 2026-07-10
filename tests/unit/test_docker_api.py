"""测试 Docker API 的实际响应

检查是否使用了工具返回的数据
"""
import requests
import json
import sys
import io

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_docker_api():
    """测试 Docker API"""
    print("\n" + "="*60)
    print("测试 Docker API 的实际响应")
    print("="*60)
    
    # Docker API 地址
    api_url = "http://localhost:8888/api/v1/chat/message/stream"
    
    # 创建会话
    create_session_url = "http://localhost:8888/api/v1/sessions/create"
    session_payload = {
        "agent_type": "chat",
        "model_name": "qwen3-max"
    }
    session_response = requests.post(
        create_session_url,
        json=session_payload,
        headers={"Content-Type": "application/json"}
    )
    session_data = session_response.json()
    
    # 检查响应
    if session_response.status_code != 200:
        print(f"\n❌ 创建会话失败: {session_response.status_code}")
        print(f"   响应: {session_data}")
        return None
    
    # 获取会话ID
    if "data" in session_data:
        session_id = session_data["data"].get("session_id")
    else:
        session_id = session_data.get("session_id")
    
    print(f"\n【会话ID】{session_id}")
    
    # 发送消息
    question = "热点新闻"
    print(f"\n【用户问题】{question}")
    
    # 构建请求
    payload = {
        "session_id": session_id,
        "message": question  # 使用 message 而不是 question
    }
    
    print(f"\n【开始获取响应】")
    
    # 发送流式请求
    response = requests.post(
        api_url,
        json=payload,
        stream=True,
        headers={"Content-Type": "application/json"}
    )
    
    response_text = ""
    
    # 读取流式响应
    for line in response.iter_lines():
        if line:
            chunk = line.decode('utf-8')
            if chunk.startswith("data:"):
                data = chunk[5:].strip()
                if data:
                    response_text += data
                    print(data, end="", flush=True)
    
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


if __name__ == "__main__":
    print("\n" + "="*60)
    print("测试 Docker API")
    print("="*60)
    
    test_docker_api()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)