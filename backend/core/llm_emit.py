"""Line A emitters for 1.5.8 success-rate events.

Schema and sanitizers stay in ``llm_telemetry``; classification stays in
``upstream_errors``. This module only posts allowlisted properties.
Keys, prompts, captions and full URLs never become event fields.
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from backend.core import llm_telemetry as schema
from backend.core.upstream_errors import UpstreamErrorType, classify_upstream_error, http_error_parts

logger = logging.getLogger(__name__)

_retry_count: contextvars.ContextVar[int] = contextvars.ContextVar("llm_retry_count", default=0)
_call_ctx: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("llm_call_ctx", default=None)
_run_acc: contextvars.ContextVar[_RunAcc | None] = contextvars.ContextVar("llm_run_acc", default=None)

_PROVIDER_ALIASES = {
    "siliconflow": "compatible",
    "88api": "api88",
    "88api.ai": "api88",
    "api.88api.ai": "api88",
    "unknown": "other",
}
_STAGE_ALIASES = {
    "INGEST": "ingest",
    "SUBTITLE": "subtitle",
    "ANALYZE": "analyze",
    "HIGHLIGHT": "analyze",
    "EXPORT": "render",
    "DONE": "render",
    "rendering": "render",
    "analysis": "analyze",
    "visual_analysis": "vision",
    "ai_cover": "other",
    "packaging": "render",
}
_OUTCOME_ALIASES = {
    "completed": "success",
    "ok": "success",
    "success": "success",
    "failed": "error",
    "error": "error",
}
_RESULT_ALIASES = {
    "ok": "success",
    "success": "success",
    "failed": "failed",
    "skipped": "skipped",
}


@dataclass
class _RunAcc:
    provider: str = ""
    model: str = ""
    host: str = ""
    calls: int = 0
    billable: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    last_retry: int = 0
    last_http_status: int | None = None
    last_upstream: str | None = None
    last_outcome: str = ""
    last_stage: str = ""


def normalize_failure_stage(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    mapped = _STAGE_ALIASES.get(value) or _STAGE_ALIASES.get(value.upper()) or value
    return mapped if mapped in schema.FAILURE_STAGES else None


def classify_run_upstream(error: BaseException | None, http_status: int | None = None) -> str | None:
    """Run-level / Sentry tag. Skip unknown and timeout/connection without HTTP.

    Site refusals must be filtered by the caller (``source_blocked`` is not an
    upstream model error). TimeoutError without a status stays a local code.
    ``http_status`` is the already-walked status from ``http_status_of`` so a
    ``PipelineFailure`` wrapper still classifies the provider 5xx/429.
    """
    status = http_status
    body = None
    error_name = None
    if error is not None:
        found_status, body = http_error_parts(error)
        status = status or found_status
        error_name = type(error).__name__
    if status is None and error is None:
        return None
    classified = classify_upstream_error(status, body, error_name=error_name)
    kind = classified.error_type.value
    if kind == UpstreamErrorType.UNKNOWN.value:
        return None
    if status is None and kind in {
        UpstreamErrorType.TIMEOUT.value,
        UpstreamErrorType.CONNECTION.value,
    }:
        return None
    return schema.sanitize_upstream_error_type(kind)


def set_retry_count(value: int) -> contextvars.Token:
    return _retry_count.set(_count(value, 32))


def reset_retry_count(token: contextvars.Token) -> None:
    _retry_count.reset(token)


def current_retry_count() -> int:
    return _count(_retry_count.get(), 32)


@contextmanager
def bind_context(*, provider: str = "", model: str = "", base_url: str = "", kind: str = "text"):
    token = _call_ctx.set({
        "provider": _provider_name(provider) or "",
        "model": _safe_model(model) or "",
        "base_url": base_url or "",
        "kind": kind if kind in schema.REQUEST_KINDS else "text",
    })
    try:
        yield
    finally:
        _call_ctx.reset(token)


@contextmanager
def track_run():
    token = _run_acc.set(_RunAcc())
    try:
        yield
    finally:
        _run_acc.reset(token)


def request_finished(
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    kind: str = "text",
    stage: str | None = None,
    http_status: int | None = None,
    upstream_error_type: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    retries: int | None = None,
    duration_ms: int | float = 0,
    outcome: str = "success",
    finish_reason: str | None = None,
    failure_stage: str | None = None,
    error: BaseException | None = None,
) -> dict[str, Any]:
    """Sanitize one request, update the run accumulator, and post llm_request_finished."""
    try:
        properties = _request_properties(
            provider=provider, model=model, base_url=base_url, kind=kind, stage=stage,
            http_status=http_status, upstream_error_type=upstream_error_type,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens, retries=retries, duration_ms=duration_ms,
            outcome=outcome, finish_reason=finish_reason, failure_stage=failure_stage,
            error=error,
        )
        _remember_run(properties)
        _post_event(schema.EVENT_LLM_REQUEST_FINISHED, properties)
        return properties
    except Exception:  # noqa: BLE001 - telemetry must not break a model call
        logger.warning("llm_request_finished was not recorded")
        return {}


def observe_provider_call(provider: Any, impl: Any, prompt: str, input_data: Any = None, **kwargs: Any):
    """Wrap LLMProvider.call. ``prompt`` / ``input_data`` stay in the callee only."""
    started = time.monotonic()
    base_url = _provider_base_url(provider)
    model = getattr(provider, "model_name", None)
    name = _provider_label(provider, base_url)
    try:
        response = impl(provider, prompt, input_data, **kwargs)
    except Exception as error:
        request_finished(
            provider=name, model=model, base_url=base_url, kind="text",
            stage=_current_stage(), http_status=_http_status(error), error=error,
            retries=current_retry_count(), duration_ms=_elapsed_ms(started),
            outcome="error", failure_stage=_current_stage() or "analyze",
        )
        raise
    usage = getattr(response, "usage", None) if response is not None else None
    prompt_tokens, completion_tokens, reasoning_tokens = _tokens_from_usage(usage)
    request_finished(
        provider=name, model=model, base_url=base_url, kind="text",
        stage=_current_stage(), http_status=200,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens, retries=current_retry_count(),
        duration_ms=_elapsed_ms(started), outcome="success",
        finish_reason=getattr(response, "finish_reason", None),
    )
    return response


def emit_vision_request(
    *,
    config: dict | None,
    started: float,
    error: BaseException | None = None,
    result: Any = None,
    retries: int = 0,
) -> dict[str, Any]:
    """vision_call success and failure both go through here."""
    try:
        config = config or {}
        usage = result.get("usage") if isinstance(result, dict) else None
        prompt_tokens, completion_tokens, reasoning_tokens = _tokens_from_usage(usage)
        finish_reason = None
        if isinstance(result, dict):
            try:
                finish_reason = ((result.get("choices") or [{}])[0] or {}).get("finish_reason")
            except (TypeError, IndexError, AttributeError):
                finish_reason = None
        outcome = "error" if error is not None else "success"
        fields = _vision_connection_fields(config)
        return request_finished(
            provider=fields.get("provider"),
            model=config.get("model") or fields.get("model"),
            base_url=config.get("base_url"),
            kind="vision",
            stage=_current_stage() or "vision",
            error=error,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            retries=retries,
            duration_ms=_elapsed_ms(started),
            outcome=outcome,
            finish_reason=finish_reason,
            failure_stage=(_current_stage() or "vision") if outcome == "error" else None,
            http_status=_http_status(error) if error is not None else 200,
        )
    except Exception:  # noqa: BLE001 - telemetry must not break vision_call
        logger.warning("vision llm_request_finished was not recorded")
        return {}


def emit_asr_readiness_checked(
    *,
    provider: str | None = None,
    code: str | None = None,
    has_subtitle: bool = False,
    blocked: bool | None = None,
) -> dict[str, Any]:
    """asr_readiness_checked. Frontend also emits this; backend covers API/MCP/old UI."""
    try:
        if provider is None or code is None or blocked is None:
            check = _transcription_check()
            code = code or check.get("code")
            provider = provider or check.get("provider") or _asr_provider_from_code(code)
            if blocked is None:
                blocked = (check.get("ok") is False) and not has_subtitle
        properties = schema.sanitize_asr_readiness_properties({
            "provider": _asr_provider_from_code(code, provider),
            "code": code,
            "has_subtitle": bool(has_subtitle),
            "blocked": bool(blocked),
        })
        _post_event(schema.EVENT_ASR_READINESS_CHECKED, properties)
        return properties
    except Exception:  # noqa: BLE001
        logger.warning("asr_readiness_checked was not recorded")
        return {}


def emit_provider_validation_finished(
    *,
    provider: str | None = None,
    base_url: str | None = None,
    result: str = "failed",
    error_type: str | None = None,
    error: BaseException | None = None,
) -> dict[str, Any]:
    """Reserved hook for settings-page validation (line B). Line A only exposes the emitter."""
    try:
        raw = {
            "provider": _provider_name(provider),
            "base_url": base_url,
            "result": _RESULT_ALIASES.get(str(result or ""), "failed"),
            "upstream_error_type": (
                schema.sanitize_upstream_error_type(error_type)
                or classify_run_upstream(error)
            ),
        }
        properties = schema.sanitize_provider_validation_properties(raw)
        _post_event(schema.EVENT_PROVIDER_VALIDATION_FINISHED, properties)
        return properties
    except Exception:  # noqa: BLE001
        logger.warning("provider_validation_finished was not recorded")
        return {}


def run_snapshot(project_id: str | None = None) -> dict[str, Any]:
    """Sanitized run-level fields for generation / production / Sentry tags."""
    acc = _run_acc.get()
    # Settings are a last-saved identity, not this run. Only fill gaps inside track_run.
    configured = configured_connection_fields() if acc is not None else {}
    usage_total = _usage_total(project_id)
    provider = (acc.provider if acc and acc.provider else None) or configured.get("provider")
    model = _safe_model((acc.model if acc and acc.model else None) or configured.get("model"))
    host = (acc.host if acc and acc.host else None) or configured.get("base_url_host")
    raw: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "base_url_host": host,
        "http_status": acc.last_http_status if acc else None,
        "upstream_error_type": acc.last_upstream if acc else None,
        "billable_calls_before_failure": acc.billable if acc else usage_total.get("calls") or 0,
    }
    calls = usage_total.get("calls") or (acc.calls if acc else 0)
    if calls:
        raw["llm_calls"] = calls
    prompt = usage_total.get("prompt_tokens") or (acc.prompt_tokens if acc else 0)
    if prompt:
        raw["prompt_tokens"] = prompt
    completion = usage_total.get("completion_tokens") or (acc.completion_tokens if acc else 0)
    if completion:
        raw["completion_tokens"] = completion
    if acc and acc.reasoning_tokens:
        raw["reasoning_tokens"] = acc.reasoning_tokens
    retry = acc.last_retry if acc else 0
    if retry:
        raw["retry_count"] = retry
    if acc and acc.last_outcome == "error":
        raw["failure_stage"] = normalize_failure_stage(acc.last_stage)
    out = schema.sanitize_run_properties(raw)
    out.pop("success_rate_schema_version", None)
    return {key: value for key, value in out.items() if value not in (None, "", 0) or key == "billable_calls_before_failure"}


def configured_connection_fields(*, role: str = "analysis") -> dict[str, Any]:
    """Current analysis/vision connection without keys or full URLs."""
    try:
        from backend.services import ai_model_settings as ai
        settings = ai.load()
        if not settings:
            return {}
        binding = settings.vision if role == "vision" and getattr(settings, "vision", None) else settings.analysis
        if not binding:
            return {}
        connection = ai.connection_for(settings, binding)
        endpoint = ai.chat_endpoint(connection, binding.model)
        return schema.sanitize_run_properties({
            "provider": _provider_name(connection.provider),
            "model": _safe_model(binding.model),
            "base_url": endpoint.get("base_url"),
        })
    except Exception:  # noqa: BLE001 - settings must not break a finish write
        return {}


def sentry_tags_for_error(error: BaseException | None, phase: str) -> dict[str, str]:
    """Allowlisted string tags only."""
    tags: dict[str, str] = {}
    snapshot = run_snapshot()
    if error is not None:
        kind = classify_run_upstream(error, _http_status(error))
        if kind:
            snapshot["upstream_error_type"] = kind
        status = _http_status(error)
        if status is not None and 400 <= status <= 599:
            snapshot["http_status"] = status
    stage = normalize_failure_stage(snapshot.get("failure_stage") or phase)
    if stage:
        tags["failure_stage"] = stage
    for key in ("provider", "upstream_error_type", "base_url_host", "model"):
        value = snapshot.get(key)
        if not isinstance(value, str) or not value:
            continue
        if key == "model" and (not schema.MODEL_PATTERN.fullmatch(value) or "sk-" in value.lower()):
            continue
        if key == "base_url_host":
            if value != "local" and schema.hostname_of_base_url(value) != value:
                continue
        if key == "provider" and value not in schema.TELEMETRY_PROVIDERS:
            continue
        if key == "upstream_error_type" and schema.sanitize_upstream_error_type(value) is None:
            continue
        tags[key] = value
    status = snapshot.get("http_status")
    if isinstance(status, int) and 400 <= status <= 599:
        tags["http_status"] = str(status)
    return tags


def _request_properties(
    *, provider, model, base_url, kind, stage, http_status, upstream_error_type,
    prompt_tokens, completion_tokens, reasoning_tokens, retries, duration_ms,
    outcome, finish_reason, failure_stage, error,
) -> dict[str, Any]:
    ctx = _call_ctx.get() or {}
    status = http_status if isinstance(http_status, int) else None
    if status is None and error is not None:
        status = _http_status(error)
    outcome_value = _OUTCOME_ALIASES.get(str(outcome or ""), "error")
    upstream = schema.sanitize_upstream_error_type(upstream_error_type)
    if upstream is None and (error is not None or status is not None):
        upstream = classify_run_upstream(error, status)
    raw = {
        "provider": _provider_name(provider or ctx.get("provider")),
        "model": _safe_model(model or ctx.get("model")),
        "base_url": base_url or ctx.get("base_url"),
        "kind": kind if kind in schema.REQUEST_KINDS else (ctx.get("kind") or "text"),
        "stage": normalize_failure_stage(stage or _current_stage()) or "other",
        "http_status": status,
        "upstream_error_type": upstream,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "retry_count": retries if retries is not None else current_retry_count(),
        "duration_ms": duration_ms,
        "outcome": outcome_value,
        "finish_reason": finish_reason,
    }
    properties = schema.sanitize_llm_request_properties(raw)
    if properties.get("outcome") == "error":
        failed_stage = normalize_failure_stage(failure_stage or stage or _current_stage()) or "analyze"
        properties["failure_stage"] = failed_stage
    return properties


def _remember_run(properties: dict[str, Any]) -> None:
    acc = _run_acc.get()
    if acc is None:
        return
    acc.calls += 1
    acc.provider = properties.get("provider") or acc.provider
    acc.model = properties.get("model") or acc.model
    acc.host = properties.get("base_url_host") or acc.host
    acc.last_retry = int(properties.get("retry_count") or 0)
    status = properties.get("http_status")
    acc.last_http_status = status if isinstance(status, int) else acc.last_http_status
    acc.last_upstream = properties.get("upstream_error_type") or acc.last_upstream
    acc.last_outcome = str(properties.get("outcome") or "")
    acc.last_stage = str(properties.get("failure_stage") or properties.get("stage") or "")
    acc.prompt_tokens += int(properties.get("prompt_tokens") or 0)
    acc.completion_tokens += int(properties.get("completion_tokens") or 0)
    acc.reasoning_tokens += int(properties.get("reasoning_tokens") or 0)
    if properties.get("outcome") == "success":
        acc.billable += 1


def _post_event(event: str, properties: dict[str, Any]) -> None:
    from backend.core.event_catalog import envelope_properties, validate_event
    from backend.services.studio.qa import telemetry as qa_telemetry
    key = qa_telemetry._key()
    if not key or not qa_telemetry._analytics_allowed():
        return
    blob = json.dumps(properties, ensure_ascii=False)
    if "sk-" in blob.lower() or "authorization" in blob.lower():
        logger.warning("refusing to post an event that looks like it contains a secret")
        return
    posted = {
        **properties,
        **envelope_properties(),
        "studio_schema_version": 2,
    }
    problems = validate_event(event, posted, envelope=True)
    if problems:
        logger.warning("%s failed catalog checks: %s", event, "; ".join(problems))
    body = json.dumps({
        "api_key": key,
        "event": event,
        "distinct_id": qa_telemetry.anonymous_distinct_id(),
        "properties": posted,
    }).encode()
    request = urllib.request.Request(
        f"{qa_telemetry._HOST}/capture/", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=1.5):
            return
    except (OSError, TypeError, ValueError, urllib.error.URLError):
        logger.warning("%s was not delivered", event)


def _current_stage() -> str:
    try:
        from backend.core import llm_usage
        return normalize_failure_stage(llm_usage._stage.get()) or "other"
    except Exception:  # noqa: BLE001
        return "other"


def _elapsed_ms(started: float) -> int:
    try:
        elapsed = int((time.monotonic() - started) * 1000)
    except Exception:  # noqa: BLE001 - patched clocks in tests must not fail the caller
        return 0
    return max(0, min(3_600_000, elapsed))


def _tokens_from_usage(usage: Any) -> tuple[int | None, int | None, int | None]:
    if not isinstance(usage, dict):
        return None, None, None
    prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
    completion = usage.get("completion_tokens", usage.get("output_tokens"))
    details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), dict) else {}
    reasoning = usage.get("reasoning_tokens", details.get("reasoning_tokens") if details else None)

    def _one(value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = int(value)
        return number if number >= 0 else None

    return _one(prompt), _one(completion), _one(reasoning)


def _provider_base_url(provider: Any) -> str:
    url = getattr(provider, "base_url", None) or ""
    if url:
        return str(url)
    name = type(provider).__name__
    if name == "GeminiProvider":
        return "https://generativelanguage.googleapis.com"
    if name == "OpenAIProvider":
        from backend.core.llm_providers import OPENAI_OFFICIAL_BASE_URL
        return OPENAI_OFFICIAL_BASE_URL
    return ""


def _provider_label(provider: Any, base_url: str) -> str:
    ctx = _call_ctx.get() or {}
    bound = _provider_name(ctx.get("provider"))
    if bound and bound != "other":
        return bound
    name = type(provider).__name__
    if name == "DashScopeProvider":
        return "dashscope"
    if name == "GeminiProvider":
        return "gemini"
    if name == "SiliconFlowProvider":
        return "compatible"
    host = schema.hostname_of_base_url(base_url) or ""
    try:
        from backend.core.cloud_presets import CLOUD_PRESETS, is_api88_host
        if is_api88_host(host):
            return "api88"
        for key, preset in CLOUD_PRESETS.items():
            if schema.hostname_of_base_url(preset.base_url) == host:
                return _provider_name(key) or "other"
    except Exception:  # noqa: BLE001
        pass
    if host in {"api.openai.com", ""}:
        return "openai"
    if host.endswith("aliyuncs.com"):
        return "dashscope"
    if host == "local":
        return "ollama"
    return "compatible"


def _vision_connection_fields(config: dict) -> dict[str, Any]:
    fields = configured_connection_fields(role="vision")
    if config.get("model") and not fields.get("model"):
        model = _safe_model(config.get("model"))
        if model:
            fields["model"] = model
    host = schema.hostname_of_base_url(config.get("base_url") if isinstance(config.get("base_url"), str) else None)
    if host:
        fields["base_url_host"] = host
    return fields


def _transcription_check() -> dict[str, Any]:
    try:
        from backend.services.studio.readiness import report
        check = (report().get("checks") or {}).get("transcription") or {}
        return check if isinstance(check, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _asr_provider_from_code(code: Any, provider: Any = None) -> str:
    named = schema.sanitize_provider(str(provider or "").strip().lower(), allow_asr=True)
    if named:
        return named
    text = str(code or "")
    if text.startswith("sensevoice"):
        return "sensevoice_local"
    if text.startswith("cloud"):
        return "cloud"
    return "whisper_local"


def _usage_total(project_id: str | None) -> dict[str, int]:
    if not project_id:
        return {}
    try:
        from backend.core import llm_usage
        total = llm_usage.summary(project_id).get("total") or {}
        return {key: int(total[key]) for key in ("calls", "prompt_tokens", "completion_tokens") if key in total}
    except Exception:  # noqa: BLE001
        return {}


def _safe_model(value: Any) -> str | None:
    cleaned = schema.sanitize_model(value if isinstance(value, str) else None)
    if cleaned and "sk-" in cleaned.lower():
        return None
    return cleaned


def _provider_name(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    text = _PROVIDER_ALIASES.get(text, text)
    return schema.sanitize_provider(text)


def _http_status(error: BaseException | None) -> int | None:
    if error is None:
        return None
    from backend.pipeline.failures import http_status_of
    status = http_status_of(error)
    return status if isinstance(status, int) and 100 <= status <= 599 else None


def _count(value: Any, cap: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, min(cap, value))
