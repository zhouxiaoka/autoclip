"""
Sentry 崩溃上报。DSN 未配置或用户关闭时全程 no-op，不发网络请求。

桌面端 DSN 由 Rust 启动器注入（构建时 SENTRY_DSN）；Docker / 脚本模式读环境变量。
不含视频内容、字幕、API key；send_default_pii=False。
"""
from __future__ import annotations

import json
import tempfile
import threading
import logging
import os
import re
import subprocess
import sys
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_ANONYMOUS_ID = re.compile(r"^(?:[A-Fa-f0-9]{32}|[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12})$")

logger = logging.getLogger(__name__)

from backend.core.failure_codes import sentry_codes
STUDIO_ERROR_CODES = sentry_codes()
# Expected failures caused by the environment or by the user's own source (too short,
# no audio track): never sent to Sentry, still recorded locally with their code.
UNREPORTED_STUDIO_ERROR_CODES = {"source_blocked", "file_locked", "source_not_found", "source_too_short", "source_no_audio", "service_restarted"}
# Provider answers PostHog already records. They are not crashes.
# 500 is not in this set: a local model-download failure is tagged 500 and must still
# be reported. A provider 500 carries upstream_unavailable and is dropped by that tag.
EXPECTED_PROVIDER_HTTP = frozenset({401, 402, 403, 404, 408, 409, 429, 502, 503, 504})
EXPECTED_PROVIDER_UPSTREAM = frozenset({
    "invalid_key", "insufficient_quota", "permission_denied", "model_not_found",
    "bad_endpoint", "rate_limited", "upstream_unavailable", "output_truncated",
})
# Legacy import task kinds (backend.tasks.import_processing) with the same meaning.
UNREPORTED_IMPORT_FAILURE_KINDS = {"source-input"}
PIPELINE_STAGES = {"INGEST", "SUBTITLE", "ANALYZE", "HIGHLIGHT", "EXPORT", "DONE"}


def studio_error_code(error: Exception) -> str:
    from backend.core.project_cancellation import ServiceRestarted
    if type(error).__name__ == "JobDurationExceeded":
        return "timeout"
    if isinstance(error, ServiceRestarted):
        return 'service_restarted'
    from backend.services.studio.intelligence import VisionRequestError
    from backend.pipeline.failures import PipelineFailure
    if isinstance(error, (VisionRequestError, PipelineFailure)) and error.code in STUDIO_ERROR_CODES:
        return error.code
    from backend.core.failure_attribution import frozen_error_code
    frozen = frozen_error_code(error)  # the code a redaction boundary froze (timeout/connection)
    if frozen in STUDIO_ERROR_CODES:
        return frozen
    # Whisper model download (whisper_model_manager.ModelDownloadFailed). Duck-typed so
    # crash reporting does not import the downloader. The code is network / disk / corrupt / unexpected.
    if type(error).__name__ == "ModelDownloadFailed":
        code = getattr(error, "code", None)
        if isinstance(code, str) and code in STUDIO_ERROR_CODES:
            return code
    # Local render, frame sampling and optional-runtime preparation use typed subprocess timeouts.
    if isinstance(error, subprocess.TimeoutExpired):
        return "timeout"
    from backend.core.file_lock import LockTimeout
    if isinstance(error, LockTimeout):
        return "store_lock_timeout"  # a local product failure, never a model timeout
    # Text rewrite/translation call the SDK directly, without a pipeline wrapper.
    # Recognize its typed failures; unrelated filesystem/programming errors stay unexpected.
    try:
        from openai import APIError
    except ImportError:
        APIError = ()
    if isinstance(error, APIError):
        from backend.pipeline.failures import model_call_error_code
        return model_call_error_code(error)
    if isinstance(error, FileNotFoundError):
        return "missing_resource"
    from backend.core.failure_attribution import ModelResponseInvalid
    if isinstance(error, ModelResponseInvalid):
        return ModelResponseInvalid.error_code  # 200 + content failed validation -> a model code
    # A blank or unreadable model body (api88 and other gateways) is not a bad
    # user input. "validation" would tell them to change the video.
    if _empty_model_reply(error):
        return "invalid_response"
    if isinstance(error, ValueError):
        return "validation"
    return "unexpected"


