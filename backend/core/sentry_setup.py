"""
Sentry 崩溃上报。DSN 未配置或用户关闭时全程 no-op，不发网络请求。

桌面端 DSN 由 Rust 启动器注入（构建时 SENTRY_DSN）；Docker / 脚本模式读环境变量。
不含视频内容、字幕、API key；send_default_pii=False。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

STUDIO_ERROR_CODES = {"validation", "missing_resource", "unexpected", "timeout", "connection", "authentication", "rate_limited", "provider_error", "invalid_response", "output_truncated", "refused", "llm_not_configured", "whisper_not_installed", "whisper_install_failed", "transcription_empty", "subtitle_setup", "timeline_empty"}


def studio_error_code(error: Exception) -> str:
    from backend.services.studio.intelligence import VisionRequestError
    from backend.pipeline.failures import PipelineFailure
    if isinstance(error, (VisionRequestError, PipelineFailure)) and error.code in STUDIO_ERROR_CODES:
        return error.code
    if isinstance(error, FileNotFoundError):
        return "missing_resource"
    if isinstance(error, ValueError):
        return "validation"
    return "unexpected"


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


def write_privacy(*, crash_reports: Optional[bool] = None) -> Path:
    path = _privacy_path()
    if path is None:
        raise RuntimeError("未设置 AUTOCLIP_APP_DIR / AUTOCLIP_DATA_DIR，写不了隐私开关")
    current: dict[str, Any] = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            current = {}
    if crash_reports is not None:
        current["crash_reports"] = bool(crash_reports)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
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


def before_send(event: dict, hint: Optional[dict] = None) -> Optional[dict]:
    """Recheck consent for every event, including long-running worker processes.

    Keep code locations, never arbitrary exception messages, request bodies,
    local variables, log messages or breadcrumbs (which may contain subtitles).
    """
    if not crash_reports_enabled():
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
    clean["exception"] = {"values": values}
    kind, fingerprint = _import_monitoring_fields(event, hint)
    tags = event.get("tags") or {}
    allowed = {
        "area": {"studio"}, "error_code": STUDIO_ERROR_CODES,
        "phase": {"screening", "production", "render", "analysis", "dispatch", "vision_test", "rewrite"},
        "analysis_mode": {"subtitle", "visual"},
        "goal": {"content", "highlight", "promo"},
        "runtime": {"python"}, "app_mode": {"web", "desktop"},
        "build_environment": {"production", "development", "validation", "unknown"},
        "telemetry_test": {"true"},
    }
    clean_tags = {key: value for key, value in tags.items()
                  if key in allowed and isinstance(value, str) and value in allowed[key]}
    if kind:
        clean_tags["import_failure"] = kind
    if clean_tags:
        clean["tags"] = clean_tags
    if clean_tags.get("area") == "studio" and clean_tags.get("error_code") in {"validation", "missing_resource", "authentication", "rate_limited", "refused", "llm_not_configured", "whisper_not_installed", "whisper_install_failed", "transcription_empty", "subtitle_setup", "timeline_empty"}:
        clean["level"] = "warning"
        clean["fingerprint"] = ["studio", clean_tags.get("phase", "unknown"), clean_tags["error_code"]]
    if fingerprint:
        clean["fingerprint"] = fingerprint
    return clean


def init_sentry(mode: str = "web") -> bool:
    """在 create_app 最早调用。返回是否真正启用。"""
    global _initialized
    if _initialized:
        return True
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
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

    release = os.getenv("AUTOCLIP_APP_VERSION") or os.getenv("SENTRY_RELEASE") or "unknown"
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
        before_send=before_send,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.ERROR, event_level=logging.ERROR),
        ],
    )
    sentry_sdk.set_tag("runtime", "python")
    sentry_sdk.set_tag("app_mode", mode)
    sentry_sdk.set_tag("build_environment", os.getenv("AUTOCLIP_BUILD_ENVIRONMENT", "unknown"))
    _initialized = True
    logger.info("Sentry 已启用（backend）")
    return True


def capture_studio_exception(error: Exception, phase: str, *, analysis_mode=None, goal=None):
    """Report caught worker errors without allowing monitoring to fail the worker.

    Consent is checked both here and in before_send. Scope is isolated so worker
    threads cannot leak their phase into unrelated requests. All tags are filtered.
    """
    if not _initialized or not crash_reports_enabled():
        return None
    try:
        import sentry_sdk
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("area", "studio")
            scope.set_tag("phase", phase)
            scope.set_tag("error_code", studio_error_code(error))
            if analysis_mode:
                scope.set_tag("analysis_mode", analysis_mode)
            if goal:
                scope.set_tag("goal", goal)
            return sentry_sdk.capture_exception(error)
    except Exception:
        return None
