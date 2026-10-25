"""Line A emitters for 1.5.7 success-rate events.

Schema and sanitizers stay in ``llm_telemetry``; classification stays in
``upstream_errors``. This module only posts allowlisted properties.
Keys, prompts, captions and full URLs never become event fields.
"""
from __future__ import annotations

import contextvars
import itertools
import json
import logging
import sys
import threading
import time
from collections import deque
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from backend.core import llm_telemetry as schema
from backend.core.upstream_errors import UpstreamErrorType, classify_upstream_error, http_error_parts

logger = logging.getLogger(__name__)

_retry_count: contextvars.ContextVar[int] = contextvars.ContextVar("llm_retry_count", default=0)
# E2: highest retry index already counted for the logical call running in *this* context.
# Contextvars are per thread / task (run_in_context copies), so concurrent calls never share it.
_retry_peak: contextvars.ContextVar[int] = contextvars.ContextVar("llm_retry_peak", default=0)


def begin_logical_call() -> None:
    """Mark the start of one logical model call (all its attempts share one retry peak)."""
    _retry_peak.set(0)
# Run id only. The counter lives in ``_degrade_runs`` so ``copy_context()``
# (pipeline chunk workers) shares one lock-protected cell instead of forking an int.
_degrade_run_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("llm_degrade_run_id", default=None)
_call_ctx: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("llm_call_ctx", default=None)
_run_acc: contextvars.ContextVar[_RunAcc | None] = contextvars.ContextVar("llm_run_acc", default=None)
_DEGRADE_CAP = 32
_degrade_seq = itertools.count(1)
_degrade_registry_lock = threading.Lock()
_degrade_runs: dict[int, _DegradeAcc] = {}

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
class _DegradeAcc:
    count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


@dataclass(frozen=True)
class RequestRecord:
    """ONE immutable record per model request. provider/config_source come as a pair from
    the connection frozen at request start; model/host/status/upstream are that SAME request's. A failed
    request's record rides on its exception; persistence and Sentry read only it (never stitched)."""
    seq: int
    role: str
    provider: str = ""
    config_source: str = ""
    model: str | None = None
    base_url_host: str | None = None
    outcome: str = ""
    http_status: int | None = None
    upstream_error_type: str | None = None
    failure_stage: str | None = None

    def attribution(self) -> dict[str, Any]:
        if not (self.provider and self.config_source):
            return {}  # an incomplete identity is no identity: never fill a half from elsewhere
        out = {"provider": self.provider, "config_source": self.config_source, "model": self.model,
               "base_url_host": self.base_url_host, "http_status": self.http_status,
               "upstream_error_type": self.upstream_error_type, "failure_stage": self.failure_stage}
        return {k: v for k, v in out.items() if v not in (None, "")}


_RECORD_ATTR = "_autoclip_request_record"
ATTRIBUTION_SOURCE_REQUEST = "request"
ATTRIBUTION_SOURCE_PHASE = "phase"
ATTRIBUTION_SOURCE_LOCAL = "local"  # no provider is blamed
ATTRIBUTION_SOURCES = frozenset({ATTRIBUTION_SOURCE_REQUEST, ATTRIBUTION_SOURCE_PHASE, ATTRIBUTION_SOURCE_LOCAL})


def _attach_record(error: BaseException | None, record: RequestRecord) -> None:
    """The failing request's record travels WITH its exception (concurrent siblings cannot replace it)."""
    if error is None or isinstance(getattr(error, _RECORD_ATTR, None), RequestRecord):
        return
    try:
        setattr(error, _RECORD_ATTR, record)
    except (AttributeError, TypeError):  # exotic exception types without __dict__
        pass
    from backend.core.failure_attribution import with_request_record
    with_request_record(error, record)  # a redaction-boundary snapshot takes the request's identity


from backend.core.failure_attribution import chain as _chain, record_of  # noqa: E402,F401 - - one home


