"""向量检索器

功能：
- 向量相似度检索
- 混合检索（向量+关键词）
- Top-K过滤
- 重排序优化

功能：
- 多种检索策略
- 结果优化
- 性能优化
"""
from typing import List, Dict, Any, Optional
import numpy as np
import re
from collections import defaultdict


class Retriever:
    """向量检索器
    
    功能：
    - 多种检索策略
    - 混合检索
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
            vector_store: 向量存储
            top_k: 返回数量
            threshold: 相似度阈值
            rerank_enabled: 是否启用重排序
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.top_k = top_k
        self.threshold = threshold
        self.rerank_enabled = rerank_enabled
        
    def retrieve(
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
        query_embedding = self.embedding_service.embed_text(query)
        
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
    
    def hybrid_retrieve(
        self,
        query: str,
        top_k: int = None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """混合检索（向量+关键词）
        
        Args:
            query: 查询文本
            top_k: 返回数量
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重
            
        Returns:
            检索结果列表
        """
        top_k = top_k or self.top_k
        
        # 1. 向量检索
        vector_results = self.retrieve(query, top_k=top_k * 2)
        
        # 2. 关键词检索
        keyword_results = self._keyword_search(query, top_k=top_k * 2)
        
        # 3. 合并结果
        merged_results = self._merge_results(
            vector_results,
            keyword_results,
            vector_weight,
            keyword_weight
        )
        
        # 4. 重排序
        if self.rerank_enabled:
            merged_results = self._rerank(query, merged_results)
        
        return merged_results[:top_k]
    
    def _keyword_search(
        self,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """关键词检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            检索结果列表
        """
        # 提取关键词
        keywords = self._extract_keywords(query)
        
        # 从向量存储获取所有文档
        # 注意：生产环境应使用专门的全文检索引擎（如Elasticsearch）
        session = self.vector_store.Session()
        
        try:
            from sqlalchemy import or_
            from .vector_store import VectorDocumentModel
            
            # 构建查询条件
            conditions = []
            for keyword in keywords:
                conditions.append(VectorDocumentModel.content.like(f"%{keyword}%"))
            
            # 执行查询
            docs = session.query(VectorDocumentModel).filter(or_(*conditions)).limit(top_k * 2).all()
            
            # 计算关键词匹配分数
            results = []
            for doc in docs:
                score = self._calculate_keyword_score(doc.content, keywords)
                results.append({
                    "id": doc.id,
                    "content": doc.content,
                    "score": score,
                    "metadata": doc.metadata,
                    "source": doc.source,
                    "doc_type": doc.doc_type,
                    "search_type": "keyword"
                })
            
            # 排序
            results.sort(key=lambda x: x["score"], reverse=True)
            
            return results[:top_k]
            
        finally:
            session.close()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词
        
        Args:
            text: 文本
            
        Returns:
            关键词列表
        """
        # 简单实现：提取中文词汇和英文单词
        # 生产环境建议使用jieba分词或其他NLP工具
        
        # 移除标点符号
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 分割
        words = text.split()
        
        # 过滤短词
        keywords = [w for w in words if len(w) >= 2]
        
        return keywords
    
    def _calculate_keyword_score(
        self,
        content: str,
        keywords: List[str]
    ) -> float:
        """计算关键词匹配分数
        
        Args:
            content: 文档内容
            keywords: 关键词列表
            
        Returns:
            分数
        """
        if not keywords:
            return 0.0
        
        # 计算匹配的关键词数量
        matched = sum(1 for kw in keywords if kw.lower() in content.lower())
        
        # 分数 = 匹配数 / 总关键词数
        score = matched / len(keywords)
        
        return score
    
    def _merge_results(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        vector_weight: float,
        keyword_weight: float
    ) -> List[Dict[str, Any]]:
        """合并检索结果
        
        Args:
            vector_results: 向量检索结果
            keyword_results: 关键词检索结果
            vector_weight: 向量权重
            keyword_weight: 关键词权重
            
        Returns:
            合并后的结果
        """
        # 按ID聚合
        merged = defaultdict(dict)
        
        for result in vector_results:
            doc_id = result["id"]
            merged[doc_id]["vector_score"] = result["score"]
            merged[doc_id]["content"] = result["content"]
            merged[doc_id]["metadata"] = result["metadata"]
            merged[doc_id]["source"] = result["source"]
            merged[doc_id]["doc_type"] = result["doc_type"]
        
        for result in keyword_results:
            doc_id = result["id"]
            merged[doc_id]["keyword_score"] = result["score"]
            if "content" not in merged[doc_id]:
                merged[doc_id]["content"] = result["content"]
                merged[doc_id]["metadata"] = result["metadata"]
                merged[doc_id]["source"] = result["source"]
                merged[doc_id]["doc_type"] = result["doc_type"]
        
        # 计算加权分数
        results = []
        for doc_id, data in merged.items():
            vector_score = data.get("vector_score", 0.0)
            keyword_score = data.get("keyword_score", 0.0)
            
            # 加权计算
            final_score = vector_score * vector_weight + keyword_score * keyword_weight
            
            results.append({
                "id": doc_id,
                "content": data["content"],
                "score": final_score,
                "vector_score": vector_score,
                "keyword_score": keyword_score,
                "metadata": data["metadata"],
                "source": data["source"],
                "doc_type": data["doc_type"],
                "search_type": "hybrid"
            })
        
        # 排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results
    
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
            content_len = len(result["content"])
            length_score = 1.0 if 200 <= content_len <= 1000 else 0.8
            
            # 元数据分数
            metadata_score = 1.0 if result.get("metadata") else 0.9
            
            # 综合分数
            rerank_score = (
                result["score"] * 0.7 +
                length_score * 0.15 +
                metadata_score * 0.15
            )
            
            result["rerank_score"] = rerank_score
        
        # 按重排序分数排序
        results.sort(key=lambda x: x.get("rerank_score", x["score"]), reverse=True)
        
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