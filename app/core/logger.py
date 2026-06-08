"""日志配置"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.config import get_settings

settings = get_settings()


def setup_logging():
    """配置日志"""
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 控制台输出（设置UTF-8编码）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    # Windows下强制UTF-8
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    # 文件输出（设置UTF-8编码）
    file_handler = RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'  # 关键：添加UTF-8编码
    )
    file_handler.setFormatter(formatter)
    
    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取日志实例"""
    return logging.getLogger(name)