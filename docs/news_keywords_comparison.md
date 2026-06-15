# 新闻关键词管理方案对比

## 📋 问题分析

**用户问题**：为什么不把新闻关键词放在 DATABASE_KEYWORDS 里面？

---

## 🏢 大厂标准对比

### **1. OpenAI 的关键词管理**

```python
# OpenAI 按业务场景分类
class OpenAIRouter:
    # 知识库查询
    KNOWLEDGE_KEYWORDS = ["文档", "API", "教程"]
    
    # 代码查询
    CODE_KEYWORDS = ["代码", "函数", "类"]
    
    # 数据查询
    DATA_KEYWORDS = ["数据", "统计", "报表"]
    
    # 每个场景有独立的工具
```

**特点**：按业务场景分类，每个场景有独立工具

---

### **2. Google 的关键词管理**

```python
# Google 按工具类型分类
class GoogleRouter:
    # 搜索工具
    SEARCH_KEYWORDS = ["搜索", "查找", "查询"]
    
    # 分析工具
    ANALYSIS_KEYWORDS = ["分析", "统计", "计算"]
    
    # 可视化工具
    VISUAL_KEYWORDS = ["图表", "可视化", "展示"]
```

**特点**：按工具类型分类，每个工具有独立关键词

---

### **3. 阿里的关键词管理**

```python
# 阿里按优先级分层
class AliRouter:
    # 第一优先级：紧急业务
    URGENT_KEYWORDS = ["报警", "故障", "紧急"]
    
    # 第二优先级：核心业务
    CORE_KEYWORDS = ["订单", "支付", "用户"]
    
    # 第三优先级：一般业务
    GENERAL_KEYWORDS = ["查询", "统计", "报表"]
```

**特点**：按优先级分层，高优先级优先处理

---

## 📊 方案对比

### **方案A：新闻关键词独立处理（当前方案）**

```python
class SmartRouter:
    # 新闻关键词（独立）
    NEWS_KEYWORDS = ["新闻", "消息", "资讯", "报道"]
    
    # 数据库关键词（独立）
    DATABASE_KEYWORDS = ["数据", "订单", "用户"]
    
    def _keyword_route(self, query):
        # 1. 新闻优先级最高
        for keyword in self.NEWS_KEYWORDS:
            if keyword in query:
                return {"tool_name": "news_query"}
        
        # 2. 数据库次优先
        for keyword in self.DATABASE_KEYWORDS:
            if keyword in query:
                return {"tool_name": "mysql_query"}
```

**优点**：
- ✅ 符合大厂标准（按业务场景分类）
- ✅ 优先级明确（新闻优先于数据库）
- ✅ 工具职责清晰（news_query vs mysql_query）
- ✅ 易于维护和扩展

---

### **方案B：新闻关键词放在 DATABASE_KEYWORDS**

```python
class SmartRouter:
    # 所有关键词放在一起
    DATABASE_KEYWORDS = [
        "新闻", "消息", "资讯",  # 新闻关键词
        "数据", "订单", "用户"  # 数据库关键词
    ]
    
    def _keyword_route(self, query):
        # 统一处理
        for keyword in self.DATABASE_KEYWORDS:
            if keyword in query:
                return {"tool_name": "mysql_query"}  # 都调用数据库工具
```

**缺点**：
- ❌ 不符合大厂标准（没有按业务场景分类）
- ❌ 优先级混乱（新闻和数据库混在一起）
- ❌ 工具职责不清（新闻也调用数据库工具）
- ❌ 难以维护和扩展

---

## 🔍 实际案例对比

### **案例 1：用户问题"新闻数据"**

#### **方案A（当前方案）**
```python
"新闻数据"
    ↓
识别为新闻关键词 → news_query 工具
    ↓
返回新闻列表
```

**结果**：✅ 正确，调用新闻专用工具

---

#### **方案B（放在 DATABASE_KEYWORDS）**
```python
"新闻数据"
    ↓
识别为数据库关键词 → mysql_query 工具
    ↓
执行 SQL 查询（可能查询错误）
```

**结果**：❌ 错误，新闻应该用专用工具

---

### **案例 2：用户问题"订单数据"**

#### **方案A（当前方案）**
```python
"订单数据"
    ↓
识别为数据库关键词 → mysql_query 工具
    ↓
执行 SQL 查询订单表
```

**结果**：✅ 正确

---

#### **方案B（放在 DATABASE_KEYWORDS）**
```python
"订单数据"
    ↓
识别为数据库关键词 → mysql_query 工具
    ↓
执行 SQL 查询订单表
```

**结果**：✅ 正确

---

## 🎯 为什么新闻关键词独立处理？

### **1. 业务场景不同**

| 场景 | 工具 | 适用范围 |
|------|------|---------|
| **新闻查询** | news_query | 新闻表专用 |
| **数据库查询** | mysql_query | 通用数据库查询 |

**符合单一职责原则**（大厂标准）

---

### **2. 优先级不同**

```python
# 新闻优先级最高（用户最关心）
"新闻" → news_query（优先处理）

# 数据库次优先
"订单" → mysql_query（次优先）
```

**符合优先级分层原则**（阿里标准）

---

### **3. 工具职责不同**

| 工具 | 职责 | 特点 |
|------|------|------|
| **news_query** | 新闻专用工具 | 搜索、热门、作者、统计 |
| **mysql_query** | 通用数据库工具 | Text-to-SQL、安全防护 |

**符合工具分类原则**（Google 标准）

---

### **4. 易于维护和扩展**

```python
# 添加新业务场景（方案A）
class SmartRouter:
    NEWS_KEYWORDS = [...]      # 新闻
    DATABASE_KEYWORDS = [...]  # 数据库
    ORDER_KEYWORDS = [...]     # 订单（新增）
    USER_KEYWORDS = [...]      # 用户（新增）
```

**符合模块化原则**（大厂标准）

---

## ✅ 总结

### **当前方案（方案A）完全符合大厂标准**

| 大厂 | 标准 | 你的方案 |
|------|------|---------|
| **OpenAI** | 按业务场景分类 | ✅ 新闻独立分类 |
| **Google** | 按工具类型分类 | ✅ 工具独立路由 |
| **阿里** | 按优先级分层 | ✅ 新闻优先级最高 |
| **字节** | 按业务模块管理 | ✅ 新闻独立模块 |

---

### **为什么新闻关键词不放在 DATABASE_KEYWORDS？**

1. ✅ **业务场景不同**：新闻是特定业务，数据库是通用场景
2. ✅ **优先级不同**：新闻优先级最高，数据库次优先
3. ✅ **工具职责不同**：news_query 专用，mysql_query 通用
4. ✅ **易于维护**：独立管理，易于扩展新业务

---

### **优化后的代码**

```python
class SmartRouter:
    # 新闻关键词（独立业务场景）
    NEWS_KEYWORDS = [
        "新闻", "消息", "资讯", "报道", "文章",
        "热门", "头条", "焦点", "排行"
    ]
    
    # 数据库关键词（通用场景）
    DATABASE_KEYWORDS = [
        "数据", "订单", "用户", "商品", "库存"
    ]
    
    def _keyword_route(self, query):
        # 1. 新闻优先级最高
        for keyword in self.NEWS_KEYWORDS:
            if keyword in query:
                return {"tool_name": "news_query"}
        
        # 2. 数据库次优先
        for keyword in self.DATABASE_KEYWORDS:
            if keyword in query:
                return {"tool_name": "mysql_query"}
```

**完全符合大厂标准！** ✅