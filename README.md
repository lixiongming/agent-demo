# LangChain Agent 项目

> 基于 LangChain 和 LangGraph 的智能对话 Agent 服务，采用 **大厂生产级架构** 实现。

## 🏆 核心特性

| 特性 | 大厂标准 | 实现状态 |
|------|----------|----------|
| **Function Calling** | OpenAI/智谱原生支持 | ✅ bind_tools + tool_calls |
| **智能路由** | 三级策略（规则→缓存→LLM） | ✅ LRU缓存 + TTL过期 |
| **ReAct 循环** | 多轮工具调用 | ✅ 最大10次迭代 |
| **记忆管理** | 遗忘机制 + 冲突修正 + 整合 | ✅ Google MemGPT 标准（Qdrant存储） |
| **Rerank 重排序** | Cross-Encoder 模型 | ✅ 智谱 bge-reranker |
| **链路追踪** | OpenTelemetry Span | ✅ 全链路追踪 + 容量上限 |
| **限流熔断** | Circuit Breaker | ✅ 滑动窗口 + asyncio.Lock |
| **审计日志** | 操作审计 + 安全审计 | ✅ 结构化记录 |
| **统一异常体系** | AgentException 层级 | ✅ 全局异常处理器 |
| **API 安全** | Admin Token + 端点认证 | ✅ hmac.compare_digest |
| **事件循环安全** | asyncio.to_thread | ✅ 所有同步IO已包装 |
| **资源生命周期** | 启动/关闭完整管理 | ✅ 连接池释放 |

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
agent-demo/
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
│   │   │   ├── rag.py          # RAG 查询接口（写入需Admin认证）
│   │   │   ├── sessions.py     # 会话管理
│   │   │   ├── admin.py        # 管理接口（需Admin Token认证）
│   │   │   └── health.py       # 健康检查（K8s探针）
│   │   └── deps.py             # 依赖注入
│   │
│   ├── core/                   # 核心基础设施（生产级）
│   │   ├── logger.py           # 日志管理（滚动 + 压缩 + 清理）
│   │   ├── audit.py            # 审计日志（操作 + 安全）
│   │   ├── tracing.py          # 链路追踪（容量上限 + 自动淘汰）
│   │   ├── rate_limit.py       # 限流（滑动窗口 + UUID去重）+ 熔断（asyncio.Lock）
│   │   ├── middleware.py       # 中间件（请求追踪）
│   │   ├── metrics.py          # 监控指标（延迟采样上限1000）
│   │   ├── exceptions.py       # 统一异常体系（AgentException层级）
│   │   ├── error_codes.py      # 错误码定义
│   │   ├── container.py        # 依赖注入容器（threading.Lock保护）
│   │   └── interfaces.py       # 接口定义
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
│   │   ├── registry.py         # 工具注册中心（限流 + 熔断 + Pydantic参数验证）
│   │   ├── tool_definitions.py # 工具定义（OpenAI格式）
│   │   ├── calculator.py       # 计算器工具（安全实现）
│   │   ├── weather.py          # 天气查询工具
│   │   ├── news_query.py       # 新闻查询工具（Function Calling）
│   │   ├── mysql_query.py      # 数据库查询工具（Function Calling）
│   │   ├── knowledge.py        # 知识库查询工具
│   │   └── search.py           # 网络搜索工具
│   │
│   ├── services/               # 业务服务层
│   │   ├── chat.py             # 对话服务（流式 + 工具调用）
│   │   ├── rag.py              # RAG 服务（检索 + Rerank + asyncio.to_thread）
│   │   ├── rerank.py           # Rerank 服务（智谱 AI + 安全关闭）
│   │   ├── session.py          # 会话服务
│   │   └── cache.py            # 缓存服务
│   │
│   ├── embeddings/             # 向量嵌入模块
│   │   ├── zhipu_embedding.py  # 智谱 Embedding
│   │   ├── qdrant_store.py     # Qdrant 向量存储（retrieve + 异常日志）
│   │   ├── retriever.py        # 向量检索器（asyncio.to_thread）
│   │   └── document.py         # 文档加载器
│   │
│   ├── llm/                    # LLM 服务模块
│   │   ├── factory.py          # LLM 工厂（多模型支持）
│   │   └── callbacks.py        # 回调处理
│   │
│   ├── db/                     # 数据库模块
│   │   ├── models/             # ORM 模型
│   │   ├── repositories/       # 数据仓库
│   │   ├── database.py         # 数据库连接（async+sync引擎均关闭）
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
│   ├── Dockerfile              # 开发镜像构建
│   ├── Dockerfile.prod         # 生产镜像构建（多 Worker）
│   ├── Dockerfile.backup       # 定时备份服务镜像
│   ├── docker-compose.yml      # 开发环境编排
│   ├── docker-compose.prod.yml # 生产环境编排
│   ├── deploy.sh               # 生产部署脚本（增量/全量/回滚）
│   └── pip.conf                # pip 国内镜像源
│
├── ops/                        # 运维脚本
│   ├── backup_mysql.sh         # MySQL 数据库备份
│   ├── restore_mysql.sh        # MySQL 数据库恢复
│   ├── start_cron.sh           # 启动 cron 定时任务
│   └── verify_backup.sh        # 备份验证脚本
│
├── scripts/                    # 工具脚本
│   ├── start.sh                # Docker 一键启动脚本
│   ├── init_db.py              # 数据库初始化
│   ├── init_mysql.py           # MySQL 建库建表（首次部署用）
│   ├── seed_data.py            # 测试数据填充
│   ├── lol_knowledge_to_qdrant.py  # 知识库导入 Qdrant
│   └── diagnose/               # 诊断脚本
│       ├── diagnose_weather_api.py  # 天气 API 诊断
│       └── view_mysql.py           # MySQL 数据查看
│
├── tests/                      # 测试代码
│   ├── unit/                   # 单元测试
│   └── integration/            # 集成测试
│
├── data/                       # 数据目录（.gitignore）
│   ├── backups/                # 数据库备份文件
│   └── volumes/                # Docker 持久化卷
│
├── docs/                       # 文档目录
├── logs/                       # 日志目录（.gitignore）
│
├── .github/                    # GitHub Actions CI
│   └── workflows/ci.yml        # CI 流水线（lint + test + build）
│
├── .env.example                # 环境变量模板
├── .gitignore                  # Git 忽略规则
├── Makefile                    # Make 命令（开发/测试/部署/运维）
├── pyproject.toml              # Python 项目配置
├── requirements.txt            # 生产依赖
├── requirements-dev.txt        # 开发依赖
└── README.md                   # 项目文档
```

---

## 🚀 快速启动

### 1. 环境准备

```bash
# 安装 Docker Desktop
# https://www.docker.com/products/docker-desktop

