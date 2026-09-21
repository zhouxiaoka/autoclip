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
