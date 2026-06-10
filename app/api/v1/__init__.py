"""API v1模块"""
from fastapi import APIRouter
from .chat import router as chat_router
from .sessions import router as sessions_router
from .health import router as health_router
from .rag import router as rag_router

# 创建v1路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(chat_router, prefix="/chat", tags=["Chat 对话"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["Sessions 会话"])
api_router.include_router(health_router, prefix="/health", tags=["Health 健康检查"])
api_router.include_router(rag_router, prefix="/rag", tags=["RAG 检索增强生成"])

__all__ = ["api_router"]