# 克隆项目
git clone <project_url>
cd agent-demo
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
# 必须配置：DASHSCOPE_API_KEY（智谱 API Key）
```

### 3. Docker 启动

```bash
# 方式一：使用一键脚本（推荐）
./scripts/start.sh start

# 方式二：使用 Makefile
make docker-up

# 方式三：手动 docker compose
cd docker
docker compose up -d --build

# 生产模式（多 Worker）
docker compose -f docker-compose.prod.yml up -d --build
```

### 4. 数据库迁移

```bash
# 使用 Alembic 迁移
make migrate

# 或手动初始化
python scripts/init_db.py
```

### 5. 导入知识库

```bash
# 方式一：使用一键脚本
./scripts/start.sh import

# 方式二：手动执行
docker compose exec api python scripts/lol_knowledge_to_qdrant.py \
    "/app/data/lol_knowledge_base.md" \
    --host qdrant \
    --port 6333
```

---

## 🐳 Docker 生产运维指令

> 以下指令均在项目根目录执行，`dc` 为 `docker compose` 的简写习惯。

### 开发环境

```bash
# ===== 启动/停止 =====
cd docker && docker compose up -d --build          # 构建并启动（后台）
docker compose down                                # 停止并移除容器
docker compose restart api                         # 重启单个服务

# ===== 状态/日志 =====
docker compose ps                                  # 查看所有服务状态
docker compose logs -f api                         # 实时查看 API 日志
docker compose logs --tail=100 api                 # 查看最近 100 行日志

# ===== 重建 =====
docker compose build api                           # 增量构建 API 镜像
docker compose build --no-cache api                # 零缓存全量重建
docker compose up -d --no-deps --build api         # 仅重建并重启 API（不影响依赖）

# ===== 调试 =====
docker compose exec api bash                       # 进入 API 容器
docker compose exec api python -c "..."            # 容器内执行 Python
docker compose exec mysql mysql -uroot -p123456 agent_db  # 连接 MySQL

