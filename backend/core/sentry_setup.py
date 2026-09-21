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


def before_send(event: dict, _hint: dict) -> Optional[dict]:
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
    _initialized = True
    logger.info("Sentry 已启用（backend）")
    return True
