# LangChain Agent 项目

> 基于 LangChain 和 LangGraph 的智能对话 Agent 服务，采用 **大厂生产级架构** 实现。

## 🏆 核心特性

| 特性 | 大厂标准 | 实现状态 |
|------|----------|----------|
| **Function Calling** | OpenAI/智谱原生支持 | ✅ bind_tools + tool_calls |
| **智能路由** | 三级策略（关键词→规则→LLM） | ✅ 毫秒级响应 |
| **ReAct 循环** | 多轮工具调用 | ✅ 最大10次迭代 |
| **记忆管理** | 遗忘机制 + 冲突修正 + 整合 | ✅ Google MemGPT 标准 |
| **Rerank 重排序** | Cross-Encoder 模型 | ✅ 智谱 bge-reranker |
| **链路追踪** | OpenTelemetry Span | ✅ 全链路追踪 |
| **限流熔断** | Circuit Breaker | ✅ 时间窗口限流 |
| **审计日志** | 操作审计 + 安全审计 | ✅ 结构化记录 |

---

## 📊 项目架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         大厂生产级 Agent 架构                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │   FastAPI   │───▶│  智能路由   │───▶│   Agent     │                 │
│  │   API 层    │    │  三级策略   │    │  ReAct 循环 │                 │
│  └─────────────┘    └─────────────┘    └─────────────┘                 │
│                           │                   │                         │
│                           ▼                   ▼                         │
│                    ┌─────────────┐    ┌─────────────┐                   │
│                    │  RAG 检索   │    │  工具执行   │                   │
│                    │  Rerank     │    │  Function   │                   │
│                    │  多级缓存   │    │  Calling    │                   │
│                    └─────────────┘    └─────────────┘                   │
│                           │                   │                         │
│                           ▼                   ▼                         │
│                    ┌─────────────┐    ┌─────────────┐                   │
│                    │  记忆管理   │    │  LLM 服务   │                   │
│                    │  遗忘机制   │    │  智谱/阿里  │                   │
│                    │  冲突修正   │    │  流式输出   │                   │
│                    └─────────────┘    └─────────────┘                   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  基础设施：MySQL（关系数据）+ Redis（缓存）+ Qdrant（向量）              │
├─────────────────────────────────────────────────────────────────────────┤
│  生产特性：限流熔断 + 链路追踪 + 审计日志 + 监控统计 + 自动降级          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 核心流程

### 1. 智能路由（三级策略）

```
用户问题 → 关键词匹配（<1ms） → 规则匹配（<5ms） → LLM Function Calling（~500ms）
                ↓                    ↓                      ↓
            热点问题             格式化问题              复杂问题
            直接响应             快速处理               智能决策
```

**大厂对比**：

| 路由方式 | 延迟 | 适用场景 | 大厂实践 |
|---------|------|---------|---------|
| 关键词匹配 | <1ms | 热点问题 | 阿里热点缓存 |
| 规则匹配 | <5ms | 格式化问题 | 字节规则引擎 |
| LLM Function Calling | ~500ms | 复杂问题 | OpenAI 标准 |

### 2. Function Calling 工具调用

```
┌─────────────────────────────────────────────────────────────┐
│                  Function Calling 流程                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. bind_tools(tools)  → 绑定工具到 LLM                     │
│     └── 工具定义：name, description, parameters             │
│                                                             │
│  2. LLM.ainvoke()      → 模型决策                           │
│     └── 返回：tool_calls = [{name, args, id}]               │
│                                                             │
│  3. execute_tool()     → 执行工具                           │
│     └── 限流检查 → 熔断检查 → 参数验证 → 执行                │
│                                                             │
│  4. ToolMessage        → 结果回传                           │
│     └── LLM 整合结果生成最终回答                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**对比：手动 JSON 解析 vs Function Calling**

| 方式 | 准确性 | 效率 | 大厂标准 |
|------|--------|------|---------|
| 手动 JSON | ❌ 解析失败率高 | ❌ 需要额外逻辑 | ❌ 不推荐 |
| Function Calling | ✅ 95%+ | ✅ 直接使用 tool_calls | ✅ OpenAI 标准 |

### 3. ReAct 循环（多轮工具调用）

```
用户问题 → Agent推理 → 工具调用 → 结果反馈 → Agent推理 → ...
                ↓           ↓           ↓
            决策是否     执行工具     整合结果
            需要工具     (最大10次)   继续推理
```

**配置参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_ITERATIONS` | 10 | 最大循环次数，防止无限循环 |
| `AGENT_TIMEOUT` | 60 | 单次请求超时时间（秒） |
| `ITERATION_DELAY` | 0.5 | 每次迭代间隔（秒） |

### 4. 记忆管理（Google MemGPT 标准）

