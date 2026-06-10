"""配置管理"""
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 基础配置
    APP_NAME: str = "Agent Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # 数据库类型
    DB_TYPE: str = "mysql"
    
    # API配置
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list = ["*"]
    
    # MySQL配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "agent_db"
    
    @property
    def DATABASE_URL(self) -> str:
        """异步数据库连接URL"""
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
    
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """同步数据库连接URL"""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # LLM配置
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL: str = "qwen3.7-plus"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7
    
    # Agent配置
    MAX_ITERATIONS: int = 10
    AGENT_TIMEOUT: int = 60
    
    # Embedding模型配置
    EMBEDDING_MODEL_NAME: str = "bge-large-zh-v1.5"
    EMBEDDING_MODEL_PATH: str = "models"  # 模型存放目录

    @property
    def get_embedding_model_path(self) -> str:
        """获取完整的模型路径"""
        return os.path.join(os.getcwd(), self.EMBEDDING_MODEL_PATH, self.EMBEDDING_MODEL_NAME)

    # Qdrant 向量数据库配置
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "knowledge_base"
    
    # 记忆配置
    MEMORY_SHORT_TERM_TTL: int = 3600  # 1小时
    MEMORY_LONG_TERM_LIMIT: int = 1000
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（缓存）"""
    return Settings()


# 环境切换
def get_test_settings() -> Settings:
    """测试环境配置"""
    return Settings(
        ENVIRONMENT="test",
        DEBUG=True,
        POSTGRES_DB="agent_test_db"
    )


def get_prod_settings() -> Settings:
    """生产环境配置"""
    return Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        LOG_LEVEL="WARNING"
    )