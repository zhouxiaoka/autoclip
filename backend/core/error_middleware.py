"""
统一错误处理中间件
为FastAPI应用提供统一的错误处理机制
"""
import re

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
    request_id: str = None,
    *,
    detail=None,
) -> JSONResponse:
    """创建统一格式的错误响应。

    D6: always expose a top-level FastAPI-compatible ``detail`` so frontend
    ``errorText`` (reads ``response.data.detail``) keeps the human message
    instead of falling back to an Axios status-code sentence.
    """
    response = ErrorResponse(error_code, message, details, request_id)
    response.timestamp = time.time()
    content = response.to_dict()
    if detail is not None:
        content["detail"] = detail
    elif isinstance(message, str) and message:
        content["detail"] = message
    return JSONResponse(
        status_code=status_code,
        content=content,
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器"""
    request_id = getattr(request.state, 'request_id', None)
    
    # 记录异常详情。校验错误的 str() 会带上被截断的 input，密钥尾巴要先抹掉。
    from backend.core.log_redaction import redact_text
    logger.error(
        "未处理的异常: %s: %s",
        type(exc).__name__,
        redact_text(str(exc)),
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "traceback": redact_text(traceback.format_exc()),
        }
    )
    if not isinstance(exc, (HTTPException, RequestValidationError, StarletteHTTPException)):
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
    
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
    """处理HTTPException — redact secrets that may appear in detail strings."""
    detail = exc.detail
    if isinstance(detail, (dict, list)):
        detail = _redact_validation_value(detail)
    elif isinstance(detail, str):
        from backend.core.log_redaction import redact_text
        detail = redact_text(detail)
    message = detail if isinstance(detail, str) else "请求失败"
    return create_error_response(
        status_code=exc.status_code,
        error_code=f"HTTP_{exc.status_code}",
        message=message,
        details={"detail": detail} if not isinstance(detail, str) else None,
        request_id=request_id,
        detail=detail,
    )


async def http_exception_handler_safe(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return handle_http_exception(exc, request_id)


# Credential-bearing keys that must never appear in 422 / HTTP error bodies.
_SECRET_KEYS = frozenset({
    "api_key", "apikey", "api-key", "access_token", "access-token",
    "authorization", "password", "secret", "secret_key", "token",
    "x-api-key", "x-goog-api-key",
})


def _redact_validation_value(value):
    """Strip credential fields from Pydantic/FastAPI error `input` / `ctx` trees."""
    from backend.core.log_redaction import redact_text
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                out[key] = "[REDACTED]"
            else:
                out[key] = _redact_validation_value(item)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact_validation_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    # Pydantic puts raw Exception objects in ctx["error"] — stringify, then redact.
    return redact_text(str(value))


def _loc_is_secret(loc) -> bool:
    return any(str(part).lower() in _SECRET_KEYS for part in (loc or ()))


_CJK = re.compile(r"[\u4e00-\u9fff]")
_PYDANTIC_PREFIXES = ("Value error, ", "Assertion failed, ")
_TYPE_HINTS = {
    "missing": "缺少必填项，请补全后再保存",
    "string_type": "这里需要填写文字",
    "int_parsing": "这里需要填写整数", "int_type": "这里需要填写整数",
    "float_parsing": "这里需要填写数字", "float_type": "这里需要填写数字",
    "bool_parsing": "这里只能选是或否", "bool_type": "这里只能选是或否",
    "literal_error": "选项不在可选范围内，请重新选择", "enum": "选项不在可选范围内，请重新选择",
    "json_invalid": "请求内容格式不对，请刷新页面后重试",
    "list_type": "这里的格式不对，请重新选择", "dict_type": "这里的格式不对，请重新填写",
    "model_type": "这里的格式不对，请重新填写",
    "url_parsing": "地址格式不对，请填写完整的 http(s):// 地址", "url_scheme": "地址格式不对，请填写完整的 http(s):// 地址",
}


def validation_message(error: dict) -> str:
    """Beginner-readable Chinese message for one pydantic error; never quotes the input."""
    kind = str(error.get("type") or "")
    loc = error.get("loc", ())
    msg = str(error.get("msg") or "")
    for prefix in _PYDANTIC_PREFIXES:
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
    if _loc_is_secret(loc):
        if kind == "string_too_long":
            return "密钥太长，请检查是否粘贴错了"
        if kind == "missing":
            return "请填写密钥"
        return "密钥格式不对，请重新粘贴"
    if kind == "string_too_long":
        limit = (error.get("ctx") or {}).get("max_length")
        return f"内容太长（最多 {limit} 个字符），请检查是否粘贴错了" if limit else "内容太长，请检查是否粘贴错了"
    if kind == "string_too_short":
        return "内容太短，请补全后再保存"
    if _CJK.search(msg):
        return msg  # our own validators already speak Chinese
    return _TYPE_HINTS.get(kind) or "填写的内容格式不对，请检查后重试"


def handle_validation_error(exc: RequestValidationError, request_id: str = None) -> JSONResponse:
    """处理请求验证错误 — never echo credential-bearing `input` (beginner self-test 422 leak)."""
    errors = []
    for error in exc.errors():
        loc = error.get("loc", ())
        entry = {
            "field": ".".join(str(part) for part in loc),
            "message": validation_message(error),
            "type": error.get("type", ""),
            "loc": list(loc),
        }
        # D5: when loc points at api_key / password / …, wipe the string input
        # entirely — regex alone misses non sk-/AIza secrets.
        # E4: a credential field never echoes its input, whatever its type (str, number,
        # list, object) — the input is omitted outright, and so is ctx (it can quote it).
        if _loc_is_secret(loc):
            pass
        else:
            if "input" in error:
                entry["input"] = _redact_validation_value(error["input"])
            if "ctx" in error:
                entry["ctx"] = _redact_validation_value(error["ctx"])
        errors.append(entry)

    return create_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="请求参数验证失败",
        details={"errors": errors},
        request_id=request_id,
        detail=errors,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Registered explicitly so FastAPI's default handler (which echoes input) is replaced."""
    request_id = getattr(request.state, "request_id", None)
    return handle_validation_error(exc, request_id)


def handle_starlette_http_exception(exc: StarletteHTTPException, request_id: str = None) -> JSONResponse:
    """处理StarletteHTTPException"""
    from backend.core.log_redaction import redact_text
    message = redact_text(str(exc.detail))
    return create_error_response(
        status_code=exc.status_code,
        error_code=f"STARLETTE_{exc.status_code}",
        message=message,
        request_id=request_id,
        detail=message,
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
