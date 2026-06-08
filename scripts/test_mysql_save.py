"""测试MySQL数据保存"""
import httpx
import json
import asyncio
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


async def test_chat():
    """测试聊天API"""
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
        
        # 2. 发送消息
        print("\n=== 2. 发送消息 ===")
        resp = await client.post(
            "http://localhost:8001/api/v1/chat/message",
            json={"session_id": session_id, "message": "你好，请介绍一下你自己"}
        )
        result = resp.json()
        print(json.dumps(result, ensure_ascii=False, indent=2))


def check_mysql_data():
    """检查MySQL数据"""
    print("\n=== 3. 检查MySQL数据 ===")
    
    config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'database': os.getenv('MYSQL_DATABASE', 'agent_db'),
        'charset': 'utf8mb4'
    }
    
    try:
        conn = pymysql.connect(**config)
        cursor = conn.cursor()
        
        # 查看sessions
        print("\n[sessions表]")
        cursor.execute("SELECT id, session_id, agent_type, message_count, created_at FROM sessions ORDER BY id DESC LIMIT 3")
        for row in cursor.fetchall():
            print(f"  id={row[0]}, session_id={row[1]}, agent_type={row[2]}, message_count={row[3]}")
        
        # 查看messages
        print("\n[messages表]")
        cursor.execute("SELECT id, session_id, role, content, created_at FROM messages ORDER BY id DESC LIMIT 5")
        for row in cursor.fetchall():
            content = row[3][:50] + "..." if len(row[3]) > 50 else row[3]
            print(f"  id={row[0]}, session_id={row[1]}, role={row[2]}, content={content}")
        
        # 统计
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM messages")
        message_count = cursor.fetchone()[0]
        
        print(f"\n[统计] sessions={session_count}, messages={message_count}")
        
        conn.close()
        print("\n[OK] MySQL数据保存成功!")
        
    except Exception as e:
        print(f"[ERROR] {e}")


async def main():
    await test_chat()
    check_mysql_data()


if __name__ == "__main__":
    asyncio.run(main())