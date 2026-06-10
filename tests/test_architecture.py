"""架构测试示例

测试依赖注入和接口抽象
"""
import pytest
import numpy as np
from typing import List, Dict, Any, Optional

from app.core.interfaces import IVectorStore, IEmbeddingService
from app.core.container import DIContainer


# ============================================
# Mock 实现用于测试
# ============================================

class MockVectorStore(IVectorStore):
    """测试用的 Mock 向量存储"""
    
    def __init__(self):
        self._documents = {}
        self._next_id = 1
    
    async def add_document(
        self,
        content: str,
        embedding: np.ndarray,
        metadata: Dict[str, Any] = None,
        source: str = "",
        doc_type: str = "text"
    ) -> int:
        doc_id = self._next_id
        self._documents[doc_id] = {
            "id": doc_id,
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
            "source": source,
            "doc_type": doc_type
        }
        self._next_id += 1
        return doc_id
    
    async def add_documents_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[int]:
        doc_ids = []
        for doc in documents:
            doc_id = await self.add_document(
                doc["content"],
                doc["embedding"],
                doc.get("metadata"),
                doc.get("source", ""),
                doc.get("doc_type", "text")
            )
            doc_ids.append(doc_id)
        return doc_ids
    
    async def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        threshold: float = 0.0,
        doc_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = []
        for doc in self._documents.values():
            if doc_type and doc["doc_type"] != doc_type:
                continue
            
            # 计算相似度
            similarity = float(np.dot(query_embedding, doc["embedding"]))
            
            if similarity >= threshold:
                results.append({
                    "id": doc["id"],
                    "content": doc["content"],
                    "score": similarity,
                    "source": doc["source"]
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    async def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        return self._documents.get(doc_id)
    
    async def delete_document(self, doc_id: int) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False
    
    async def delete_by_source(self, source: str) -> int:
        count = 0
        for doc_id, doc in list(self._documents.items()):
            if doc["source"] == source:
                del self._documents[doc_id]
                count += 1
        return count
    
    async def get_stats(self) -> Dict[str, Any]:
        return {
            "total_count": len(self._documents),
            "is_mock": True
        }


class MockEmbeddingService(IEmbeddingService):
    """测试用的 Mock 向量嵌入服务"""
    
    def embed_text(self, text: str) -> np.ndarray:
        # 返回固定向量（测试用）
        return np.random.rand(1024).astype(np.float32)
    
    def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        return [self.embed_text(t) for t in texts]
    
    def get_model_info(self) -> Dict[str, Any]:
        return {"model": "mock", "dimension": 1024}


# ============================================
# 测试用例
# ============================================

@pytest.fixture(autouse=True)
def clear_container():
    """每个测试前清除容器"""
    DIContainer.clear()
    yield
    DIContainer.clear()


class TestDIContainer:
    """测试依赖注入容器"""
    
    def test_bind_and_get(self):
        """测试绑定和获取"""
        DIContainer.bind(IVectorStore, MockVectorStore)
        
        store = DIContainer.get(IVectorStore)
        
        assert store is not None
        assert isinstance(store, MockVectorStore)
    
    def test_singleton(self):
        """测试单例"""
        DIContainer.bind(IVectorStore, MockVectorStore)
        
        store1 = DIContainer.get(IVectorStore)
        store2 = DIContainer.get(IVectorStore)
        
        # 应该是同一个实例
        assert store1 is store2
    
    def test_replace_binding(self):
        """测试替换绑定"""
        DIContainer.bind(IVectorStore, MockVectorStore)
        store1 = DIContainer.get(IVectorStore)
        
        # 替换绑定
        class AnotherMock(IVectorStore):
            async def add_document(self, *args): return 999
        
        DIContainer.clear_services()
        DIContainer.bind(IVectorStore, AnotherMock)
        store2 = DIContainer.get(IVectorStore)
        
        assert store1 is not store2
        assert isinstance(store2, AnotherMock)


class TestRAGServiceV2:
    """测试 RAG 服务"""
    
    @pytest.mark.asyncio
    async def test_query_with_mock(self):
        """测试使用 Mock 的查询"""
        # 配置 Mock
        DIContainer.bind(IVectorStore, MockVectorStore)
        DIContainer.bind(IEmbeddingService, MockEmbeddingService)
        
        from app.services.rag_service_v2 import RAGServiceV2
        
        service = RAGServiceV2()
        
        # 添加测试文档
        embedding = np.random.rand(1024).astype(np.float32)
        doc_id = await service.vector_store.add_document(
            content="测试内容",
            embedding=embedding,
            source="test"
        )
        
        assert doc_id == 1
        
        # 查询
        result = await service.query("测试问题", top_k=5)
        
        assert result["question"] == "测试问题"
        assert "sources" in result


class TestAsyncVectorStore:
    """测试异步向量存储"""
    
    @pytest.mark.asyncio
    async def test_add_and_search(self):
        """测试添加和检索"""
        store = MockVectorStore()
        
        # 添加文档
        embedding1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        embedding2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        
        doc_id1 = await store.add_document(
            content="文档1",
            embedding=embedding1,
            source="test"
        )
        
        doc_id2 = await store.add_document(
            content="文档2",
            embedding=embedding2,
            source="test"
        )
        
        # 检索
        query = np.array([0.9, 0.1, 0.0], dtype=np.float32)
        results = await store.search(query, top_k=2)
        
        assert len(results) == 2
        # 第一个文档应该更相似
        assert results[0]["id"] == doc_id1


# ============================================
# 运行测试
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])