# 向量功能快速入门指南

## 一、准备工作

### 1. 安装依赖
```bash
pip install sentence-transformers pymysql sqlalchemy
```

### 2. 执行SQL建表
```bash
# 方式1: 命令行执行
mysql -u root -p123456 < scripts/init_vector_db.sql

# 方式2: MySQL客户端执行
source scripts/init_vector_db.sql
```

### 3. 确保模型文件存在
检查 `bge-large-zh-v1.5` 目录是否存在，如果不存在会自动下载。

---

## 二、基础使用

### 1. 文本向量化
```python
from app.embeddings import EmbeddingService

# 初始化
embedding = EmbeddingService(model_name="bge-large-zh-v1.5")

# 单文本向量化
vector = embedding.embed_text("Python是一种编程语言")
print(f"向量维度: {len(vector)}")  # 输出: 1024

# 批量向量化
texts = ["文本1", "文本2", "文本3"]
vectors = embedding.embed_texts(texts)

# 计算相似度
similarity = embedding.similarity("Python编程", "Python开发")
print(f"相似度: {similarity}")
```

### 2. 文档入库
```python
from app.embeddings import VectorStore, EmbeddingService

# 初始化
embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
store = VectorStore(db_password="123456")

# 添加文档
text = "Python用于Web开发"
vector = embedding.embed_text(text)
doc_id = store.add_document(
    content=text,
    embedding=vector,
    source="manual",
    doc_type="text"
)
print(f"文档ID: {doc_id}")
```

### 3. 向量检索
```python
from app.embeddings import VectorStore, EmbeddingService

# 初始化
embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
store = VectorStore(db_password="123456")

# 查询
query = "Python有什么用途"
query_vector = embedding.embed_text(query)

# 检索
results = store.search_by_similarity(
    query_embedding=query_vector,
    top_k=5,
    threshold=0.5
)

for result in results:
    print(f"内容: {result['content']}")
    print(f"相似度: {result['score']}")
```

---

## 三、RAG完整流程

### 1. 使用RAG服务
```python
from app.services.rag_service import RAGService
import asyncio

# 初始化RAG服务
rag = RAGService(
    embedding_model="bge-large-zh-v1.5",
    db_config={"db_password": "123456"}
)

# 文档入库
async def ingest():
    # 文本入库
    doc_id = await rag.ingest_text(
        content="Python是一种编程语言",
        source="doc1",
        metadata={"topic": "python"}
    )
    
    # 文件入库
    result = await rag.ingest_document("docs/manual.pdf")
    print(result)

# RAG查询
async def query():
    result = await rag.query(
        question="Python有什么用途",
        top_k=5
    )
    
    print(f"问题: {result['question']}")
    for source in result['sources']:
        print(f"相关文档: {source['content']}")
        print(f"相似度: {source['score']}")

# 运行
asyncio.run(ingest())
asyncio.run(query())
```

---

## 四、文档加载

### 1. 加载不同格式文档
```python
from app.embeddings import DocumentLoader

loader = DocumentLoader(chunk_size=500)

# 加载TXT
chunks = loader.load_file("document.txt")

# 加载PDF（需要安装pypdf）
chunks = loader.load_file("document.pdf")

# 加载Word（需要安装python-docx）
chunks = loader.load_file("document.docx")

# 加载Markdown
chunks = loader.load_file("document.md")

# 批量加载目录
chunks = loader.load_directory("docs/", recursive=True)
```

---

## 五、混合检索

### 1. 向量+关键词检索
```python
from app.embeddings import Retriever, EmbeddingService, VectorStore

# 初始化
embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
store = VectorStore(db_password="123456")
retriever = Retriever(embedding, store)

# 混合检索
results = retriever.hybrid_retrieve(
    query="Python编程",
    top_k=5,
    vector_weight=0.7,   # 向量权重
    keyword_weight=0.3   # 关键词权重
)

for result in results:
    print(f"综合分数: {result['score']}")
    print(f"向量分数: {result['vector_score']}")
    print(f"关键词分数: {result['keyword_score']}")
```

---

## 六、API接口使用

### 1. 文档入库接口
```bash
# 文本入库
curl -X POST http://localhost:8000/api/v1/rag/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"content": "Python是一种编程语言", "source": "test"}'

# 文件入库
curl -X POST http://localhost:8000/api/v1/rag/ingest/file \
  -F "file=@document.pdf"
```

### 2. RAG查询接口
```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Python有什么用途", "top_k": 5}'
```

### 3. 统计信息接口
```bash
curl http://localhost:8000/api/v1/rag/stats
```

---

## 七、常见问题

### Q1: 向量维度是多少？
A: bge-large-zh-v1.5 模型的向量维度是 **1024**

### Q2: 向量如何存储？
A: 向量以二进制格式存储在MySQL的LONGBLOB字段中

### Q3: 相似度范围是多少？
A: Cosine相似度范围是 [-1, 1]，归一化后是 [0, 1]

### Q4: 如何提高检索效率？
A: 
- 使用Redis缓存热门查询向量
- 使用专门的向量数据库（如Milvus、Pinecone）
- 批量处理文档入库

---

## 八、测试脚本

运行测试：
```bash
python scripts/vector_usage_examples.py
```