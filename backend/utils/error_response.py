"""
统一错误响应格式
提供标准化的错误响应结构和用户友好的错误消息
"""

from typing import Any, Dict, Optional, Union
from enum import Enum
from datetime import datetime
import traceback
import uuid
from fastapi import HTTPException
from fastapi.responses import JSONResponse


class ErrorCode(Enum):
    """错误代码枚举"""
    # 通用错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    
    # 请求错误
    INVALID_REQUEST = "INVALID_REQUEST"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    
    # 认证授权错误
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    
    # 资源错误
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    
    # 业务逻辑错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # 外部服务错误
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    
    # 文件处理错误
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_FORMAT = "UNSUPPORTED_FILE_FORMAT"
    FILE_PROCESSING_ERROR = "FILE_PROCESSING_ERROR"


class ErrorLevel(Enum):
    """错误级别枚举"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorResponse:
    """统一错误响应类"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        user_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        level: ErrorLevel = ErrorLevel.ERROR,
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        self.error_code = error_code
        self.message = message
        self.user_message = user_message or self._get_user_friendly_message(error_code, message)
        self.details = details or {}
        self.level = level
        self.request_id = request_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.utcnow()
    
    def _get_user_friendly_message(self, error_code: ErrorCode, message: str) -> str:
        """获取用户友好的错误消息"""
        friendly_messages = {
            ErrorCode.UNKNOWN_ERROR: "发生了未知错误，请稍后重试",
            ErrorCode.INTERNAL_SERVER_ERROR: "服务器内部错误，请稍后重试",
            ErrorCode.SERVICE_UNAVAILABLE: "服务暂时不可用，请稍后重试",
            
            ErrorCode.INVALID_REQUEST: "请求格式不正确，请检查后重试",
            ErrorCode.MISSING_PARAMETER: "缺少必要参数，请检查请求",
            ErrorCode.INVALID_PARAMETER: "参数格式不正确，请检查后重试",
            ErrorCode.REQUEST_TOO_LARGE: "请求内容过大，请减少数据量后重试",
            ErrorCode.UNSUPPORTED_MEDIA_TYPE: "不支持的文件格式，请选择支持的文件类型",
            
            ErrorCode.UNAUTHORIZED: "未授权访问，请先登录",
            ErrorCode.FORBIDDEN: "权限不足，无法执行此操作",
            ErrorCode.TOKEN_EXPIRED: "登录已过期，请重新登录",
            ErrorCode.INVALID_CREDENTIALS: "认证信息无效，请检查后重试",
            
            ErrorCode.RESOURCE_NOT_FOUND: "请求的资源不存在",
            ErrorCode.RESOURCE_ALREADY_EXISTS: "资源已存在，请使用其他名称",
            ErrorCode.RESOURCE_CONFLICT: "资源冲突，请检查后重试",
            
            ErrorCode.VALIDATION_ERROR: "数据验证失败，请检查输入内容",
            ErrorCode.PROCESSING_ERROR: "处理过程中发生错误，请重试",
            ErrorCode.QUOTA_EXCEEDED: "超出使用限制，请稍后重试",
            ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后再试",
            
            ErrorCode.EXTERNAL_API_ERROR: "外部服务暂时不可用，请稍后重试",
            ErrorCode.NETWORK_ERROR: "网络连接失败，请检查网络连接",
            ErrorCode.TIMEOUT_ERROR: "请求超时，请重试",
            
            ErrorCode.FILE_NOT_FOUND: "文件不存在，请检查文件路径",
            ErrorCode.FILE_TOO_LARGE: "文件过大，请选择较小的文件",
            ErrorCode.UNSUPPORTED_FILE_FORMAT: "不支持的文件格式，请选择支持的文件类型",
            ErrorCode.FILE_PROCESSING_ERROR: "文件处理失败，请检查文件内容",
        }
        
        return friendly_messages.get(error_code, message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "user_message": self.user_message,
                "level": self.level.value,
                "request_id": self.request_id,
                "timestamp": self.timestamp.isoformat(),
                "details": self.details
            }
        }
    
    def to_json_response(self, status_code: int = 500) -> JSONResponse:
        """转换为JSON响应"""
        return JSONResponse(
            status_code=status_code,
            content=self.to_dict()
        )


