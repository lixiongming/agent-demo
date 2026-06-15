# MySQL 数据库查询解决方案

## 📋 概述

本方案实现了符合大厂标准的 MySQL 结构化数据查询功能，采用 **Text-to-SQL** 技术，让聊天机器人能够智能查询数据库。

## 🏢 大厂标准方案对比

| 大厂 | 方案 | 特点 |
|------|------|------|
| **OpenAI** | GPT-4 + SQL 执行 | Text-to-SQL 自动生成 |
| **Google** | BigQuery + AI 查询 | 自然语言查询数据库 |
| **阿里** | 智能数据助手 | Text-to-SQL + 可视化 |
| **字节** | 内部 BI 平台 | 预定义模板 + AI 增强 |

## 🔧 实现方案

### 1. 核心组件

#### **MySQL 查询工具** ([mysql_query.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/tools/mysql_query.py))

```python
# 功能：
- Text-to-SQL（LLM 自动生成 SQL）
- 安全防护（SQL 注入防护）
- 权限控制（白名单表）
- 限流熔断（防止数据库过载）
- 结果缓存（提升性能）
- 链路追踪（监控查询性能）
```

#### **智能路由增强** ([smart_router.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/agent/smart_router.py))

```python
# 新增数据库查询关键词：
DATABASE_KEYWORDS = [
    "数据", "数据库", "查询", "统计", "报表",
    "订单", "用户", "客户", "商品", "库存",
    "数量", "总数", "最近", "本周", "本月"
]
```

#### **工具决策优化** ([nodes.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/agent/nodes.py))

```python
# 优化逻辑：
1. 优先检查路由决策（如果路由已指定工具）
2. 使用 LLM 自主决策（如果路由未指定）
```

---

## 🔐 安全防护机制

### 1. SQL 白名单

```python
# 只允许查询特定表
ALLOWED_TABLES = [
    "users", "sessions", "messages",
    "orders", "products", "customers"
]
```

### 2. 禁止关键词

```python
# 防止 SQL 注入
FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT",
    "ALTER", "CREATE", "TRUNCATE",
    "GRANT", "REVOKE", "EXEC"
]
```

### 3. 必须包含 LIMIT

```python
# 防止全表扫描
if "LIMIT" not in sql_upper:
    return False, "必须包含 LIMIT 限制返回行数"
```

### 4. 最大返回行数

```python
# 防止数据过载
MAX_ROWS = 1000
```

---

## 📊 使用流程

### 流程图

```
用户问题："查询最近一周的订单"
    ↓
【智能路由】
    ├─ 匹配数据库关键词 → ✅ 需要工具
    └─ 返回决策：needs_tool=True, tool_name=mysql_query
    ↓
【工具决策】
    ├─ 检查路由决策 → 已指定 mysql_query
    └─ 返回工具调用决策
    ↓
【工具执行】
    ├─ Text-to-SQL 生成 SQL
    │   SELECT * FROM orders WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY) LIMIT 100
    ├─ SQL 安全验证
    ├─ 执行查询
    └─ LLM 总结结果
    ↓
【返回答案】
    "最近一周共有 156 个订单，总销售额 12.5 万元..."
```

---

## 💡 使用示例

### 1. 数据查询

```python
# 用户问题
"查询最近10个用户"

# 自动生成 SQL
SELECT * FROM users ORDER BY created_at DESC LIMIT 10

# 返回结果
{
    "success": True,
    "sql": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10",
    "rows_count": 10,
    "data": [...],
    "summary": "最近注册的10个用户包括..."
}
```

### 2. 统计查询

```python
# 用户问题
"统计订单总数"

# 自动生成 SQL
SELECT COUNT(*) as total FROM orders LIMIT 1

# 返回结果
{
    "success": True,
    "sql": "SELECT COUNT(*) as total FROM orders LIMIT 1",
    "rows_count": 1,
    "data": [{"total": 1234}],
    "summary": "订单总数为 1234 个"
}
```

