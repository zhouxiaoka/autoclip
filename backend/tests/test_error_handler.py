"""
错误处理系统单元测试
"""
import time
from unittest.mock import patch, MagicMock

import pytest
from shared.utils.error_handler import (
    AutoClipsException, APIError, NetworkError, ConfigurationError,
    FileIOError, ProcessingError, ValidationError,
    ErrorLevel, ErrorCategory, RetryConfig, CircuitBreaker,
    retry_with_backoff, error_context, ErrorHandler, safe_execute
)


class TestAutoClipsException:
    """测试基础异常类"""
    
    def test_exception_creation(self):
        """测试异常创建"""
        error = AutoClipsException("测试错误", ErrorCategory.API)
        assert error.message == "测试错误"
        assert error.category == ErrorCategory.API
        assert error.level == ErrorLevel.ERROR
        assert error.timestamp > 0
    
    def test_exception_to_dict(self):
        """测试异常转字典"""
        original_exception = ValueError("原始错误")
        error = AutoClipsException(
            "测试错误", 
            ErrorCategory.API, 
            ErrorLevel.WARNING,
            {"detail": "详细信息"},
            original_exception
        )
        
        error_dict = error.to_dict()
        assert error_dict["message"] == "测试错误"
        assert error_dict["category"] == "API"
        assert error_dict["level"] == "WARNING"
        assert error_dict["details"]["detail"] == "详细信息"
        assert "原始错误" in error_dict["original_exception"]
    
    def test_exception_str_representation(self):
        """测试异常字符串表示"""
        error = AutoClipsException("测试错误", ErrorCategory.NETWORK)
        assert str(error) == "[NETWORK] 测试错误"


class TestSpecificExceptions:
    """测试特定异常类"""
    
    def test_api_error(self):
        """测试API错误"""
        error = APIError("API调用失败", status_code=400)
        assert error.category == ErrorCategory.API
        assert error.details["status_code"] == 400
    
    def test_network_error(self):
        """测试网络错误"""
        original_exception = ConnectionError("连接失败")
        error = NetworkError("网络错误", original_exception=original_exception)
        assert error.category == ErrorCategory.NETWORK
        assert error.original_exception == original_exception
    
    def test_file_io_error(self):
        """测试文件IO错误"""
        error = FileIOError("文件读取失败", file_path="/test/file.txt")
        assert error.category == ErrorCategory.FILE_IO
        assert error.details["file_path"] == "/test/file.txt"
    
    def test_processing_error(self):
        """测试处理错误"""
        error = ProcessingError("处理失败", step="Step 1")
        assert error.category == ErrorCategory.PROCESSING
        assert error.details["step"] == "Step 1"
    
    def test_validation_error(self):
        """测试验证错误"""
        error = ValidationError("验证失败", field="api_key")
        assert error.category == ErrorCategory.VALIDATION
        assert error.level == ErrorLevel.WARNING
        assert error.details["field"] == "api_key"


class TestRetryConfig:
    """测试重试配置"""
    
    def test_retry_config_defaults(self):
        """测试重试配置默认值"""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert len(config.retryable_exceptions) > 0
    
    def test_retry_config_custom_values(self):
        """测试重试配置自定义值"""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0
        )
        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0