_EMPTY_MODEL_REPLY = frozenset({
    "empty completion",
    "invalid completion",
    "completion was not an object",
    "choices",
})


def _empty_model_reply(error: Exception) -> bool:
    return str(error).strip().lower() in _EMPTY_MODEL_REPLY


_PIPELINE_FAILURE_STAGES = {"INGEST": "ingest", "SUBTITLE": "subtitle", "ANALYZE": "analyze",
                            "HIGHLIGHT": "analyze", "EXPORT": "render"}


def studio_failure_context(error: Exception, phase: str) -> dict:
    """Where an automatic run failed and, for a MODEL failure only, the provider HTTP status/upstream type
    without messages or URLs. Built by THE snapshot factory (failure_attribution.build_attribution)."""
    from backend.services.studio.intelligence import VisionRequestError
    from backend.pipeline.failures import PipelineFailure
    from backend.core.failure_attribution import build_attribution, export_attribution
    stage = phase
    if isinstance(error, PipelineFailure):
        stage = _PIPELINE_FAILURE_STAGES.get(error.stage, phase)
    elif isinstance(error, VisionRequestError) and phase != "screening":
        stage = "vision"
    snap = build_attribution(error, failure_stage=stage)
    fields = export_attribution(snap)  # THE serializer
    return {k: fields[k] for k in ("failure_stage", "http_status", "upstream_error_type") if k in fields} or {"failure_stage": stage}


PRIVACY_FILE = "privacy.json"
_initialized = False


def _privacy_path() -> Optional[Path]:
    raw = os.getenv("AUTOCLIP_APP_DIR") or os.getenv("AUTOCLIP_DATA_DIR")
    if raw:
        return Path(raw).expanduser() / PRIVACY_FILE
    from backend.core.path_utils import get_data_directory
    return get_data_directory() / PRIVACY_FILE


def crash_reports_enabled() -> bool:
    """设置页「崩溃报告」写入 privacy.json；缺省为开。"""
    path = _privacy_path()
    if path is None or not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("crash_reports", True))
    except Exception:  # noqa: BLE001
        return False


_privacy_lock = threading.Lock()


