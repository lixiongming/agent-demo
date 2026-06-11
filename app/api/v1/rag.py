"""RAG API接口

功能：
- 文档入库接口
- RAG查询接口
- 文档管理接口
- 统计信息接口

API 文档：
- 所有接口都有清晰的请求参数定义
- 访问 http://localhost:8888/docs 查看 Swagger 文档
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Body
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import os
import tempfile
import shutil
import json

from app.schemas.common import SuccessResponse
from app.schemas.rag import (
    IngestTextRequest,
    IngestDirectoryRequest,
    RAGQueryRequest,
    RAGQueryWithFiltersRequest,
    RAGQueryResponse,
    DocumentSource
)
from app.services.rag import RAGService
from app.core.logger import get_logger
from app.core.container import DIContainer
from app.core.interfaces import IRAGService

logger = get_logger(__name__)
router = APIRouter()


def get_rag_service() -> RAGService:
    """获取RAG服务实例（容器单例）
    
    生产标准：
    - 使用容器获取单例
    - 只初始化一次
    - 后续请求直接获取
    """
    return DIContainer.get(IRAGService)


# ============================================
# 文档入库接口
# ============================================

@router.post(
    "/ingest/text",
    response_model=SuccessResponse,
    summary="文本入库",
    description="""
将纯文本内容入库到向量数据库。

**请求参数说明：**
- `content`: 必填，要入库的文本内容
- `source`: 可选，来源标识，用于追踪和管理文档
- `metadata`: 可选，元数据字典，可包含作者、分类、标签等

**使用示例：**
```json
{
    "content": "这是一段关于人工智能的知识内容...",
    "source": "manual_input",
    "metadata": {"author": "张三", "category": "技术文档"}
}
```
"""
)
async def ingest_text(request: IngestTextRequest = Body(...)):
    """文本入库接口
    
    Args:
        request: 入库请求参数
        
    Returns:
        入库结果，包含文档ID
    """
    service = get_rag_service()
    
    try:
        doc_id = await service.ingest_text(
            content=request.content,
            source=request.source,
            metadata=request.metadata
        )
        
        return SuccessResponse(
            message="文本入库成功",
            data={
                "doc_id": doc_id,
                "content_length": len(request.content),
                "source": request.source
            }
        )
        
    except Exception as e:
        logger.error(f"文本入库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/ingest/file",
    response_model=SuccessResponse,
    summary="文件入库",
    description="""
上传文件并入库到向量数据库。

**支持的文件类型：**
- PDF (.pdf)
- Word (.doc, .docx)
- 文本 (.txt)
- Markdown (.md)

**请求方式：**
- 使用 multipart/form-data 上传文件
- metadata 参数为 JSON 字符串

**使用示例（curl）：**
```bash
curl -X POST "http://localhost:8888/api/v1/rag/ingest/file" \
  -F "file=@document.pdf" \
  -F 'metadata={"category": "技术文档"}'
```
"""
)
async def ingest_file(
    file: UploadFile = File(..., description="要上传的文件"),
    metadata: str = Form(default="{}", description="元数据 JSON 字符串")
):
    """文件入库接口
    
    Args:
        file: 上传的文件
        metadata: 元数据JSON字符串
        
    Returns:
        入库结果
    """
    service = get_rag_service()
    
    # 保存临时文件
    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, file.filename)
    
    try:
        # 写入文件
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 解析元数据
        try:
            meta_dict = json.loads(metadata)
        except json.JSONDecodeError:
            meta_dict = {}
        
        # 入库
        result = await service.ingest_document(temp_file, metadata=meta_dict)
        
        return SuccessResponse(
            message="文件入库成功",
            data={
                "file_name": file.filename,
                "total_chunks": result["total_chunks"],
                "stored_ids": result["stored_ids"]
            }
        )
        
    except Exception as e:
        logger.error(f"文件入库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post(
    "/ingest/directory",
    response_model=SuccessResponse,
    summary="批量目录入库",
    description="""
批量入库指定目录下的所有文档。

**请求参数说明：**
- `directory`: 必填，要扫描的目录路径
- `file_types`: 可选，文件类型过滤列表
- `metadata`: 可选，全局元数据，应用到所有文档

**使用示例：**
```json
{
    "directory": "/data/documents",
    "file_types": [".pdf", ".txt", ".md"],
    "metadata": {"project": "知识库建设"}
}
```
"""
)
async def ingest_directory(request: IngestDirectoryRequest = Body(...)):
    """批量入库目录
    
    Args:
        request: 目录入库请求参数
        
    Returns:
        入库结果
    """
    service = get_rag_service()
    
    try:
        result = await service.ingest_directory(
            directory=request.directory,
            file_types=request.file_types,
            metadata=request.metadata
        )
        
        return SuccessResponse(
            message="批量入库成功",
            data={
                "directory": request.directory,
                "total_chunks": result["total_chunks"],
                "stored_ids": result["stored_ids"],
                "status": result["status"]
            }
        )
        
    except Exception as e:
        logger.error(f"批量入库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# RAG 查询接口
# ============================================

@router.post(
    "/query",
    response_model=SuccessResponse,
    summary="RAG 查询",
    description="""
