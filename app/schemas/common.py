"""通用响应"""
from typing import Optional, Any
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """成功响应"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    message: str
    data: Optional[Any] = None


class PaginateResponse(BaseModel):
    """分页响应"""
    code: int = 200
    message: str = "success"
    data: dict
    
    class Config:
        arbitrary_types_allowed = True


def success(data: Any = None, message: str = "success") -> SuccessResponse:
    """创建成功响应"""
    return SuccessResponse(message=message, data=data)


def error(code: int = 400, message: str = "error", data: Any = None) -> ErrorResponse:
    """创建错误响应"""
    return ErrorResponse(code=code, message=message, data=data)


def paginate(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "success"
) -> PaginateResponse:
    """创建分页响应"""
    return PaginateResponse(
        message=message,
        data={
            "list": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": total > page * page_size
        }
    )