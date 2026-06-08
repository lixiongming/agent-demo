"""查看MySQL数据库数据"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# MySQL连接配置
config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DATABASE', 'agent_db'),
    'charset': 'utf8mb4'
}

try:
    conn = pymysql.connect(**config)
    cursor = conn.cursor()
    
    # 查看表
    print("=== 数据库表 ===")
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    for table in tables:
        print(f"- {table[0]}")
    
    # 查看会话数据
    print("\n=== sessions 表数据 ===")
    cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT 5")
    rows = cursor.fetchall()
    cursor.execute("DESCRIBE sessions")
    columns = [col[0] for col in cursor.fetchall()]
    print(f"列: {columns}")
    for row in rows:
        print(row)
    
    # 查看消息数据
    print("\n=== messages 表数据 ===")
    cursor.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT 10")
    rows = cursor.fetchall()
    cursor.execute("DESCRIBE messages")
    columns = [col[0] for col in cursor.fetchall()]
    print(f"列: {columns}")
    for row in rows:
        print(row)
    
    # 统计
    print("\n=== 数据统计 ===")
    cursor.execute("SELECT COUNT(*) FROM sessions")
    print(f"会话总数: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM messages")
    print(f"消息总数: {cursor.fetchone()[0]}")
    
    conn.close()
    
except Exception as e:
    print(f"连接失败: {e}")
    print("\n请检查:")
    print("1. MySQL服务是否启动")
    print("2. .env中的MYSQL_PASSWORD是否正确")
    print("3. agent_db数据库是否已创建")