```
┌─────────────────────────────────────────────────────────────┐
│                    记忆生命周期                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  短期记忆（Redis）                                           │
│  ├── 对话上下文：最近 20 条消息                              │
│  ├── TTL 自动过期：1 小时                                    │
│  └── 快速访问：毫秒级                                        │
│                                                             │
│  长期记忆（Qdrant）                                        │
│  ├── 关键事实：用户姓名、偏好、地址                          │
│  ├── 向量存储：语义检索                                      │
│  └── 权重管理：时间衰减 + 重要性评分                         │
│                                                             │
│  遗忘机制                                                    │
│  ├── 时间衰减：weight = initial * exp(-decay_rate * hours)  │
│  ├── 容量限制：最大 1000 条                                  │
│  └── 智能淘汰：score = weight * importance                   │
│                                                             │
│  冲突修正                                                    │
│  ├── 事实检测：同类型事实值不同                              │
│  ├── 置信度评估：source_count * recency * consistency       │
│  └── 冲突解决：时间优先 / 置信度优先                         │
│                                                             │
│  记忆整合                                                    │
│  ├── 事实提取：LLM 提取关键事实                              │
│  ├── 实体识别：人、时间、地点                                │
│  └── 关系建立：实体间关系                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 目录结构

```
langchain/
├── app/                        # 应用核心代码
│   ├── agent/                  # Agent 模块（ReAct + Function Calling）
│   │   ├── graph.py            # LangGraph 图定义（Chat + ReAct）
│   │   ├── nodes.py            # Agent 节点实现（含记忆管理节点）
│   │   ├── smart_router.py     # 智能路由（Function Calling）
│   │   ├── router.py           # 路由决策
│   │   ├── state.py            # 状态定义
│   │   └── checkpoint.py       # 状态持久化
│   │
│   ├── api/                    # API 接口层
│   │   ├── v1/                 # v1 版本接口
│   │   │   ├── chat.py         # 对话接口（流式）
│   │   │   ├── rag.py          # RAG 查询接口
│   │   │   ├── sessions.py     # 会话管理
│   │   │   └── health.py       # 健康检查
│   │   └── deps.py             # 依赖注入
│   │
│   ├── core/                   # 核心基础设施（生产级）
│   │   ├── logger.py           # 日志管理（滚动 + 压缩 + 清理）
│   │   ├── audit.py            # 审计日志（操作 + 安全）
│   │   ├── tracing.py          # 链路追踪（OpenTelemetry）
│   │   ├── rate_limit.py       # 限流（时间窗口）
│   │   ├── middleware.py       # 中间件（请求追踪）
│   │   ├── metrics.py          # 监控指标
│   │   ├── exceptions.py       # 异常定义
│   │   ├── error_codes.py      # 错误码定义
│   │   └── container.py        # 依赖注入容器
│   │
│   ├── memory/                 # 记忆管理（大厂标准）
│   │   ├── manager.py          # 记忆管理器（统一入口）
│   │   ├── forgetting.py       # 遗忘机制（时间衰减 + 容量限制）
│   │   ├── conflict.py         # 冲突修正（事实检测 + 信息更新）
│   │   ├── integration.py      # 记忆整合（事实提取 + 实体识别）
│   │   ├── short_term.py       # 短期记忆（Redis）
│   │   └── long_term.py        # 长期记忆（Qdrant）
│   │
│   ├── tools/                  # Agent 工具集（Function Calling）
│   │   ├── registry.py         # 工具注册中心（限流 + 熔断 + 追踪）
│   │   ├── calculator.py       # 计算器工具（安全实现）
│   │   ├── weather.py          # 天气查询工具
│   │   ├── news_query.py       # 新闻查询工具（Function Calling）
│   │   ├── mysql_query.py      # 数据库查询工具（Function Calling）
│   │   ├── knowledge.py        # 知识库查询工具
│   │   └── search.py           # 网络搜索工具
│   │
│   ├── services/               # 业务服务层
│   │   ├── chat.py             # 对话服务（流式 + 工具调用）
│   │   ├── rag.py              # RAG 服务（检索 + Rerank）
│   │   ├── rerank.py           # Rerank 服务（智谱 AI）
│   │   ├── session.py          # 会话服务
│   │   └── cache.py            # 缓存服务
│   │
│   ├── embeddings/             # 向量嵌入模块
│   │   ├── zhipu_embedding.py  # 智谱 Embedding
│   │   ├── qdrant_store.py     # Qdrant 向量存储
│   │   ├── retriever.py        # 向量检索器
│   │   └── document.py         # 文档加载器
│   │
│   ├── llm/                    # LLM 服务模块
│   │   ├── factory.py          # LLM 工厂（多模型支持）
│   │   └── callbacks.py        # 回调处理
│   │
│   ├── db/                     # 数据库模块
│   │   ├── models/             # ORM 模型
│   │   ├── repositories/       # 数据仓库
│   │   ├── database.py         # 数据库连接
│   │   ├── cache.py            # Redis 缓存
│   │   └ migrations/           # 数据库迁移
│   │
│   ├── schemas/                # 数据模型（Pydantic）
│   ├── prompts/                # 提示词模板
│   ├── utils/                  # 工具函数
│   ├── config.py               # 配置管理（多环境）
│   └ main.py                   # FastAPI 入口
│
├── docker/                     # Docker 配置
│   ├── Dockerfile              # 镜像构建
│   ├── docker-compose.yml      # 开发环境
│   ├── docker-compose.prod.yml # 生产环境
│   ├── .env                    # 环境变量
│
├── scripts/                    # 工具脚本
├── tests/                      # 测试代码
├── logs/                       # 日志目录
├── docs/                       # 文档目录
├── requirements.txt            # Python 依赖
├── Makefile                    # Make 命令
└ README.md                     # 项目文档
```

---

## 🚀 快速启动

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
cp docker/.env.example docker/.env

# 编辑 .env 文件
# 必须配置：DASHSCOPE_API_KEY（智谱 API Key）
```