def write_privacy(*, crash_reports: Optional[bool] = None, analytics: Optional[bool] = None) -> Path:
    """Single writer: only the backend API process writes privacy.json (settings endpoints);
    worker processes only read it.
    atomic (temp file + os.replace) so a concurrent reader never sees a
    truncated privacy.json; read-modify-write is serialized in-process. An unreadable
    existing file keeps collection OFF unless this call sets analytics explicitly."""
    path = _privacy_path()
    if path is None:
        raise RuntimeError("未设置 AUTOCLIP_APP_DIR / AUTOCLIP_DATA_DIR，写不了隐私开关")
    with _privacy_lock:
        current: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                current = loaded if isinstance(loaded, dict) else {"analytics": False, "crash_reports": False}
            except Exception:  # noqa: BLE001
                # corrupt file => analytics AND crash reports default off; only the
                # toggle named in this request changes below.
                current = {"analytics": False, "crash_reports": False}
        if crash_reports is not None:
            current["crash_reports"] = bool(crash_reports)
        if analytics is not None:
            current["analytics"] = bool(analytics)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".privacy-", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(current, ensure_ascii=False, indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return path


def _import_monitoring_fields(event: dict, hint: Optional[dict]) -> tuple[Optional[str], Optional[list[str]]]:
    """缺字幕 / 缺密钥要单独归组。

    before_send 会丢掉事件上原有的 tags 和 fingerprint，只留下异常类型。
    配置类失败如果仍都叫 ImportProcessingError，就会和未预期故障合成一条 issue。
    这里按异常类型写回稳定 tag；只有配置类失败覆盖 fingerprint。
    指纹里只有 kind，没有错误正文。
    """
    try:
        from backend.tasks.import_processing import (
            fingerprint_for_import_kind,
            import_failure_kind_for_type,
            kind_of_exception,
        )
    except Exception:
        logger.debug("导入失败分类不可用", exc_info=True)
        return None, None

    kind = None
    if hint:
        exc_info = hint.get("exc_info")
        if isinstance(exc_info, tuple) and len(exc_info) >= 2 and isinstance(exc_info[1], BaseException):
            kind = kind_of_exception(exc_info[1])
    if not kind:
        values = (event.get("exception") or {}).get("values") or []
        if values and isinstance(values[-1], dict):
            kind = import_failure_kind_for_type(str(values[-1].get("type") or ""))
    if not kind:
        return None, None
    return kind, fingerprint_for_import_kind(kind)


# CPython 3.13.13 Proactor teardown noise (PYTHON-FASTAPI-3 and the same callback).
# socket.shutdown / overlapped I/O on Windows surfaces these; none of them fail a task.
# 10054 WSAECONNRESET → ConnectionResetError (the published issue).
# 10053 WSAECONNABORTED → ConnectionAbortedError. 10052 WSAENETRESET and 10058 WSAESHUTDOWN
# stay OSError or ConnectionAbortedError. 109 ERROR_BROKEN_PIPE → BrokenPipeError.
# IocpProactor.finish_socket_func rewrites 64 ERROR_NETNAME_DELETED and 995
# ERROR_OPERATION_ABORTED into ConnectionResetError before they leave the proactor.
_PROACTOR_DISCONNECT_TYPES = frozenset({
    "ConnectionResetError",
    "ConnectionAbortedError",
    "BrokenPipeError",
})
_PROACTOR_DISCONNECT_WINERRORS = frozenset({64, 109, 995, 10052, 10053, 10054, 10058})


def _frame_is_proactor(filename: object, module: object) -> bool:
    name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    return module == "asyncio.proactor_events" or name == "proactor_events.py"


def _raised_value(event: dict) -> Optional[dict]:
    values = (event.get("exception") or {}).get("values") or []
    if values and isinstance(values[-1], dict):
        return values[-1]
    return None


def _frame_is_backend(filename: object, module: object) -> bool:
    if str(module or "").startswith("backend."):
        return True
    path = str(filename or "").replace("\\", "/")
    return path.startswith("backend/") or "/backend/" in f"/{path}"


def _event_frames(event: dict):
    value = _raised_value(event)
    if value is None:
        return
    for frame in (value.get("stacktrace") or {}).get("frames") or []:
        if isinstance(frame, dict):
            yield frame


def _event_has_proactor_frame(event: dict) -> bool:
    return any(
        _frame_is_proactor(frame.get("filename") or frame.get("abs_path"), frame.get("module"))
        for frame in _event_frames(event)
    )


def _event_has_backend_frame(event: dict) -> bool:
    return any(
        _frame_is_backend(frame.get("filename") or frame.get("abs_path"), frame.get("module"))
        for frame in _event_frames(event)
    )


def _traceback_has_proactor(exc: BaseException) -> bool:
    tb = exc.__traceback__
    while tb is not None:
        if _frame_is_proactor(tb.tb_frame.f_code.co_filename, ""):
            return True
        tb = tb.tb_next
    return False


def _traceback_has_backend(exc: BaseException) -> bool:
    tb = exc.__traceback__
    while tb is not None:
        if _frame_is_backend(tb.tb_frame.f_code.co_filename, ""):
            return True
        tb = tb.tb_next
    return False


def _is_harmless_proactor_disconnect(event: dict, hint: Optional[dict]) -> bool:
    """Drop peer-disconnect noise that never entered backend code.

    ConnectionResetError (WinError 10054), ConnectionAbortedError (10053) and
    BrokenPipeError (109) are ignored only when the stack is asyncio's Proactor
    and no backend frame is on it. The same types raised by application code,
    including a protocol failure that unwinds through the Proactor, are reported.
    Classification uses the exception class and winerror, never the message.
    """
    exc = None
    info = (hint or {}).get("exc_info") if hint else None
    if isinstance(info, tuple) and len(info) >= 2 and isinstance(info[1], BaseException):
        exc = info[1]
    value = _raised_value(event)
    type_name = str(value.get("type")) if value else ""
    typed = type_name in _PROACTOR_DISCONNECT_TYPES or isinstance(
        exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)
    )
    winerror = getattr(exc, "winerror", None) if isinstance(exc, OSError) else None
    coded = isinstance(winerror, int) and winerror in _PROACTOR_DISCONNECT_WINERRORS
    if not typed and not coded:
        return False
    on_proactor = _event_has_proactor_frame(event) or (exc is not None and _traceback_has_proactor(exc))
    if not on_proactor:
        return False
    if _event_has_backend_frame(event) or (exc is not None and _traceback_has_backend(exc)):
        return False
    return True