# ===== 健康检查 =====
curl -f http://localhost:8888/api/v1/health/health  # 存活探针
curl -f http://localhost:8888/api/v1/health/ready   # 就绪探针
```

### 生产环境

```bash
# ===== 启动/停止 =====
cd docker && docker compose -f docker-compose.prod.yml up -d --build   # 生产构建并启动
docker compose -f docker-compose.prod.yml down                          # 停止生产环境
docker compose -f docker-compose.prod.yml restart api                   # 重启 API

# ===== 滚动更新（零停机） =====
docker compose -f docker-compose.prod.yml build api                    # 构建新镜像
docker compose -f docker-compose.prod.yml up -d --no-deps api          # 仅更新 API 容器

# ===== 全量重建 =====
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# ===== 状态/日志 =====
docker compose -f docker-compose.prod.yml ps                           # 查看服务状态
docker compose -f docker-compose.prod.yml logs -f --tail=50 api        # 实时日志
docker compose -f docker-compose.prod.yml top                          # 查看容器资源占用

# ===== 数据库运维 =====
docker compose -f docker-compose.prod.yml exec mysql \
    mysqldump -uroot -p${MYSQL_ROOT_PASSWORD} agent_db | gzip > backup.sql.gz  # 手动备份
docker compose -f docker-compose.prod.yml exec redis redis-cli info memory     # Redis 内存信息
docker compose -f docker-compose.prod.yml exec redis redis-cli dbsize          # Redis key 数量

# ===== 资源监控 =====
docker stats --no-stream                            # 所有容器资源使用快照
docker system df                                    # 磁盘占用（镜像/容器/卷）

# ===== 清理 =====
docker system prune -f                              # 清理无用镜像/容器/网络
docker volume prune -f                              # 清理无用卷（注意：勿删数据卷）
```

### 部署脚本

```bash
# 增量部署（只重建有变化的层）
bash docker/deploy.sh

# 全量部署（零缓存重建）
bash docker/deploy.sh full

# 回滚到上一版本
bash docker/deploy.sh rollback
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
# 存活探针（K8s Liveness Probe）
curl http://localhost:8888/api/v1/health/health

# 就绪探针（K8s Readiness Probe）
curl http://localhost:8888/api/v1/health/ready
```

### 管理接口（需 Admin Token）

```bash
# 系统信息
curl -H "X-Admin-Token: your_token" http://localhost:8888/api/v1/admin/info

# 系统指标
curl -H "X-Admin-Token: your_token" http://localhost:8888/api/v1/admin/metrics

# 熔断器状态
curl -H "X-Admin-Token: your_token" http://localhost:8888/api/v1/admin/circuit-breakers

# 链路追踪统计
curl -H "X-Admin-Token: your_token" http://localhost:8888/api/v1/admin/tracing/stats

# 缓存统计
curl -H "X-Admin-Token: your_token" http://localhost:8888/api/v1/admin/cache/stats

# 工具管理
curl -H "X-Admin-Token: your_token" http://localhost:8888/api/v1/admin/tools/stats
```

### 对话接口（流式）

```bash
curl -X POST http://localhost:8888/api/v1/chat/message/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "热门的新闻"}'
```

### RAG 查询

```bash
# RAG 查询（公开）
curl -X POST http://localhost:8888/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "亚索怎么玩"}'

# 文档入库（需 Admin Token）
curl -X POST http://localhost:8888/api/v1/rag/ingest/text \
  -H "X-Admin-Token: your_token" \
  -H "Content-Type: application/json" \
  -d '{"content": "文档内容", "source": "test"}'
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

# ===== 安全配置 =====
ADMIN_TOKEN=your_secure_token_here      # Admin Token（管理接口认证，必须配置）

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
RAG_ALLOWED_DIRS=/data/documents,/app/documents  # 允许入库的目录白名单

# ===== 日志配置 =====
LOG_LEVEL=INFO                          # 日志级别（生产用 WARNING）
DEBUG=false                             # 调试模式

