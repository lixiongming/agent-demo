# 新闻查询系统实现文档

## 📋 概述

本方案实现了完整的新闻查询系统，包括：
- **Model**: SQLAlchemy ORM 模型
- **Repository**: 数据访问层
- **Tool**: 聊天机器人查询工具
- **智能路由**: 自动识别新闻查询场景

## 🗂️ 文件结构

### 1. Model 层

**文件**: [app/db/models/news.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/db/models/news.py)

```python
class News(Base):
    """新闻表模型
    
    字段：
    - id: 新闻ID（主键）
    - title: 新闻标题
    - description: 新闻简介
    - content: 新闻内容
    - image: 封面图片URL
    - author: 作者
    - views: 浏览量
    - created_at: 创建时间
    - updated_at: 更新时间
    """
```

### 2. Repository 层

**文件**: [app/db/repositories/news.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/db/repositories/news.py)

```python
class NewsRepository:
    """新闻数据访问
    
    功能：
    - 基础查询（ID、列表、分页）
    - 搜索查询（关键词、标题、内容）
    - 统计查询（总数、浏览量）
    - 热门新闻（浏览量排序）
    - 作者新闻（按作者查询）
    - 时间范围查询（最近、本周、本月）
    """
```

### 3. Tool 层

**文件**: [app/tools/news_query.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/tools/news_query.py)

```python
async def news_query_tool(
    query_type: str,
    keyword: Optional[str] = None,
    author: Optional[str] = None,
    limit: int = 10,
    days: Optional[int] = None
) -> Dict[str, Any]:
    """新闻查询工具
    
    查询类型：
    - search: 搜索新闻
    - hot: 热门新闻
    - recent: 最近新闻
    - author: 作者新闻
    - stats: 新闻统计
    - today: 今天新闻
    - week: 本周新闻
    - month: 本月新闻
    """
```

---

## 📊 数据库表结构

```sql
CREATE TABLE `news` (
  `id` int UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '新闻ID',
  `title` varchar(255) NOT NULL COMMENT '新闻标题',
  `description` varchar(500) NULL COMMENT '新闻简介',
  `content` text NOT NULL COMMENT '新闻内容',
  `image` varchar(255) NULL COMMENT '封面图片URL',
  `author` varchar(50) NULL COMMENT '作者',
  `views` int UNSIGNED NOT NULL DEFAULT 0 COMMENT '浏览量',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`)
) COMMENT = '新闻表';
```

---

## 🔧 使用方法

### 1. 基础查询

```python
from app.db.repositories.news import NewsRepository
from app.db.database import AsyncSessionLocal

async with AsyncSessionLocal() as db:
    repo = NewsRepository(db)
    
    # 获取最近新闻
    news_list = await repo.get_recent(limit=10)
    
    # 搜索新闻
    news_list = await repo.search(keyword="科技", limit=10)
    
    # 获取热门新闻
    news_list = await repo.get_hot_news(limit=10)
    
    # 获取作者新闻
    news_list = await repo.get_by_author(author="新华社", limit=10)
```

### 2. 工具调用

```python
from app.tools.news_query import news_query_tool

# 搜索新闻
result = await news_query_tool(
    query_type="search",
    keyword="科技",
    limit=10
)

# 热门新闻
result = await news_query_tool(
    query_type="hot",
    limit=10
)

# 作者新闻
result = await news_query_tool(
    query_type="author",
    author="新华社",
    limit=10
)

# 新闻统计
result = await news_query_tool(
    query_type="stats"
)
```

### 3. 智能查询

```python
from app.tools.news_query import smart_news_query

# 用户问题自动判断查询类型
result = await smart_news_query("最近有什么新闻")
result = await smart_news_query("查看热门新闻")
result = await smart_news_query("新华社发布了什么新闻")
```

---

## 🤖 聊天机器人集成

### 智能路由

**文件**: [app/agent/smart_router.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/agent/smart_router.py)

```python
# 新闻查询关键词（自动识别）
news_keywords = ["新闻", "消息", "资讯", "报道", "文章", "热门", "头条"]

