"""智谱 AI Embedding 服务

功能：
- 使用智谱 AI embedding-3 模型
- API 调用向量化
- 批量处理优化
- 向量缓存机制

优势：
- 无需本地模型文件
- 响应速度快
- 高质量中文向量
"""
from typing import List, Optional, Dict, Any
import numpy as np
import hashlib
import json
import httpx
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ZhipuEmbeddingService:
    """智谱 AI 向量嵌入服务
    
    功能：
    - 使用智谱 AI embedding-3 模型
    - API 调用向量化
    - 批量处理优化
    - 向量缓存机制
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "embedding-3",
        cache_enabled: bool = True,
        batch_size: int = 32
    ):
        """初始化智谱 AI 向量化服务
        
        Args:
            api_key: 智谱 AI API Key（默认从配置读取）
            model_name: 模型名称（embedding-3）
            cache_enabled: 是否启用向量缓存
            batch_size: 批处理大小
        """
        self.api_key = api_key or settings.ZHIPU_API_KEY
        self.model_name = model_name
        self.cache_enabled = cache_enabled
        self.batch_size = batch_size
        
        # 智谱 AI API 配置
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
        
        # Embedding-3 向量维度
        self.embedding_dim = 2048  # embedding-3 的实际维度
        
        # 向量缓存
        self._cache: Dict[str, np.ndarray] = {}
        
        # HTTP 客户端
        self.client = httpx.AsyncClient(timeout=30.0)
        
        logger.info(f"智谱 AI Embedding 服务初始化完成: model={model_name}, dim={self.embedding_dim}")
    
    async def embed_text(self, text: str) -> np.ndarray:
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
        
        # 调用智谱 AI API
        embedding = await self._call_api([text])
        
        # 缓存
        if self.cache_enabled:
            self._cache[cache_key] = embedding[0]
        
        return embedding[0]
    
    async def embed_texts(self, texts: List[str]) -> np.ndarray:
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
            # 分批调用 API（智谱 AI 支持批量）
            new_embeddings = await self._call_api(uncached_texts)
            
            # 缓存并添加到结果
            for i, (text, embedding) in enumerate(zip(uncached_texts, new_embeddings)):
                if self.cache_enabled:
                    cache_key = self._get_cache_key(text)
                    self._cache[cache_key] = embedding
                embeddings.append(embedding)
        
        # 按原始顺序排列
        result = np.array(embeddings)
        
        return result
    
    async def _call_api(self, texts: List[str]) -> List[np.ndarray]:
        """调用智谱 AI Embedding API
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        try:
            # 构建请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model_name,
                "input": texts
            }
            
            # 发送请求
            response = await self.client.post(
                self.api_url,
                headers=headers,
                json=data
            )
            
            # 检查响应
            if response.status_code != 200:
                error_msg = f"智谱 AI API 调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # 解析响应
            result = response.json()
            
            # 提取向量
            embeddings = []
            for item in result.get("data", []):
                embedding = item.get("embedding", [])
                embeddings.append(np.array(embedding))
            
            logger.info(f"智谱 AI Embedding 成功: {len(texts)} 个文本")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"智谱 AI Embedding 调用异常: {e}")
            raise
    
    def similarity(
        self,
        vec1: np.ndarray,
        vec2: np.ndarray,
        metric: str = "cosine"
    ) -> float:
        """计算向量相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            metric: 相似度度量 (cosine, euclidean, dot)
            
        Returns:
            相似度分数
        """
        if metric == "cosine":
            # 归一化后点积
            vec1_norm = vec1 / np.linalg.norm(vec1)
            vec2_norm = vec2 / np.linalg.norm(vec2)
            return float(np.dot(vec1_norm, vec2_norm))
        elif metric == "euclidean":
            return float(-np.linalg.norm(vec1 - vec2))
        elif metric == "dot":
            return float(np.dot(vec1, vec2))
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    async def batch_similarity(
        self,
        query_vec: np.ndarray,
        text_vecs: np.ndarray,
        metric: str = "cosine"
    ) -> List[float]:
        """批量计算相似度
        
        Args:
            query_vec: 查询向量
            text_vecs: 文本向量矩阵
            metric: 相似度度量
            
        Returns:
            相似度分数列表
        """
        if metric == "cosine":
            # 归一化
            query_norm = query_vec / np.linalg.norm(query_vec)
            text_norms = text_vecs / np.linalg.norm(text_vecs, axis=1, keepdims=True)
            # 批量点积
            scores = np.dot(text_norms, query_norm)
        elif metric == "euclidean":
            scores = -np.linalg.norm(text_vecs - query_vec, axis=1)
        elif metric == "dot":
            scores = np.dot(text_vecs, query_vec)
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        return scores.tolist()
    
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
        logger.info("Embedding 缓存已清空")
    
    def get_embedding_dim(self) -> int:
        """获取向量维度"""
        return self.embedding_dim
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "cache_enabled": self.cache_enabled,
            "cache_size": len(self._cache),
            "api_url": self.api_url
        }
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
        logger.info("智谱 AI Embedding 服务已关闭")