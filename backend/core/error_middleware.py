"""
统一错误处理中间件
为FastAPI应用提供统一的错误处理机制
"""

import logging
import traceback
import time
import asyncio
import functools
from typing import Union
from contextlib import contextmanager
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..utils.error_handler import AutoClipsException, ErrorCategory, ErrorLevel
from ..services.exceptions import ServiceError

logger = logging.getLogger(__name__)


class ErrorResponse:
    """统一错误响应格式"""
    
    def __init__(self, 
                 error_code: str,
                 message: str,
                 details: dict = None,
                 request_id: str = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.request_id = request_id
        self.timestamp = None
    
    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
                "request_id": self.request_id,
                "timestamp": self.timestamp
            }
        }


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: dict = None,
    request_id: str = None
) -> JSONResponse:
    """创建统一格式的错误响应"""
    response = ErrorResponse(error_code, message, details, request_id)
    response.timestamp = time.time()
    
    return JSONResponse(
        status_code=status_code,
        content=response.to_dict()
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器"""
    request_id = getattr(request.state, 'request_id', None)
    
    # 记录异常详情
    logger.error(
        f"未处理的异常: {type(exc).__name__}: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        }
    )
    
    # 根据异常类型返回不同的错误响应
    if isinstance(exc, AutoClipsException):
        return handle_autoclips_exception(exc, request_id)
    elif isinstance(exc, ServiceError):
        return handle_service_error(exc, request_id)
    elif isinstance(exc, HTTPException):
        return handle_http_exception(exc, request_id)
    elif isinstance(exc, RequestValidationError):
        return handle_validation_error(exc, request_id)
    elif isinstance(exc, StarletteHTTPException):
        return handle_starlette_http_exception(exc, request_id)
    else:
        return handle_generic_exception(exc, request_id)


def handle_autoclips_exception(exc: AutoClipsException, request_id: str = None) -> JSONResponse:
    """处理AutoClipsException"""
    status_code = get_status_code_for_category(exc.category)
    
    return create_error_response(
        status_code=status_code,
        error_code=f"AUTOCLIPS_{exc.category.value}",
        message=exc.message,
        details=exc.details,
        request_id=request_id
    )


def handle_service_error(exc: ServiceError, request_id: str = None) -> JSONResponse:
    """处理ServiceError"""
    status_code = get_status_code_for_service_error(exc.error_code)
    
    return create_error_response(
        status_code=status_code,
        error_code=exc.error_code.value,
        message=exc.message,
        details=exc.details,
        request_id=request_id
    )


def handle_http_exception(exc: HTTPException, request_id: str = None) -> JSONResponse:
    """处理HTTPException"""
    return create_error_response(
        status_code=exc.status_code,
        error_code=f"HTTP_{exc.status_code}",
        message=exc.detail,
        request_id=request_id
    )


def handle_validation_error(exc: RequestValidationError, request_id: str = None) -> JSONResponse:
    """处理请求验证错误"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return create_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="请求参数验证失败",
        details={"errors": errors},
        request_id=request_id
    )


def handle_starlette_http_exception(exc: StarletteHTTPException, request_id: str = None) -> JSONResponse:
    """处理StarletteHTTPException"""
    return create_error_response(
        status_code=exc.status_code,
        error_code=f"STARLETTE_{exc.status_code}",
        message=str(exc.detail),
        request_id=request_id
    )


def handle_generic_exception(exc: Exception, request_id: str = None) -> JSONResponse:
    """处理通用异常"""
    return create_error_response(
        status_code=500,
        error_code="INTERNAL_SERVER_ERROR",
        message="服务器内部错误",
        details={"exception_type": type(exc).__name__},
        request_id=request_id
    )


def get_status_code_for_category(category: ErrorCategory) -> int:
    """根据错误分类获取HTTP状态码"""
    status_mapping = {
        ErrorCategory.CONFIGURATION: 500,
        ErrorCategory.NETWORK: 503,
        ErrorCategory.API: 502,
        ErrorCategory.FILE_IO: 500,
        ErrorCategory.PROCESSING: 500,
        ErrorCategory.VALIDATION: 400,
        ErrorCategory.SYSTEM: 500
    }
    return status_mapping.get(category, 500)


def get_status_code_for_service_error(error_code) -> int:
    """根据服务错误代码获取HTTP状态码"""
    status_mapping = {
        "CONFIG_NOT_FOUND": 500,
        "CONFIG_INVALID": 500,
        "CONFIG_MISSING_REQUIRED": 500,
        "FILE_NOT_FOUND": 404,
        "FILE_PERMISSION_DENIED": 403,
        "FILE_CORRUPTED": 500,
        "PROCESSING_FAILED": 500,
        "STEP_EXECUTION_FAILED": 500,
        "PIPELINE_VALIDATION_FAILED": 400,
        "TASK_NOT_FOUND": 404,
        "TASK_ALREADY_RUNNING": 409,
        "TASK_CANCELLED": 410,
        "PROJECT_NOT_FOUND": 404,
        "PROJECT_ALREADY_EXISTS": 409,
        "SYSTEM_ERROR": 500,
        "NETWORK_ERROR": 503,
        "TIMEOUT_ERROR": 504,
        "CONCURRENT_ACCESS": 409,
        "LOCK_ACQUISITION_FAILED": 423,
        "UNKNOWN_ERROR": 500
    }
    return status_mapping.get(error_code.value, 500)


# 装饰器：自动错误处理
def handle_errors(error_category: ErrorCategory = ErrorCategory.SYSTEM):
    """错误处理装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except AutoClipsException:
                # 重新抛出AutoClipsException
                raise
            except ServiceError:
                # 重新抛出ServiceError
                raise
            except Exception as e:
                # 转换为AutoClipsException
                raise AutoClipsException(
                    message=str(e),
                    category=error_category,
                    original_exception=e
                )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AutoClipsException:
                # 重新抛出AutoClipsException
                raise
            except ServiceError:
                # 重新抛出ServiceError
                raise
            except Exception as e:
                # 转换为AutoClipsException
                raise AutoClipsException(
                    message=str(e),
                    category=error_category,
                    original_exception=e
                )
        
        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 上下文管理器：错误上下文
@contextmanager
def error_context(category: ErrorCategory, context_info: dict = None):
    """错误上下文管理器"""
    try:
        yield
    except Exception as e:
        if isinstance(e, AutoClipsException):
            # 已经是自定义异常，直接抛出
            raise
        else:
            # 转换为自定义异常
            details = context_info or {}
            details["original_exception_type"] = type(e).__name__
            
            raise AutoClipsException(
                message=str(e),
                category=category,
                details=details,
                original_exception=e
            )