def before_send(event: dict, hint: Optional[dict] = None) -> Optional[dict]:
    """Recheck consent for every event, including long-running worker processes.

    Keep code locations, never arbitrary exception messages, request bodies,
    local variables, log messages or breadcrumbs (which may contain subtitles).
    """
    if not crash_reports_enabled():
        return None
    if _is_harmless_proactor_disconnect(event, hint):
        return None
    clean = {k: event[k] for k in (
        "event_id", "timestamp", "platform", "level", "release", "environment", "sdk"
    ) if k in event}
    values = []
    for value in event.get("exception", {}).get("values", []):
        frames = []
        for frame in value.get("stacktrace", {}).get("frames", []):
            safe = {k: frame[k] for k in ("function", "module", "lineno", "colno", "in_app") if k in frame}
            if frame.get("filename"):
                safe["filename"] = frame["filename"].replace("\\", "/").rsplit("/", 1)[-1]
            frames.append(safe)
        values.append({"type": value.get("type", "Error"), "value": "[message omitted for privacy]",
                       "stacktrace": {"frames": frames}})
    if not values:
        return None  # Logging-only payloads can contain video text; do not send them.
    if (event.get("tags") or {}).get("error_code") in UNREPORTED_STUDIO_ERROR_CODES:
        return None
    incoming = event.get("tags") or {}
    if _provider_expected(incoming.get("http_status"), incoming.get("upstream_error_type")):
        return None
    clean["exception"] = {"values": values}
    kind, fingerprint = _import_monitoring_fields(event, hint)
    if kind in UNREPORTED_IMPORT_FAILURE_KINDS:
        return None
    tags = event.get("tags") or {}
    from backend.core.llm_telemetry import (
        ASR_PROVIDERS, FAILURE_STAGES, MODEL_PATTERN, TELEMETRY_PROVIDERS,
        hostname_of_base_url,
    )
    from backend.core.upstream_errors import UPSTREAM_ERROR_TYPES
    allowed = {
        "area": {"studio"}, "error_code": STUDIO_ERROR_CODES,
        "phase": {"screening", "production", "render", "analysis", "dispatch", "vision_test", "rewrite", "auto_frame", "framing_install", "qa", "packaging_html", "packaging_runtime", "model_download"},
        "analysis_mode": {"subtitle", "visual"},
        "goal": {"content", "highlight", "promo"},
        "runtime": {"python"}, "app_mode": {"web", "desktop"},
        "os": {"macos", "windows", "linux", "unknown"},
        "arch": {"aarch64", "x86_64", "unknown"},
        "build_environment": {"production", "development", "validation", "unknown"},
        "telemetry_test": {"true"},
        "pipeline_stage": PIPELINE_STAGES,
        "upstream_error_type": UPSTREAM_ERROR_TYPES,
        "failure_stage": FAILURE_STAGES,
        "attribution_source": {"request", "phase", "local"},  
        "provider": TELEMETRY_PROVIDERS | ASR_PROVIDERS,
    }
    clean_tags = {key: value for key, value in tags.items()
                  if key in allowed and isinstance(value, str) and value in allowed[key]}
    model = tags.get("model")
    if isinstance(model, str) and MODEL_PATTERN.fullmatch(model) and "sk-" not in model.lower():
        clean_tags["model"] = model
    host = tags.get("base_url_host")
    if isinstance(host, str) and (host == "local" or hostname_of_base_url(host) == host):
        clean_tags["base_url_host"] = host
    status = tags.get("http_status")
    if isinstance(status, str) and status.isdigit() and 400 <= int(status) <= 599:
        clean_tags["http_status"] = status
    user_id = _event_distinct_id(event)
    if user_id:
        clean["user"] = {"id": user_id}
    if kind:
        clean_tags["import_failure"] = kind
    if clean_tags:
        clean["tags"] = clean_tags
    if clean_tags.get("area") == "studio" and clean_tags.get("error_code") in {"validation", "missing_resource", "authentication", "rate_limited", "refused", "llm_not_configured", "llm_auth_invalid", "whisper_not_installed", "whisper_install_failed", "transcription_empty", "subtitle_setup", "timeline_empty"}:
        clean["level"] = "warning"
        clean["fingerprint"] = ["studio", clean_tags.get("phase", "unknown"), clean_tags["error_code"]]
    if fingerprint:
        clean["fingerprint"] = fingerprint
    return clean


