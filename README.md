# LangChain Agent 项目

基于 LangChain 和 LangGraph 的智能对话 Agent 服务，采用 **ReAct 模式** 实现工具调用循环。

## 项目架构

```
┌─────────────────────────────────────────────────────┐
│                    服务架构                          │
├─────────────────────────────────────────────────────┤
│  API (FastAPI)  → 对话接口、RAG 查询                 │
│  Agent (ReAct)  → 工具调用循环（最大10次）           │
│  Qdrant         → 向量数据库（知识库存储）           │
│  MySQL          → 关系数据库（会话、消息存储）       │
│  Redis          → 缓存（短期记忆）                   │
│  LLM            → 通义千问（DashScope API）          │
└─────────────────────────────────────────────────────┘
```

### ReAct 模式说明

本项目使用 **ReAct（Reasoning + Acting）模式**：

```
用户输入 → Agent推理 → 工具调用 → 结果反馈 → Agent推理 → ...
```

**配置参数**：
- `MAX_ITERATIONS`: 最大循环次数（默认 10 次）
- `AGENT_TIMEOUT`: Agent 超时时间（默认 60 秒）

**工作流程**：
1. Agent 接收用户消息
2. LLM 进行推理，决定是否调用工具
3. 如果需要工具，执行工具调用
4. 工具结果返回给 Agent
5. Agent 继续推理，直到得出最终答案或达到最大循环次数

## 目录结构

```
langchain/
├── app/                        # 应用核心代码
│   ├── agent/                  # Agent 模块（ReAct 模式）
│   │   ├── graph.py            # LangGraph 图定义
│   │   ├── nodes.py            # Agent 节点实现
│   │   ├── router.py           # 路由决策
│   │   ├── state.py            # 状态定义
│   │   └── checkpoint.py       # 状态持久化
│   │
│   ├── api/                    # API 接口层
│   │   ├── v1/                 # v1 版本接口
│   │   │   ├── chat.py         # 对话接口
│   │   │   ├── rag.py          # RAG 查询接口
│   │   │   ├── sessions.py     # 会话管理
│   │   │   └── health.py       # 健康检查
│   │   └── deps.py             # 依赖注入
│   │
│   ├── embeddings/             # 向量嵌入模块
│   │   ├── embedding.py        # Embedding 服务
│   │   ├── qdrant_store.py     # Qdrant 向量存储
│   │   ├── retriever.py        # 向量检索器
│   │   └── document.py         # 文档加载器
│   │
│   ├── llm/                    # LLM 服务模块
│   │   ├── factory.py          # LLM 工厂
│   │   └── callbacks.py        # 回调处理
│   │
│   ├── services/               # 业务服务层
│   │   ├── chat.py             # 对话服务
│   │   ├── rag.py              # RAG 服务
│   │   └── session.py          # 会话服务
│   │
│   ├── tools/                  # Agent 工具集
│   │   ├── registry.py         # 工具注册中心
│   │   ├── calculator.py       # 计算器工具
│   │   ├── weather.py          # 天气查询工具
│   │   ├── search.py           # 搜索工具
│   │   └── knowledge.py        # 知识库查询工具
│   │
│   ├── memory/                 # 记忆模块
│   │   ├── short_term.py       # 短期记忆（Redis）
│   │   └── long_term.py        # 长期记忆（MySQL）
│   │
│   ├── db/                     # 数据库模块
│   │   ├── models/             # ORM 模型
│   │   │   ├── session.py      # 会话模型
│   │   │   ├── message.py      # 消息模型
│   │   │   └── user.py         # 用户模型
│   │   ├── repositories/       # 数据仓库
│   │   ├── database.py         # 数据库连接
│   │   └ cache.py              # 缓存管理
│   │
│   ├── schemas/                # 数据模型（Pydantic）
│   │   ├── chat.py             # 对话模型
│   │   ├── rag.py              # RAG 模型
│   │   └── session.py          # 会话模型
│   │
│   ├── prompts/                # 提示词模板
│   │   └ templates.py          # 模板定义
│   │
│   ├── core/                   # 核心模块
│   │   ├── container.py        # 依赖注入容器
│   │   ├── interfaces.py       # 接口抽象
│   │   ├── logger.py           # 日志管理（按日期滚动）
│   │   ├── middleware.py       # 中间件
│   │   ├── exceptions.py       # 异常定义
│   │   ├── error_codes.py      # 错误码定义
│   │   ├── rate_limit.py       # 限流/熔断
│   │   └── metrics.py          # 监控指标
│   │
│   ├── utils/                  # 工具函数
│   │   ├── helpers.py          # 辅助函数
│   │   └ validators.py         # 验证器
│   │
│   ├── config.py               # 配置管理
│   └ main.py                   # FastAPI 入口
│
├── docker/                     # Docker 配置
│   ├── Dockerfile              # 镜像构建
│   ├── docker-compose.yml      # 服务编排
│   ├── start.sh                # Linux 启动脚本
│   └ start.bat                 # Windows 启动脚本
│
├── scripts/                    # 工具脚本
│   ├── lol_knowledge_to_qdrant.py  # LOL 知识库导入
│   ├── init_db.py              # 数据库初始化
│   ├── seed_data.py            # 测试数据生成
│
├── data/                       # 数据文件
│   ├── agent_db.sql            # 数据库初始化 SQL
│   └ lol_knowledge_base.md     # LOL 知识库文件
│
├── tests/                      # 测试代码
│   ├── conftest.py             # 测试配置
│   ├── test_architecture.py    # 架构测试
│
├── logs/                       # 日志目录
│   └ app.log                   # 应用日志
│
├── .env.example                # 环境变量模板
├── .dockerignore               # Docker 忽略文件
├── requirements.txt            # Python 依赖
├── run_server.py               # 本地启动脚本
├── main.py                     # 入口文件
├── Makefile                    # Make 命令
└ README.md                     # 项目文档
```

