"""向量检索器

功能：
- 向量相似度检索
- Top-K过滤
- 重排序优化

注意：
- 混合检索（向量+关键词）需要专门的全文检索引擎（如Elasticsearch）
- 当前仅支持向量检索
"""
from typing import List, Dict, Any, Optional
import numpy as np
import re
from collections import defaultdict


class Retriever:
    """向量检索器
    
    功能：
    - 向量检索
    - 结果重排序
    - 性能优化
    """
    
    def __init__(
        self,
        embedding_service,
        vector_store,
        top_k: int = 5,
        threshold: float = 0.5,
        rerank_enabled: bool = True
    ):
        """初始化检索器
        
        Args:
            embedding_service: 向量化服务
            vector_store: 向量存储（Qdrant）
            top_k: 返回数量
            threshold: 相似度阈值
            rerank_enabled: 是否启用重排序
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.top_k = top_k
        self.threshold = threshold
        self.rerank_enabled = rerank_enabled
        
    async def retrieve(
        self,
        query: str,
        top_k: int = None,
        threshold: float = None,
        doc_type: Optional[str] = None,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """向量检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            threshold: 相似度阈值
            doc_type: 文档类型过滤
            filters: 其他过滤条件
            
        Returns:
            检索结果列表
        """
        top_k = top_k or self.top_k
        threshold = threshold or self.threshold
        
        # 查询向量化
        query_embedding = await self.embedding_service.embed_text(query)
        
        # 向量检索
        results = self.vector_store.search_by_similarity(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # 取更多结果用于重排序
            threshold=threshold,
            doc_type=doc_type
        )
        
        # 应用过滤条件
        if filters:
            results = self._apply_filters(results, filters)
        
        # 重排序
        if self.rerank_enabled and results:
            results = self._rerank(query, results)
        
        return results[:top_k]
    
    async def hybrid_retrieve(
        self,
        query: str,
        top_k: int = None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """混合检索（向量+关键词）
        
        注意：当前仅支持向量检索，关键词检索需要 Elasticsearch
        
        Args:
            query: 查询文本
            top_k: 返回数量
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重
            
        Returns:
            检索结果列表
        """
        # 当前仅使用向量检索
        # 生产环境建议集成 Elasticsearch 实现真正的混合检索
        return await self.retrieve(query, top_k=top_k)
    
    def _rerank(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """重排序
        
        Args:
            query: 查询文本
            results: 检索结果
            
        Returns:
            重排序后的结果
        """
        # 简单重排序策略：
        # 1. 相似度分数
        # 2. 内容长度（优先适中长度）
        # 3. 元数据质量
        
        for result in results:
            # 内容长度分数（适中长度优先）
            content_len = len(result.get("content", ""))
            length_score = 1.0 if 200 <= content_len <= 1000 else 0.8
            
            # 元数据分数
            metadata_score = 1.0 if result.get("metadata") else 0.9
            
            # 综合分数
            rerank_score = (
                result.get("score", 0) * 0.7 +
                length_score * 0.15 +
                metadata_score * 0.15
            )
            
            result["rerank_score"] = rerank_score
        
        # 按重排序分数排序
        results.sort(key=lambda x: x.get("rerank_score", x.get("score", 0)), reverse=True)
        
        return results
    
    def _apply_filters(
        self,
        results: List[Dict[str, Any]],
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """应用过滤条件
        
        Args:
            results: 检索结果
            filters: 过滤条件
            
        Returns:
            过滤后的结果
        """
        filtered = []
        
        for result in results:
            match = True
            
            # 检查每个过滤条件
            for key, value in filters.items():
                if key == "source":
                    if result.get("source") != value:
                        match = False
                elif key == "doc_type":
                    if result.get("doc_type") != value:
                        match = False
                elif key in result.get("metadata", {}):
                    if result["metadata"].get(key) != value:
                        match = False
            
            if match:
                filtered.append(result)
        
        return filtered
    
    def batch_retrieve(
        self,
        queries: List[str],
        top_k: int = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量检索
        
        Args:
            queries: 查询列表
            top_k: 返回数量
            
        Returns:
            查询结果字典
        """
        results = {}
        
        for query in queries:
            results[query] = self.retrieve(query, top_k=top_k)
        
        return results