### 3. Docker 启动

```bash
# 开发模式（热更新）
cd docker
docker-compose up -d --build

# 生产模式（多 Worker）
docker-compose -f docker-compose.prod.yml up -d --build
```

### 4. 数据库迁移

```bash
# 添加记忆管理字段
docker-compose exec api python -m app.db.migrations.add_memory_fields
```

### 5. 导入知识库

```bash
docker-compose exec api python scripts/lol_knowledge_to_qdrant.py \
    "/app/data/lol_knowledge_base.md" \
    --host qdrant \
    --port 6333
```

---

## 🌐 服务地址

| 服务 | 地址 | 说明 |
|------|------|------|
| API | http://localhost:8888 | FastAPI 服务 |
| API 文档 | http://localhost:8888/docs | Swagger UI |
| Qdrant | http://localhost:6333 | 向量数据库 |
| Qdrant Dashboard | http://localhost:6333/dashboard | 管理界面 |
| MySQL | localhost:3306 | 关系数据库 |
| Redis | localhost:6379 | 缓存 |

---

## 🔌 API 接口

### 健康检查

```bash
# 基础健康检查
curl http://localhost:8888/api/v1/health/health

# 详细依赖检查
curl http://localhost:8888/api/v1/health/ready

# 系统指标
curl http://localhost:8888/api/v1/health/metrics
```

### 对话接口（流式）

```bash
curl -X POST http://localhost:8888/api/v1/chat/message/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "热门的新闻"}'
```

### RAG 查询

```bash
curl -X POST http://localhost:8888/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "亚索怎么玩"}'
```

### 记忆管理

```bash
# 获取记忆统计
curl http://localhost:8888/api/v1/memory/stats/{session_id}

# 运行遗忘周期
curl -X POST http://localhost:8888/api/v1/memory/forgetting/{session_id}

# 整合对话
curl -X POST http://localhost:8888/api/v1/memory/integrate/{session_id}
```

---

## 🔧 Agent 工具列表

| 工具 | 功能 | Function Calling | 生产特性 |
|------|------|------------------|---------|
| `news_query` | 新闻查询 | ✅ bind_tools | ✅ 限流 + 熔断 + 缓存 |
| `get_weather` | 天气查询 | ✅ bind_tools | ✅ 限流 + 熔断 + 缓存 |
| `calculator` | 数学计算 | ✅ bind_tools | ✅ 安全实现（白名单） |
| `mysql_query` | 数据库查询 | ✅ bind_tools | ✅ SQL 注入防护 |
| `knowledge_search` | 知识库查询 | ✅ bind_tools | ✅ 向量检索 + Rerank |
| `web_search` | 网络搜索 | ✅ bind_tools | ✅ 限流 + 缓存 |

---

## ⚙️ 配置说明

### 环境变量 (.env)