# 路由逻辑：
用户问题："最近有什么新闻"
    ↓
智能路由识别 → 包含"新闻"关键词
    ↓
指定调用 news_query 工具
    ↓
执行查询 → 返回结果
```

### 工具决策

**文件**: [app/agent/nodes.py](file:///c:/Users/Administrator/PycharmProjects/langchain/app/agent/nodes.py)

```python
# 工具决策节点会自动调用 news_query 工具
if route_decision.get("needs_tool"):
    tool_name = route_decision.get("tool_name")
    # 如果 tool_name == "news_query"，调用新闻查询工具
```

---

## 📈 查询类型说明

| 查询类型 | 说明 | 参数 | 示例 |
|---------|------|------|------|
| **search** | 搜索新闻 | keyword | "搜索科技新闻" |
| **hot** | 热门新闻 | days（可选） | "查看热门新闻" |
| **recent** | 最近新闻 | - | "最近有什么新闻" |
| **author** | 作者新闻 | author | "新华社的新闻" |
| **stats** | 新闻统计 | - | "统计新闻数据" |
| **today** | 今天新闻 | - | "今天的新闻" |
| **week** | 本周新闻 | - | "本周新闻" |
| **month** | 本月新闻 | - | "本月新闻" |

---

## 🧪 测试

运行测试脚本：

```bash
python scripts/test_news_tool.py
```

测试内容：
1. 基础查询（搜索、热门、最近、作者）
2. 时间范围查询（今天、本周、本月）
3. 智能查询（LLM 决策）
4. 完整流程（智能路由 + 工具调用）

---

## 🔍 实际案例

### 案例 1：搜索新闻

```python
# 用户问题
"搜索关于科技的新闻"

# 查询参数
{
    "query_type": "search",
    "keyword": "科技",
    "limit": 10
}

# 返回结果
{
    "success": True,
    "news_count": 5,
    "news_list": [
        {
            "id": 8,
            "title": "我国科学家在量子计算领域取得新突破",
            "views": 10800,
            "author": "科技日报"
        },
        ...
    ]
}
```

### 案例 2：热门新闻

```python
# 用户问题
"查看热门新闻"

# 查询参数
{
    "query_type": "hot",
    "limit": 10
}

# 返回结果
{
    "success": True,
    "news_count": 10,
    "news_list": [
        {
            "id": 4,
            "title": "2023年我国GDP同比增长5.2%",
            "views": 15314,
            "author": "经济日报"
        },
        ...
    ]
}
```

### 案例 3：作者新闻

```python
# 用户问题
"新华社发布了什么新闻"

# 查询参数
{
    "query_type": "author",
    "author": "新华社",
    "limit": 10
}

# 返回结果
{
    "success": True,
    "news_count": 3,
    "news_list": [
        {
            "id": 1,
            "title": "国家主席发表2024年新年贺词",
            "views": 12558,
            "author": "新华社"
        },
        ...
    ]
}
```

---

## 🎯 扩展建议

### 1. 添加更多查询类型

```python
# 添加分类查询
async def get_by_category(self, category: str, limit: int = 10):
    """按分类查询新闻"""
    ...
```

### 2. 添加缓存机制

```python
# 缓存热门新闻
await CacheService.set_hot_news(news_list)
```

### 3. 添加推荐算法

```python
# 基于用户兴趣推荐新闻
async def get_recommended_news(user_id: int, limit: int = 10):
    """推荐新闻"""
    ...
```

---

## ✅ 总结

本方案实现了完整的新闻查询系统：

- ✅ **Model**: SQLAlchemy ORM 模型
- ✅ **Repository**: 完整的数据访问层
- ✅ **Tool**: 聊天机器人查询工具
- ✅ **智能路由**: 自动识别新闻查询
- ✅ **多种查询**: 搜索、热门、作者、统计
- ✅ **时间范围**: 今天、本周、本月
- ✅ **智能查询**: LLM 自动决策

**现在你的聊天机器人可以智能查询新闻数据了！** 🎉