## 快速启动

### 1. 环境准备

```bash
# 安装 Docker Desktop
# https://www.docker.com/products/docker-desktop

# 克隆项目
git clone <project_url>
cd langchain
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，修改以下配置：
# DASHSCOPE_API_KEY=your_api_key_here  # 通义千问 API Key（必须）
```

### 3. Docker 启动

```bash
# 进入 docker 目录
cd docker

# 启动服务
docker-compose up -d

# 重新构建并启动（代码变化时）
docker-compose up -d --build
```

**依赖安装说明：**
- ✅ 依赖安装使用 Docker 缓存，构建速度很快（约 2-3 秒）
- ✅ 只有 `requirements.txt` 变化时才重新安装依赖
- ✅ 代码变化只重新构建代码层

**常用命令：**
```bash
docker-compose ps              # 查看状态
docker-compose logs -f api     # 查看日志
docker-compose down            # 停止服务
docker-compose up -d           # 日常启动（推荐）
docker-compose up -d --build   # 代码变化时才使用 --build
docker-compose build api --no-cache  # 强制重建,依赖更新后使用
```

### 4. 导入知识库（参考 LOL 知识库导入）

```bash
# 将 LOL 知识库导入到 Qdrant
docker-compose exec api python scripts/lol_knowledge_to_qdrant.py \
    "/app/data/lol_knowledge_base.md" \
    --host qdrant \
    --port 6333
```

### 5. 数据库备份和恢复

```bash
# 进入 ops 目录
cd ops

# 备份 MySQL
./backup_mysql.sh

# 恢复 MySQL（指定备份文件）
./restore_mysql.sh ../data/backups/agent_db_YYYYMMDD.sql.gz

# 查看备份文件
ls ../data/backups/
```

## 服务地址

| 服务 | 地址 | 说明 |
|------|------|------|
| API | http://localhost:8888 | FastAPI 服务 |
| API 文档 | http://localhost:8888/docs | Swagger UI |
| ReAct 文档 | http://localhost:8888/redoc | ReDoc 文档 |
| Qdrant | http://localhost:6333 | 向量数据库 |
| Qdrant Dashboard | http://localhost:6333/dashboard | 管理界面 |
| MySQL | localhost:3306 | 数据库 |
| Redis | localhost:6379 | 缓存 |

## API 接口

### 健康检查
```bash
# 基础健康检查
curl http://localhost:8888/api/v1/health

# 详细依赖检查（数据库、Redis、Qdrant）
curl http://localhost:8888/api/v1/ready

# 应用信息
curl http://localhost:8888/api/v1/info

# 系统指标（请求统计、LLM调用、RAG检索）
curl http://localhost:8888/api/v1/metrics

# 熔断器状态
curl http://localhost:8888/api/v1/circuit-breakers

# 重置熔断器
curl -X POST http://localhost:8888/api/v1/circuit-breakers/reset
```

### 对话接口（ReAct 模式）
```bash
curl -X POST http://localhost:8888/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "今天北京天气怎么样？", "session_id": "test"}'
```

**ReAct 流程示例**：
```
用户: 今天北京天气怎么样？
Agent: 需要调用天气工具
Tool: weather("北京") → {"temp": 25, "weather": "晴"}
Agent: 根据结果回答：北京今天天气晴朗，气温25度
```

