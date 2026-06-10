"""RAG API 请求模型

定义清晰的请求参数结构，FastAPI 会自动生成详细的 API 文档
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# ============================================
# 文档入库请求
# ============================================

class IngestTextRequest(BaseModel):
    """文本入库请求
    
    用于将纯文本内容入库到向量数据库
    """
    content: str = Field(
        ...,
        description="要入库的文本内容",
        example="这是一段关于人工智能的知识内容，包含重要信息..."
    )
    source: str = Field(
        default="",
        description="来源标识，用于追踪文档来源",
        example="manual_input"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="元数据，可包含作者、分类、标签等信息",
        example={"author": "张三", "category": "技术文档", "tags": ["AI", "机器学习"]}
    )


class IngestFileRequest(BaseModel):
    """文件入库请求（元数据部分）
    
    文件通过 multipart/form-data 上传，此模型仅定义元数据
    """
    metadata: str = Field(
        default="{}",
        description="元数据 JSON 字符串",
        example='{"category": "产品文档", "version": "v1.0"}'
    )


class IngestDirectoryRequest(BaseModel):
    """批量目录入库请求
    
    批量入库指定目录下的所有文档
    """
    directory: str = Field(
        ...,
        description="要扫描的目录路径",
        example="/data/documents"
    )
    file_types: Optional[List[str]] = Field(
        default=None,
        description="文件类型过滤，如 ['.pdf', '.txt', '.md']",
        example=[".pdf", ".txt", ".md", ".docx"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="全局元数据，会应用到所有文档",
        example={"project": "知识库建设", "batch_id": "20240101"}
    )


# ============================================
# RAG 查询请求
# ============================================

class RAGQueryRequest(BaseModel):
    """RAG 查询请求
    
    向量检索查询，返回相关文档
    """
    question: str = Field(
        ...,
        description="查询问题",
        example="什么是人工智能？"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="返回结果数量，范围 1-20",
        example=5
    )
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="相似度阈值，范围 0.0-1.0，越高越严格",
        example=0.5
    )
    doc_type: Optional[str] = Field(
        default=None,
        description="文档类型过滤，如 'pdf', 'txt', 'markdown'",
        example="pdf"
    )
    hybrid: bool = Field(
        default=False,
        description="是否使用混合检索（向量+关键词），提高召回率",
        example=False
    )


class RAGQueryWithFiltersRequest(RAGQueryRequest):
    """带过滤条件的 RAG 查询请求"""
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="额外过滤条件，如 {'source': 'file.pdf', 'author': '张三'}",
        example={"source": "knowledge.pdf", "category": "技术文档"}
    )


# ============================================
# 删除请求
# ============================================

class DeleteBySourceRequest(BaseModel):
    """按来源删除请求"""
    source: str = Field(
        ...,
        description="要删除的来源标识",
        example="old_document.pdf"
    )


# ============================================
# 响应模型
# ============================================

class DocumentSource(BaseModel):
    """文档来源信息"""
    id: int = Field(..., description="文档ID")
    content: str = Field(..., description="文档内容摘要")
    score: float = Field(..., description="相似度分数")
    source: str = Field(default="", description="来源标识")


class RAGQueryResponse(BaseModel):
    """RAG 查询响应"""
    question: str = Field(..., description="原始问题")
    answer: Optional[str] = Field(default=None, description="生成的回答（如果配置了LLM）")
    context: str = Field(default="", description="检索到的上下文")
    sources: List[DocumentSource] = Field(default_factory=list, description="来源文档列表")
    total_results: int = Field(..., description="检索结果总数")
    search_type: str = Field(..., description="检索类型：vector 或 hybrid")
    timestamp: str = Field(..., description="查询时间")


class IngestResponse(BaseModel):
    """入库响应"""
    status: str = Field(..., description="状态：success 或 failed")
    total_chunks: int = Field(default=0, description="入库的分块数量")
    stored_ids: List[int] = Field(default_factory=list, description="存储的文档ID列表")
    timestamp: str = Field(..., description="入库时间")