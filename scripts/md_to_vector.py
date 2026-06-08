"""MD文件转向量示例"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.embeddings import DocumentLoader, EmbeddingService, VectorStore
from app.services.rag_service import RAGService
import asyncio


def md_to_vector(file_path):
    """将MD文件转换为向量并存储"""
    print(f"\n处理文件: {file_path}")
    
    # 1. 初始化服务
    loader = DocumentLoader(chunk_size=500, chunk_overlap=50)
    embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
    store = VectorStore(db_password="123456")
    
    # 2. 加载文件
    print("步骤1: 加载文件...")
    chunks = loader.load_file(file_path)
    print(f"文件分块数量: {len(chunks)}")
    
    # 3. 向量化并存储
    print("\n步骤2: 向量化并存储...")
    doc_ids = []
    for i, chunk in enumerate(chunks):
        vector = embedding.embed_text(chunk.content)
        doc_id = store.add_document(
            content=chunk.content,
            embedding=vector,
            source=file_path,
            doc_type="markdown",
            metadata={
                "chunk_index": i,
                "total_chunks": len(chunks),
                **chunk.metadata
            }
        )
        doc_ids.append(doc_id)
        print(f"  分块 {i+1}/{len(chunks)}: ID={doc_id}")
    
    print(f"\n完成！共存储 {len(doc_ids)} 个向量")
    return doc_ids


async def md_to_vector_rag(file_path):
    """使用RAG服务处理MD文件"""
    print(f"\n使用RAG服务处理: {file_path}")
    
    rag = RAGService(
        embedding_model="bge-large-zh-v1.5",
        db_config={"db_password": "123456"}
    )
    
    # 直接入库
    result = await rag.ingest_document(file_path)
    print(f"入库结果: {result}")
    
    # 查询测试
    print("\n测试查询:")
    query_result = await rag.query(
        question="文档主要讲了什么？",
        top_k=3
    )
    print(f"问题: {query_result['question']}")
    print(f"找到 {query_result['total_results']} 个相关文档")
    
    return result


if __name__ == "__main__":
    # 创建测试MD文件
    test_file = "test_document.md"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("""# Python教程

## 简介

Python是一种高级编程语言，由Guido van Rossum创建。

## 特点

- 语法简洁
- 易于学习
- 跨平台

## 应用领域

1. Web开发
2. 数据分析
3. 机器学习

## 代码示例

```python
print("Hello, World!")
```
""")
    
    # 方式1: 使用基础API
    md_to_vector(test_file)
    
    # 方式2: 使用RAG服务
    asyncio.run(md_to_vector_rag(test_file))
    
    # 清理
    os.remove(test_file)
    
    print("\n测试完成！")