"""
分层错误处理系统 - 提供统一的错误处理、重试机制和熔断器
"""
import logging
import time
import functools
from typing import Type, Callable, Any, Optional, Dict, List
from enum import Enum
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class ErrorLevel(Enum):
    """错误级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ErrorCategory(Enum):
    """错误分类枚举"""
    CONFIGURATION = "CONFIGURATION"
    NETWORK = "NETWORK"
    API = "API"
    FILE_IO = "FILE_IO"
    PROCESSING = "PROCESSING"
    VALIDATION = "VALIDATION"
    SYSTEM = "SYSTEM"

class AutoClipsException(Exception):
    """自动切片工具基础异常类"""
    
    def __init__(self, message: str, category: ErrorCategory, level: ErrorLevel = ErrorLevel.ERROR, 
                 details: Optional[Dict[str, Any]] = None, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.level = level
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = time.time()
    
    def __str__(self):
        return f"[{self.category.value}] {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "message": self.message,
            "category": self.category.value,
            "level": self.level.value,
            "details": self.details,
            "timestamp": self.timestamp,
            "original_exception": str(self.original_exception) if self.original_exception else None
        }

class ConfigurationError(AutoClipsException):
    """配置错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.CONFIGURATION, ErrorLevel.ERROR, details)

class NetworkError(AutoClipsException):
    """网络错误"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.NETWORK, ErrorLevel.ERROR, details, original_exception)

class APIError(AutoClipsException):
    """API调用错误"""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        api_details = details or {}
        if status_code:
            api_details["status_code"] = status_code
        super().__init__(message, ErrorCategory.API, ErrorLevel.ERROR, api_details)

class FileIOError(AutoClipsException):
    """文件IO错误"""
    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        file_details = details or {}
        if file_path:
            file_details["file_path"] = file_path
        super().__init__(message, ErrorCategory.FILE_IO, ErrorLevel.ERROR, file_details)

class ProcessingError(AutoClipsException):
    """处理错误"""
    def __init__(self, message: str, step: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        processing_details = details or {}
        if step:
            processing_details["step"] = step
        super().__init__(message, ErrorCategory.PROCESSING, ErrorLevel.ERROR, processing_details)

class ValidationError(AutoClipsException):
    """验证错误"""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        validation_details = details or {}
        if field:
            validation_details["field"] = field
        super().__init__(message, ErrorCategory.VALIDATION, ErrorLevel.WARNING, validation_details)

@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_exceptions: List[Type[Exception]] = None
    
    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = [
                NetworkError,
                APIError,
                ConnectionError,
                TimeoutError,
                OSError
            ]

class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0, 
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数，应用熔断器逻辑"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise AutoClipsException(
                    "熔断器处于开启状态，拒绝执行",
                    ErrorCategory.SYSTEM,
                    ErrorLevel.WARNING
                )
        
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            
            raise e

def retry_with_backoff(config: Optional[RetryConfig] = None):
    """重试装饰器，支持指数退避"""
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(config.retryable_exceptions) as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        logger.error(f"函数 {func.__name__} 在 {config.max_retries} 次重试后失败: {e}")
                        raise e
                    
                    # 计算延迟时间
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败，{delay}秒后重试: {e}")
                    time.sleep(delay)
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator

@contextmanager
def error_context(category: ErrorCategory, context_info: Optional[Dict[str, Any]] = None):
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
            
            if category == ErrorCategory.API:
                raise APIError(str(e), details=details)
            elif category == ErrorCategory.NETWORK:
                raise NetworkError(str(e), details=details, original_exception=e)
            elif category == ErrorCategory.FILE_IO:
                raise FileIOError(str(e), details=details)
            elif category == ErrorCategory.PROCESSING:
                raise ProcessingError(str(e), details=details)
            elif category == ErrorCategory.VALIDATION:
                raise ValidationError(str(e), details=details)
            else:
                raise AutoClipsException(str(e), category, details=details, original_exception=e)

class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.error_log: List[AutoClipsException] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def handle_error(self, error: AutoClipsException, context: Optional[str] = None):
        """处理错误"""
        # 记录错误
        self.error_log.append(error)
        
        # 根据错误级别记录日志
        if error.level == ErrorLevel.DEBUG:
            logger.debug(f"[{context}] {error}")
        elif error.level == ErrorLevel.INFO:
            logger.info(f"[{context}] {error}")
        elif error.level == ErrorLevel.WARNING:
            logger.warning(f"[{context}] {error}")
        elif error.level == ErrorLevel.ERROR:
            logger.error(f"[{context}] {error}")
        elif error.level == ErrorLevel.CRITICAL:
            logger.critical(f"[{context}] {error}")
        
        # 根据错误分类进行特殊处理
        if error.category == ErrorCategory.API and isinstance(error, APIError):
            self._handle_api_error(error)
        elif error.category == ErrorCategory.NETWORK and isinstance(error, NetworkError):
            self._handle_network_error(error)
        elif error.category == ErrorCategory.CONFIGURATION and isinstance(error, ConfigurationError):
            self._handle_configuration_error(error)
    
    def _handle_api_error(self, error: APIError):
        """处理API错误"""
        # 可以在这里添加API错误的具体处理逻辑
        # 比如更新API密钥、切换备用API等
        pass
    
    def _handle_network_error(self, error: NetworkError):
        """处理网络错误"""
        # 可以在这里添加网络错误的具体处理逻辑
        # 比如切换网络、重试连接等
        pass
    
    def _handle_configuration_error(self, error: ConfigurationError):
        """处理配置错误"""
        # 可以在这里添加配置错误的具体处理逻辑
        # 比如加载默认配置、提示用户修复等
        pass
    
    def get_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(**kwargs)
        return self.circuit_breakers[name]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        if not self.error_log:
            return {"total_errors": 0}
        
        error_counts = {}
        for error in self.error_log:
            category = error.category.value
            error_counts[category] = error_counts.get(category, 0) + 1
        
        return {
            "total_errors": len(self.error_log),
            "error_counts": error_counts,
            "latest_error": self.error_log[-1].to_dict() if self.error_log else None
        }
    
    def clear_error_log(self):
        """清空错误日志"""
        self.error_log.clear()

# 全局错误处理器实例
error_handler = ErrorHandler()

def safe_execute(func: Callable, *args, context: Optional[str] = None, 
                retry_config: Optional[RetryConfig] = None, **kwargs) -> Any:
    """安全执行函数，包含错误处理和重试"""
    if retry_config:
        func = retry_with_backoff(retry_config)(func)
    
    try:
        return func(*args, **kwargs)
    except AutoClipsException as e:
        error_handler.handle_error(e, context)
        raise
    except Exception as e:
        # 转换为通用异常
        auto_clips_error = AutoClipsException(
            str(e), 
            ErrorCategory.SYSTEM, 
            ErrorLevel.ERROR,
            original_exception=e
        )
        error_handler.handle_error(auto_clips_error, context)
        raise auto_clips_error 