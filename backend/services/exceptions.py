"""
服务异常体系
统一的异常处理机制
"""

import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """错误代码枚举"""
    # 配置相关错误
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING_REQUIRED = "CONFIG_MISSING_REQUIRED"
    
    # 文件相关错误
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_PERMISSION_DENIED = "FILE_PERMISSION_DENIED"
    FILE_CORRUPTED = "FILE_CORRUPTED"
    
    # 处理相关错误
    PROCESSING_FAILED = "PROCESSING_FAILED"
    STEP_EXECUTION_FAILED = "STEP_EXECUTION_FAILED"
    PIPELINE_VALIDATION_FAILED = "PIPELINE_VALIDATION_FAILED"
    
    # 任务相关错误
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_ALREADY_RUNNING = "TASK_ALREADY_RUNNING"
    TASK_CANCELLED = "TASK_CANCELLED"
    
    # 项目相关错误
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    PROJECT_ALREADY_EXISTS = "PROJECT_ALREADY_EXISTS"
    
    # 系统相关错误
    SYSTEM_ERROR = "SYSTEM_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    
    # 并发相关错误
    CONCURRENT_ACCESS = "CONCURRENT_ACCESS"
    LOCK_ACQUISITION_FAILED = "LOCK_ACQUISITION_FAILED"
    
    # 未知错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ServiceError(Exception):
    """服务异常基类"""
    
    def __init__(self, 
                 message: str,
                 error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.timestamp = None  # 将在子类中设置
        
        # 记录错误日志
        self._log_error()
    
    def _log_error(self):
        """记录错误日志"""
        log_message = f"ServiceError: {self.error_code.value} - {self.message}"
        if self.details:
            log_message += f" | Details: {self.details}"
        if self.cause:
            log_message += f" | Cause: {self.cause}"
        
        logger.error(log_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class ConfigurationError(ServiceError):
    """配置相关错误"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(message, ErrorCode.CONFIG_INVALID, details, cause)


class FileOperationError(ServiceError):
    """文件操作相关错误"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if file_path:
            details = details or {}
            details["file_path"] = file_path
        super().__init__(message, ErrorCode.FILE_NOT_FOUND, details, cause)


class ProcessingError(ServiceError):
    """处理相关错误"""
    
    def __init__(self, message: str, step_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if step_name:
            details = details or {}
            details["step_name"] = step_name
        super().__init__(message, ErrorCode.PROCESSING_FAILED, details, cause)


class TaskError(ServiceError):
    """任务相关错误"""
    
    def __init__(self, message: str, task_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if task_id:
            details = details or {}
            details["task_id"] = task_id
        super().__init__(message, ErrorCode.TASK_NOT_FOUND, details, cause)


class ProjectError(ServiceError):
    """项目相关错误"""
    
    def __init__(self, message: str, project_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if project_id:
            details = details or {}
            details["project_id"] = project_id
        super().__init__(message, ErrorCode.PROJECT_NOT_FOUND, details, cause)


class ConcurrentError(ServiceError):
    """并发相关错误"""
    
    def __init__(self, message: str, resource: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if resource:
            details = details or {}
            details["resource"] = resource
        super().__init__(message, ErrorCode.CONCURRENT_ACCESS, details, cause)


class SystemError(ServiceError):
    """系统相关错误"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(message, ErrorCode.SYSTEM_ERROR, details, cause)


def handle_service_error(func):
    """服务错误处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceError:
            # 重新抛出ServiceError
            raise
        except Exception as e:
            # 将其他异常包装为ServiceError
            logger.error(f"未处理的异常: {e}")
            raise SystemError(f"系统错误: {str(e)}", cause=e)
    return wrapper


def create_error_response(error: ServiceError) -> Dict[str, Any]:
    """创建错误响应"""
    return {
        "success": False,
        "error": error.to_dict()
    }


def is_service_error(exception: Exception) -> bool:
    """检查是否为服务异常"""
    return isinstance(exception, ServiceError) 