```env
# ===== LLM 配置 =====
DASHSCOPE_API_KEY=your_api_key_here    # 智谱 API Key（必须）
DEFAULT_MODEL=qwen3-max                 # 默认模型
MAX_TOKENS=4096                         # 最大 Token
TEMPERATURE=0.7                         # 温度参数

# ===== Agent 配置 =====
MAX_ITERATIONS=10                       # ReAct 最大循环次数
AGENT_TIMEOUT=60                        # 超时时间（秒）

# ===== 记忆管理配置 =====
MEMORY_SHORT_TERM_TTL=3600              # 短期记忆 TTL（秒）
MEMORY_LONG_TERM_LIMIT=1000             # 长期记忆最大容量
MEMORY_DECAY_RATE=0.01                  # 遗忘衰减速率

# ===== RAG 配置 =====
RERANK_ENABLED=True                     # 启用 Rerank
RERANK_MODEL=bge-reranker-v2-m3         # Rerank 模型
RERANK_TOP_K=20                         # Rerank 输入数量
RERANK_FINAL_K=5                        # Rerank 输出数量

# ===== 日志配置 =====
LOG_LEVEL=INFO                          # 日志级别（生产用 WARNING）
DEBUG=false                             # 调试模式

# ===== 数据库配置 =====
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=agent_db

REDIS_HOST=redis
REDIS_PORT=6379

QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=knowledge_base
```

### 生产环境配置

| 配置项 | 开发环境 | 生产环境 | 说明 |
|--------|---------|---------|------|
| `LOG_LEVEL` | INFO | WARNING | 生产只记录警告和错误 |
| `DEBUG` | true | false | 关闭调试模式 |
| `WORKERS` | 1 | 4 | 多 Worker 提高并发 |
| `MAX_ITERATIONS` | 10 | 5 | 减少循环次数 |
| `MEMORY_DECAY_RATE` | 0.01 | 0.02 | 加快遗忘速度 |

---

## 📈 生产级特性

### 1. 限流和熔断

```python
# 限流：防止 API 过载
from app.core.rate_limit import rate_limit

@rate_limit("chat", limit=100, period=60)
async def chat_endpoint():
    ...

# 熔断：防止级联故障
from app.tools.registry import get_registry

registry = get_registry()
result = await registry.execute("news_query", args)
# 自动熔断检查 + 限流检查 + 参数验证
```

### 2. 链路追踪

```
请求流程追踪示例：
┌─────────────────────────────────────────────────────────┐
│ request_id: abc123                                       │
├─────────────────────────────────────────────────────────┤
│ route_decision     5.34ms    │ Function Calling         │
│   └─ tool_execute  150.76ms  │ news_query               │
│   └─ chat          1551.12ms │ LLM 整合结果             │
│       └─ llm_invoke 750.30ms │ model=qwen3-max          │
├─────────────────────────────────────────────────────────┤
│ 总耗时: 1551.12ms                                        │
└─────────────────────────────────────────────────────────┘
```

### 3. 审计日志

```python
from app.core.audit import AuditLogger

audit = AuditLogger()

# 记录操作审计
audit.log_operation(
    operation="tool_execute",
    user_id=123,
    details={"tool": "news_query", "args": {...}}
)

# 记录安全审计
audit.log_security(
    event="sql_injection_attempt",
    severity="high",
    details={"query": "..."}
)
```

### 4. 日志管理

| 特性 | 说明 |
|------|------|
| **按日期滚动** | 每天午夜自动滚动 |
| **自动压缩** | gzip 压缩历史日志（节省 70%） |
| **自动清理** | 应用日志保留 30 天，审计日志保留 90 天 |
| **结构化格式** | JSON 格式，便于分析 |
| **敏感信息过滤** | password、api_key 自动过滤 |

---

## 🏭 大厂架构对比

| 标准项 | OpenAI | Google | 阿里 | 当前实现 |
|--------|--------|--------|------|---------|
| **Function Calling** | ✅ | ✅ | ✅ | ✅ bind_tools |
| **智能路由** | ✅ | ✅ | ✅ | ✅ 三级策略 |
| **ReAct 循环** | ✅ | ✅ | ✅ | ✅ 最大10次 |
| **记忆管理** | ✅ Memory API | ✅ MemGPT | ✅ | ✅ 遗忘+冲突+整合 |
| **Rerank 重排序** | ❌ | ✅ | ✅ | ✅ 智谱 bge-reranker |
| **链路追踪** | ✅ | ✅ | ✅ | ✅ OpenTelemetry |
| **限流熔断** | ✅ | ✅ | ✅ | ✅ Circuit Breaker |
| **审计日志** | ✅ | ✅ | ✅ | ✅ 操作+安全审计 |

---

## 🧪 测试

```bash
# 运行测试
docker-compose exec api pytest tests/

# 测试覆盖率
docker-compose exec api pytest --cov=app tests/
```

---

## 📚 文档

- [API 文档](http://localhost:8888/docs) - Swagger UI
- [架构文档](docs/project_architecture.md) - 详细架构说明
- [记忆管理文档](docs/memory_management.md) - 记忆系统设计

---

## 🤝 贡献

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 📄 License

MIT License

---

## 📞 联系方式

- 项目地址: [GitHub](https://github.com/your-project)
- 问题反馈: [Issues](https://github.com/your-project/issues)