# ===== 数据库配置 =====
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password_here       # 生产环境请使用强密码
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
| `DEBUG` | true | false | 关闭调试模式，隐藏 /docs |
| `WORKERS` | 1 | 4 | 多 Worker 提高并发 |
| `MAX_ITERATIONS` | 10 | 5 | 减少循环次数 |
| `MEMORY_DECAY_RATE` | 0.01 | 0.02 | 加快遗忘速度 |
| `ADMIN_TOKEN` | - | 必须配置 | 管理接口认证 Token |
| `RAG_ALLOWED_DIRS` | - | 必须配置 | 允许入库的目录白名单 |

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
| **Function Calling** | ✅ | ✅ | ✅ | ✅ bind_tools + Pydantic参数验证 |
| **智能路由** | ✅ | ✅ | ✅ | ✅ 规则→缓存→LLM + 动态工具描述 |
| **ReAct 循环** | ✅ | ✅ | ✅ | ✅ 最大10次 |
| **记忆管理** | ✅ Memory API | ✅ MemGPT | ✅ | ✅ Qdrant存储 + 遗忘+冲突+整合 |
| **Rerank 重排序** | ❌ | ✅ | ✅ | ✅ 智谱 bge-reranker |
| **链路追踪** | ✅ | ✅ | ✅ | ✅ 容量上限 + 自动淘汰 |
| **限流熔断** | ✅ | ✅ | ✅ | ✅ 滑动窗口UUID + asyncio.Lock |
| **审计日志** | ✅ | ✅ | ✅ | ✅ 操作+安全审计 |
| **异常体系** | ✅ | ✅ | ✅ | ✅ 统一AgentException + 全局处理器 |
| **API安全** | ✅ | ✅ | ✅ | ✅ Admin Token + hmac防时序攻击 |
| **事件循环安全** | ✅ | ✅ | ✅ | ✅ asyncio.to_thread包装所有同步IO |
| **资源管理** | ✅ | ✅ | ✅ | ✅ 完整启动/关闭生命周期 |

---

## 🛠️ 脚本使用说明

### Makefile 命令（推荐）

```bash
make help              # 查看所有可用命令
```

| 分类 | 命令 | 说明 |
|------|------|------|
| **开发** | `make install` | 安装生产依赖 |
| | `make dev` | 安装开发依赖 |
| | `make run` | 启动开发服务器（热更新） |
| **质量** | `make lint` | Ruff 代码检查 |
| | `make format` | Black + isort 格式化 |
| | `make typecheck` | MyPy 类型检查 |
| | `make test` | 运行测试（含覆盖率） |
| | `make check` | 运行所有检查 |
| **Docker** | `make docker-up` | 启动所有服务 |
| | `make docker-down` | 停止所有服务 |
| | `make docker-build` | 重建镜像 |
| | `make docker-logs` | 查看 API 日志 |
| **数据库** | `make migrate` | Alembic 迁移 |
| | `make init-db` | 初始化数据库 |
| | `make seed` | 填充测试数据 |
| **运维** | `make backup` | 备份 MySQL |
| | `make restore` | 恢复 MySQL |
| | `make deploy` | 生产部署（增量） |
| | `make deploy-full` | 生产部署（全量重建） |
| | `make rollback` | 回滚到上一版本 |

### 一键启动脚本

```bash
./scripts/start.sh start     # 启动所有服务
./scripts/start.sh stop      # 停止所有服务
./scripts/start.sh logs      # 查看 API 日志
./scripts/start.sh rebuild   # 重建服务（无缓存）
./scripts/start.sh import    # 导入知识库到 Qdrant
./scripts/start.sh backup    # 备份 MySQL 数据库
./scripts/start.sh restore   # 恢复 MySQL 数据库
```

### 运维脚本（ops/）

```bash
# 备份数据库
bash ops/backup_mysql.sh

# 恢复数据库（交互式选择备份文件）
bash ops/restore_mysql.sh

# 恢复数据库（指定备份文件）
bash ops/restore_mysql.sh data/backups/agent_db_20260710_120000.sql.gz

# 验证备份功能
bash ops/verify_backup.sh
```

### 生产部署（docker/deploy.sh）

```bash
# 增量部署（只重建有变化的层）
bash docker/deploy.sh

# 全量部署（零缓存重建）
bash docker/deploy.sh full

# 回滚到上一版本
bash docker/deploy.sh rollback
```

### Python 工具脚本（scripts/）

```bash
# 初始化数据库（ORM 建表）
python scripts/init_db.py

# 首次部署建库建表（直接 DDL，生产环境建议用 Alembic）
python scripts/init_mysql.py

# 填充测试数据
python scripts/seed_data.py

# 知识库导入 Qdrant
python scripts/lol_knowledge_to_qdrant.py data/lol_knowledge_base.md --host localhost --port 6333
```

