"""应用初始化"""
from app.config import get_settings
from app.core import setup_logging, setup_middlewares

settings = get_settings()

__all__ = ["settings", "setup_logging", "setup_middlewares"]