向量检索查询，返回与问题相关的文档。

**请求参数说明：**
- `question`: 必填，查询问题
- `top_k`: 返回结果数量（默认5，范围1-20）
- `threshold`: 相似度阈值（默认0.5，范围0.0-1.0）
- `doc_type`: 文档类型过滤（可选）
- `hybrid`: 是否使用混合检索（默认False）

**检索模式：**
- **向量检索**（hybrid=False）：基于语义相似度
- **混合检索**（hybrid=True）：向量+关键词，提高召回率

**使用示例：**
```json
{
    "question": "什么是人工智能？",
    "top_k": 5,
    "threshold": 0.5,
    "hybrid": false
}
```
"""
)
async def rag_query(request: RAGQueryRequest = Body(...)):
    """RAG查询接口
    
    Args:
        request: 查询请求参数
        
    Returns:
        查询结果，包含相关文档和上下文
    """
    service = get_rag_service()
    
    try:
        result = await service.query(
            question=request.question,
            top_k=request.top_k,
            threshold=request.threshold,
            doc_type=request.doc_type,
            hybrid=request.hybrid
        )
        
        return SuccessResponse(
            message="查询成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/query/advanced",
    response_model=SuccessResponse,
    summary="高级 RAG 查询",
    description="""
带过滤条件的高级向量检索查询。

**额外过滤条件：**
- `filters`: 元数据过滤条件，如 {"source": "file.pdf", "author": "张三"}

**使用示例：**
```json
{
    "question": "什么是人工智能？",
    "top_k": 5,
    "filters": {"category": "技术文档", "author": "张三"}
}
```
"""
)
async def rag_query_advanced(request: RAGQueryWithFiltersRequest = Body(...)):
    """高级RAG查询接口
    
    Args:
        request: 高级查询请求参数
        
    Returns:
        查询结果
    """
    service = get_rag_service()
    
    try:
        result = await service.query(
            question=request.question,
            top_k=request.top_k,
            threshold=request.threshold,
            doc_type=request.doc_type,
            filters=request.filters,
            hybrid=request.hybrid
        )
        
        return SuccessResponse(
            message="查询成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 文档管理接口
# ============================================

@router.delete(
    "/document/{doc_id}",
    response_model=SuccessResponse,
    summary="删除单个文档",
    description="""
根据文档ID删除单个文档。

**参数说明：**
- `doc_id`: 文档ID（路径参数）
"""
)
async def delete_document(doc_id: int):
    """删除文档
    
    Args:
        doc_id: 文档ID
        
    Returns:
        删除结果
    """
    service = get_rag_service()
    
    try:
        success = await service.delete_document(doc_id)
        
        if success:
            return SuccessResponse(
                message="删除成功",
                data={"doc_id": doc_id}
            )
        else:
            raise HTTPException(status_code=404, detail="文档不存在")
            
    except Exception as e:
        logger.error(f"删除失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/source/{source}",
    response_model=SuccessResponse,
    summary="按来源批量删除",
    description="""
根据来源标识批量删除所有相关文档。

**参数说明：**
- `source`: 来源标识（路径参数）

**使用示例：**
删除来源为 "old_document.pdf" 的所有文档：
```
DELETE /api/v1/rag/source/old_document.pdf
```
"""
)
async def delete_by_source(source: str):
    """按来源删除文档
    
    Args:
        source: 来源标识
        
    Returns:
        删除结果
    """
    service = get_rag_service()
    
    try:
        count = await service.delete_by_source(source)
        
        return SuccessResponse(
            message=f"删除了 {count} 个文档",
            data={"source": source, "deleted_count": count}
        )
        
    except Exception as e:
        logger.error(f"删除失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 统计与健康检查
# ============================================

@router.get(
    "/stats",
    response_model=SuccessResponse,
    summary="获取统计信息",
    description="""
获取向量存储和嵌入模型的统计信息。

**返回信息：**
- 向量存储：文档总数、缓存大小
- 嵌入模型：模型名称、向量维度
- 检索器：top_k、阈值配置
"""
)
async def get_stats():
    """获取统计信息
    
    Returns:
        统计信息
    """
    service = get_rag_service()
    
    try:
        stats = service.get_stats()
        
        return SuccessResponse(
            message="获取成功",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health",
    response_model=SuccessResponse,
    summary="健康检查",
    description="检查 RAG 服务是否正常运行"
)
async def health_check():
    """健康检查
    
    Returns:
        健康状态
    """
    return SuccessResponse(
        message="RAG服务正常",
        data={
            "status": "healthy",
            "service": "rag",
            "embedding_model": "智谱 AI embedding-3"
        }
    )