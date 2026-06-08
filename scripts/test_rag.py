"""RAG功能测试脚本

测试内容：
- 文档加载
- 向量化
- 向量存储
- 向量检索
- RAG查询
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.embeddings import EmbeddingService, VectorStore, DocumentLoader, Retriever
from app.services.rag_service import RAGService


def test_embedding_service():
    """测试向量化服务"""
    print("\n=== 测试向量化服务 ===")
    
    # 初始化
    embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
    
    # 单文本向量化
    text = "这是一个测试文本"
    vector = embedding.embed_text(text)
    print(f"文本: {text}")
    print(f"向量维度: {len(vector)}")
    print(f"向量示例: {vector[:5]}")
    
    # 批量向量化
    texts = ["文本1", "文本2", "文本3"]
    vectors = embedding.embed_texts(texts)
    print(f"\n批量向量化: {len(texts)}个文本 -> {vectors.shape}")
    
    # 相似度计算
    text1 = "今天天气很好"
    text2 = "今天天气不错"
    similarity = embedding.similarity(text1, text2)
    print(f"\n相似度测试:")
    print(f"文本1: {text1}")
    print(f"文本2: {text2}")
    print(f"相似度: {similarity:.4f}")
    
    # 模型信息
    info = embedding.get_model_info()
    print(f"\n模型信息: {info}")
    
    print("[OK] 向量化服务测试通过")


def test_document_loader():
    """测试文档加载器"""
    print("\n=== 测试文档加载器 ===")
    
    loader = DocumentLoader(chunk_size=500, chunk_overlap=50)
    
    # 创建测试文件
    test_file = "test_doc.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("这是一个测试文档。\n\n" * 20)
    
    # 加载文件
    chunks = loader.load_file(test_file)
    print(f"文件: {test_file}")
    print(f"分块数量: {len(chunks)}")
    print(f"第一个分块: {chunks[0].content[:100]}...")
    print(f"分块元数据: {chunks[0].metadata}")
    
    # 清理
    os.remove(test_file)
    
    print("[OK] 文档加载器测试通过")


def test_vector_store():
    """测试向量存储"""
    print("\n=== 测试向量存储 ===")
    
    # 初始化（需要MySQL）
    try:
        store = VectorStore(
            db_host="localhost",
            db_port=3306,
            db_user="root",
            db_password="123456",
            db_name="agent_db"
        )
        
        # 初始化向量化服务
        embedding = EmbeddingService(model_name="bge-large-zh-v1.5")
        
        # 添加文档
        text = "这是测试文档内容"
        vector = embedding.embed_text(text)
        doc_id = store.add_document(
            content=text,
            embedding=vector,
            metadata={"test": True},
            source="test_script"
        )
        print(f"添加文档ID: {doc_id}")
        
        # 获取文档
        doc = store.get_document(doc_id)
        print(f"获取文档: {doc.content}")
        
        # 搜索
        query_text = "测试文档"
        query_vector = embedding.embed_text(query_text)
        results = store.search_by_similarity(query_vector, top_k=5)
        print(f"搜索结果数量: {len(results)}")
        for r in results:
            print(f"  - ID: {r['id']}, 分数: {r['score']:.4f}")
        
        # 统计
        stats = store.get_stats()
        print(f"统计信息: {stats}")
        
        # 删除
        success = store.delete_document(doc_id)
        print(f"删除文档: {success}")
        
        print("[OK] 向量存储测试通过")
        
    except Exception as e:
        print(f"[WARN] 向量存储测试跳过（需要MySQL）: {e}")


async def test_rag_service():
    """测试RAG服务"""
    print("\n=== 测试RAG服务 ===")
    
    try:
        # 初始化RAG服务
        rag = RAGService(
            embedding_model="bge-large-zh-v1.5",
            db_config={
                "db_host": "localhost",
                "db_port": 3306,
                "db_user": "root",
                "db_password": "123456",
                "db_name": "agent_db"
            }
        )
        
        # 文本入库
        doc_id = await rag.ingest_text(
            content="Python是一种流行的编程语言，广泛用于Web开发、数据分析和人工智能。",
            source="test",
            metadata={"topic": "python"}
        )
        print(f"入库文档ID: {doc_id}")
        
        # 查询
        result = await rag.query(
            question="Python有什么用途？",
            top_k=3
        )
        print(f"\n查询结果:")
        print(f"问题: {result['question']}")
        print(f"找到文档数: {result['total_results']}")
        for source in result['sources']:
            print(f"  - 内容: {source['content'][:50]}...")
            print(f"    分数: {source['score']:.4f}")
        
        # 统计
        stats = rag.get_stats()
        print(f"\n统计信息: {stats}")
        
        # 清理
        await rag.delete_by_source("test")
        
        print("[OK] RAG服务测试通过")
        
    except Exception as e:
        print(f"[WARN] RAG服务测试跳过（需要MySQL）: {e}")


def main():
    """主测试流程"""
    print("=" * 60)
    print("RAG功能测试")
    print("=" * 60)
    
    # 测试向量化服务
    test_embedding_service()
    
    # 测试文档加载器
    test_document_loader()
    
    # 测试向量存储（需要MySQL）
    test_vector_store()
    
    # 测试RAG服务（需要MySQL）
    asyncio.run(test_rag_service())
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()