def get_http_status_code(error_code: ErrorCode) -> int:
    """根据错误代码获取HTTP状态码"""
    status_mapping = {
        # 4xx 客户端错误
        ErrorCode.INVALID_REQUEST: 400,
        ErrorCode.MISSING_PARAMETER: 400,
        ErrorCode.INVALID_PARAMETER: 400,
        ErrorCode.REQUEST_TOO_LARGE: 413,
        ErrorCode.UNSUPPORTED_MEDIA_TYPE: 415,
        ErrorCode.UNAUTHORIZED: 401,
        ErrorCode.FORBIDDEN: 403,
        ErrorCode.TOKEN_EXPIRED: 401,
        ErrorCode.INVALID_CREDENTIALS: 401,
        ErrorCode.RESOURCE_NOT_FOUND: 404,
        ErrorCode.RESOURCE_ALREADY_EXISTS: 409,
        ErrorCode.RESOURCE_CONFLICT: 409,
        ErrorCode.VALIDATION_ERROR: 422,
        ErrorCode.QUOTA_EXCEEDED: 429,
        ErrorCode.RATE_LIMIT_EXCEEDED: 429,
        ErrorCode.FILE_NOT_FOUND: 404,
        ErrorCode.FILE_TOO_LARGE: 413,
        ErrorCode.UNSUPPORTED_FILE_FORMAT: 415,
        
        # 5xx 服务器错误
        ErrorCode.INTERNAL_SERVER_ERROR: 500,
        ErrorCode.SERVICE_UNAVAILABLE: 503,
        ErrorCode.EXTERNAL_API_ERROR: 502,
        ErrorCode.NETWORK_ERROR: 502,
        ErrorCode.TIMEOUT_ERROR: 504,
        ErrorCode.PROCESSING_ERROR: 500,
        ErrorCode.FILE_PROCESSING_ERROR: 500,
        ErrorCode.UNKNOWN_ERROR: 500,
    }
    
    return status_mapping.get(error_code, 500)


def create_error_response(
    error_code: ErrorCode,
    message: str,
    user_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    level: ErrorLevel = ErrorLevel.ERROR,
    request_id: Optional[str] = None
) -> JSONResponse:
    """创建标准错误响应"""
    error_response = ErrorResponse(
        error_code=error_code,
        message=message,
        user_message=user_message,
        details=details,
        level=level,
        request_id=request_id
    )
    
    status_code = get_http_status_code(error_code)
    return error_response.to_json_response(status_code)


def create_validation_error_response(
    errors: list,
    request_id: Optional[str] = None
) -> JSONResponse:
    """创建验证错误响应"""
    error_details = []
    for error in errors:
        if hasattr(error, 'loc') and hasattr(error, 'msg'):
            error_details.append({
                "field": ".".join(str(loc) for loc in error.loc),
                "message": error.msg,
                "type": error.type if hasattr(error, 'type') else "validation_error"
            })
        else:
            error_details.append({
                "message": str(error),
                "type": "validation_error"
            })
    
    return create_error_response(
        error_code=ErrorCode.VALIDATION_ERROR,
        message="数据验证失败",
        details={"validation_errors": error_details},
        request_id=request_id
    )


def create_exception_error_response(
    exception: Exception,
    request_id: Optional[str] = None,
    context: Optional[str] = None
) -> JSONResponse:
    """从异常创建错误响应"""
    # 根据异常类型确定错误代码
    if isinstance(exception, FileNotFoundError):
        error_code = ErrorCode.FILE_NOT_FOUND
    elif isinstance(exception, PermissionError):
        error_code = ErrorCode.FORBIDDEN
    elif isinstance(exception, ValueError):
        error_code = ErrorCode.INVALID_PARAMETER
    elif isinstance(exception, TimeoutError):
        error_code = ErrorCode.TIMEOUT_ERROR
    elif isinstance(exception, ConnectionError):
        error_code = ErrorCode.NETWORK_ERROR
    else:
        error_code = ErrorCode.UNKNOWN_ERROR
    
    # 构建详细信息
    details = {
        "exception_type": type(exception).__name__,
        "traceback": traceback.format_exc()
    }
    
    if context:
        details["context"] = context
    
    return create_error_response(
        error_code=error_code,
        message=str(exception),
        details=details,
        request_id=request_id
    )


def create_http_exception_response(
    exc: HTTPException,
    request_id: Optional[str] = None
) -> JSONResponse:
    """从HTTP异常创建错误响应"""
    # 根据状态码确定错误代码
    status_code = exc.status_code
    
    if status_code == 400:
        error_code = ErrorCode.INVALID_REQUEST
    elif status_code == 401:
        error_code = ErrorCode.UNAUTHORIZED
    elif status_code == 403:
        error_code = ErrorCode.FORBIDDEN
    elif status_code == 404:
        error_code = ErrorCode.RESOURCE_NOT_FOUND
    elif status_code == 409:
        error_code = ErrorCode.RESOURCE_CONFLICT
    elif status_code == 413:
        error_code = ErrorCode.REQUEST_TOO_LARGE
    elif status_code == 415:
        error_code = ErrorCode.UNSUPPORTED_MEDIA_TYPE
    elif status_code == 422:
        error_code = ErrorCode.VALIDATION_ERROR
    elif status_code == 429:
        error_code = ErrorCode.RATE_LIMIT_EXCEEDED
    elif status_code >= 500:
        error_code = ErrorCode.INTERNAL_SERVER_ERROR
    else:
        error_code = ErrorCode.UNKNOWN_ERROR
    
    return create_error_response(
        error_code=error_code,
        message=exc.detail,
        request_id=request_id
    )