def _provider_expected(status: object, upstream: object) -> bool:
    """401/429/503 and the other provider answers belong in PostHog, not Sentry."""
    if isinstance(status, bool):
        status = None
    if isinstance(status, str) and status.isdigit():
        status = int(status)
    if isinstance(status, int) and status in EXPECTED_PROVIDER_HTTP:
        return True
    return isinstance(upstream, str) and upstream in EXPECTED_PROVIDER_UPSTREAM


# one machine stuck in a loop must not use up the project quota.
EVENTS_PER_FINGERPRINT_PER_HOUR = 5
# Sentry's project inbound filter is 120/day for this backend. Stay under it per device:
# the first 40 events of a UTC day are sent whole, then 1 in 10 until the hard stop.
DAILY_HARD_CAP = 120
DAILY_FULL_FIDELITY = 40
DAILY_SAMPLE_EVERY = 10
_DAILY_FILE = "sentry-daily.json"
_VOLUME_WINDOW_SECONDS = 3600.0
_VOLUME_MAX_KEYS = 512
# Polled by the UI every few seconds; one report per process is enough to locate the fault.
POLLING_FUNCTIONS = frozenset({"get_processing_status", "get_ai_models"})
_volume_lock = threading.Lock()
_volume_sent: "OrderedDict[tuple, deque]" = OrderedDict()
_polling_reported: set[str] = set()
_clock = time.monotonic


def _exception_frames(event: dict):
    for value in (event.get("exception") or {}).get("values") or []:
        for frame in (value.get("stacktrace") or {}).get("frames") or []:
            yield value, frame


def _polling_endpoint(event: dict) -> Optional[str]:
    for _value, frame in _exception_frames(event):
        if frame.get("function") in POLLING_FUNCTIONS and str(frame.get("module") or "").startswith("backend."):
            return frame["function"]
    return None


def _volume_key(event: dict) -> tuple:
    """Client-side stand-in for the issue fingerprint: explicit fingerprint, else
    exception types plus code locations (module/function, no line numbers, no text)."""
    fingerprint = event.get("fingerprint")
    if fingerprint:
        return ("fingerprint",) + tuple(str(part) for part in fingerprint)
    parts: list = []
    for value in (event.get("exception") or {}).get("values") or []:
        parts.append(str(value.get("type")))
        for frame in (value.get("stacktrace") or {}).get("frames") or []:
            parts.append((frame.get("module") or frame.get("filename"), frame.get("function")))
    return ("default",) + tuple(parts)


def _volume_allows(event: dict) -> bool:
    now = _clock()
    with _volume_lock:
        endpoint = _polling_endpoint(event)
        if endpoint is not None:
            if endpoint in _polling_reported:
                return False
            _polling_reported.add(endpoint)
            return True
        key = _volume_key(event)
        sent = _volume_sent.get(key)
        if sent is None:
            sent = _volume_sent[key] = deque()
            while len(_volume_sent) > _VOLUME_MAX_KEYS:
                _volume_sent.popitem(last=False)
        else:
            _volume_sent.move_to_end(key)
        while sent and now - sent[0] >= _VOLUME_WINDOW_SECONDS:
            sent.popleft()
        if len(sent) >= EVENTS_PER_FINGERPRINT_PER_HOUR:
            return False
        sent.append(now)
        return True


def _daily_path() -> Optional[Path]:
    privacy = _privacy_path()
    if privacy is None:
        return None
    return privacy.with_name(_DAILY_FILE)


def _read_daily(path: Optional[Path]) -> dict:
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_daily(path: Optional[Path], state: dict) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        logger.debug("Sentry daily counter was not saved", exc_info=True)


def _sampled_in(event: dict) -> bool:
    token = str(event.get("event_id") or "").replace("-", "")
    try:
        bucket = int(token, 16)
    except ValueError:
        return False
    return bucket % DAILY_SAMPLE_EVERY == 0