### 诊断脚本（scripts/diagnose/）

```bash
# 诊断天气 API 连接问题
python scripts/diagnose/diagnose_weather_api.py

# 查看 MySQL 数据
python scripts/diagnose/view_mysql.py
```

---

## 🧪 测试

```bash
# 运行测试
docker compose exec api pytest tests/

# 测试覆盖率
docker compose exec api pytest --cov=app tests/
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

---

## 🔒 生产模式改造记录

以下为框架从开发模式升级到生产模式的所有改造项，共修复 **22 项** 致命/高危/中危问题。

### 架构安全（6项）

| # | 问题 | 修复 | 涉及文件 |
|---|------|------|----------|
| 1 | Memory模块混用MySQL和Qdrant | ForgettingManager/ConflictResolver统一使用Qdrant | `memory/forgetting.py`, `memory/conflict.py` |
| 2 | QdrantAdapter.get_document用scroll模拟精确查询 | 改用retrieve按ID精确获取 | `embeddings/qdrant_store.py` |
| 3 | 两个同名ToolRegistry类导致导入混淆 | 重命名为tool_definitions.py | `tools/tool_definitions.py` |
| 4 | 两套异常体系+SessionNotFoundException继承HTTPException | 统一AgentException层级+全局异常处理器 | `core/exceptions.py`, `main.py` |
| 5 | ingest_directory路径遍历漏洞 | 白名单+realpath检查 | `services/rag.py` |
| 6 | .env未加入.gitignore，API密钥泄露 | 取消注释.env行 | `.gitignore` |

### 事件循环安全（5项）

| # | 问题 | 修复 | 涉及文件 |
|---|------|------|----------|
| 7 | RAG ingest_document/add_documents_batch同步阻塞 | asyncio.to_thread包装 | `services/rag.py` |
| 8 | RAG ingest_text/delete_document/delete_by_source同步阻塞 | asyncio.to_thread包装 | `services/rag.py` |
| 9 | RAG _generate_answer同步LLM调用阻塞 | asyncio.to_thread包装 | `services/rag.py` |
| 10 | Retriever.retrieve同步Qdrant搜索阻塞 | asyncio.to_thread包装 | `embeddings/retriever.py` |
| 11 | 健康检查readiness_probe同步Qdrant调用 | asyncio.to_thread包装 | `api/v1/health.py` |

### 并发安全（4项）

| # | 问题 | 修复 | 涉及文件 |
|---|------|------|----------|
| 12 | CircuitBreaker状态转换非线程安全 | 添加asyncio.Lock + 拆分同步/异步路径 | `core/rate_limit.py` |
| 13 | DIContainer类变量无锁保护 | 添加threading.Lock | `core/container.py` |
| 14 | 限流器滑动窗口zadd同秒请求覆盖 | 使用`{timestamp}:{uuid}`作为member | `core/rate_limit.py` |
| 15 | SmartRouter缓存非线程安全 | OrderedDict + LRU淘汰（单线程事件循环下安全） | `agent/smart_router.py` |

### 内存安全（2项）

| # | 问题 | 修复 | 涉及文件 |
|---|------|------|----------|
| 16 | Tracer._completed_spans无限增长 | MAX_COMPLETED_REQUESTS=1000 + 自动淘汰 | `core/tracing.py` |
| 17 | Metrics延迟列表无限增长 | MAX_LATENCY_SAMPLES=1000 + 裁剪 | `core/metrics.py` |

### 资源管理（3项）

| # | 问题 | 修复 | 涉及文件 |
|---|------|------|----------|
| 18 | sync_engine数据库连接从未关闭 | close_db()中添加sync_engine.dispose() | `db/database.py` |
| 19 | QdrantClient实例关闭时未释放 | lifespan中添加IVectorStore.close() | `main.py` |
| 20 | shutdown_rerank_service中threading.Lock内await死锁 | 锁内仅原子置None，锁外await close() | `services/rerank.py` |

### API安全（2项）

| # | 问题 | 修复 | 涉及文件 |
|---|------|------|----------|
| 21 | Admin Token使用!=比较，存在时序攻击风险 | 改用hmac.compare_digest常量时间比较 | `api/v1/admin.py` |
| 22 | RAG写入/删除端点无认证保护 | 添加verify_admin_token依赖 | `api/v1/rag.py` |