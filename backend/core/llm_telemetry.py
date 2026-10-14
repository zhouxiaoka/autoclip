"""成功率埋点字段契约（1.5.8）。

定义 run 级与 ``llm_request_finished`` 级允许字段，以及脱敏 helper。
本模块提供字段白名单与 ``sanitize_*``。事件发送在 ``llm_emit``（经 ``__getattr__``
再导出），调用链由线 A 挂上。设置页校验线只借 ``upstream_errors`` 的分类。

隐私：不上报 key、完整 URL、提示词、字幕、模型原文。base_url 只留域名；
本机 / 局域网统一记 ``local``。model 必须匹配 ``^[\\w.\\-:/]{1,64}$``。
``upstream_error_type`` 只用 :class:`UpstreamErrorType` 枚举。
"""
from __future__ import annotations

import ipaddress
import re
from typing import Any, Mapping
from urllib.parse import urlparse

from backend.core.upstream_errors import UPSTREAM_ERROR_TYPES, UpstreamErrorType

SUCCESS_RATE_SCHEMA_VERSION = 1

EVENT_LLM_REQUEST_FINISHED = "llm_request_finished"
EVENT_ASR_READINESS_CHECKED = "asr_readiness_checked"
EVENT_PROVIDER_VALIDATION_FINISHED = "provider_validation_finished"
# 现有 run 终态事件：后续埋点线往这些事件**追加**下列字段，不改事件名、不升 studio_schema_version。
EVENT_STUDIO_GENERATION_FINISHED = "studio_generation_finished"
EVENT_STUDIO_PRODUCTION_FINISHED = "studio_production_finished"

TELEMETRY_PROVIDERS: frozenset[str] = frozenset({
    "dashscope", "openai", "gemini", "deepseek", "seed", "kimi", "glm", "grok",
    "infistar", "api88", "compatible", "ollama", "lmstudio", "other",
})
ASR_PROVIDERS: frozenset[str] = frozenset({
    "whisper_local", "sensevoice_local", "cloud",
})
REQUEST_KINDS: frozenset[str] = frozenset({"text", "vision"})
REQUEST_OUTCOMES: frozenset[str] = frozenset({"success", "error"})
VALIDATION_RESULTS: frozenset[str] = frozenset({"success", "failed", "skipped"})
FINISH_REASONS: frozenset[str] = frozenset({"stop", "length", "content_filter", "unknown"})
FAILURE_STAGES: frozenset[str] = frozenset({
    "screening", "dispatch", "production", "ingest", "subtitle", "analyze",
    "vision", "render", "outline", "timeline", "scoring", "title", "clustering",
    "other",
})

# run 级（generation / production 终态 + Sentry tag）
RUN_LEVEL_FIELDS: frozenset[str] = frozenset({
    "provider", "model", "base_url_host", "http_status", "upstream_error_type",
    "failure_stage", "llm_calls", "prompt_tokens", "completion_tokens",
    "reasoning_tokens", "retry_count", "billable_calls_before_failure",
})
# 单次模型请求
LLM_REQUEST_FIELDS: frozenset[str] = frozenset({
    "success_rate_schema_version", "provider", "model", "base_url_host", "kind",
    "stage", "http_status", "upstream_error_type", "prompt_tokens",
    "completion_tokens", "reasoning_tokens", "retry_count", "duration_ms",
    "outcome", "finish_reason",
})
ASR_READINESS_FIELDS: frozenset[str] = frozenset({
    "success_rate_schema_version", "provider", "code", "has_subtitle", "blocked",
})
PROVIDER_VALIDATION_FIELDS: frozenset[str] = frozenset({
    "success_rate_schema_version", "provider", "base_url_host", "result",
    "upstream_error_type",
})

MODEL_PATTERN = re.compile(r"^[\w.\-:/]{1,64}$")
_HOST_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,251}[a-z0-9])?$")
_LOCAL_HOSTS = frozenset({"localhost", "0.0.0.0", "host.docker.internal", "::1"})
_SECRET_MARKERS = ("sk-", "api_key", "apikey", "authorization", "bearer ", "token=")


def hostname_of_base_url(url: str | None) -> str | None:
    """只返回域名或 ``local``。解析失败、密钥形、无 host 时返回 None。"""
    if not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw or (_looks_like_secret(raw) and "://" not in raw and "/" not in raw):
        return None
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().strip("[]")
    if not host:
        return None
    if _is_local_host(host):
        return "local"
    if len(host) > 253 or not _HOST_PATTERN.fullmatch(host):
        return None
    return host


def sanitize_model(name: str | None) -> str | None:
    if not isinstance(name, str):
        return None
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 64 or not MODEL_PATTERN.fullmatch(cleaned):
        return None
    return cleaned