class TestCircuitBreaker:
    """测试熔断器"""
    
    def test_circuit_breaker_initial_state(self):
        """测试熔断器初始状态"""
        cb = CircuitBreaker()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
    
    def test_circuit_breaker_successful_call(self):
        """测试熔断器成功调用"""
        cb = CircuitBreaker()
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == "CLOSED"
    
    def test_circuit_breaker_failure_threshold(self):
        """测试熔断器失败阈值"""
        cb = CircuitBreaker(failure_threshold=2)
        
        def failing_func():
            raise ValueError("测试失败")
        
        # 第一次失败
        with patch('time.time', return_value=1000):
            with pytest.raises(ValueError):
                cb.call(failing_func)
            assert cb.state == "CLOSED"
            assert cb.failure_count == 1
        
        # 第二次失败，触发熔断
        with patch('time.time', return_value=1001):
            with pytest.raises(ValueError):
                cb.call(failing_func)
            assert cb.state == "OPEN"
            assert cb.failure_count == 2
    
    def test_circuit_breaker_recovery(self):
        """测试熔断器恢复"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
        
        def failing_func():
            raise ValueError("测试失败")
        
        # 触发熔断
        with patch('time.time', return_value=1000):
            with pytest.raises(ValueError):
                cb.call(failing_func)
            assert cb.state == "OPEN"
        
        # 等待恢复时间后，状态变为半开
        with patch('time.time', return_value=1002):  # 超过恢复时间
            def success_func():
                return "success"
            
            result = cb.call(success_func)
            assert result == "success"
            assert cb.state == "CLOSED"  # 成功后关闭


class TestRetryDecorator:
    """测试重试装饰器"""
    
    def test_retry_success_on_first_try(self):
        """测试第一次就成功"""
        @retry_with_backoff()
        def success_func():
            return "success"
        
        result = success_func()
        assert result == "success"
    
    def test_retry_success_after_failures(self):
        """测试失败后重试成功"""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=2, base_delay=0.1))
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("网络错误")
            return "success"
        
        result = failing_then_success()
        assert result == "success"
        assert call_count == 3
    
    def test_retry_max_attempts_exceeded(self):
        """测试超过最大重试次数"""
        @retry_with_backoff(RetryConfig(max_retries=1, base_delay=0.1))
        def always_failing():
            raise APIError("API错误")
        
        with pytest.raises(APIError):
            always_failing()


class TestErrorContext:
    """测试错误上下文管理器"""
    
    def test_error_context_no_exception(self):
        """测试无异常的情况"""
        with error_context(ErrorCategory.API):
            result = "success"
        
        assert result == "success"
    
    def test_error_context_with_exception(self):
        """测试有异常的情况"""
        with pytest.raises(APIError):
            with error_context(ErrorCategory.API):
                raise ValueError("原始错误")
    
    def test_error_context_preserves_auto_clips_exception(self):
        """测试保留AutoClipsException"""
        original_error = APIError("API错误")
        with pytest.raises(APIError) as exc_info:
            with error_context(ErrorCategory.NETWORK):
                raise original_error
        
        assert exc_info.value == original_error


class TestErrorHandler:
    """测试错误处理器"""
    
    def test_error_handler_initialization(self):
        """测试错误处理器初始化"""
        handler = ErrorHandler()
        assert len(handler.error_log) == 0
        assert len(handler.circuit_breakers) == 0
    
    def test_error_handler_handle_error(self):
        """测试错误处理"""
        handler = ErrorHandler()
        error = APIError("测试API错误")
        
        with patch('logging.Logger.error') as mock_logger:
            handler.handle_error(error, "测试上下文")
            
            assert len(handler.error_log) == 1
            assert handler.error_log[0] == error
            mock_logger.assert_called_once()
    
    def test_error_handler_get_circuit_breaker(self):
        """测试获取熔断器"""
        handler = ErrorHandler()
        
        cb1 = handler.get_circuit_breaker("test")
        cb2 = handler.get_circuit_breaker("test")
        
        assert cb1 is cb2  # 同一个名称返回同一个实例
        assert len(handler.circuit_breakers) == 1
    
    def test_error_handler_get_error_summary(self):
        """测试获取错误摘要"""
        handler = ErrorHandler()
        
        # 无错误时
        summary = handler.get_error_summary()
        assert summary["total_errors"] == 0
        
        # 有错误时
        handler.handle_error(APIError("API错误1"))
        handler.handle_error(NetworkError("网络错误"))
        handler.handle_error(APIError("API错误2"))
        
        summary = handler.get_error_summary()
        assert summary["total_errors"] == 3
        assert summary["error_counts"]["API"] == 2
        assert summary["error_counts"]["NETWORK"] == 1
        assert summary["latest_error"] is not None
    
    def test_error_handler_clear_error_log(self):
        """测试清空错误日志"""
        handler = ErrorHandler()
        handler.handle_error(APIError("测试错误"))
        assert len(handler.error_log) == 1
        
        handler.clear_error_log()
        assert len(handler.error_log) == 0


class TestSafeExecute:
    """测试安全执行函数"""
    
    def test_safe_execute_success(self):
        """测试成功执行"""
        def success_func():
            return "success"
        
        result = safe_execute(success_func, context="测试")
        assert result == "success"
    
    def test_safe_execute_with_retry(self):
        """测试带重试的执行"""
        call_count = 0
        
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("网络错误")
            return "success"
        
        retry_config = RetryConfig(max_retries=1, base_delay=0.1)
        result = safe_execute(failing_then_success, context="测试", retry_config=retry_config)
        assert result == "success"
        assert call_count == 2
    
    def test_safe_execute_handles_auto_clips_exception(self):
        """测试处理AutoClipsException"""
        def raise_auto_clips_error():
            raise APIError("API错误")
        
        with pytest.raises(APIError):
            safe_execute(raise_auto_clips_error, context="测试")
    
    def test_safe_execute_converts_generic_exception(self):
        """测试转换通用异常"""
        def raise_generic_error():
            raise ValueError("通用错误")
        
        with pytest.raises(AutoClipsException) as exc_info:
            safe_execute(raise_generic_error, context="测试")
        
        assert exc_info.value.category == ErrorCategory.SYSTEM
        assert "通用错误" in str(exc_info.value)


# 测试辅助函数
def test_error_level_enum():
    """测试错误级别枚举"""
    assert ErrorLevel.DEBUG.value == "DEBUG"
    assert ErrorLevel.ERROR.value == "ERROR"
    assert ErrorLevel.CRITICAL.value == "CRITICAL"


def test_error_category_enum():
    """测试错误分类枚举"""
    assert ErrorCategory.API.value == "API"
    assert ErrorCategory.NETWORK.value == "NETWORK"
    assert ErrorCategory.CONFIGURATION.value == "CONFIGURATION"


if __name__ == '__main__':
    pytest.main([__file__]) 