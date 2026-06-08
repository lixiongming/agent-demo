"""API模块"""
from fastapi import APIRouter
from .deps import get_db, get_redis_cache, get_current_user, get_optional_user
from .v1 import api_router

__all__ = [
    "get_db", "get_redis_cache",
    "get_current_user", "get_optional_user",
    "api_router"
]