def sanitize_provider(value: str | None, *, allow_asr: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    if key in TELEMETRY_PROVIDERS:
        return key
    if allow_asr and key in ASR_PROVIDERS:
        return key
    return None


def sanitize_upstream_error_type(value: str | UpstreamErrorType | None) -> str | None:
    if isinstance(value, UpstreamErrorType):
        return value.value
    if isinstance(value, str) and value in UPSTREAM_ERROR_TYPES:
        return value
    return None


def sanitize_llm_request_properties(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """``llm_request_finished`` 白名单。多出来的 key / 原文全部丢掉。"""
    return _sanitize(value, kind="request")


def sanitize_run_properties(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """run 级附加字段白名单。供后续挂到 generation / production 终态。"""
    return _sanitize(value, kind="run")


def sanitize_asr_readiness_properties(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return _sanitize(value, kind="asr")


def sanitize_provider_validation_properties(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return _sanitize(value, kind="validation")


def _sanitize(value: Mapping[str, Any] | None, *, kind: str) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    out: dict[str, Any] = {"success_rate_schema_version": SUCCESS_RATE_SCHEMA_VERSION}
    provider = sanitize_provider(
        _as_str(raw.get("provider")),
        allow_asr=kind == "asr",
    )
    if provider is not None:
        out["provider"] = provider
    model = sanitize_model(_as_str(raw.get("model")))
    if model is not None and kind in {"request", "run"}:
        out["model"] = model
    host = hostname_of_base_url(_as_str(raw.get("base_url")) or _as_str(raw.get("base_url_host")))
    if host is None and isinstance(raw.get("base_url_host"), str):
        candidate = raw["base_url_host"].strip().lower()
        if candidate == "local" or _HOST_PATTERN.fullmatch(candidate):
            host = "local" if candidate == "local" or _is_local_host(candidate) else candidate
    if host is not None and kind in {"request", "run", "validation"}:
        out["base_url_host"] = host
    error_type = sanitize_upstream_error_type(raw.get("upstream_error_type") or raw.get("error_type"))
    if error_type is not None and kind in {"request", "run", "validation"}:
        out["upstream_error_type"] = error_type
    if kind == "request":
        _put_enum(out, raw, "kind", REQUEST_KINDS)
        _put_enum(out, raw, "stage", FAILURE_STAGES)
        _put_enum(out, raw, "outcome", REQUEST_OUTCOMES)
        _put_enum(out, raw, "finish_reason", FINISH_REASONS)
        _put_http_status(out, raw.get("http_status"), minimum=100)
        for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "retry_count", "duration_ms"):
            _put_count(out, raw, key)
    elif kind == "run":
        _put_enum(out, raw, "failure_stage", FAILURE_STAGES)
        _put_http_status(out, raw.get("http_status"), minimum=400)
        for key in (
            "llm_calls", "prompt_tokens", "completion_tokens", "reasoning_tokens",
            "retry_count", "billable_calls_before_failure",
        ):
            _put_count(out, raw, key)
    elif kind == "asr":
        _put_enum(out, raw, "code", None, pattern=re.compile(r"^[a-z][a-z0-9_]{1,64}$"))
        _put_bool(out, raw, "has_subtitle")
        _put_bool(out, raw, "blocked")
    else:
        _put_enum(out, raw, "result", VALIDATION_RESULTS)
    return out


def _looks_like_secret(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _is_local_host(host: str) -> bool:
    if host in _LOCAL_HOSTS or host.endswith(".local") or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _put_enum(
    out: dict[str, Any],
    raw: Mapping[str, Any],
    key: str,
    allowed: frozenset[str] | None,
    *,
    pattern: re.Pattern[str] | None = None,
) -> None:
    value = raw.get(key)
    if not isinstance(value, str):
        return
    if allowed is not None and value in allowed:
        out[key] = value
    elif pattern is not None and pattern.fullmatch(value):
        out[key] = value


def _put_count(out: dict[str, Any], raw: Mapping[str, Any], key: str) -> None:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return
    if isinstance(value, float) and not value.is_integer():
        return
    number = int(value)
    if number >= 0:
        out[key] = number


def _put_http_status(out: dict[str, Any], value: Any, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        return
    if minimum <= value <= 599:
        out["http_status"] = value


def _put_bool(out: dict[str, Any], raw: Mapping[str, Any], key: str) -> None:
    if isinstance(raw.get(key), bool):
        out[key] = raw[key]


_EMITTERS = frozenset({
    "request_finished",
    "observe_provider_call",
    "emit_vision_request",
    "emit_asr_readiness_checked",
    "emit_provider_validation_finished",
    "run_snapshot",
    "configured_connection_fields",
    "sentry_tags_for_error",
    "bind_context",
    "track_run",
    "set_retry_count",
    "reset_retry_count",
    "current_retry_count",
    "normalize_failure_stage",
    "classify_run_upstream",
})


def __getattr__(name: str):
    """Line A emitters live in ``llm_emit`` so this module stays a schema for step-0 tests."""
    if name in _EMITTERS:
        from backend.core import llm_emit
        return getattr(llm_emit, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
