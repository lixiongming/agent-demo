"""Rerank 服务 - 智谱 AI 实现

功能：
- 使用智谱 AI Rerank API 对检索结果重排序
- 提高检索精度
- 支持 Cross-Encoder 模型

使用示例：
    from app.services.rerank import RerankService
    
    reranker = RerankService()
    result = await reranker.rerank(
        query="产品价格",
        documents=["文档1内容", "文档2内容", ...],
        top_k=5
    )
"""

from typing import List, Dict, Any, Optional
import httpx
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RerankService:
    """Rerank 服务 - 智谱 AI 实现
    
    使用 Cross-Encoder 模型对检索结果进行重排序，
    提高检索精度。
    
    智谱 AI Rerank API：
    - 模型：bge-reranker-v2-m3（推荐）
    - 支持中英文
    - 高精度
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "bge-reranker-v2-m3"
    ):
        """初始化 Rerank 服务
        
        Args:
            api_key: 智谱 AI API Key（默认从配置读取）
            model_name: Rerank 模型名称
        """
        self.api_key = api_key or settings.ZHIPU_API_KEY
        self.model_name = model_name
        
        # 智谱 AI Rerank API
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/rerank"
        
        # HTTP 客户端
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # 统计
        self.stats = {
            "total_requests": 0,
            "total_documents": 0,
            "total_latency_ms": 0
        }
        
        logger.info(f"Rerank 服务初始化完成: model={model_name}")
    
    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5,
        return_documents: bool = True
    ) -> List[Dict[str, Any]]:
        """对文档进行重排序
        
        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前 K 个结果
            return_documents: 是否返回文档内容
            
        Returns:
            [
                {
                    "index": 0,  # 原文档索引
                    "relevance_score": 0.95,  # 相关性分数
                    "document": "文档内容"  # 可选
                },
                ...
            ]
        """
        import time
        start_time = time.time()
        
        if not documents:
            return []
        
        try:
            # 构建请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model_name,
                "query": query,
                "documents": documents,
                "top_n": min(top_k, len(documents)),
                "return_documents": return_documents
            }
            
            # 发送请求
            response = await self.client.post(
                self.api_url,
                headers=headers,
                json=data
            )
            
            # 检查响应
            if response.status_code != 200:
                error_msg = f"Rerank API 调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                # 降级：返回原始顺序
                return self._fallback_results(documents, top_k)
            
            # 解析响应
            result = response.json()
            
            # 提取结果
            results = []
            for item in result.get("results", []):
                results.append({
                    "index": item.get("index", 0),
                    "relevance_score": item.get("relevance_score", 0.0),
                    "document": item.get("document", "") if return_documents else None
                })
            
            # 更新统计
            latency_ms = int((time.time() - start_time) * 1000)
            self.stats["total_requests"] += 1
            self.stats["total_documents"] += len(documents)
            self.stats["total_latency_ms"] += latency_ms
            
            logger.info(
                f"Rerank 完成: query={query[:20]}..., "
                f"docs={len(documents)}, top_k={top_k}, latency={latency_ms}ms"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Rerank 调用异常: {e}")
            # 降级：返回原始顺序
            return self._fallback_results(documents, top_k)
    
    def _fallback_results(
        self,
        documents: List[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """降级策略：返回原始顺序
        
        当 Rerank API 失败时，按原始顺序返回文档
        """
        logger.warning("Rerank 降级：返回原始顺序")
        results = []
        for i, doc in enumerate(documents[:top_k]):
            results.append({
                "index": i,
                "relevance_score": 0.5,  # 默认分数
                "document": doc
            })
        return results
    
    async def rerank_with_metadata(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        content_key: str = "content",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """对带元数据的文档进行重排序
        
        Args:
            query: 查询文本
            documents: 文档列表（带元数据）
            content_key: 文档内容字段名
            top_k: 返回前 K 个结果
            
        Returns:
            重排序后的文档列表（保留原始元数据）
        """
        if not documents:
            return []
        
        # 提取文档内容
        contents = [doc.get(content_key, "") for doc in documents]
        
        # 调用 Rerank
        rerank_results = await self.rerank(query, contents, top_k)
        
        # 合并结果
        results = []
        for item in rerank_results:
            idx = item["index"]
            if idx < len(documents):
                # 复制原始文档并添加 Rerank 分数
                doc = documents[idx].copy()
                doc["rerank_score"] = item["relevance_score"]
                results.append(doc)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_latency = (
            self.stats["total_latency_ms"] / self.stats["total_requests"]
            if self.stats["total_requests"] > 0
            else 0
        )
        
        return {
            "total_requests": self.stats["total_requests"],
            "total_documents": self.stats["total_documents"],
            "avg_latency_ms": round(avg_latency, 2),
            "model": self.model_name
        }
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
        logger.info("Rerank 服务已关闭")


# 全局单例（线程安全）
_rerank_service: Optional[RerankService] = None
_lock = __import__('threading').Lock()


def get_rerank_service() -> RerankService:
    """获取 Rerank 服务单例（线程安全）"""
    global _rerank_service
    if _rerank_service is None:
        with _lock:
            if _rerank_service is None:
                _rerank_service = RerankService()
    return _rerank_service


async def shutdown_rerank_service():
    """关闭 Rerank 服务（应用关闭时调用）"""
    global _rerank_service
    with _lock:
        service = _rerank_service
        if service is None:
            return
        _rerank_service = None
    
    await service.close()
    logger.info("Rerank 服务已关闭")


async def rerank_documents(
    query: str,
    documents: List[str],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """快捷函数：对文档进行重排序"""
    service = get_rerank_service()
    return await service.rerank(query, documents, top_k)