_daily_lock = threading.Lock()
_daily_memory: dict[str, int] = {}


def _daily_state() -> tuple[str, Optional[Path], dict, int]:
    day = datetime.now(timezone.utc).date().isoformat()
    path = _daily_path()
    state = _read_daily(path)
    if state.get("day") != day:
        state = {"day": day, "sent": _daily_memory.get(day, 0) if path is None else 0}
    return day, path, state, int(state.get("sent") or 0)


def _daily_would_send(event: dict) -> bool:
    """Peek. Volume-rejected events must not consume this counter."""
    with _daily_lock:
        _day, _path, _state, sent = _daily_state()
    if sent >= DAILY_HARD_CAP:
        return False
    if sent >= DAILY_FULL_FIDELITY and not _sampled_in(event):
        return False
    return True


def _daily_record(event: dict) -> None:
    with _daily_lock:
        day, path, state, sent = _daily_state()
        if sent >= DAILY_HARD_CAP:
            return
        if sent >= DAILY_FULL_FIDELITY and not _sampled_in(event):
            return
        sent += 1
        state["sent"] = sent
        _daily_memory.clear()
        _daily_memory[day] = sent
        _write_daily(path, state)


def _before_send_limited(event: dict, hint: Optional[dict] = None) -> Optional[dict]:
    """SDK hook: privacy first, then the daily peek, then the fingerprint budget.

    A fingerprint that is already full does not advance the daily counter, and a
    daily drop does not take a fingerprint slot.
    """
    clean = before_send(event, hint)
    if clean is None or not _daily_would_send(clean) or not _volume_allows(clean):
        return None
    _daily_record(clean)
    return clean


def clear_anonymous_user() -> None:
    """drop Sentry user.id in this process now, without reading privacy.json."""
    if not _initialized:
        return
    try:
        import sentry_sdk
        sentry_sdk.get_global_scope().set_user(None)
    except Exception:  # noqa: BLE001
        logger.debug("Sentry anonymous user was not cleared", exc_info=True)


def sync_anonymous_user(distinct_id: str | None = None) -> None:
    """Align Sentry user.id with the PostHog anonymous distinct_id. Id only."""
    if not _initialized:
        return
    try:
        from backend.services.studio.qa.telemetry import _analytics_allowed, stored_distinct_id
        import sentry_sdk
        value = distinct_id if isinstance(distinct_id, str) else stored_distinct_id()
        # Identity updates may arrive in an API request. Worker threads need the
        # process scope, not the transient request/isolation scope.
        scope = sentry_sdk.get_global_scope()
        if value and _ANONYMOUS_ID.fullmatch(value) and _analytics_allowed():
            scope.set_user({"id": value})
        else:
            scope.set_user(None)
    except Exception:  # noqa: BLE001 - identity sync cannot break crash reporting
        logger.debug("Sentry anonymous user was not updated", exc_info=True)


def _event_distinct_id(event: dict) -> str | None:
    try:
        from backend.services.studio.qa.telemetry import _analytics_allowed, stored_distinct_id
    except Exception:
        return None
    if not _analytics_allowed():
        return None
    # Also recover identities written after SDK init, including worker processes.
    stored = stored_distinct_id()
    if stored:
        return stored
    user = event.get("user") if isinstance(event.get("user"), dict) else {}
    candidate = user.get("id") if isinstance(user, dict) else None
    if isinstance(candidate, str) and _ANONYMOUS_ID.fullmatch(candidate):
        return candidate
    return None


# Packaged acceptance builds set validation on purpose. Anything else, including the
# unset default "unknown" and the launcher's debug value "development", does not report.
_REPORTING_BUILD_ENVIRONMENTS = frozenset({"production", "validation"})


def _under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def _running_from_source_tree() -> bool:
    """A checkout keeps backend/tests. The desktop bundle's copy of backend omits it."""
    try:
        backend_dir = Path(__file__).resolve().parents[1]
    except (OSError, IndexError, RuntimeError):
        return True
    return (backend_dir / "tests").is_dir()


