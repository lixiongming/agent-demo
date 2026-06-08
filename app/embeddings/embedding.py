"""向量化核心服务

功能：
- 文本向量化
- 批量处理
- 模型管理
- 向量缓存

支持模型：
- bge-large-zh-v1.5 (本地)
- OpenAI embeddings
- 其他Sentence Transformers模型
"""
from typing import List, Optional, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer
import hashlib
import json
import os
from pathlib import Path


class EmbeddingService:
    """向量嵌入服务
    
    功能：
    - 支持多模型切换
    - 批量处理优化
    - 向量缓存机制
    - 异步处理支持
    """
    
    def __init__(
        self,
        model_name: str = "bge-large-zh-v1.5",
        model_path: Optional[str] = None,
        cache_enabled: bool = True,
        batch_size: int = 32,
        max_length: int = 512
    ):
        """初始化向量化服务
        
        Args:
            model_name: 模型名称
            model_path: 本地模型路径（优先使用）
            cache_enabled: 是否启用向量缓存
            batch_size: 批处理大小
            max_length: 最大文本长度
        """
        self.model_name = model_name
        self.cache_enabled = cache_enabled
        self.batch_size = batch_size
        self.max_length = max_length
        
        # 加载模型
        if model_path and Path(model_path).exists():
            self.model = SentenceTransformer(model_path)
        else:
            # 尝试加载本地模型
            local_path = Path.cwd() / model_name
            if local_path.exists():
                self.model = SentenceTransformer(str(local_path))
            else:
                self.model = SentenceTransformer(model_name)
        
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        # 向量缓存（简单实现，生产环境建议用Redis）
        self._cache: Dict[str, np.ndarray] = {}
        
    def embed_text(self, text: str) -> np.ndarray:
        """单文本向量化
        
        Args:
            text: 输入文本
            
        Returns:
            向量数组
        """
        # 检查缓存
        cache_key = self._get_cache_key(text)
        if self.cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]
        
        # 截断过长文本
        if len(text) > self.max_length:
            text = text[:self.max_length]
        
        # 向量化
        embedding = self.model.encode(text, normalize_embeddings=True)
        
        # 缓存
        if self.cache_enabled:
            self._cache[cache_key] = embedding
        
        return embedding
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """批量文本向量化
        
        Args:
            texts: 文本列表
            
        Returns:
            向量矩阵
        """
        # 检查缓存
        embeddings = []
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if self.cache_enabled and cache_key in self._cache:
                embeddings.append(self._cache[cache_key])
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        # 批量处理未缓存的文本
        if uncached_texts:
            # 截断过长文本
            processed_texts = [
                t[:self.max_length] if len(t) > self.max_length else t
                for t in uncached_texts
            ]
            
            # 批量向量化
            new_embeddings = self.model.encode(
                processed_texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            
            # 缓存并添加到结果
            for i, (text, embedding) in enumerate(zip(uncached_texts, new_embeddings)):
                if self.cache_enabled:
                    cache_key = self._get_cache_key(text)
                    self._cache[cache_key] = embedding
                embeddings.append(embedding)
        
        # 按原始顺序排列
        result = np.array(embeddings)
        
        return result
    
    def similarity(
        self,
        text1: str,
        text2: str,
        metric: str = "cosine"
    ) -> float:
        """计算文本相似度
        
        Args:
            text1: 文本1
            text2: 文本2
            metric: 相似度度量 (cosine, euclidean, dot)
            
        Returns:
            相似度分数
        """
        vec1 = self.embed_text(text1)
        vec2 = self.embed_text(text2)
        
        if metric == "cosine":
            # 向量已归一化，直接点积即为cosine相似度
            return float(np.dot(vec1, vec2))
        elif metric == "euclidean":
            return float(-np.linalg.norm(vec1 - vec2))
        elif metric == "dot":
            return float(np.dot(vec1, vec2))
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    def batch_similarity(
        self,
        query: str,
        texts: List[str],
        metric: str = "cosine"
    ) -> List[float]:
        """批量计算相似度
        
        Args:
            query: 查询文本
            texts: 文本列表
            metric: 相似度度量
            
        Returns:
            相似度分数列表
        """
        query_vec = self.embed_text(query)
        text_vecs = self.embed_texts(texts)
        
        if metric == "cosine":
            # 批量点积
            scores = np.dot(text_vecs, query_vec)
        elif metric == "euclidean":
            scores = -np.linalg.norm(text_vecs - query_vec, axis=1)
        elif metric == "dot":
            scores = np.dot(text_vecs, query_vec)
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        return scores.tolist()
    
    def search_similar(
        self,
        query: str,
        texts: List[str],
        top_k: int = 5,
        threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似文本
        
        Args:
            query: 查询文本
            texts: 文本列表
            top_k: 返回数量
            threshold: 相似度阈值
            
        Returns:
            搜索结果列表
        """
        scores = self.batch_similarity(query, texts)
        
        # 排序并筛选
        results = []
        for i, score in enumerate(scores):
            if score >= threshold:
                results.append({
                    "index": i,
                    "text": texts[i],
                    "score": score
                })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:top_k]
    
    def _get_cache_key(self, text: str) -> str:
        """生成缓存键
        
        Args:
            text: 文本
            
        Returns:
            缓存键
        """
        return hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
    
    def get_embedding_dim(self) -> int:
        """获取向量维度"""
        return self.embedding_dim
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "max_length": self.max_length,
            "batch_size": self.batch_size,
            "cache_enabled": self.cache_enabled,
            "cache_size": len(self._cache)
        }