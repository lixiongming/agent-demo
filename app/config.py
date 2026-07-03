"""配置管理 - 大厂生产模式

特性：
- Pydantic BaseSettings 自动读取环境变量
- 启动时校验必填配置项
- CORS 可通过环境变量配置
- 敏感配置（密钥、密码）必须通过环境变量设置
"""
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus


# 项目根目录（用于定位 .env 文件）
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    APP_NAME: str = "Agent Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development / staging / production

    # 数据库类型
    DB_TYPE: str = "mysql"

    # API配置
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "*"  # 多个域名用逗号分隔，如 "https://a.com,https://b.com"
    ADMIN_TOKEN: str = ""  # 管理接口 Token，生产环境必须配置

    @property
    def cors_origins_list(self) -> List[str]:
        """解析 CORS_ORIGINS 为列表"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # JWT 配置
    JWT_SECRET_KEY: str = ""  # JWT 签名密钥，生产环境必须配置
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # Access Token 过期时间（2小时，大厂标准）
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # Refresh Token 过期时间（天）

    # MySQL配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "agent_db"

    @property
    def DATABASE_URL(self) -> str:
        """异步数据库连接URL"""
        return f"mysql+aiomysql://{self.MYSQL_USER}:{quote_plus(self.MYSQL_PASSWORD)}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """同步数据库连接URL"""
        return f"mysql+pymysql://{self.MYSQL_USER}:{quote_plus(self.MYSQL_PASSWORD)}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

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

    # LLM配置（阿里云 DashScope）
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL: str = "qwen3-max"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7

    # Agent配置
    MAX_ITERATIONS: int = 10
    AGENT_TIMEOUT: int = 60

    # Checkpoint 配置
    CHECKPOINT_TYPE: str = "memory"  # memory | sqlite
    CHECKPOINT_DB_PATH: str = "data/checkpoints.db"  # SQLite checkpointer 路径

    # 历史消息配置
    HISTORY_LIMIT: int = 20  # 加载历史消息数量

    # ReAct 循环配置（大厂标准）
    MAX_REACT_ITERATIONS: int = 5  # 最大工具调用轮次
    REACT_TIMEOUT: int = 120  # ReAct 总超时时间（秒）

    # 对话历史配置
    HISTORY_ENABLED: bool = True  # 是否加载历史消息
    HISTORY_MODE: str = "token"  # 模式: rounds(按轮数) / token(按token数)
    HISTORY_ROUNDS_LIMIT: int = 10  # 轮数模式: 保留最近 N 轮对话（1轮=1问1答）
    HISTORY_TOKEN_LIMIT: int = 16000  # Token模式: 历史消息最大 token 数（32K上下文，预留一半给输出）
    HISTORY_TOKEN_SAFETY_MARGIN: int = 500  # Token 安全边界

    # Embedding 配置
    EMBEDDING_PROVIDER: str = "zhipu"  # 提供商: zhipu, openai, local
    EMBEDDING_MODEL_NAME: str = "embedding-3"  # 模型名称
    EMBEDDING_API_KEY: str = ""  # Embedding API Key（统一变量）
    EMBEDDING_DIM: int = 2048  # 向量维度（智谱 embedding-3 = 2048）

    # 智谱 AI 配置
    ZHIPU_API_KEY: str = ""  # 智谱 AI API Key（用于 Embedding 和 Rerank）

    # Rerank 配置
    RERANK_ENABLED: bool = True  # 是否启用 Rerank
    RERANK_MODEL: str = "bge-reranker-v2-m3"  # Rerank 模型
    RERANK_TOP_K: int = 20  # Rerank 召回数量
    RERANK_FINAL_K: int = 5  # Rerank 最终返回数量

    # RAG 检索配置（统一参数）
    RAG_TOP_K: int = 20  # 初始召回数量（用于 Rerank 前的粗召回）
    RAG_THRESHOLD: float = 0.2  # 初始召回阈值
    RAG_FINAL_TOP_K: int = 5  # 最终返回数量（Rerank 后）

    # OpenAI Embedding 配置（可选）
    OPENAI_API_KEY: str = ""  # OpenAI API Key（已废弃，使用 EMBEDDING_API_KEY）
    OPENAI_BASE_URL: str = ""  # OpenAI API Base URL（可选）

    # Qdrant 向量数据库配置
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "knowledge_base"

    # 记忆配置
    MEMORY_SHORT_TERM_TTL: int = 3600  # 1小时
    MEMORY_LONG_TERM_LIMIT: int = 1000

    # ============================================
    # 天气 API 配置（和风天气）
    # ============================================
    QWEATHER_API_HOST: str = "https://devapi.qweather.com"  # API Host
    QWEATHER_API_TOKEN: str = ""  # API Token
    QWEATHER_DEFAULT_LOCATION: str = "101010100"  # 默认城市代码（北京）

    # ============================================
    # 搜索 API 配置（Tavily）
    # ============================================
    TAVILY_API_KEY: str = ""  # Tavily API Key（网络搜索）

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT 必须是 {allowed} 之一，当前值: {v}")
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v: str, info) -> str:
        # 仅在生产环境强制校验
        if info.data.get("ENVIRONMENT") == "production":
            if not v or len(v) < 16:
                raise ValueError("生产环境 JWT_SECRET_KEY 不能为空且长度不能少于 16 个字符")
        return v

    def validate_production_config(self) -> List[str]:
        """校验生产环境必填配置，返回警告列表"""
        warnings = []
        if self.ENVIRONMENT == "production":
            if not self.JWT_SECRET_KEY:
                warnings.append("JWT_SECRET_KEY 未配置，认证功能不可用")
            if not self.ADMIN_TOKEN:
                warnings.append("ADMIN_TOKEN 未配置，管理接口不可用")
            if self.CORS_ORIGINS == "*":
                warnings.append("CORS_ORIGINS 为 *，生产环境应限制为具体域名")
            if self.DEBUG:
                warnings.append("DEBUG 为 True，生产环境应设为 False")
            if self.MYSQL_PASSWORD in ("", "123456"):
                warnings.append("MYSQL_PASSWORD 为默认值，生产环境必须修改")
        return warnings

    class Config:
        # 从项目根目录加载 .env
        env_file = str(PROJECT_ROOT / ".env")
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
        MYSQL_DATABASE="agent_test_db"
    )


def get_prod_settings() -> Settings:
    """生产环境配置"""
    return Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        LOG_LEVEL="WARNING"
    )