@dataclass
class _RunAcc:
    calls: int = 0
    billable: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    last_retry: int = 0  # run-level total retries (sum over logical calls)
    last_degrade: int = 0
    persisted_usage: dict = field(default_factory=dict)
    seq: int = 0
    # / identity the current phase froze at its start from ONE connection.
    phase_identity: dict = field(default_factory=dict)
    # E2: one run accumulator is shared by worker threads (run_in_context); guard mutations.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


def _request_upstream_fallback(error: BaseException | None, http_status: int | None) -> str:
    """Closed-set type for an error `llm_request_finished` that classify_run_upstream skipped.

    Unknown HTTP, a timeout or connection with no status, and an error that has
    neither an exception nor a status all still need a value. The body is not read.
    """
    name = type(error).__name__ if error is not None else None
    kind = classify_upstream_error(http_status, None, error_name=name).error_type.value
    return schema.sanitize_upstream_error_type(kind) or UpstreamErrorType.UNKNOWN.value


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


def increment_degrade_count() -> int:
    """Count one same-provider candidate fallback. calls this when switching models.

    Uses a lock-protected per-run cell. ``copy_context()`` (parallel chunks) only
    copies the run id, so two degrades cannot both write 1. Integer only — no
    model name, URL, or user text. Without a bound run, skip counting.
    """
    cell = _degrade_cell()
    if cell is None:
        return 0
    with cell.lock:
        cell.count = _count(cell.count + 1, _DEGRADE_CAP)
        value = cell.count
    _sync_last_degrade(value)
    return value


def set_degrade_count(value: int) -> contextvars.Token:
    counted = _count(value, _DEGRADE_CAP)
    existing = _degrade_run_id.get()
    cell, token = _bind_degrade_run()
    if cell is not None:
        with cell.lock:
            cell.count = counted
        _sync_last_degrade(counted)
    if token is None:
        token = _degrade_run_id.set(existing if existing is not None else _degrade_run_id.get())
    return token


def reset_degrade_count(token: contextvars.Token) -> None:
    leaving = _degrade_run_id.get()
    _degrade_run_id.reset(token)
    staying = _degrade_run_id.get()
    if leaving is not None and leaving != staying:
        with _degrade_registry_lock:
            _degrade_runs.pop(leaving, None)


def current_degrade_count() -> int:
    cell = _degrade_cell()
    if cell is None:
        return 0
    with cell.lock:
        return _count(cell.count, _DEGRADE_CAP)


def _degrade_cell() -> _DegradeAcc | None:
    run_id = _degrade_run_id.get()
    if run_id is None:
        return None
    with _degrade_registry_lock:
        return _degrade_runs.get(run_id)


def _bind_degrade_run() -> tuple[_DegradeAcc | None, contextvars.Token | None]:
    with _degrade_registry_lock:
        run_id = _degrade_run_id.get()
        if run_id is not None:
            # Same run id after copy_context(); do not allocate a second cell.
            # A missing cell means track_run already ended — do not resurrect.
            return _degrade_runs.get(run_id), None
        run_id = next(_degrade_seq)
        cell = _DegradeAcc()
        _degrade_runs[run_id] = cell
        return cell, _degrade_run_id.set(run_id)


def _sync_last_degrade(value: int) -> None:
    acc = _run_acc.get()
    if acc is None:
        return
    acc.last_degrade = max(acc.last_degrade, value)