def _packaged_desktop_reporting(mode: str) -> bool:
    """True only for a packaged desktop production or validation build.

    pytest and a source checkout return False even when SENTRY_DSN, mode and
    AUTOCLIP_BUILD_ENVIRONMENT are all set to look like a release.
    """
    if _under_pytest() or _running_from_source_tree():
        return False
    release = (os.getenv("AUTOCLIP_APP_VERSION") or os.getenv("SENTRY_RELEASE") or "").strip()
    build_environment = (os.getenv("AUTOCLIP_BUILD_ENVIRONMENT") or "").strip()
    if mode != "desktop" or release.lower() in {"", "unknown"}:
        return False
    return build_environment in _REPORTING_BUILD_ENVIRONMENTS


def init_sentry(mode: str = "web") -> bool:
    """在 create_app 最早调用。返回是否真正启用。"""
    global _initialized
    if _initialized:
        return True
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    # tests, source checkouts, web/Docker/scripts and tauri dev never init.
    if not _packaged_desktop_reporting(mode):
        logger.info("非桌面正式版，跳过 Sentry")
        return False
    release = (os.getenv("AUTOCLIP_APP_VERSION") or os.getenv("SENTRY_RELEASE") or "").strip()
    build_environment = (os.getenv("AUTOCLIP_BUILD_ENVIRONMENT") or "").strip()
    if not crash_reports_enabled():
        logger.info("崩溃报告已关闭，跳过 Sentry")
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        logger.warning("未安装 sentry-sdk，崩溃上报不可用")
        return False

    sentry_sdk.init(
        dsn=dsn,
        release=f"autoclip-backend@{release}",
        environment=mode,
        send_default_pii=False,
        traces_sample_rate=0.0,
        auto_session_tracking=False,
        auto_enabling_integrations=False,
        include_local_variables=False,
        include_source_context=False,
        max_request_body_size="never",
        max_breadcrumbs=0,
        before_send=_before_send_limited,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.ERROR, event_level=logging.ERROR),
        ],
    )
    # Consent can first enable the SDK inside a settings request. Request-local
    # tags disappear when that request exits; process identity belongs globally.
    scope = sentry_sdk.get_global_scope()
    scope.set_tag("runtime", "python")
    scope.set_tag("app_mode", mode)
    from backend.core.event_catalog import detect_os, detect_arch
    scope.set_tag("os", detect_os())
    scope.set_tag("arch", detect_arch())
    scope.set_tag("build_environment", build_environment)
    if build_environment == "validation":
        scope.set_tag("telemetry_test", "true")
    _initialized = True
    sync_anonymous_user()
    logger.info("Sentry 已启用（backend）")
    return True


def capture_studio_exception(error: Exception, phase: str, *, analysis_mode=None, goal=None, http_status: int | None = None):
    """Report caught worker errors without allowing monitoring to fail the worker.

    Consent is checked both here and in before_send. Scope is isolated so worker
    threads cannot leak their phase into unrelated requests. All tags are filtered.
    """
    if not _initialized or not crash_reports_enabled():
        return None
    from backend.core.project_cancellation import ProjectDeleted
    if isinstance(error, ProjectDeleted):
        return None  # the user deleted the project mid-run: expected, not a crash (RC156 #12)
    try:
        code = studio_error_code(error)
        if code in UNREPORTED_STUDIO_ERROR_CODES:
            return None
        import sentry_sdk
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("area", "studio")
            scope.set_tag("phase", phase)
            scope.set_tag("error_code", code)
            stage = getattr(error, "stage", None)
            if isinstance(stage, str) and stage in PIPELINE_STAGES:
                scope.set_tag("pipeline_stage", stage)
            if analysis_mode:
                scope.set_tag("analysis_mode", analysis_mode)
            if goal:
                scope.set_tag("goal", goal)
            if http_status is not None:
                scope.set_tag("http_status", str(http_status))  # before_send keeps 400-599 only
            try:
                from backend.core.llm_telemetry import sentry_tags_for_error
                for key, value in sentry_tags_for_error(error, phase).items():
                    scope.set_tag(key, value)
            except Exception:
                pass
            detail = getattr(error, "probe_detail", None)
            if isinstance(detail, str) and detail:
                scope.set_context("source_probe", {"stderr_tail": detail[-600:]})
            return sentry_sdk.capture_exception(error)
    except Exception:
        return None
