"""RAG API接口

功能：
- 文档入库接口
- RAG查询接口
- 文档管理接口
- 统计信息接口

功能：
- RESTful API设计
- 统一响应格式
- 参数验证
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import os
import tempfile
import shutil

from app.schemas.common import SuccessResponse
from app.services.rag_service import RAGService
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# 全局RAG服务实例
rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取RAG服务实例"""
    global rag_service
    if rag_service is None:
        rag_service = RAGService()
    return rag_service


@router.post("/ingest/file", response_model=SuccessResponse)
async def ingest_file(
    file: UploadFile = File(...),
    metadata: str = Form(default="{}")
):
    """文档入库接口
    
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
        import json
        try:
            meta_dict = json.loads(metadata)
        except:
            meta_dict = {}
        
        # 入库
        result = await service.ingest_document(temp_file, metadata=meta_dict)
        
        return SuccessResponse(
            message="文档入库成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"文档入库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/ingest/text", response_model=SuccessResponse)
async def ingest_text(
    content: str,
    source: str = "",
    metadata: Dict[str, Any] = None
):
    """文本入库接口
    
    Args:
        content: 文本内容
        source: 来源标识
        metadata: 元数据
        
    Returns:
        入库结果
    """
    service = get_rag_service()
    
    try:
        doc_id = await service.ingest_text(
            content=content,
            source=source,
            metadata=metadata
        )
        
        return SuccessResponse(
            message="文本入库成功",
            data={"doc_id": doc_id}
        )
        
    except Exception as e:
        logger.error(f"文本入库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/directory", response_model=SuccessResponse)
async def ingest_directory(
    directory: str,
    file_types: List[str] = None,
    metadata: Dict[str, Any] = None
):
    """批量入库目录
    
    Args:
        directory: 目录路径
        file_types: 文件类型过滤
        metadata: 元数据
        
    Returns:
        入库结果
    """
    service = get_rag_service()
    
    try:
        result = await service.ingest_directory(
            directory=directory,
            file_types=file_types,
            metadata=metadata
        )
        
        return SuccessResponse(
            message="批量入库成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"批量入库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=SuccessResponse)
async def rag_query(
    question: str,
    top_k: int = 5,
    threshold: float = 0.5,
    doc_type: Optional[str] = None,
    hybrid: bool = False
):
    """RAG查询接口
    
    Args:
        question: 问题
        top_k: 检索数量
        threshold: 相似度阈值
        doc_type: 文档类型过滤
        hybrid: 是否使用混合检索
        
    Returns:
        查询结果
    """
    service = get_rag_service()
    
    try:
        result = await service.query(
            question=question,
            top_k=top_k,
            threshold=threshold,
            doc_type=doc_type,
            hybrid=hybrid
        )
        
        return SuccessResponse(
            message="查询成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/document/{doc_id}", response_model=SuccessResponse)
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


@router.delete("/source/{source}", response_model=SuccessResponse)
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


@router.get("/stats", response_model=SuccessResponse)
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


@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """健康检查
    
    Returns:
        健康状态
    """
    return SuccessResponse(
        message="RAG服务正常",
        data={"status": "healthy"}
    )