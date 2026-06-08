"""向量功能使用示例

演示：
1. 文本向量化
2. 文档入库
3. 向量检索
4. RAG查询
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.embeddings import EmbeddingService, VectorStore, DocumentLoader, Retriever
from app.services.rag_service import RAGService
import asyncio


def example_1_basic_embedding():
    """示例1: 基础向量化"""
    print("\n" + "="*60)
    print("示例1: 基础向量化")
    print("="*60)
    
    # 初始化向量化服务（使用本地模型）
    embedding = EmbeddingService(
        model_name="bge-large-zh-v1.5",
        model_path="bge-large-zh-v1.5"  # 本地模型路径
    )
    
    # 单文本向量化
    text = "Python是一种流行的编程语言"
    vector = embedding.embed_text(text)
    
    print(f"文本: {text}")
    print(f"向量维度: {len(vector)}")
    print(f"向量前5个值: {vector[:5]}")
    
    # 批量向量化
    texts = [
        "机器学习是AI的核心技术",
        "深度学习用于图像识别",
        "自然语言处理处理文本"
    ]
    vectors = embedding.embed_texts(texts)
    print(f"\n批量向量化: {len(texts)}个文本 -> {vectors.shape}形状")
    
    # 计算相似度
    text1 = "Python编程"
    text2 = "Python开发"
    similarity = embedding.similarity(text1, text2)
    print(f"\n相似度计算:")
    print(f"'{text1}' vs '{text2}' = {similarity:.4f}")


def example_2_vector_store():
    """示例2: 向量存储"""
    print("\n" + "="*60)
    print("示例2: 向量存储到MySQL")
    print("="*60)
    
    # 初始化
    embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
    
    # 连接MySQL（修改为你的密码）
    store = VectorStore(
        db_host="localhost",
        db_port=3306,
        db_user="root",
        db_password="123456",  # 修改为你的密码
        db_name="agent_db"
    )
    
    # 添加文档
    docs = [
        {"content": "Python用于Web开发", "source": "example", "doc_type": "text"},
        {"content": "机器学习用于数据分析", "source": "example", "doc_type": "text"},
        {"content": "向量数据库支持相似度搜索", "source": "example", "doc_type": "text"}
    ]
    
    # 向量化
    for doc in docs:
        doc["embedding"] = embedding.embed_text(doc["content"])
    
    # 批量存储
    doc_ids = store.add_documents_batch(docs)
    print(f"成功存储 {len(doc_ids)} 个文档")
    print(f"文档ID列表: {doc_ids}")
    
    # 查看统计
    stats = store.get_stats()
    print(f"\n存储统计: {stats}")


def example_3_vector_search():
    """示例3: 向量检索"""
    print("\n" + "="*60)
    print("示例3: 向量相似度检索")
    print("="*60)
    
    # 初始化
    embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
    store = VectorStore(
        db_password="123456",  # 修改为你的密码
        db_name="agent_db"
    )
    
    # 查询
    query = "Python有什么用途"
    query_vector = embedding.embed_text(query)
    
    # 检索
    results = store.search_by_similarity(
        query_embedding=query_vector,
        top_k=3,
        threshold=0.3
    )
    
    print(f"查询: '{query}'")
    print(f"\n检索结果 ({len(results)}个):")
    for i, result in enumerate(results):
        print(f"\n[{i+1}] 相似度: {result['score']:.4f}")
        print(f"    内容: {result['content']}")
        print(f"    来源: {result['source']}")


def example_4_document_loader():
    """示例4: 文档加载"""
    print("\n" + "="*60)
    print("示例4: 文档加载与分块")
    print("="*60)
    
    loader = DocumentLoader(
        chunk_size=500,    # 分块大小
        chunk_overlap=50   # 重叠大小
    )
    
    # 创建测试文件
    test_file = "test_document.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("""Python编程语言介绍

Python是一种高级编程语言，由Guido van Rossum于1991年创建。
Python的设计哲学强调代码的可读性和简洁性。

主要特点：
1. 语法简单易学
2. 丰富的标准库
3. 跨平台兼容
4. 强大的社区支持

