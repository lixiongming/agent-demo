"""LOL 知识库导入到 Qdrant 向量数据库"""
import re
import json
import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.embeddings import get_embedding_service
from app.embeddings.qdrant_store import QdrantKnowledgeStore


def parse_lol_knowledge_base(file_path: str) -> list:
    """
    解析 LOL 知识库文档

    格式：
    ### doc_type
    ```json
    {...}
    ```
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配 ### doc_type 和 ```json ... ``` 块
    pattern = r'###\s+(\w+)\s*\n+```json\s*\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)

    documents = []
    for doc_type, json_content in matches:
        try:
            doc = json.loads(json_content)
            doc["doc_type"] = doc_type
            documents.append(doc)
        except json.JSONDecodeError as e:
            print(f"[ERROR] 解析 JSON 失败: {e}")
            continue

    return documents


async def store_lol_knowledge_to_qdrant(
    file_path: str,
    collection_name: str = "knowledge_base",
    use_memory: bool = False,
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    clear_existing: bool = False,
):
    """
    将 LOL 知识库存储到 Qdrant

    Args:
        file_path: 知识库文件路径
        collection_name: Qdrant 集合名称
        use_memory: 是否使用内存模式（用于测试）
        qdrant_host: Qdrant 服务地址
        qdrant_port: Qdrant 服务端口
        clear_existing: 是否清空现有数据
    """
    print(f"[INFO] 解析知识库文件: {file_path}")
    documents = parse_lol_knowledge_base(file_path)
    print(f"[OK] 解析完成，共 {len(documents)} 个文档")

    if not documents:
        print("[ERROR] 没有找到文档")
        return

    # 初始化 Embedding 服务
    print("\n[INFO] 初始化 Embedding 服务...")
    embedding = get_embedding_service()

    # 初始化 Qdrant 存储
    print("[INFO] 初始化 Qdrant 存储...")
    vector_size = embedding.get_embedding_dim()  # 获取向量维度
    print(f"[INFO] 向量维度: {vector_size}")
    
    if use_memory:
        store = QdrantKnowledgeStore(
            collection_name=collection_name,
            path=":memory:",
            vector_size=vector_size,
        )
    else:
        store = QdrantKnowledgeStore(
            collection_name=collection_name,
            host=qdrant_host,
            port=qdrant_port,
            vector_size=vector_size,
        )

    # 清空现有数据
    if clear_existing:
        print("[INFO] 清空现有数据...")
        store.clear_collection()

    # 获取集合信息
    info = store.get_collection_info()
    print(f"[INFO] 集合信息: {info}")

    # 批量处理文档
    print("\n[INFO] 开始处理文档...")
    batch_size = 10
    total = len(documents)

    for i in range(0, total, batch_size):
        batch = documents[i : i + batch_size]

        # 提取 embedding_text 并生成向量
        texts = [doc.get("embedding_text", "") for doc in batch]
        vectors = await embedding.embed_texts(texts)

        # 添加到 Qdrant
        store.add_documents_batch(documents=batch, vectors=vectors)

        print(f"[OK] 已处理 {min(i + batch_size, total)}/{total} 个文档")

    # 显示最终统计
    info = store.get_collection_info()
    print(f"\n[DONE] 导入完成!")
    print(f"[INFO] 集合: {info['name']}")
    print(f"[INFO] 文档数: {info['points_count']}")

    return store


async def test_search(store: QdrantKnowledgeStore, query: str, doc_type: str = None):
    """测试搜索功能"""
    print(f"\n[TEST] 搜索测试: '{query}'")

    # 初始化 Embedding 服务
    embedding = get_embedding_service()
    query_vector = await embedding.embed_text(query)

    # 执行搜索（先不带过滤条件测试）
    results = store.search(
        query_vector=query_vector,
        top_k=3,
    )

    print(f"[RESULT] 找到 {len(results)} 个结果:")
    for i, result in enumerate(results, 1):
        print(f"\n--- 结果 {i} ---")
        print(f"相似度: {result['score']:.4f}")
        print(f"文档ID: {result['payload'].get('doc_id')}")
        print(f"类型: {result['payload'].get('doc_type')}")
        print(f"标题: {result['payload'].get('title', 'N/A')}")
        print(f"关键词: {result['payload'].get('keywords', [])}")
        content = result['payload'].get('content', '')
        print(f"内容预览: {content[:100]}...")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="LOL 知识库导入到 Qdrant")
    parser.add_argument(
        "file_path",
        help="知识库文件路径",
    )
    parser.add_argument(
        "--collection",
        default="knowledge_base",
        help="Qdrant 集合名称",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Qdrant 服务地址",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6333,
        help="Qdrant 服务端口",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="使用内存模式（用于测试）",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="清空现有数据",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="导入后运行搜索测试",
    )

    args = parser.parse_args()

    # 导入数据
    store = await store_lol_knowledge_to_qdrant(
        file_path=args.file_path,
        collection_name=args.collection,
        use_memory=args.memory,
        qdrant_host=args.host,
        qdrant_port=args.port,
        clear_existing=args.clear,
    )

    # 测试搜索
    if args.test and store:
        await test_search(store, "亚索怎么玩", doc_type="hero")
        await test_search(store, "无尽之刃", doc_type="item")


if __name__ == "__main__":
    asyncio.run(main())