@contextmanager
def bind_context(*, provider: str = "", model: str = "", base_url: str = "", kind: str = "text",
                 identity: dict | None = None):
    token = _call_ctx.set({
        "identity": dict(identity or {}),
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
    run_id = next(_degrade_seq)
    with _degrade_registry_lock:
        _degrade_runs[run_id] = _DegradeAcc()
    acc_token = _run_acc.set(_RunAcc())
    peak_token = _retry_peak.set(0)  # E2: a fresh worker never inherits a previous run's peak
    degrade_token = _degrade_run_id.set(run_id)
    try:
        yield
    finally:
        _run_acc.reset(acc_token)
        _retry_peak.reset(peak_token)
        _degrade_run_id.reset(degrade_token)
        with _degrade_registry_lock:
            _degrade_runs.pop(run_id, None)


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
    degrades: int | None = None,
    duration_ms: int | float = 0,
    outcome: str = "success",
    finish_reason: str | None = None,
    failure_stage: str | None = None,
    error: BaseException | None = None,
    identity: dict | None = None,
) -> dict[str, Any]:
    """Sanitize one request, update the run accumulator, and post llm_request_finished.

    ``identity`` is the request's connection identity frozen when the request STARTED."""
    try:
        properties = _request_properties(
            provider=provider, model=model, base_url=base_url, kind=kind, stage=stage,
            http_status=http_status, upstream_error_type=upstream_error_type,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens, retries=retries, degrades=degrades,
            duration_ms=duration_ms,
            outcome=outcome, finish_reason=finish_reason, failure_stage=failure_stage,
            error=error,
        )
        if not identity:
            # no frozen identity -> the config this request sent (one rule, never settings).
            from backend.services.studio.failure_identity import sent_identity
            identity = sent_identity(properties.get("provider"), base_url, properties.get("model"))
        _remember_run(properties, role="vision" if kind == "vision" else "analysis", identity=identity, error=error)
        _submit_event(schema.EVENT_LLM_REQUEST_FINISHED, properties)
        return properties
    except Exception:  # noqa: BLE001 - telemetry must not break a model call
        logger.warning("llm_request_finished was not recorded")
        return {}


def observe_provider_call(provider: Any, impl: Any, prompt: str, input_data: Any = None, **kwargs: Any):
    """Wrap LLMProvider.call. ``prompt`` / ``input_data`` stay in the callee only."""
    started = time.monotonic()
    # the identity of the route's own connection, frozen when the route was resolved (same
    # as vision). Never read settings here: a save between route and send must not move attribution.
    identity = dict((_call_ctx.get() or {}).get("identity") or {})
    base_url = _provider_base_url(provider)
    from backend.core.llm_degrade import bound_request_model
    model = bound_request_model(getattr(provider, "model_name", None))
    name = _provider_label(provider, base_url)
    if not identity:
        # no frozen identity -> the config this request actually sends; never settings.
        from backend.services.studio.failure_identity import sent_identity
        identity = sent_identity(name, base_url, model)
    try:
        response = impl(provider, prompt, input_data, **kwargs)
    except Exception as error:
        request_finished(
            provider=name, model=model, base_url=base_url, kind="text",
            stage=_current_stage(), http_status=_http_status(error), error=error,
            retries=current_retry_count(), duration_ms=_elapsed_ms(started),
            outcome="error", failure_stage=_current_stage() or "analyze", identity=identity,
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
        finish_reason=getattr(response, "finish_reason", None), identity=identity,
    )
    return response


def emit_vision_request(
    *,
    config: dict | None,
    started: float,
    error: BaseException | None = None,
    result: Any = None,
    retries: int = 0,
    identity: dict | None = None,
) -> dict[str, Any]:
    """vision_call success and failure both go through here. ``identity``: frozen at request start."""
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
        # one rule with text: frozen identity, else the config actually sent; never settings.
        identity = identity or config.get("identity") or sent_vision_identity(config)
        return request_finished(
            provider=identity.get("provider"),
            model=config.get("model"),
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
            identity=identity,
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
        _submit_event(schema.EVENT_ASR_READINESS_CHECKED, properties)
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
        _submit_event(schema.EVENT_PROVIDER_VALIDATION_FINISHED, properties)
        return properties
    except Exception:  # noqa: BLE001
        logger.warning("provider_validation_finished was not recorded")
        return {}


def run_usage_checkpoint() -> dict | None:
    """Worker-local usage already persisted; advance only after a successful write."""
    acc = _run_acc.get()
    return acc.persisted_usage if acc is not None else None


_held_failure: contextvars.ContextVar[BaseException | None] = contextvars.ContextVar("autoclip_held_failure", default=None)


@contextmanager
def failure_in_hand(error: BaseException | None):
    """a failure caught earlier (e.g. one goal's 503 while a later goal succeeded) stays the
    error that attribution reads for writes inside this block, so its request record is persisted."""
    token = _held_failure.set(error)
    try:
        yield
    finally:
        _held_failure.reset(token)


def failure_now() -> BaseException | None:
    """The failure in hand: the exception being handled, else one held past its except (#397)."""
    return sys.exc_info()[1] or _held_failure.get()


def attribution_snapshot(error: BaseException | None = None, *, failure_stage: str | None = None,
                         start_identity: dict | None = None, phase_identity: dict | None = None):
    """this run's failure-attribution snapshot, from THE factory
    (``failure_attribution.build_attribution``); this only supplies the error and the frozen phase.
    a redaction boundary that knows the connection its call used passes that identity
    (``phase_identity``, a provider/config_source pair); it wins over the run's frozen phase identity."""
    from backend.core.failure_attribution import _paired_identity, build_attribution
    if error is None:
        error = failure_now()  # 3.10; a failure held past its except
    phase: dict[str, Any] = _paired_identity(phase_identity)
    acc = _run_acc.get()
    if not phase and acc is not None:
        with acc.lock:
            phase = dict(acc.phase_identity)
    return build_attribution(error, phase_identity=phase, start_identity=start_identity,
                             failure_stage=failure_stage)


def attribution(error: BaseException | None = None) -> dict[str, Any]:
    """The snapshot as fields ({} when there is none), via THE serializer."""
    from backend.core.failure_attribution import export_attribution
    return export_attribution(attribution_snapshot(error))


from backend.core.failure_attribution import MODEL_ERROR_CODES  # noqa: E402,F401 - re-exported


def is_model_error(error: BaseException | None) -> bool:
    """a thin wrapper; the one rule is ``failure_attribution.classify_failure``."""
    from backend.core.failure_attribution import FailureKind, classify_failure
    return classify_failure(error).kind is FailureKind.MODEL


def run_snapshot(project_id: str | None = None, *, error: BaseException | None = None,
                 with_source: bool = False) -> dict[str, Any]:
    """Sanitized run-level fields for generation / production / Sentry tags. Identity fields come
    whole from ``attribution``; settings are never read."""
    from backend.core.failure_attribution import export_attribution
    acc = _run_acc.get()
    fields = export_attribution(attribution_snapshot(error))  # THE serializer, no field read off
    raw: dict[str, Any] = {
        "provider": fields.get("provider"),
        "model": _safe_model(fields.get("model")),
        "base_url_host": fields.get("base_url_host"),
        "config_source": fields.get("config_source"),
        "http_status": fields.get("http_status"),
        "upstream_error_type": fields.get("upstream_error_type"),
        "billable_calls_before_failure": acc.billable if acc else 0,
    }
    # Project usage is historical; track_run's accumulator belongs to this attempt only.
    calls = acc.calls if acc else 0
    if calls:
        raw["llm_calls"] = calls
    prompt = acc.prompt_tokens if acc else 0
    if prompt:
        raw["prompt_tokens"] = prompt
    completion = acc.completion_tokens if acc else 0
    if completion:
        raw["completion_tokens"] = completion
    if acc and acc.reasoning_tokens:
        raw["reasoning_tokens"] = acc.reasoning_tokens
    retry = acc.last_retry if acc else 0
    if retry:
        raw["retry_count"] = retry
    degrade = current_degrade_count()
    if acc:
        degrade = max(degrade, acc.last_degrade)
    if degrade:
        raw["degrade_count"] = degrade
    if acc is not None:
        raw.update(llm_calls=calls, prompt_tokens=prompt, completion_tokens=completion,
                   reasoning_tokens=acc.reasoning_tokens, retry_count=retry, degrade_count=degrade)
    if fields.get("failure_stage"):
        raw["failure_stage"] = normalize_failure_stage(fields["failure_stage"])
    out = schema.sanitize_run_properties(raw)
    out.pop("success_rate_schema_version", None)
    if not (out.get("provider") and out.get("config_source")):
        for key in ("provider", "config_source", "model", "base_url_host"):
            out.pop(key, None)  # a pair or nothing
    if with_source and fields.get("attribution_source"):
        out["attribution_source"] = fields["attribution_source"]
    return {key: value for key, value in out.items()
            if value not in (None, "", 0) or key == "billable_calls_before_failure"
            or (acc is not None and value == 0)}


def configured_connection_fields(*, role: str = "analysis") -> dict[str, Any]:
    """Current analysis/vision connection without keys or full URLs."""
    try:
        from backend.services import ai_model_settings as ai
        settings = ai.load()
        if not settings:
            return {}
        binding = settings.vision if role == "vision" and getattr(settings, "vision", None) else getattr(settings, "analysis", None)
        if not binding:
            return {}
        connection = next((c for c in settings.connections if c.id == binding.connection_id), None)
        if connection is None:
            return {}
        try:
            endpoint = ai.chat_endpoint(connection, binding.model)
        except Exception:  # noqa: BLE001 - identity does not need a usable endpoint
            endpoint = {}
        from backend.services.studio.failure_identity import connection_identity
        identity = connection_identity(connection, binding.model)  # the one identity rule
        return schema.sanitize_run_properties({
            **identity,
            "model": _safe_model(binding.model),
            "base_url": endpoint.get("base_url"),
        })
    except Exception:  # noqa: BLE001 - settings must not break a finish write
        return {}


def sentry_tags_for_error(error: BaseException | None, phase: str) -> dict[str, str]:
    """Allowlisted string tags only. read the failed request's record whole; the exception's
    own status is never pasted onto another request's identity."""
    from backend.core.failure_attribution import export_attribution
    tags: dict[str, str] = {}
    fields = export_attribution(attribution_snapshot(error))  # one snapshot; THE serializer
    stage = normalize_failure_stage(fields.get("failure_stage") or phase)
    if fields.get("attribution_source"):
        tags["attribution_source"] = fields["attribution_source"]  
    if stage:
        tags["failure_stage"] = stage
    values = {key: fields.get(key) for key in ("provider", "upstream_error_type", "base_url_host", "model")}
    for key, value in values.items():
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
    status = fields.get("http_status")
    if isinstance(status, int) and 400 <= status <= 599:
        tags["http_status"] = str(status)
    return tags


def _request_properties(
    *, provider, model, base_url, kind, stage, http_status, upstream_error_type,
    prompt_tokens, completion_tokens, reasoning_tokens, retries, degrades,
    duration_ms, outcome, finish_reason, failure_stage, error,
) -> dict[str, Any]:
    ctx = _call_ctx.get() or {}
    status = http_status if isinstance(http_status, int) else None
    if status is None and error is not None:
        status = _http_status(error)
    outcome_value = _OUTCOME_ALIASES.get(str(outcome or ""), "error")
    upstream = schema.sanitize_upstream_error_type(upstream_error_type)
    if upstream is None and (error is not None or status is not None):
        upstream = classify_run_upstream(error, status)
    # Run snapshots still omit unknown and a timeout/connection with no HTTP status
    # (those stay local). The request event itself always names a closed-set type.
    if outcome_value == "error" and upstream is None:
        upstream = _request_upstream_fallback(error, status)
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
        "degrade_count": degrades if degrades is not None else current_degrade_count(),
        "duration_ms": duration_ms,
        "outcome": outcome_value,
        "finish_reason": finish_reason,
    }
    properties = schema.sanitize_llm_request_properties(raw)
    if properties.get("outcome") == "error":
        failed_stage = normalize_failure_stage(failure_stage or stage or _current_stage()) or "analyze"
        properties["failure_stage"] = failed_stage
    return properties


def freeze_phase_identity(identity: dict | None) -> None:
    """the identity a phase froze at its start; run snapshots and Sentry use it until a
    request has run in this run accumulator."""
    acc = _run_acc.get()
    if acc is None:
        return
    from backend.services.studio.failure_identity import PHASE_KEY, frozen_phase
    identity = identity if isinstance(identity, dict) else {}
    # provider/source/model/host of the ONE connection the phase froze; {} when incomplete.
    whole = frozen_phase(identity.get(PHASE_KEY)) or frozen_phase(identity)
    with acc.lock:
        acc.phase_identity = whole


def _remember_run(properties: dict[str, Any], role: str = "analysis", identity: dict | None = None,
                 error: BaseException | None = None) -> None:
    from backend.services.studio.failure_identity import frozen
    pair = frozen(identity)
    status = properties.get("http_status")
    failed = properties.get("outcome") != "success"
    acc = _run_acc.get()
    seq = 0
    if acc is not None:
        with acc.lock:
            acc.seq += 1
            seq = acc.seq
    record = RequestRecord(
        seq=seq, role=role,
        provider=pair.get("provider", ""), config_source=pair.get("config_source", ""),
        model=properties.get("model") or None, base_url_host=properties.get("base_url_host") or None,
        outcome=str(properties.get("outcome") or ""),
        http_status=status if isinstance(status, int) else None,
        upstream_error_type=(properties.get("upstream_error_type") or None) if failed else None,
        failure_stage=(properties.get("failure_stage") or None) if failed else None,
    )
    if failed:
        _attach_record(error, record)
    if acc is None:
        return
    # E2: retries are counted per logical call. ``retry_count`` on a request is that call's
    # attempt index (text) or its own retry total (vision); only the rise above the peak
    # already counted for this call in this context is new. The peak lives in a contextvar,
    # so interleaved / concurrent calls in other threads never reset or inflate each other.
    retry = int(properties.get("retry_count") or 0)
    peak = _retry_peak.get()
    delta = 0
    if retry > peak:
        delta = retry - peak
        _retry_peak.set(retry)
    elif retry == 0:
        _retry_peak.set(0)
    with acc.lock:
        acc.calls += 1
        acc.last_retry += delta
        acc.last_degrade = max(acc.last_degrade, int(properties.get("degrade_count") or 0))
        acc.prompt_tokens += int(properties.get("prompt_tokens") or 0)
        acc.completion_tokens += int(properties.get("completion_tokens") or 0)
        acc.reasoning_tokens += int(properties.get("reasoning_tokens") or 0)
        if not failed:
            acc.billable += 1


# Non-terminal events only. Terminal studio events stay on terminal_outbox and call _post_event themselves.
_EVENT_LIMIT = 64
_events: deque = deque()
_events_guard = threading.Lock()
_events_wake = threading.Event()
_events_idle = threading.Event()
_events_idle.set()
_events_sending = False
_events_worker: threading.Thread | None = None


def _submit_event(event: str, properties: dict[str, Any], *, envelope: dict[str, Any] | None = None) -> bool:
    """Queue one non-terminal event. Returns when the item is queued, never when the network finishes."""
    from backend.services.studio.qa import telemetry as qa_telemetry
    if not qa_telemetry._key() or not qa_telemetry._analytics_allowed():
        return False
    try:
        blob = json.dumps(properties, ensure_ascii=False)
    except (TypeError, ValueError):
        return False
    if "sk-" in blob.lower() or "authorization" in blob.lower():
        logger.warning("refusing to post an event that looks like it contains a secret")
        return False
    global _events_worker
    with _events_guard:
        if len(_events) >= _EVENT_LIMIT:
            _events.popleft()
            logger.warning("llm event queue dropped the oldest item")
        _events.append((event, properties, envelope))
        _events_idle.clear()
        if _events_worker is None or not _events_worker.is_alive():
            _events_worker = threading.Thread(target=_drain_events, name="studio-llm-event", daemon=True)
            _events_worker.start()
    _events_wake.set()
    return True


def _drain_events() -> None:
    global _events_sending
    while True:
        with _events_guard:
            if _events:
                event, properties, envelope = _events.popleft()
                _events_sending = True
            else:
                _events_sending = False
                _events_idle.set()
                event = None
        if event is None:
            _events_wake.wait()
            _events_wake.clear()
            continue
        try:
            if envelope is None:
                _post_event(event, properties)
            else:
                _post_event(event, properties, envelope=envelope)
        except Exception:  # noqa: BLE001 - a telemetry failure must not kill the sender
            logger.warning("%s was not delivered", event)
        finally:
            with _events_guard:
                _events_sending = False
                if not _events:
                    _events_idle.set()


def wait_until_idle(timeout: float = 3) -> bool:
    """Test helper: block until queued non-terminal events have been handed to the sender."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with _events_guard:
            if not _events and not _events_sending:
                return True
        _events_idle.wait(0.02)
    with _events_guard:
        return not _events and not _events_sending


class Rejected(Exception):
    """The capture endpoint refused this payload. 408 and 429 are not refusals."""


def _post_event(event: str, properties: dict[str, Any], *, envelope: dict[str, Any] | None = None,
                timestamp: str | None = None) -> bool:
    from backend.core.event_catalog import envelope_properties, validate_event
    from backend.services.studio.qa import telemetry as qa_telemetry
    key = qa_telemetry._key()
    if not key or not qa_telemetry._analytics_allowed():
        return False
    blob = json.dumps(properties, ensure_ascii=False)
    if "sk-" in blob.lower() or "authorization" in blob.lower():
        logger.warning("refusing to post an event that looks like it contains a secret")
        return False
    posted = {
        **properties,
        **(envelope if envelope is not None else envelope_properties()),
        "studio_schema_version": 2,
    }
    problems = validate_event(event, posted, envelope=True)
    if problems:
        logger.warning("%s failed catalog checks: %s", event, "; ".join(problems))
    payload = {
        "api_key": key,
        "event": event,
        "distinct_id": qa_telemetry.anonymous_distinct_id(),
        "properties": posted,
    }
    if timestamp:
        payload["timestamp"] = timestamp
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{qa_telemetry._HOST}/capture/", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=1.5):
            return True
    except urllib.error.HTTPError as error:
        status = int(getattr(error, "code", 0) or 0)
        if 400 <= status < 500 and status not in (408, 429):
            logger.warning("%s was rejected", event)
            raise Rejected(status) from None
        logger.warning("%s was not delivered", event)
        return False
    except (OSError, TypeError, ValueError, urllib.error.URLError):
        logger.warning("%s was not delivered", event)
        return False


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
        return "siliconflow"
    host = schema.hostname_of_base_url(base_url) or ""
    try:
        # the provider catalog is the only slug source (no private alias table here).
        from backend.core.cloud_presets import is_api88_host
        from backend.core.provider_presets import iter_providers
        if is_api88_host(host):
            return "api88"
        for preset in iter_providers():
            if host and preset.base_url and schema.hostname_of_base_url(preset.base_url) == host:
                return _provider_name(preset.id) or "other"
    except Exception:  # noqa: BLE001
        pass
    if host in {"api.openai.com", ""}:
        return "openai"
    if host.endswith("aliyuncs.com"):
        return "dashscope"
    if host == "local":
        return "ollama"
    return "compatible"


def sent_vision_identity(config: dict | None) -> dict:
    """identity of the vision config actually sent (no settings read)."""
    config = config or {}
    from backend.services.studio.failure_identity import sent_identity
    base = config.get("base_url") if isinstance(config.get("base_url"), str) else ""
    label = config.get("provider") or _provider_label(object(), base)
    return sent_identity(label, base, config.get("model"))


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


def _safe_model(value: Any) -> str | None:
    cleaned = schema.sanitize_model(value if isinstance(value, str) else None)
    if cleaned and "sk-" in cleaned.lower():
        return None
    return cleaned


def _provider_name(value: Any) -> str | None:
    # Catalog ids + catalog aliases (provider_presets.json) via the shared sanitizer; nothing local.
    return schema.sanitize_provider(str(value or "").strip().lower())


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