### RAG 查询
```bash
curl -X POST http://localhost:8888/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "亚索怎么玩"}'
```

### 会话管理
```bash
# 创建会话
curl -X POST http://localhost:8888/api/v1/sessions

# 获取会话历史
curl http://localhost:8888/api/v1/sessions/{session_id}/messages
```

## Agent 工具列表

| 工具 | 功能 | 示例 |
|------|------|------|
| calculator | 数学计算 | "计算 123 * 456" |
| weather | 天气查询 | "北京天气怎么样" |
| search | 网络搜索 | "搜索 Python 教程" |
| knowledge | 知识库查询 | "亚索出装推荐" |

## 本地开发

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动服务
```bash
# 启动 Qdrant（Docker）
docker run -p 6333:6333 qdrant/qdrant

# 启动 MySQL（Docker）
docker run -p 3306:3306 -e MYSQL_ROOT_PASSWORD=123456 mysql:8.0

# 启动 Redis（Docker）
docker run -p 6379:6379 redis:7-alpine

# 启动 API
python run_server.py
```

### 导入知识库
```bash
python scripts/lol_knowledge_to_qdrant.py \
    "C:\Users\Administrator\Downloads\lol_knowledge_base.md" \
    --host localhost \
    --port 6333
```

## 配置说明

### 环境变量 (.env)

```env
# MySQL 配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=agent_db

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379

# Qdrant 配置
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=knowledge_base

# LLM 配置（阿里云 DashScope）
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DEFAULT_MODEL=qwen3.7-plus
MAX_TOKENS=4096
TEMPERATURE=0.7

# Agent 配置（ReAct 模式）
MAX_ITERATIONS=10        # 最大循环次数
AGENT_TIMEOUT=60         # 超时时间（秒）

# Embedding 配置（支持多种 Provider）
EMBEDDING_PROVIDER=zhipu  # 提供商: zhipu, openai, local
EMBEDDING_MODEL_NAME=embedding-3

# 智谱 AI Embedding 配置（EMBEDDING_PROVIDER=zhipu）
ZHIPU_API_KEY=your_zhipu_api_key_here

# OpenAI Embedding 配置（EMBEDDING_PROVIDER=openai）
# OPENAI_API_KEY=your_openai_api_key_here
```

### ReAct 配置说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| MAX_ITERATIONS | 10 | Agent 最大循环次数，防止无限循环 |
| AGENT_TIMEOUT | 60 | 单次请求超时时间（秒） |
| TEMPERATURE | 0.7 | LLM 温度参数，越高越随机 |

## 常见问题

### Q: 如何查看 Qdrant 中的数据？
A: 访问 http://localhost:6333/dashboard 查看集合和数据。

### Q: Agent 循环次数过多怎么办？
A: 调整 `MAX_ITERATIONS` 参数（默认 10 次），在 `.env` 文件中修改。

### Q: 如何重置数据库？
A:
```bash
docker-compose down -v  # 删除 volumes
docker-compose up -d    # 重新启动
```

### Q: 如何添加新工具？
A: 在 `app/tools/` 目录创建新工具文件，然后在 `registry.py` 中注册。

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.12.10 | 运行环境 |
| FastAPI | 0.136.3 | Web 框架 |
| LangChain | 1.3.4 | LLM 框架 |
| LangGraph | 1.2.4 | Agent 图框架 |
| Qdrant | latest | 向量数据库 |
| MySQL | 8.0 | 关系数据库 |
| Redis | 7 | 缓存 |
| 智谱 AI | embedding-3 | Embedding API |

## 生产级别功能

### 1. 限流和熔断

**限流**：防止 API 过载，基于 Redis 滑动窗口算法
```python
from app.core import rate_limit

@rate_limit("chat", limit=50, period=60)
async def chat_endpoint():
    ...
```

**熔断器**：防止级联故障，自动恢复
```python
from app.core import llm_breaker

async def call_llm():
    with llm_breaker:
        return await llm.invoke()
```

### 2. 统一错误码

所有 API 返回统一格式的错误响应：
```json
{
  "code": 2001,
  "message": "会话不存在",
  "data": null,
  "error": {
    "level": "warning",
    "solution": "请创建新会话或检查会话ID"
  }
}
```

### 3. 监控指标

自动收集以下指标：
- 请求统计（计数、延迟、错误率）
- LLM 调用（次数、Token、延迟）
- RAG 检索（命中率、延迟）
- 数据库查询（次数、延迟）

### 4. 日志管理

- 按日期滚动（每天一个文件）
- 自动压缩（节省 ~70% 存储空间）
- 自动清理（保留 30 天）
- 结构化 JSON 格式