应用领域：
- Web开发（Django, Flask）
- 数据分析（Pandas, NumPy）
- 机器学习（TensorFlow, PyTorch）
- 自动化脚本
""")
    
    # 加载文件
    chunks = loader.load_file(test_file)
    
    print(f"文件: {test_file}")
    print(f"分块数量: {len(chunks)}")
    
    for i, chunk in enumerate(chunks):
        print(f"\n[分块 {i+1}]")
        print(f"内容: {chunk.content[:100]}...")
        print(f"元数据: {chunk.metadata}")
    
    # 清理
    os.remove(test_file)


async def example_5_rag_service():
    """示例5: RAG完整流程"""
    print("\n" + "="*60)
    print("示例5: RAG检索增强生成")
    print("="*60)
    
    # 初始化RAG服务
    rag = RAGService(
        embedding_model="bge-large-zh-v1.5",
        db_config={
            "db_host": "localhost",
            "db_port": 3306,
            "db_user": "root",
            "db_password": "123456",  # 修改为你的密码
            "db_name": "agent_db"
        }
    )
    
    # 1. 文本入库
    print("\n[步骤1] 文本入库")
    texts = [
        "Python是一种编程语言，广泛用于Web开发和数据分析",
        "机器学习是人工智能的核心技术，可以从数据中学习模式",
        "向量数据库用于存储和检索高维向量数据"
    ]
    
    for text in texts:
        doc_id = await rag.ingest_text(
            content=text,
            source="rag_example",
            metadata={"example": True}
        )
        print(f"入库成功: ID={doc_id}, 内容='{text[:30]}...'")
    
    # 2. RAG查询
    print("\n[步骤2] RAG查询")
    result = await rag.query(
        question="Python有什么用途？",
        top_k=3,
        threshold=0.3
    )
    
    print(f"问题: {result['question']}")
    print(f"找到文档: {result['total_results']}个")
    
    for source in result['sources']:
        print(f"\n- 内容: {source['content']}")
        print(f"  相似度: {source['score']:.4f}")
    
    # 3. 清理测试数据
    print("\n[步骤3] 清理测试数据")
    count = await rag.delete_by_source("rag_example")
    print(f"删除了 {count} 个文档")


def example_6_hybrid_search():
    """示例6: 混合检索"""
    print("\n" + "="*60)
    print("示例6: 混合检索（向量+关键词）")
    print("="*60)
    
    embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
    store = VectorStore(db_password="123456", db_name="agent_db")
    
    retriever = Retriever(
        embedding_service=embedding,
        vector_store=store,
        top_k=5,
        rerank_enabled=True
    )
    
    # 混合检索
    query = "Python编程"
    results = retriever.hybrid_retrieve(
        query=query,
        top_k=3,
        vector_weight=0.7,   # 向量权重
        keyword_weight=0.3   # 关键词权重
    )
    
    print(f"查询: '{query}'")
    print(f"\n混合检索结果:")
    for i, result in enumerate(results):
        print(f"\n[{i+1}] 综合分数: {result['score']:.4f}")
        print(f"    向量分数: {result.get('vector_score', 0):.4f}")
        print(f"    关键词分数: {result.get('keyword_score', 0):.4f}")
        print(f"    内容: {result['content']}")


def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("向量功能使用示例")
    print("="*60)
    print("\n注意: 需要先执行以下步骤:")
    print("1. 安装依赖: pip install sentence-transformers pymysql")
    print("2. 执行SQL: scripts/init_vector_db.sql")
    print("3. 修改MySQL密码为你的实际密码")
    
    # 运行示例
    try:
        example_1_basic_embedding()
        example_4_document_loader()
        # example_2_vector_store()  # 需要MySQL
        # example_3_vector_search()  # 需要MySQL
        # asyncio.run(example_5_rag_service())  # 需要MySQL
        # example_6_hybrid_search()  # 需要MySQL
    except Exception as e:
        print(f"\n错误: {e}")
        print("请确保MySQL已启动并执行了init_vector_db.sql")


if __name__ == "__main__":
    main()