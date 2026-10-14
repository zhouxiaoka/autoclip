"""上游 HTTP 错误分类（1.5.8 成功率契约）。

只提供能力：解析状态码 + 响应体，输出稳定枚举。不改现有调用链、不重试、不上报。
后续埋点 / 设置页校验 / 退避 / 付费前预检都只应引用这里的枚举与 ``classify_upstream_error``。

兼容 OpenAI、new-api（88API / Infistar）、Gemini、DeepSeek、DashScope 的常见错误信封。
返回值只有枚举、是否可重试、一句中文 i18n key——不含响应原文、URL、密钥或用户内容。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class UpstreamErrorType(str, Enum):
    """机器可读分类。埋点 ``upstream_error_type`` 只允许这些值。"""

    INVALID_KEY = "invalid_key"
    INSUFFICIENT_QUOTA = "insufficient_quota"
    PERMISSION_DENIED = "permission_denied"
    MODEL_NOT_FOUND = "model_not_found"
    BAD_ENDPOINT = "bad_endpoint"
    RATE_LIMITED = "rate_limited"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    OUTPUT_TRUNCATED = "output_truncated"
    UNKNOWN = "unknown"


UPSTREAM_ERROR_TYPES: frozenset[str] = frozenset(item.value for item in UpstreamErrorType)

# 中文句子即前端 i18n catalog key（八语必须同步）。
# timeout / connection / rate_limited 与 pipeline.failures.MODEL_CALL_MESSAGES 同句，避免两套文案。
HINT_KEYS: dict[UpstreamErrorType, str] = {
    UpstreamErrorType.INVALID_KEY: "密钥无效或已过期，请到「设置 → 模型」检查密钥后重试。",
    UpstreamErrorType.INSUFFICIENT_QUOTA: "账户余额或令牌额度不足，请充值或更换令牌后再试。",
    UpstreamErrorType.PERMISSION_DENIED: "当前令牌没有该模型权限或分组不对，请到服务商控制台勾选模型或更换分组。",
    UpstreamErrorType.MODEL_NOT_FOUND: "当前分组或服务下没有这个模型，请换一个模型或分组。",
    UpstreamErrorType.BAD_ENDPOINT: "接口地址不正确（常见是漏了 /v1 或填成了控制台网址），请到「设置 → 模型」核对地址。",
    UpstreamErrorType.RATE_LIMITED: "提供商限制了请求频率或额度，请检查配额并稍后重试。",
    UpstreamErrorType.UPSTREAM_UNAVAILABLE: "模型服务暂时不可用，请稍后重试。",
    UpstreamErrorType.TIMEOUT: "模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。",
    UpstreamErrorType.CONNECTION: "无法连接模型服务，请检查接口地址与网络；本地模型请先启动服务后重试。",
    UpstreamErrorType.OUTPUT_TRUNCATED: "模型输出被截断，请稍后重试或换一个模型。",
    UpstreamErrorType.UNKNOWN: "模型服务返回了无法识别的错误，请检查配置后重试。",
}

# 瞬时故障才重试。401/402/403/404、余额、权限、地址错、截断、未知一律不重试。
RETRYABLE_TYPES: frozenset[UpstreamErrorType] = frozenset({
    UpstreamErrorType.RATE_LIMITED,
    UpstreamErrorType.UPSTREAM_UNAVAILABLE,
    UpstreamErrorType.TIMEOUT,
    UpstreamErrorType.CONNECTION,
})

_HTML_HEAD = re.compile(r"<!doctype\s+html|<html[\s>]|<head[\s>]|<title[\s>]", re.I)
_STATUS_IN_TEXT = re.compile(r"(?:error[_ ]code|status(?:[_ ]code)?|http)\s*[:=]?\s*(\d{3})\b", re.I)
_LENGTH_REASONS = frozenset({"length", "max_tokens", "max_output_tokens"})

# 结构化 code / type / Gemini reason / DashScope code。只匹配规范化后的小写 token。
_CODE_QUOTA = frozenset({
    "insufficient_quota", "insufficient_user_quota", "insufficient_balance",
    "billing_not_active", "billing_quota_exceeded", "quota_exceeded",
    "allocationquota", "allocationquota.freetieronly", "throttling.allocationquota",
})
_CODE_KEY = frozenset({
    "invalid_api_key", "invalid_key", "invalid_token", "authentication_error",
    "api_key_invalid", "invalidapikey", "unauthenticated",
})
_CODE_MODEL = frozenset({"model_not_found", "model_not_available", "not_found"})
_CODE_RATE = frozenset({
    "rate_limit_exceeded", "rate_limit", "rate_limit_error",
    "throttling.ratequota", "throttling", "too_many_requests",
})
_CODE_PERMISSION = frozenset({
    "permission_denied", "access_denied", "model_not_supported",
    "forbidden",
})
_CODE_RESOURCE = frozenset({"resource_exhausted"})

_QUOTA_HINTS = (
    "insufficient_quota", "insufficient_user_quota", "insufficient balance",
    "insufficient_balance", "exceeded your current quota", "quota exceeded",
    "check quota", "has been exhausted", "billing",
    "余额不足", "额度不足", "额度用尽", "额度已用尽", "额度用完", "额度已用完",
    "令牌额度", "用户余额", "预扣费",
)
_KEY_HINTS = (
    "invalid api key", "incorrect api key", "invalid_api_key", "invalid token",
    "无效的令牌", "令牌无效", "令牌已禁用", "令牌已过期", "api key not valid",
    "api_key_invalid", "authentication", "unauthorized", "incorrect api-key",
    "invalid api-key",
)
_PERMISSION_HINTS = (
    "无权访问", "无权访问模型", "该令牌无权", "分组", "does not have access",
    "permission denied", "forbidden", "not allowed to use", "model is not supported",
    "ip whitelist", "ip 白名单",
)
_MODEL_HINTS = (
    "model_not_found", "does not exist", "no available channel",
    "没有可用渠道", "模型不存在", "is not found",
)
_RATE_HINTS = ("rate limit", "too many requests", "retry later", "throttl", "频率")
_TIMEOUT_HINTS = ("timeout", "timed out", "deadline exceeded", "read timed out")
_CONNECTION_HINTS = (
    "connection error", "connection reset", "connecterror", "connect error",
    "name or service not known", "nodename nor servname", "connection refused",
    "network is unreachable", "failed to establish", "apiconnectionerror",
)
_TIMEOUT_NAMES = frozenset({
    "timeouterror", "apitimeouterror", "readtimeout", "connecttimeout",
    "deadlineexceeded", "timeoutexpired",
})
_CONNECTION_NAMES = frozenset({
    "connectionerror", "apiconnectionerror", "connecterror", "connectionreseterror",
    "connectionabortederror", "connectionrefusederror", "brokenpipeerror",
    "oserror", "urlerror",
})


@dataclass(frozen=True)
class ClassifiedUpstreamError:
    error_type: UpstreamErrorType
    retryable: bool
    hint_key: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type.value,
            "retryable": self.retryable,
            "hint_key": self.hint_key,
        }


def is_retryable(error_type: UpstreamErrorType | str) -> bool:
    value = error_type if isinstance(error_type, UpstreamErrorType) else _parse_type(error_type)
    return value in RETRYABLE_TYPES


def hint_key_for(error_type: UpstreamErrorType | str) -> str:
    value = error_type if isinstance(error_type, UpstreamErrorType) else _parse_type(error_type)
    return HINT_KEYS[value]


def classify_upstream_error(
    status_code: int | None = None,
    body: Any = None,
    *,
    finish_reason: str | None = None,
    error_name: str | None = None,
) -> ClassifiedUpstreamError:
    """根据 HTTP 状态码和响应体分类。

    ``body`` 可以是 dict / JSON 字符串 / bytes / 异常原文。结果不含任何正文片段。
    ``finish_reason`` 用于 200 + ``length`` 截断。``error_name`` 用于无状态码的超时/断连。
    """
    status = _coerce_status(status_code)
    payload, text = _coerce_body(body)
    if status is None:
        status = _status_from_text(text)
    fields = _error_fields(payload, text)
    error_type = _classify(status, payload, text, fields, finish_reason, error_name)
    return ClassifiedUpstreamError(
        error_type=error_type,
        retryable=error_type in RETRYABLE_TYPES,
        hint_key=HINT_KEYS[error_type],
    )


def classify_exception(error: BaseException, *, finish_reason: str | None = None) -> ClassifiedUpstreamError:
    """从常见 SDK 异常取出状态码和响应体再分类。不改变异常、不重试。"""
    status, body = http_error_parts(error)
    return classify_upstream_error(
        status, body, finish_reason=finish_reason, error_name=type(error).__name__,
    )


def http_error_parts(error: BaseException) -> tuple[int | None, Any]:
    """沿异常取出 ``(status_code, body)``，读不到 body 时退回 ``str(error)``。"""
    status = _status_from_obj(error)
    body: Any = _first_attr(error, "body")
    response = _first_attr(error, "response")
    if response is not None:
        if status is None:
            status = _status_from_obj(response)
        if body is None:
            body = _body_from_response(response)
    if body is None:
        body = str(error) if error.args else ""
    return status, body


def _classify(
    status: int | None,
    payload: dict[str, Any] | None,
    text: str,
    fields: tuple[str, str, str],
    finish_reason: str | None,
    error_name: str | None,
) -> UpstreamErrorType:
    reason = (finish_reason or "").strip().lower()
    if reason in _LENGTH_REASONS:
        return UpstreamErrorType.OUTPUT_TRUNCATED
    if _looks_like_html(text, payload):
        return UpstreamErrorType.BAD_ENDPOINT

    code, kind, message = fields
    blob = " ".join(part for part in (code, kind, message, text.lower()) if part)
    named = _normalize_token(error_name or "")

    structured = _from_structured_code(code, kind, blob, status)
    if structured is not None:
        return structured

    hinted = _from_hints(blob, status)
    if hinted is not None:
        return hinted

    if status == 402:
        return UpstreamErrorType.INSUFFICIENT_QUOTA
    if status == 401:
        return UpstreamErrorType.INVALID_KEY
    if status == 403:
        return UpstreamErrorType.PERMISSION_DENIED
    if status == 404:
        return UpstreamErrorType.BAD_ENDPOINT
    if status == 429:
        return UpstreamErrorType.RATE_LIMITED
    if status in {500, 502, 503, 504}:
        return UpstreamErrorType.UPSTREAM_UNAVAILABLE
    if status == 408:
        return UpstreamErrorType.TIMEOUT

    if named in _TIMEOUT_NAMES or _contains(blob, _TIMEOUT_HINTS):
        return UpstreamErrorType.TIMEOUT
    if named in _CONNECTION_NAMES or _contains(blob, _CONNECTION_HINTS):
        return UpstreamErrorType.CONNECTION
    return UpstreamErrorType.UNKNOWN


def _from_structured_code(
    code: str, kind: str, blob: str, status: int | None,
) -> UpstreamErrorType | None:
    tokens = {code, kind, code.replace(".", ""), kind.replace(".", "")}
    if tokens & _CODE_QUOTA:
        return UpstreamErrorType.INSUFFICIENT_QUOTA
    if tokens & _CODE_KEY:
        if _contains(blob, _QUOTA_HINTS):
            return UpstreamErrorType.INSUFFICIENT_QUOTA
        return UpstreamErrorType.INVALID_KEY
    if tokens & _CODE_MODEL:
        if status == 404 and not _contains(blob, _MODEL_HINTS + ("model", "模型")):
            return UpstreamErrorType.BAD_ENDPOINT
        return UpstreamErrorType.MODEL_NOT_FOUND
    if tokens & _CODE_RATE:
        return UpstreamErrorType.RATE_LIMITED
    if tokens & _CODE_RESOURCE:
        return (
            UpstreamErrorType.INSUFFICIENT_QUOTA
            if _contains(blob, _QUOTA_HINTS)
            else UpstreamErrorType.RATE_LIMITED
        )
    if tokens & _CODE_PERMISSION:
        if _contains(blob, _QUOTA_HINTS):
            return UpstreamErrorType.INSUFFICIENT_QUOTA
        return UpstreamErrorType.PERMISSION_DENIED
    return None


def _from_hints(blob: str, status: int | None) -> UpstreamErrorType | None:
    if _contains(blob, _QUOTA_HINTS):
        return UpstreamErrorType.INSUFFICIENT_QUOTA
    if _contains(blob, _MODEL_HINTS) and status in {400, 404, 503, None}:
        return UpstreamErrorType.MODEL_NOT_FOUND
    if status == 429 or (status is None and _contains(blob, _RATE_HINTS)):
        if _contains(blob, _RATE_HINTS) and status in {429, None}:
            return UpstreamErrorType.RATE_LIMITED
    if status in {401, 403, None} and _contains(blob, _PERMISSION_HINTS) and status != 401:
        return UpstreamErrorType.PERMISSION_DENIED
    if status in {401, None} and _contains(blob, _KEY_HINTS):
        return UpstreamErrorType.INVALID_KEY
    if status == 403 and _contains(blob, _PERMISSION_HINTS):
        return UpstreamErrorType.PERMISSION_DENIED
    if status in {429} and _contains(blob, _RATE_HINTS):
        return UpstreamErrorType.RATE_LIMITED
    return None


def _coerce_status(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    if isinstance(value, str) and value.isdigit():
        number = int(value)
        if 100 <= number <= 599:
            return number
    return None


def _status_from_obj(obj: Any) -> int | None:
    for attr in ("status_code", "status", "http_status", "code"):
        status = _coerce_status(getattr(obj, attr, None))
        if status is not None:
            return status
    return None


def _status_from_text(text: str) -> int | None:
    match = _STATUS_IN_TEXT.search(text or "")
    return _coerce_status(int(match[1])) if match else None


def _coerce_body(body: Any) -> tuple[dict[str, Any] | None, str]:
    if body is None:
        return None, ""
    if isinstance(body, dict):
        return body, ""
    if isinstance(body, (bytes, bytearray)):
        text = body.decode("utf-8", errors="replace")
    else:
        text = str(body)
    text = text.strip()
    if not text:
        return None, ""
    parsed = _parse_json_object(text)
    if parsed is not None:
        return parsed, text
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        parsed = _parse_json_object(text[start:end + 1])
        if parsed is not None:
            return parsed, text
    return None, text


def _parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _error_fields(payload: dict[str, Any] | None, text: str) -> tuple[str, str, str]:
    if not payload:
        return "", "", text.lower()
    error = payload.get("error")
    if not isinstance(error, dict):
        error = {}
    details = error.get("details") if isinstance(error.get("details"), list) else []
    reasons = []
    for item in details:
        if isinstance(item, dict) and item.get("reason"):
            reasons.append(str(item["reason"]))
    # Gemini 把 HTTP 状态写在 error.code（数字），真正的原因在 details[].reason。
    code = _symbolic_code(*reasons, error.get("reason"), error.get("code"), payload.get("code"))
    kind = _symbolic_code(error.get("type"), error.get("status"), payload.get("type"), payload.get("status"))
    message = _first_str(error.get("message"), payload.get("message"), error.get("msg"))
    return _normalize_token(code), _normalize_token(kind), (message or text).lower()


def _looks_like_html(text: str, payload: dict[str, Any] | None) -> bool:
    if payload is not None:
        return False
    head = (text or "").lstrip()[:800]
    if not head:
        return False
    return bool(_HTML_HEAD.search(head))


def _contains(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _normalize_token(value: str) -> str:
    return re.sub(r"[\s]+", "_", (value or "").strip().lower())


def _first_str(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _symbolic_code(*values: Any) -> str:
    """跳过纯数字状态码，只取 invalid_api_key / API_KEY_INVALID 这类符号。"""
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int):
            continue
        text = str(value).strip()
        if text and not text.isdigit():
            return text
    return ""


def _first_attr(obj: Any, name: str) -> Any:
    return getattr(obj, name, None)


def _body_from_response(response: Any) -> Any:
    for attr in ("json", "text", "content", "body"):
        value = getattr(response, attr, None)
        if callable(value):
            try:
                parsed = value()
            except Exception:  # noqa: BLE001 - 分类不得因读 body 失败而抛
                continue
            if parsed not in (None, ""):
                return parsed
        elif value not in (None, ""):
            return value
    return None


def _parse_type(value: str) -> UpstreamErrorType:
    try:
        return UpstreamErrorType(value)
    except ValueError:
        return UpstreamErrorType.UNKNOWN
