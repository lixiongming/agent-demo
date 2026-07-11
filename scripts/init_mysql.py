"""初始化MySQL数据库（首次部署用）

注意：生产环境数据库变更应使用 Alembic 迁移，此脚本仅用于首次建库建表。
"""
import re
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


def validate_identifier(name: str) -> str:
    """校验 SQL 标识符，防止注入"""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"非法的数据库标识符: {name}")
    return name

# MySQL连接配置（不指定数据库）
config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'charset': 'utf8mb4'
}

database = validate_identifier(os.getenv('MYSQL_DATABASE', 'agent_db'))

try:
    # 连接MySQL服务器
    conn = pymysql.connect(**config)
    cursor = conn.cursor()
    
    # 创建数据库
    print(f"创建数据库: {database}")
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    
    # 切换到数据库
    cursor.execute(f"USE {database}")
    
    # 创建sessions表
    print("创建 sessions 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL UNIQUE,
            user_id INT NULL,
            agent_type VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            title VARCHAR(200) NULL,
            model_name VARCHAR(100) NOT NULL,
            system_prompt TEXT NULL,
            config JSON NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            ended_at DATETIME NULL,
            message_count INT DEFAULT 0,
            token_count INT DEFAULT 0,
            INDEX idx_session_id (session_id),
            INDEX idx_created_at (created_at),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # 创建messages表
    print("创建 messages 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id INT NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            token_count INT DEFAULT 0,
            model_name VARCHAR(100) NULL,
            tool_calls JSON NULL,
            tool_results JSON NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_session_id (session_id),
            INDEX idx_created_at (created_at),
            INDEX idx_role (role),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # 创建users表
    print("创建 users 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NULL UNIQUE,
            password_hash VARCHAR(255) NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE,
            preferences JSON NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            last_login_at DATETIME NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    conn.commit()
    print("\n[OK] MySQL数据库初始化成功!")
    
    # 显示表
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"\n数据库表: {[t[0] for t in tables]}")
    
    conn.close()
    
except Exception as e:
    print(f"[ERROR] 初始化失败: {e}")
    print("\n请检查:")
    print("1. MySQL服务是否启动")
    print("2. .env中的MYSQL_PASSWORD是否正确")
    print("3. MySQL用户是否有创建数据库的权限")