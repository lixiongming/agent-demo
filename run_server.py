"""启动服务脚本"""
import uvicorn
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app


def run_server():
    """启动FastAPI服务"""
    print("""
╔══════════════════════════════════════╗
║     Agent Service 启动               ║
║     地址: http://localhost:8888      ║
║     文档: http://localhost:8888/docs ║``                                                                                                                    
╚══════════════════════════════════════╝
""")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8888,
        reload=True,
        reload_dirs=["app"]
    )


if __name__ == "__main__":
    run_server()