### 3. 条件查询

```python
# 用户问题
"查询销售额超过100万的订单"

# 自动生成 SQL
SELECT * FROM orders WHERE amount > 1000000 LIMIT 100

# 返回结果
{
    "success": True,
    "sql": "SELECT * FROM orders WHERE amount > 1000000 LIMIT 100",
    "rows_count": 15,
    "data": [...],
    "summary": "销售额超过100万的订单有15个..."
}
```

---

## 🎯 配置说明

### 1. 白名单表配置

修改 [mysql_query.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/tools/mysql_query.py#L27-L35)：

```python
# 添加你的业务表
ALLOWED_TABLES = [
    "users", "sessions", "messages",
    # 添加业务表
    "orders", "products", "customers",
    "inventory", "transactions", "invoices"
]
```

### 2. 关键词配置

修改 [smart_router.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/agent/smart_router.py#L51-L64)：

```python
# 添加业务关键词
DATABASE_KEYWORDS = [
    # 现有关键词...
    # 添加业务关键词
    "发票", "合同", "项目", "任务",
    "员工", "部门", "工资", "绩效"
]
```

### 3. 工具配置

修改 [mysql_query.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/tools/mysql_query.py#L298-L307)：

```python
# 调整限流和熔断参数
config = ToolConfig(
    name="mysql_query",
    timeout=30,        # 超时时间
    rate_limit=50,     # 每分钟50次
    failure_threshold=5,  # 失败5次熔断
    recovery_timeout=60   # 60秒后恢复
)
```

---

## 🧪 测试

运行测试脚本：

```bash
python scripts/test_mysql_tool.py
```

测试内容：
1. Text-to-SQL 自动生成
2. SQL 安全验证
3. MySQL 查询工具调用
4. 完整流程（智能路由 + 工具调用）

---

## 📈 性能优化

### 1. 缓存机制

```python
# 查询结果缓存（Redis）
await CacheService.set_query_result(question, result)
```

### 2. 限流保护

```python
# 每分钟50次查询限制
rate_limit=50
```

### 3. 熔断保护

```python
# 失败5次后熔断，防止数据库过载
failure_threshold=5
```

---

## 🔍 监控

### 1. 链路追踪

```python
# 查询性能监控
async with tracer.span("mysql_query"):
    span.set_attribute("sql", sql)
    span.set_attribute("rows_count", len(data))
```

### 2. 统计信息

```python
# 获取工具统计
stats = ToolRegistry().get_stats("mysql_query")
print(stats)
```

---

## 🚀 扩展建议

### 1. 添加更多表

```python
# 根据业务需求添加表
ALLOWED_TABLES.append("your_table")
```

### 2. 添加预定义查询

```python
# 高频查询使用模板
QUERY_TEMPLATES = {
    "订单查询": "SELECT * FROM orders WHERE user_id = {user_id} LIMIT {limit}"
}
```

### 3. 添加可视化

```python
# 返回图表数据
result["chart_data"] = generate_chart(data)
```

---

## 📚 参考资料

- [OpenAI Text-to-SQL](https://platform.openai.com/docs/guides/text-to-sql)
- [Google BigQuery AI](https://cloud.google.com/bigquery/docs/reference/ai)
- [阿里智能数据助手](https://www.alibabacloud.com/help/zh/dataworks)

---

## ✅ 总结

本方案实现了符合大厂标准的 MySQL 查询功能：

- ✅ **Text-to-SQL**：自动生成 SQL
- ✅ **安全防护**：SQL 注入防护、白名单控制
- ✅ **限流熔断**：防止数据库过载
- ✅ **链路追踪**：监控查询性能
- ✅ **智能路由**：自动识别数据库查询场景
- ✅ **工具集成**：无缝集成到现有框架

**现在你的聊天机器人可以智能查询 MySQL 数据库了！** 🎉