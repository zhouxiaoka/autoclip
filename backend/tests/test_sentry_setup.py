"""崩溃报告开关与 DSN 缺省行为。"""
import json
from pathlib import Path

from backend.core import sentry_setup as sentry_setup


def test_crash_reports_default_on(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    assert sentry_setup.crash_reports_enabled() is True


def test_crash_reports_reads_privacy_file(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    (tmp_path / "privacy.json").write_text(json.dumps({"crash_reports": False}), encoding="utf-8")
    assert sentry_setup.crash_reports_enabled() is False


def test_write_privacy_roundtrip(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    sentry_setup.write_privacy(crash_reports=False)
    assert sentry_setup.crash_reports_enabled() is False
    sentry_setup.write_privacy(crash_reports=True)
    assert sentry_setup.crash_reports_enabled() is True


def test_init_sentry_noop_without_dsn(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert sentry_setup.init_sentry("desktop") is False


def test_before_send_rechecks_opt_out_without_restart(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    event = {"exception": {"values": [{"type": "ValueError", "value": "secret"}]}}
    assert sentry_setup.before_send(event, {}) is not None
    sentry_setup.write_privacy(crash_reports=False)
    assert sentry_setup.before_send(event, {}) is None
    sentry_setup.write_privacy(crash_reports=True)
    assert sentry_setup.before_send(event, {}) is not None


def test_before_send_splits_import_failures_without_keeping_the_message(monkeypatch, tmp_path):
    """配置类失败用固定 fingerprint；正文仍被抹掉，未预期故障不覆盖默认归组。"""
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    from backend.tasks.import_processing import (
        ImportMissingCredential,
        ImportProcessingError,
        ImportSubtitleUnavailable,
    )

    subtitle_message = "没有字幕可分析：/Users/private/talk.mp4 的口播内容"
    key_message = "缺少 API Key sk-live-secret"
    unexpected_message = "broker down /Users/private/input.mp4"

    subtitle = sentry_setup.before_send(
        {"exception": {"values": [{"type": "ImportSubtitleUnavailable", "value": subtitle_message}]}},
        {"exc_info": (ImportSubtitleUnavailable, ImportSubtitleUnavailable(subtitle_message), None)},
    )
    missing_key = sentry_setup.before_send(
        {"exception": {"values": [{"type": "ImportMissingCredential", "value": key_message}]}},
        {},
    )
    unexpected = sentry_setup.before_send(
        {"exception": {"values": [{"type": "ImportProcessingError", "value": unexpected_message}]}},
        {"exc_info": (ImportProcessingError, ImportProcessingError(unexpected_message), None)},
    )

    assert subtitle["fingerprint"] == ["import-processing", "missing-subtitle"]
    assert subtitle["tags"] == {"import_failure": "missing-subtitle"}
    assert subtitle["exception"]["values"][0]["type"] == "ImportSubtitleUnavailable"
    assert missing_key["fingerprint"] == ["import-processing", "missing-key"]
    assert missing_key["tags"] == {"import_failure": "missing-key"}
    assert missing_key["exception"]["values"][0]["type"] == "ImportMissingCredential"
    assert "fingerprint" not in unexpected
    assert unexpected["tags"] == {"import_failure": "unexpected"}
    assert unexpected["exception"]["values"][0]["type"] == "ImportProcessingError"

    blob = json.dumps({"subtitle": subtitle, "key": missing_key, "unexpected": unexpected}, ensure_ascii=False)
    assert "private" not in blob
    assert "sk-live-secret" not in blob
    assert "口播" not in blob
    assert subtitle["exception"]["values"][0]["value"] == "[message omitted for privacy]"


def test_before_send_keeps_code_locations_without_private_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    event = {"release": "autoclip-backend@1.3.1", "request": {"data": "private"},
             "breadcrumbs": ["private"], "extra": {"key": "private"}, "server_name": "private",
             "exception": {"values": [{"type": "ValueError", "value": "private",
                 "stacktrace": {"frames": [{"filename": "/Users/private/backend/service.py",
                     "lineno": 42, "function": "run", "vars": {"text": "private"},
                     "context_line": "private"}]}}]}}
    clean = sentry_setup.before_send(event, {})
    assert "private" not in json.dumps(clean)
    frame = clean["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame == {"filename": "service.py", "lineno": 42, "function": "run"}
    assert sentry_setup.before_send({"logentry": {"message": "private"}}, {}) is None


def test_corrupt_privacy_file_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    (tmp_path / "privacy.json").write_text("invalid json")
    assert sentry_setup.crash_reports_enabled() is False


def test_privacy_uses_web_data_directory(monkeypatch, tmp_path):
    from backend.core import path_utils
    monkeypatch.delenv("AUTOCLIP_APP_DIR", raising=False)
    monkeypatch.delenv("AUTOCLIP_DATA_DIR", raising=False)
    monkeypatch.setattr(path_utils, "get_data_directory", lambda: tmp_path)
    sentry_setup.write_privacy(crash_reports=False)
    assert (tmp_path / "privacy.json").is_file()
    assert sentry_setup.crash_reports_enabled() is False
