"""Diagnostics opt-in: allowlist, consent races, and no change to attempt state."""
from __future__ import annotations

import importlib.util
import json
import logging
import sys
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.diagnostics import (
    consent,
    media,
    observe,
    queue,
    service,
    source,
    upload,
)
from backend.services.diagnostics.manifest import build_manifest

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "t-" + "ab" * 16
OTHER = "t-" + "cd" * 16


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_DIAGNOSTICS_SYNC", "1")
    monkeypatch.delenv("AUTOCLIP_DIAGNOSTICS_ENDPOINT", raising=False)
    return tmp_path


def _receipt(**extra):
    return {
        "attempt_id": TOKEN, "flow_id": OTHER, "sequence": 2, "kind": "generation",
        "trigger": "initial", "state": "failed", "error_code": "timeout", "failure_stage": "analyze",
        "finished_at": "2026-11-16T12:00:00+00:00", "summary": {"provider": "deepseek", "model": "deepseek-chat", "duration_ms": 15},
        **extra,
    }


def test_privacy_copy_exists_in_all_eight_locales():
    notice = "从这一版开始，新的安装会在失败后自动发送脱敏诊断，用来排查问题并改进产品，不会用来训练模型。这不是你以前单独同意过的记录；你现在就可以关闭。"
    media_scope = "本地视频默认会压缩并上传这次失败附近的短片段。没有失败时间时，用片头约 60 秒。短片段可能包含私人内容。完整原片默认不上传，需要你打开开关。如果这次用的是视频链接，只发送清洗后的链接，不发送下载下来的视频。字幕正文不会自动上传。"
    retention = "已上传的诊断会在 14 天后自动删除。你可以在这条说明里关闭总开关或单独关闭素材。关闭总开关会取消还没完成的上传。"
    for lang in ("zh", "zh-TW", "en", "ja", "ko", "es", "pt", "ru", "fr", "id", "tr", "vi", "de"):
        data = json.loads((ROOT / "frontend/src/i18n/locales" / f"{lang}.json").read_text(encoding="utf-8"))
        prefix = 'settings.diagnostics.'
        assert data[prefix + 'report']
        assert '14' in data[prefix + 'privacy_use']
        assert '60' in data[prefix + 'clip_hint']
        assert data[notice]
        assert data[media_scope]
        assert data[retention]
        if lang == 'zh':
            assert '默认发送失败报告和短片段' in data[prefix + 'privacy_use']
            assert '默认关闭' in data[prefix + 'original_hint']
        else:
            assert data[prefix + 'original_hint'] != '默认关闭。开启后会上传整个视频，可能包含私人内容。'
            assert data[notice] != notice


def test_manifest_drops_secrets_paths_names_and_transcript(data_dir):
    receipt = _receipt(summary={
        "provider": "deepseek", "model": "deepseek-chat", "duration_ms": 15,
        "api_key": "sk-supersecretvalue", "title": "我的项目", "source_url": "https://example.com/a?token=1",
        "error": "/Users/me/Movies/talk.mp4",
    }, error="sk-supersecretvalue /Users/me")
    log = (
        "2026-11-16 00:00:00 INFO project_id=proj step=analyze error_code=timeout\n"
        "2026-11-16 00:00:01 ERROR sk-abcdefghijklmnopqrstuvwxyz leaked\n"
        "2026-11-16 00:00:02 INFO project_id=proj subtitle hello --> world\n"
        "这不是日志，是转写正文\n"
        "2026-11-16 00:00:03 INFO project_id=other step=analyze"
    )
    built = build_manifest(receipt, log_text=log, project_id="proj")
    blob = json.dumps(built, ensure_ascii=False)
    assert "sk-" not in blob
    assert "Users" not in blob
    assert "我的项目" not in blob
    assert "token=" not in blob
    assert "-->" not in blob
    assert built["attempt"]["attempt_id"] == TOKEN
    assert built["attempt"]["sequence"] == 2
    assert built["attempt"]["error_code"] == "timeout"
    assert built["not_for_training"] is True
    assert built["log_lines"][0]["message"].startswith("project_id=proj")
    assert "error" not in built["attempt"]


def test_placeholder_logs_are_gone_and_raw_lines_are_not_returned(data_dir, tmp_path):
    source = (ROOT / "backend/api/v1/projects.py").read_text(encoding="utf-8")
    desktop = (ROOT / "backend/api/v1/desktop.py").read_text(encoding="utf-8")
    assert "开始处理项目" not in source
    assert "autoclip.log" not in desktop
    log = tmp_path / "backend.log"
    log.write_text("2026-11-16 00:00:00 ERROR sk-abcdefghijklmnopqrstuvwxyz /Users/me/secret\n", encoding="utf-8")
    from backend.services.diagnostics.redact import sanitized_log_file
    rows = sanitized_log_file(log, limit=10)
    blob = json.dumps(rows)
    assert "sk-" not in blob
    assert "/Users/" not in blob
    assert rows[0]["message"].startswith("[REDACTED]")


def test_symlink_and_escape_are_rejected(data_dir, tmp_path):
    from backend.services.studio import store
    root = store.directory("proj")
    (root / "raw").mkdir(parents=True)
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"secret-video")
    (root / "raw" / "input.mp4").symlink_to(outside)
    assert media.candidates("proj") == []
    with pytest.raises(media.MediaRejected):
        media.resolve_role("proj", "original")


def test_consent_defaults_off_and_narrowing_cancels_queued_work(data_dir):
    unset = consent.load()
    assert unset.diagnostics is True and unset.media is True and unset.full_original is False
    assert unset.notice_seen is False and unset.diagnostics_at is None
    with pytest.raises(PermissionError):
        consent.update(diagnostics=True, media=True, full_original=True, informed=False)
    granted = consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    assert granted.epoch == 0 and granted.diagnostics_at and granted.notice_seen is True
    item = queue.enqueue({
        "id": "c-1", "idempotency_key": "k1", "status": "queued", "epoch": granted.epoch,
        "manifest": build_manifest(_receipt()), "files": [], "explicit": False,
    })
    assert item["status"] == "queued"
    service.set_consent(diagnostics=False, media=False, full_original=False, informed=True)
    assert queue.list_items()[0]["status"] == "cancelled"
    assert consent.load().epoch == 1


def test_historical_failure_is_not_queued_and_a_later_one_is(data_dir, monkeypatch):
    granted = consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    early = _receipt(finished_at="2020-01-01T00:00:00+00:00")
    assert service.background_enqueue("proj", early) is None
    observe.schedule_new_failures("proj", {"attempts": [{"attempt_id": TOKEN, "state": "failed"}]}, {"attempts": [early]})
    observe.deliver_pending()
    assert queue.list_items() == []
    later = _receipt(finished_at="2999-01-01T00:00:00+00:00")
    from backend.services.studio import store
    monkeypatch.setattr(store, "write", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("studio write")))
    observe.schedule_new_failures("proj", {"attempts": [{"attempt_id": TOKEN, "state": "open"}]}, {"attempts": [later]})
    observe.deliver_pending()
    class Transport:
        def __init__(self):
            self.calls = []

        def create_case(self, base, body, key):
            self.calls.append((base, body, key))
            raise upload.Offline("offline")

    transport = Transport()
    upload.pump_once(transport)
    rows = queue.list_items()
    assert len(rows) == 1
    assert rows[0]["attempt_id"] == TOKEN
    assert rows[0]["status"] == "offline"
    assert rows[0]["files"] == []
    assert transport.calls[0][0] == upload.DEFAULT_ENDPOINT
    assert transport.calls[0][1]["files"] == []
    assert granted.diagnostics is True


def test_revocation_during_authorize_aborts_and_does_not_upload_bytes(data_dir, tmp_path):
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    (tmp_path / "diagnostics").mkdir(exist_ok=True)
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    calls = {"put": 0, "abort": 0}

    class Transport:
        def create_case(self, base, body, key):
            consent.update(diagnostics=False, media=False, full_original=False, informed=True)
            return {"case_id": "remote", "capability": "cap", "uploads": [{"role": "excerpt", "url": "http://169.254.169.254/latest"}]}

        def delete(self, base, case_id, capability):
            calls["abort"] += 1

        def put_part(self, url, data, headers):
            calls["put"] += 1
            return "etag"

    built = build_manifest(_receipt())
    queue.enqueue({
        "id": "c-race", "idempotency_key": "race", "status": "queued", "epoch": consent.load().epoch,
        "manifest": built, "files": [], "explicit": False, "attempts": 0, "upload": {},
    })
    upload.pump_once(Transport())
    assert calls["put"] == 0
    assert calls["abort"] == 1
    assert queue.list_items()[0]["status"] == "deleted"


def test_offline_retry_and_idempotent_enqueue(data_dir, tmp_path):
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    built = build_manifest(_receipt())
    item = {
        "id": "c-off", "idempotency_key": "same", "status": "queued", "epoch": consent.load().epoch,
        "manifest": built, "files": [], "explicit": False, "attempts": 0, "upload": {},
    }
    assert queue.enqueue(item)["id"] == queue.enqueue(dict(item))["id"]
    assert len(queue.list_items()) == 1

    class Transport:
        def __init__(self):
            self.creates = 0

        def create_case(self, base, body, key):
            self.creates += 1
            raise upload.Offline("offline")

    transport = Transport()
    upload.pump_once(transport)
    assert transport.creates == 1
    assert queue.list_items()[0]["status"] == "offline"
    upload.pump_once(transport)
    assert transport.creates == 1  # backoff has not elapsed


def test_new_install_uploads_without_acknowledgement_and_explicit_off_does_not(data_dir, tmp_path):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    assert consent.load().persisted is False and consent.load().diagnostics is True

    class Transport:
        def __init__(self):
            self.creates = 0

        def create_case(self, base, body, key):
            self.creates += 1
            return {"case_id": "remote", "capability": "cap", "uploads": []}

        def put_part(self, *args, **kwargs):
            raise AssertionError("manifest-only upload has no media")

        def complete(self, *args, **kwargs):
            raise AssertionError("manifest-only upload has no media")

    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued is not None and queued["files"] == []
    assert not consent.consent_path().exists()
    transport = Transport()
    upload.pump_once(transport)
    assert transport.creates == 1
    consent.update(diagnostics=False, media=False, full_original=False, informed=True)
    assert service.background_enqueue("proj", _receipt(finished_at="2999-01-02T00:00:00+00:00", attempt_id="t-" + "ef" * 16)) is None


def test_media_toggle_stays_off_when_diagnostics_are_on(data_dir):
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    from backend.services.studio import store
    root = store.directory("proj")
    (root / "raw").mkdir(parents=True)
    (root / "raw" / "input.mp4").write_bytes(b"clip-bytes")
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued is not None
    assert queued["files"] == []
    assert (root / "raw" / "input.mp4").read_bytes() == b"clip-bytes"


def test_unreadable_consent_is_not_treated_as_default_on(data_dir):
    consent.consent_path().parent.mkdir(parents=True, exist_ok=True)
    consent.consent_path().write_text("{", encoding="utf-8")
    grant = consent.load()
    assert grant.unreadable is True
    assert grant.diagnostics is False and grant.media is False and grant.full_original is False
    assert grant.notice_seen is False
    assert service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00")) is None


def test_explicit_off_for_every_scope_survives_reload(data_dir):
    consent.update(diagnostics=False, media=False, full_original=False, informed=True)
    again = consent.load()
    assert again.diagnostics is False and again.media is False and again.full_original is False
    assert again.notice_seen is True
    assert service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00")) is None
    raw = {
        "diagnostics": True, "media": False, "full_original": False, "epoch": 3,
        "text_version": "2026-11-16.1", "diagnostics_at": "2026-11-16T00:00:00+00:00",
        "updated_at": "2026-11-16T00:00:00+00:00",
    }
    consent.consent_path().write_text(json.dumps(raw), encoding="utf-8")
    kept = consent.load()
    assert kept.diagnostics is True and kept.media is False and kept.full_original is False
    assert kept.notice_seen is True
    raw["diagnostics"] = False
    raw["media"] = False
    raw["full_original"] = False
    consent.consent_path().write_text(json.dumps(raw), encoding="utf-8")
    assert consent.load().diagnostics is False


def test_pre_159_consent_without_notice_seen_keeps_explicit_false(data_dir):
    consent.consent_path().parent.mkdir(parents=True, exist_ok=True)
    consent.consent_path().write_text(json.dumps({
        "diagnostics": False, "media": False, "full_original": False, "epoch": 2,
        "text_version": "2026-11-16.1", "updated_at": "2026-11-16T00:00:00+00:00",
    }), encoding="utf-8")
    grant = consent.load()
    assert grant.notice_seen is True
    assert grant.diagnostics is False and grant.media is False and grant.full_original is False
    assert service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00")) is None


def test_background_checkbox_keeps_original_off(data_dir):
    from backend.services.studio import store
    root = store.directory("proj")
    (root / "metadata").mkdir(parents=True)
    (root / "metadata" / "studio.json").write_text(json.dumps({"attempts": [_receipt()]}), encoding="utf-8")
    service.submit("proj", TOKEN, roles=[], informed=True, also_enable_background=True)
    grant = consent.load()
    assert grant.diagnostics is True and grant.media is True and grant.full_original is False
    assert grant.persisted is True


def test_confirmed_default_asks_for_the_original_and_not_subtitles(data_dir, monkeypatch):
    source.record_input_origin("proj", "file")
    consent.update(diagnostics=True, media=True, full_original=True, informed=True)
    seen = {}

    def fake(project_id, roles, excerpt_dir, cut=None):
        seen["roles"] = list(roles)
        return []

    monkeypatch.setattr(media, "materialize", fake)
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued is not None
    assert seen["roles"] == ["original"]
    assert "subtitle" not in seen["roles"]


def test_master_off_cancels_queued_work_and_media_off_cancels_only_that_scope(data_dir):
    granted = consent.update(diagnostics=True, media=True, full_original=True, informed=True)
    manifest = build_manifest(_receipt())
    queue.enqueue({
        "id": "c-plain", "idempotency_key": "plain", "status": "queued", "epoch": granted.epoch,
        "manifest": manifest, "files": [], "explicit": False,
    })
    queue.enqueue({
        "id": "c-film", "idempotency_key": "film", "status": "queued", "epoch": granted.epoch,
        "manifest": manifest, "explicit": True,
        "files": [{"role": "original", "path": "raw/input.mp4", "size_bytes": 4, "sha256": "ab", "content_type": "video/mp4"}],
    })
    queue.enqueue({
        "id": "c-clip", "idempotency_key": "clip", "status": "queued", "epoch": granted.epoch,
        "manifest": manifest, "explicit": True,
        "files": [{"role": "excerpt", "path": "excerpt.mp4", "size_bytes": 4, "sha256": "ab", "content_type": "video/mp4"}],
    })
    service.set_consent(diagnostics=True, media=True, full_original=False, informed=True)
    assert queue.get("c-plain")["status"] == "queued"
    assert queue.get("c-film")["status"] == "cancelled"
    assert queue.get("c-clip")["status"] == "queued"
    service.set_consent(diagnostics=True, media=False, full_original=False, informed=True)
    assert queue.get("c-plain")["status"] == "queued"
    assert queue.get("c-clip")["status"] == "cancelled"
    service.set_consent(diagnostics=False, media=False, full_original=False, informed=True)
    assert queue.get("c-plain")["status"] == "cancelled"


def test_confirmed_delete_removes_diagnostic_copies_and_keeps_secrets_while_retrying(data_dir, tmp_path):
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    from backend.services.studio import store
    original = store.directory("proj") / "raw" / "input.mp4"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"original-bytes")
    item_id = "c-clean"
    excerpt = data_dir / "diagnostics" / "excerpts" / item_id / "excerpt.mp4"
    excerpt.parent.mkdir(parents=True)
    excerpt.write_bytes(b"excerpt-bytes")
    queue.write_capability(item_id, "cap-secret")
    queue.recovery_token(item_id, create=True)
    outside = tmp_path / "linked.mp4"
    outside.write_bytes(b"do-not-follow")
    link = data_dir / "diagnostics" / "excerpts" / "c-link"
    link.symlink_to(outside)
    queue.release_local_residue({"id": "c-link", "status": "deleted"})
    queue.enqueue({
        "id": item_id, "idempotency_key": "clean", "status": "queued", "epoch": consent.load().epoch,
        "project_id": "proj", "explicit": True, "manifest": build_manifest(_receipt()), "attempts": 0,
        "upload": {}, "files": [], "case_id": "remote-clean",
    })

    class Transport:
        def __init__(self):
            self.allow = False

        def delete(self, base, case_id, capability):
            if not self.allow:
                raise upload.Offline("timeout")

    transport = Transport()
    (data_dir / "diagnostics").mkdir(exist_ok=True)
    (data_dir / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    first = upload.finish_delete(queue.get(item_id), transport)
    assert first["status"] == "delete_pending"
    assert not excerpt.exists()
    assert queue.read_capability(item_id) == "cap-secret"
    assert queue.recovery_token(item_id) != ""
    assert original.read_bytes() == b"original-bytes"
    assert outside.read_bytes() == b"do-not-follow"
    assert not link.exists()
    transport.allow = True
    second = upload.finish_delete(queue.get(item_id), transport)
    assert second["status"] == "deleted"
    assert queue.read_capability(item_id) == ""
    assert queue.recovery_token(item_id) == ""
    assert original.read_bytes() == b"original-bytes"
    assert outside.read_bytes() == b"do-not-follow"


def test_endpoint_precedence_is_env_then_file_then_builtin(data_dir, monkeypatch):
    monkeypatch.delenv("AUTOCLIP_DIAGNOSTICS_ENDPOINT", raising=False)
    assert upload.endpoint() == upload.DEFAULT_ENDPOINT
    file = data_dir / "diagnostics" / "endpoint.json"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("{", encoding="utf-8")
    assert upload.endpoint() == upload.DEFAULT_ENDPOINT
    file.write_text(json.dumps({"endpoint": "  "}), encoding="utf-8")
    assert upload.endpoint() == upload.DEFAULT_ENDPOINT
    file.write_text(json.dumps({"endpoint": "https://file.example/diag/"}), encoding="utf-8")
    assert upload.endpoint() == "https://file.example/diag"
    monkeypatch.setenv("AUTOCLIP_DIAGNOSTICS_ENDPOINT", "  ")
    assert upload.endpoint() == "https://file.example/diag"
    monkeypatch.setenv("AUTOCLIP_DIAGNOSTICS_ENDPOINT", "https://env.example/diag/")
    assert upload.endpoint() == "https://env.example/diag"


def test_worker_requests_send_autoclip_user_agent_not_urllib_default(monkeypatch):
    from backend.core.event_catalog import app_version

    seen = []

    class Response:
        status = 200
        headers = {}

        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def capture(request, timeout=None, context=None):
        assert context is None
        seen.append((request, timeout))
        return Response()

    monkeypatch.setattr(upload.urllib.request, "urlopen", capture)
    monkeypatch.setenv("AUTOCLIP_APP_VERSION", "1.5.9")
    transport = upload.UrllibTransport()
    base = "http://127.0.0.1:9"
    transport.create_case(base, {"manifest": {}}, "idem")
    transport.cancel_creation(base, "idem", "recovery")
    transport.complete(base, "case", "cap", {"object_id": "obj", "bytes": 1})
    transport.delete(base, "case", "cap")
    transport.put_part("http://127.0.0.1/part", b"abcd", {"Content-Length": "4", "content-md5": "abc"})
    expected = f"AutoClip/{app_version()} diagnostics"
    assert expected == "AutoClip/1.5.9 diagnostics"
    assert len(seen) == 5
    for request, _timeout in seen[:4]:
        agent = request.get_header("User-agent")
        assert agent == expected
        assert not str(agent).startswith("Python-urllib/")
        assert all("Python-urllib" not in value for _name, value in request.header_items())
    put, _timeout = seen[4]
    assert put.get_header("User-agent") is None
    names = [name.lower() for name, _value in put.header_items()]
    assert "user-agent" not in names
    assert put.get_method() == "PUT"


def test_blank_endpoint_override_still_waits_without_a_network_call(data_dir, monkeypatch):
    monkeypatch.setattr(upload, "endpoint", lambda: "")
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    queue.enqueue({
        "id": "c-empty", "idempotency_key": "empty", "status": "queued", "epoch": consent.load().epoch,
        "manifest": build_manifest(_receipt()), "files": [], "explicit": False,
    })

    class Transport:
        def create_case(self, *args, **kwargs):
            raise AssertionError("blank endpoint contacted the worker")

    upload.pump_once(Transport())
    assert queue.get("c-empty")["status"] == "needs_endpoint"


def test_explicit_submit_without_endpoint_saves_locally_and_does_not_touch_attempt(data_dir):
    from backend.services.studio import store
    project = "proj"
    root = store.directory(project)
    (root / "metadata").mkdir(parents=True)
    state = {"attempts": [_receipt()], "generation": {"status": "failed", "error_code": "timeout"}}
    path = root / "metadata" / "studio.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    before = path.read_bytes()
    result = service.submit(project, TOKEN, roles=[], informed=True, save_local=True)
    assert result["status"] == "saved_local"
    assert path.read_bytes() == before
    export = data_dir / "diagnostics" / "exports" / result["id"] / "manifest.json"
    assert "sk-" not in export.read_text(encoding="utf-8")


def test_one_click_original_requires_separate_ack_and_api_is_local(data_dir):
    spec = importlib.util.spec_from_file_location(
        "backend.api.v1.diagnostics", ROOT / "backend/api/v1/diagnostics.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.api.v1.diagnostics"] = module
    spec.loader.exec_module(module)
    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1")
    client = TestClient(app)
    denied = client.put("/api/v1/diagnostics/consent", json={"diagnostics": True, "informed": False})
    assert denied.status_code == 422
    from backend.services.studio import store
    root = store.directory("proj")
    (root / "metadata").mkdir(parents=True)
    (root / "metadata" / "studio.json").write_text(json.dumps({"attempts": [_receipt()]}), encoding="utf-8")
    missing = client.post("/api/v1/diagnostics/submit", json={
        "project_id": "proj", "attempt_id": TOKEN, "roles": ["original"], "informed": True,
    })
    assert missing.status_code == 422
    assert missing.json()["detail"] == "full_original_required"


def test_real_logger_formats_keep_safe_lines_and_drop_secrets():
    desktop = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    runner = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    safe = logging.LogRecord(
        "backend.services.studio.jobs", logging.ERROR, __file__, 10,
        "project_id=proj step=analyze error_code=timeout", (), None,
    )
    leaked = logging.LogRecord(
        "backend.services.studio.jobs", logging.ERROR, __file__, 11,
        "project_id=proj sk-abcdefghijklmnopqrstuvwxyz https://api.example/v1?token=secret /Users/me/a.mp4 cue --> text",
        (), None,
    )
    from backend.services.diagnostics.redact import sanitized_log_records
    rows = sanitized_log_records(desktop.format(safe) + "\n" + runner.format(safe), project_id="proj")
    assert len(rows) == 2
    assert all("error_code=timeout" in row["message"] for row in rows)
    blob = json.dumps(sanitized_log_records(desktop.format(leaked) + "\n" + runner.format(leaked), project_id="proj"))
    assert "sk-" not in blob
    assert "token=" not in blob
    assert "/Users/" not in blob
    assert "-->" not in blob


def test_save_local_never_touches_the_network_when_an_endpoint_exists(data_dir, tmp_path):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    from backend.services.studio import store
    project = "proj"
    root = store.directory(project)
    (root / "metadata").mkdir(parents=True)
    (root / "raw").mkdir()
    video = root / "raw" / "input.mp4"
    video.write_bytes(b"clip-bytes")
    (root / "metadata" / "studio.json").write_text(json.dumps({"attempts": [_receipt()]}), encoding="utf-8")
    source.record_input_origin(project, "file")
    calls = {"n": 0}

    class Transport:
        def create_case(self, *args, **kwargs):
            calls["n"] += 1
            raise AssertionError("local save contacted the network")

        def put_part(self, *args, **kwargs):
            calls["n"] += 1
            raise AssertionError("local save uploaded media")

        def complete(self, *args, **kwargs):
            calls["n"] += 1
            raise AssertionError("local save completed a remote file")

        def delete(self, *args, **kwargs):
            calls["n"] += 1
            raise AssertionError("local save deleted remotely")

    result = service.submit(
        project, TOKEN, roles=["original"], informed=True, full_original_ack=True,
        save_local=True, transport=Transport(),
    )
    assert result["status"] == "saved_local"
    assert calls["n"] == 0
    exported = Path(result["export_path"])
    assert (exported / "manifest.json").is_file()
    assert (exported / "original.mp4").read_bytes() == b"clip-bytes"
    assert "sk-" not in (exported / "manifest.json").read_text(encoding="utf-8")
    removed = service.delete_local(result["id"], transport=Transport())
    assert removed["status"] == "deleted"
    assert calls["n"] == 0


def test_delete_during_upload_is_not_overwritten_and_stays_retryable(data_dir, tmp_path):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    source.record_input_origin("proj", "file")
    built = build_manifest(_receipt())
    from backend.services.studio import store
    root = store.directory("proj")
    (root / "raw").mkdir(parents=True)
    media_file = root / "raw" / "input.mp4"
    media_file.write_bytes(b"abcdef")
    item = queue.enqueue({
        "id": "c-del", "idempotency_key": "del", "status": "queued", "epoch": consent.load().epoch,
        "project_id": "proj", "attempt_id": TOKEN, "explicit": True, "disposition": "upload",
        "save_local": False, "manifest": built, "attempts": 0, "upload": {},
        "files": [{"role": "excerpt", "path": str(media_file), "size_bytes": 6, "sha256": __import__("hashlib").sha256(b"abcdef").hexdigest(), "content_type": "video/mp4"}],
    })

    class Transport:
        def __init__(self):
            self.puts = 0
            self.deletes = 0
            self.completes = 0
            self.allow_delete = False

        def create_case(self, base, body, key):
            return {"case_id": "remote", "capability": "secret-token", "uploads": [{
                "role": "excerpt", "object_id": "obj",
                "parts": [{"number": 1, "url": "http://127.0.0.1/part", "headers": {}, "offset": 0, "length": 6}],
            }]}

        def put_part(self, url, data, headers):
            self.puts += 1
            service.delete_local(item["id"], transport=self)
            return "etag-1"

        def delete(self, base, case_id, capability):
            self.deletes += 1
            if not self.allow_delete:
                raise upload.Offline("timeout")

        def complete(self, *args, **kwargs):
            self.completes += 1
            raise AssertionError("complete after delete")

    transport = Transport()
    upload.pump_once(transport)
    assert queue.get("c-del")["status"] == "delete_pending"
    assert transport.completes == 0
    assert "secret-token" not in queue.queue_path().read_text(encoding="utf-8")
    transport.allow_delete = True
    upload.pump_once(transport)
    assert queue.get("c-del")["status"] == "deleted"
    assert transport.deletes >= 2


def test_lost_create_response_replays_the_plan_and_uploads_every_byte(data_dir, tmp_path):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    source.record_input_origin("proj", "file")
    payload = b"hello-media"
    from backend.services.studio import store
    root = store.directory("proj")
    (root / "raw").mkdir(parents=True)
    media_file = root / "raw" / "input.mp4"
    media_file.write_bytes(payload)
    digest = __import__("hashlib").sha256(payload).hexdigest()
    built = build_manifest(_receipt())
    queue.enqueue({
        "id": "c-lost", "idempotency_key": "lost-key", "status": "queued", "epoch": consent.load().epoch,
        "project_id": "proj", "attempt_id": TOKEN, "explicit": True, "disposition": "upload",
        "save_local": False, "manifest": built, "attempts": 0, "upload": {},
        "files": [{"role": "excerpt", "path": str(media_file), "size_bytes": len(payload), "sha256": digest, "content_type": "video/mp4"}],
    })
    server = {"uploads": [{
        "role": "excerpt", "object_id": "obj",
        "parts": [{"number": 1, "url": "http://127.0.0.1/part", "headers": {}, "offset": 0, "length": len(payload)}],
    }]}

    class Transport:
        def __init__(self):
            self.creates = 0
            self.received = b""
            self.completed = []

        def create_case(self, base, body, key):
            self.creates += 1
            if self.creates == 1:
                raise upload.Offline("response_lost")
            return {"case_id": "remote", "capability": "second-secret", "uploads": server["uploads"]}

        def put_part(self, url, data, headers):
            self.received += data
            return "etag-1"

        def complete(self, base, case_id, capability, body):
            self.completed.append(body)
            return {"ok": True, "bytes": body["bytes"]}

        def delete(self, *args, **kwargs):
            raise AssertionError("delete")

    transport = Transport()
    first = upload.pump_once(transport)
    assert first[0]["status"] == "offline"
    assert transport.received == b""
    second = upload.pump_once(transport, now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc) + __import__("datetime").timedelta(hours=1))
    assert second[0]["status"] == "uploaded"
    assert transport.received == payload
    assert transport.completed[0]["bytes"] == len(payload)
    assert "second-secret" not in queue.queue_path().read_text(encoding="utf-8")
    assert queue.read_capability("c-lost") == "second-secret"


def _remote_case_item(item_id: str, key: str) -> None:
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    queue.enqueue({
        "id": item_id, "idempotency_key": key, "status": "queued", "epoch": consent.load().epoch,
        "project_id": "proj", "attempt_id": TOKEN, "explicit": True, "disposition": "upload",
        "save_local": False, "manifest": build_manifest(_receipt()), "attempts": 0, "upload": {},
        "files": [], "version": 1,
    })


def test_delete_during_create_keeps_a_retryable_cleanup_across_restart(data_dir, tmp_path):
    (tmp_path / "diagnostics").mkdir()
    endpoint = tmp_path / "diagnostics" / "endpoint.json"
    endpoint.write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    _remote_case_item("c-late", "late-key")
    entered = threading.Event()
    release = threading.Event()

    class Transport:
        def __init__(self):
            self.deletes = []
            self.allow = False

        def create_case(self, base, body, key):
            entered.set()
            assert release.wait(3)
            return {"case_id": "remote-case", "capability": "late-secret", "uploads": []}

        def delete(self, base, case_id, capability):
            self.deletes.append((case_id, capability, base))
            if not self.allow:
                raise upload.Offline("timeout")

        def put_part(self, *args, **kwargs):
            raise AssertionError("put after delete")

        def complete(self, *args, **kwargs):
            raise AssertionError("complete after delete")

    transport = Transport()
    worker = threading.Thread(target=lambda: upload.pump_once(transport))
    worker.start()
    assert entered.wait(3)
    service.delete_local("c-late", transport=transport)
    release.set()
    worker.join(3)
    assert not worker.is_alive()
    item = queue.get("c-late")
    assert item["status"] == "delete_pending"
    assert item["case_id"] == "remote-case"
    assert item["cleanup_endpoint"] == "http://127.0.0.1:9"
    assert queue.read_capability("c-late") == "late-secret"
    assert "late-secret" not in queue.queue_path().read_text(encoding="utf-8")
    assert len(transport.deletes) == 1
    assert transport.deletes[0] == ("remote-case", "late-secret", "http://127.0.0.1:9")
    assert queue.update("c-late", status="uploaded", if_status=queue.OPEN) is None
    parked = queue.enqueue({
        "id": "c-park", "idempotency_key": "park", "status": "queued", "epoch": 1,
        "manifest": build_manifest(_receipt()), "files": [], "explicit": True, "version": 1,
    })
    assert queue.update(parked["id"], status="deleted")["status"] == "deleted"
    assert queue.update(parked["id"], status="delete_pending") is None
    endpoint.write_text(json.dumps({"endpoint": "http://127.0.0.1:1"}), encoding="utf-8")
    transport.allow = True
    upload.pump_once(transport)
    assert queue.get("c-late")["status"] == "deleted"
    assert len(transport.deletes) == 2
    assert transport.deletes[1][2] == "http://127.0.0.1:9"
    assert queue.read_capability("c-late") == ""
    assert queue.get("c-late")["status"] != "uploaded"


def test_revocation_during_create_retries_cleanup_when_the_delete_times_out(data_dir, tmp_path):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    _remote_case_item("c-revoke", "revoke-key")
    entered = threading.Event()
    release = threading.Event()

    class Transport:
        def __init__(self):
            self.deletes = 0
            self.allow = False

        def create_case(self, base, body, key):
            entered.set()
            assert release.wait(3)
            return {"case_id": "remote-revoke", "capability": "revoke-secret", "uploads": []}

        def delete(self, base, case_id, capability):
            self.deletes += 1
            if not self.allow:
                raise upload.Offline("timeout")

        def put_part(self, *args, **kwargs):
            raise AssertionError("put")

        def complete(self, *args, **kwargs):
            raise AssertionError("complete")

    transport = Transport()
    worker = threading.Thread(target=lambda: upload.pump_once(transport))
    worker.start()
    assert entered.wait(3)
    service.set_consent(diagnostics=False, media=False, full_original=False, informed=True, transport=transport)
    release.set()
    worker.join(3)
    assert not worker.is_alive()
    item = queue.get("c-revoke")
    assert item["status"] == "delete_pending"
    assert item["case_id"] == "remote-revoke"
    assert queue.read_capability("c-revoke") == "revoke-secret"
    assert item["status"] != "uploaded"
    transport.allow = True
    upload.pump_once(transport)
    assert queue.get("c-revoke")["status"] == "deleted"
    assert transport.deletes == 2


def test_preview_without_attempt_id_maps_the_failure_and_submit_uses_it(data_dir):
    spec = importlib.util.spec_from_file_location(
        "backend.api.v1.diagnostics_preview", ROOT / "backend/api/v1/diagnostics.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.api.v1.diagnostics"] = module
    spec.loader.exec_module(module)
    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1")
    client = TestClient(app)
    from backend.services.studio import store
    root = store.directory("proj")
    (root / "metadata").mkdir(parents=True)
    path = root / "metadata" / "studio.json"
    path.write_text(json.dumps({"attempts": [_receipt(), {**_receipt(), "attempt_id": OTHER, "sequence": 1, "state": "failed"}]}), encoding="utf-8")
    before = path.read_bytes()
    preview = client.get("/api/v1/diagnostics/preview", params={"project_id": "proj"})
    assert preview.status_code == 200
    attempt_id = preview.json()["manifest"]["attempt"]["attempt_id"]
    assert attempt_id == TOKEN
    submitted = client.post("/api/v1/diagnostics/submit", json={
        "project_id": "proj", "attempt_id": attempt_id, "roles": [], "informed": True, "save_local": True,
    })
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "saved_local"
    assert path.read_bytes() == before


def test_incomplete_plan_is_not_marked_uploaded(data_dir, tmp_path):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    source.record_input_origin("proj", "file")
    from backend.services.studio import store
    root = store.directory("proj")
    (root / "raw").mkdir(parents=True)
    media_file = root / "raw" / "input.mp4"
    payload = b"abcdef"
    media_file.write_bytes(payload)
    queue.enqueue({
        "id": "c-plan", "idempotency_key": "plan", "status": "queued", "epoch": consent.load().epoch,
        "project_id": "proj", "attempt_id": TOKEN, "explicit": True, "disposition": "upload",
        "save_local": False, "manifest": build_manifest(_receipt()), "attempts": 0, "upload": {},
        "files": [{"role": "excerpt", "path": str(media_file), "size_bytes": len(payload), "sha256": __import__("hashlib").sha256(payload).hexdigest(), "content_type": "video/mp4"}],
    })

    class Transport:
        def create_case(self, base, body, key):
            return {"case_id": "remote", "capability": "secret", "uploads": []}

        def put_part(self, *args, **kwargs):
            raise AssertionError("put")

        def complete(self, *args, **kwargs):
            raise AssertionError("complete")

        def delete(self, *args, **kwargs):
            return None

    result = upload.pump_once(Transport())
    assert result[0]["status"] == "failed"
    assert result[0]["error"] == "RuntimeError"


def test_one_part_is_retried_twice_and_a_due_plan_refreshes_without_a_new_ttl():
    from datetime import datetime, timedelta, timezone

    calls = {"put": 0}

    class Transport:
        def put_part(self, url, data, headers):
            calls["put"] += 1
            if calls["put"] < 3:
                raise upload.Offline("offline")
            return "etag-kept"

    assert upload._put_part_attempts(Transport(), "https://acct.r2.cloudflarestorage.com/bucket/key", b"abcd", {}) == "etag-kept"
    assert calls["put"] == 3
    soon = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    assert upload._plan_due({"expires_at": soon}) is True
    later = (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat()
    assert upload._plan_due({"expires_at": later}) is False
    assert upload._plan_expired({"expires_at": soon}) is False


def test_http_400_is_permanent_and_presigned_urls_are_not_written_to_the_queue(data_dir):
    calls = {"put": 0}

    class Transport:
        def put_part(self, url, data, headers):
            calls["put"] += 1
            raise upload.PermanentUploadError("http_400")

    try:
        upload._put_part_attempts(Transport(), "https://acct.r2.cloudflarestorage.com/bucket/key", b"abcd", {})
    except upload.PermanentUploadError as exc:
        assert str(exc) == "http_400"
    else:
        raise AssertionError("400 must not be retried as offline")
    assert calls["put"] == 1

    item = queue.enqueue({
        "id": "c-url", "idempotency_key": "url", "status": "queued", "epoch": consent.load().epoch,
        "project_id": "proj", "attempt_id": TOKEN, "explicit": True, "disposition": "upload",
        "save_local": False, "manifest": build_manifest(_receipt()), "attempts": 0, "upload": {},
        "files": [],
    })
    grant = {
        "object_id": "obj", "role": "excerpt", "bytes": 4, "already_complete": False,
        "url": "https://acct.r2.cloudflarestorage.com/bucket/object?X-Amz-Signature=secret",
        "headers": {"content-md5": "abcd"},
        "parts": [{"number": 1, "offset": 0, "length": 4, "url": "https://acct.r2.cloudflarestorage.com/bucket/object?part=1&X-Amz-Signature=secret", "etag": "done"}],
    }
    live = queue.attach_remote_case(item["id"], case_id="remote", uploads=[grant], endpoint="https://127.0.0.1:9")
    assert live["upload"]["objects"][0]["url"] == grant["url"]
    stored = json.loads((data_dir / "diagnostics" / "queue.json").read_text())
    text = json.dumps(stored)
    assert "X-Amz-Signature" not in text
    assert "r2.cloudflarestorage.com" not in text
    resumed = queue.update(item["id"], upload={"case_id": "remote", "objects": [grant], "done": [{"number": 1, "etag": "done"}]})
    assert resumed["upload"]["objects"][0]["parts"][0]["etag"] == "done"
    text = (data_dir / "diagnostics" / "queue.json").read_text()
    assert "X-Amz-Signature" not in text
    reloaded = queue.get(item["id"])
    assert "url" not in reloaded["upload"]["objects"][0]
    assert reloaded["upload"]["done"] == [{"number": 1, "etag": "done"}]


def test_multipart_request_sends_one_md5_per_part(tmp_path):
    import base64
    import hashlib

    payload = b"abcdefghij"
    path = tmp_path / "clip.bin"
    path.write_bytes(payload)
    digests = media.part_md5s(path, len(payload), 4)
    assert digests == [
        base64.b64encode(hashlib.md5(payload[0:4]).digest()).decode("ascii"),
        base64.b64encode(hashlib.md5(payload[4:8]).digest()).decode("ascii"),
        base64.b64encode(hashlib.md5(payload[8:10]).digest()).decode("ascii"),
    ]
    assert media.part_md5s(path, len(payload), 16) == []


def test_source_link_keeps_the_video_id_and_drops_secrets():
    raw = "https://user:pass@www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLpublic&token=abc&signature=dead#frag"
    assert source.sanitize_source_link(raw) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLpublic"
    assert source.sanitize_source_link("file:///tmp/private.mp4") is None
    assert source.sanitize_source_link("https://www.youtube.com/watch?v=abc") == "https://www.youtube.com/watch?v=abc"
    secret_query = "https://www.youtube.com/watch?v=abc&api-key=1&x-api-key=2&x-auth=3&sign=4&%2574oken=5"
    assert source.sanitize_source_link(secret_query) == "https://www.youtube.com/watch?v=abc"
    assert source.sanitize_source_link("https://cdn.example/watch/%2FUsers%2Falice?v=abc") is None
    assert source.sanitize_source_link("https://www.youtube.com/watch?v=abc&next=%2FUsers%2Falice") == "https://www.youtube.com/watch?v=abc"
    assert source.sanitize_source_link("https://cdn.example/sk-live/watch?v=abc") is None
    assert source.sanitize_source_link("https://www.youtube.com/watch?v=abc&note=sk-live") == "https://www.youtube.com/watch?v=abc"
    assert source.sanitize_source_link("https://www.youtube.com:99999/watch?v=abc") is None
    contradictory = source.classify_metadata({"input_origin": "file", "source_url": "https://www.youtube.com/watch?v=abc"})
    assert contradictory.origin == "unknown"
    legacy_link = source.classify_metadata({"source_url": "https://youtu.be/A_156w0aYtU"})
    legacy_file = source.classify_metadata({"source_url": None, "via": "cli"})
    assert legacy_link.origin == "link" and legacy_link.source_url.startswith("https://youtu.be/")
    assert legacy_file.origin == "file"
    assert source.classify_metadata({}).origin == "unknown"
    assert source.classify_metadata(None).origin == "unknown"


def test_link_input_sends_the_url_and_does_not_transcode_or_upload_media(data_dir, tmp_path, monkeypatch):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    consent.update(diagnostics=True, media=True, full_original=True, informed=True)
    source.record_input_origin(
        "proj", "link",
        source_url="https://user:pass@www.youtube.com/watch?v=dQw4w9WgXcQ&token=abc#t=1",
    )
    raw = data_dir / "projects" / "proj" / "raw"
    raw.mkdir(parents=True)
    (raw / "input.mp4").write_bytes(b"downloaded-video")

    def boom(*args, **kwargs):
        raise AssertionError("link input must not transcode")

    monkeypatch.setattr(media, "default_cut", boom)
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued["files"] == []
    assert queued["manifest"]["source_link"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert "downloaded-video" not in json.dumps(queued)
    assert "token" not in queued["manifest"]["source_link"]
    assert "pass" not in queued["manifest"]["source_link"]

    class Transport:
        def __init__(self):
            self.files = None
            self.puts = 0

        def create_case(self, base, body, key):
            self.files = body["files"]
            return {"case_id": "remote", "capability": "cap", "uploads": []}

        def put_part(self, *args, **kwargs):
            self.puts += 1
            raise AssertionError("link input must not upload media")

        def complete(self, *args, **kwargs):
            raise AssertionError("no media part to complete")

    transport = Transport()
    upload.pump_once(transport)
    assert transport.files == []
    assert transport.puts == 0
    assert queue.list_items()[0]["status"] == "uploaded"


def test_unknown_origin_does_not_auto_upload_a_downloaded_file(data_dir, monkeypatch):
    consent.update(diagnostics=True, media=True, full_original=True, informed=True)
    raw = data_dir / "projects" / "proj" / "raw"
    raw.mkdir(parents=True)
    (raw / "input.mp4").write_bytes(b"downloaded-video")

    def boom(*args, **kwargs):
        raise AssertionError("unknown origin must not transcode")

    monkeypatch.setattr(media, "default_cut", boom)
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued["files"] == []
    assert "source_link" not in queued["manifest"]


def test_queued_link_media_is_blocked_before_put(data_dir, tmp_path):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "diagnostics" / "endpoint.json").write_text(json.dumps({"endpoint": "http://127.0.0.1:9"}), encoding="utf-8")
    consent.update(diagnostics=True, media=True, full_original=True, informed=True)
    source.record_input_origin("proj", "link", source_url="https://www.bilibili.com/video/BV1qheu6kEFV/?token=secret")
    media_file = data_dir / "projects" / "proj" / "raw" / "input.mp4"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"cached-link-video")
    queue.enqueue({
        "id": "c-old-link", "idempotency_key": "old-link", "status": "queued", "epoch": consent.load().epoch,
        "project_id": "proj", "attempt_id": TOKEN, "explicit": False, "disposition": "upload",
        "save_local": False, "manifest": build_manifest(_receipt()), "attempts": 0, "upload": {},
        "files": [{
            "role": "original", "path": str(media_file), "size_bytes": len(b"cached-link-video"),
            "sha256": __import__("hashlib").sha256(b"cached-link-video").hexdigest(), "content_type": "video/mp4",
        }],
    })

    class Transport:
        def __init__(self):
            self.files = None
            self.puts = 0

        def create_case(self, base, body, key):
            self.files = body["files"]
            return {"case_id": "remote", "capability": "cap", "uploads": []}

        def put_part(self, *args, **kwargs):
            self.puts += 1
            raise AssertionError("queued link video must not be uploaded")

        def complete(self, *args, **kwargs):
            raise AssertionError("no media part to complete")

    transport = Transport()
    upload.pump_once(transport)
    stored = queue.get("c-old-link")
    assert transport.files == []
    assert transport.puts == 0
    assert stored["files"] == []
    assert stored["manifest"]["source_link"] == "https://www.bilibili.com/video/BV1qheu6kEFV/"
    assert "token" not in stored["manifest"]["source_link"]
    assert "cached-link-video" not in json.dumps(stored)


def test_invalid_link_is_omitted_and_the_diagnostic_still_queues(data_dir, monkeypatch):
    consent.update(diagnostics=True, media=True, full_original=True, informed=True)
    source.record_input_origin("proj", "link", source_url="https://www.youtube.com:99999/watch?v=abc")
    raw = data_dir / "projects" / "proj" / "raw"
    raw.mkdir(parents=True)
    (raw / "input.mp4").write_bytes(b"downloaded-video")

    def boom(*args, **kwargs):
        raise AssertionError("invalid link must not transcode")

    monkeypatch.setattr(media, "default_cut", boom)
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued["files"] == []
    assert "source_link" not in queued["manifest"]
    assert queued["manifest"]["attempt"]["error_code"] == "timeout"
    assert "99999" not in json.dumps(queued["manifest"])


def test_contradictory_file_origin_does_not_upload_media(data_dir, monkeypatch):
    consent.update(diagnostics=True, media=True, full_original=True, informed=True)
    folder = data_dir / "projects" / "proj" / "metadata"
    folder.mkdir(parents=True)
    (folder / "input_origin.json").write_text(
        json.dumps({"origin": "file", "source_url": "https://www.youtube.com/watch?v=abc"}),
        encoding="utf-8",
    )
    raw = data_dir / "projects" / "proj" / "raw"
    raw.mkdir(parents=True)
    (raw / "input.mp4").write_bytes(b"downloaded-video")

    def boom(*args, **kwargs):
        raise AssertionError("contradictory origin must not transcode")

    monkeypatch.setattr(media, "default_cut", boom)
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued["files"] == []
    assert "source_link" not in queued["manifest"]


def test_unknown_origin_submit_does_not_transcode(data_dir, monkeypatch):
    root = data_dir / "projects" / "proj"
    (root / "metadata").mkdir(parents=True)
    (root / "raw").mkdir()
    (root / "raw" / "input.mp4").write_bytes(b"local-video")
    (root / "metadata" / "studio.json").write_text(json.dumps({"attempts": [_receipt()]}), encoding="utf-8")

    def boom(*args, **kwargs):
        raise AssertionError("unknown origin must not transcode")

    monkeypatch.setattr(media, "default_cut", boom)
    service.submit("proj", TOKEN, roles=["excerpt"], informed=True)
    stored = queue.list_items()[0]
    assert stored["files"] == []
    assert stored["manifest"]["attempt"]["error_code"] == "timeout"


def test_preview_includes_the_sanitized_source_link(data_dir):
    root = data_dir / "projects" / "proj"
    (root / "metadata").mkdir(parents=True)
    (root / "metadata" / "studio.json").write_text(json.dumps({"attempts": [_receipt()]}), encoding="utf-8")
    source.record_input_origin("proj", "link", source_url="https://www.youtube.com/watch?v=abc&api-key=secret")
    shown = service.preview("proj", TOKEN)
    assert shown["manifest"]["source_link"] == "https://www.youtube.com/watch?v=abc"


def test_unset_link_sends_the_url_only_and_explicit_off_stops(data_dir):
    source.record_input_origin("proj", "link", source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ&token=secret")
    raw = data_dir / "projects" / "proj" / "raw"
    raw.mkdir(parents=True)
    (raw / "input.mp4").write_bytes(b"downloaded-video")
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued["files"] == []
    assert queued["manifest"]["source_link"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert "downloaded-video" not in json.dumps(queued)
    assert not consent.consent_path().exists()
    service.set_consent(diagnostics=False, media=False, full_original=False, informed=True)
    assert queue.get(queued["id"])["status"] == "cancelled"
    assert service.background_enqueue("proj", _receipt(finished_at="2999-01-02T00:00:00+00:00", attempt_id="t-" + "ef" * 16)) is None


def test_unset_consent_is_excerpt_on_and_original_off():
    grant = consent._unset()
    assert grant.diagnostics is True and grant.media is True and grant.full_original is False
    assert grant.notice_seen is False and grant.persisted is False


def test_excerpt_span_uses_failure_time_or_the_first_minute():
    assert media.excerpt_span({"media_time_sec": 100}) == (85.0, 60.0)
    assert media.excerpt_span({"summary": {"media_time_sec": 40}}) == (25.0, 60.0)
    assert media.excerpt_span({}) == (0.0, 60.0)
    assert media.excerpt_span({"media_time_sec": 5}) == (0.0, 60.0)
    with pytest.raises(media.MediaRejected) as caught:
        media.default_cut(Path("/missing-source"), Path("/missing-dest"), duration_sec=181)
    assert caught.value.reason == "excerpt_window"


def test_default_cut_reencodes_with_the_diagnostics_preset(tmp_path, monkeypatch):
    source = tmp_path / "in.mp4"
    source.write_bytes(b"v")
    dest = tmp_path / "out" / "excerpt.mp4"
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = list(cmd)
        seen["timeout"] = kwargs.get("timeout")
        Path(cmd[-1]).write_bytes(b"ok")
        return media.subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    monkeypatch.setattr("backend.utils.ffmpeg_utils.get_ffmpeg_path", lambda: "ffmpeg")
    media.default_cut(source, dest)
    cmd = seen["cmd"]
    assert "copy" not in cmd
    assert seen["timeout"] == 180
    assert cmd[cmd.index("-ss") + 1] == "0.000"
    assert cmd[cmd.index("-t") + 1] == "60.000"
    assert cmd[cmd.index("-vf") + 1] == "scale='min(1280,iw)':-2"
    assert cmd[cmd.index("-vf") + 2:-1] == [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-map", "0:v:0", "-map", "0:a:0?",
    ]


def test_excerpt_over_40mb_is_discarded(tmp_path, monkeypatch):
    source = tmp_path / "in.mp4"
    source.write_bytes(b"v")
    dest = tmp_path / "excerpt.mp4"

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"x" * (media.EXCERPT_CLIENT_MAX + 1))
        return media.subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    monkeypatch.setattr("backend.utils.ffmpeg_utils.get_ffmpeg_path", lambda: "ffmpeg")
    with pytest.raises(media.MediaRejected) as caught:
        media.default_cut(source, dest)
    assert caught.value.reason == "excerpt_unavailable"
    assert not dest.exists()
    assert media.EXCERPT_CLIENT_MAX == 41943040


def test_confirmed_default_uploads_a_compressed_excerpt(data_dir, monkeypatch):
    source.record_input_origin("proj", "file")
    consent.update(diagnostics=True, media=True, full_original=False, informed=True)
    seen = {}

    def fake(project_id, roles, *, excerpt_dir, cut=None):
        seen["roles"] = list(roles)
        return []

    monkeypatch.setattr(media, "materialize", fake)
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert seen["roles"] == ["excerpt"]
    assert queued["files"] == []


def test_transcode_failure_keeps_the_manifest_and_skips_the_original(data_dir, monkeypatch):
    source.record_input_origin("proj", "file")
    consent.update(diagnostics=True, media=True, full_original=False, informed=True)
    raw = data_dir / "projects" / "proj" / "raw"
    raw.mkdir(parents=True)
    (raw / "input.mp4").write_bytes(b"full-original-bytes")

    def boom(*args, **kwargs):
        raise media.MediaRejected("excerpt_unavailable")

    monkeypatch.setattr(media, "default_cut", boom)
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert queued["files"] == []
    assert queued["manifest"]["attempt"]["error_code"] == "timeout"
    blob = json.dumps(queued)
    assert "full-original-bytes" not in blob
    assert "input.mp4" not in blob
    assert "original" not in {row.get("role") for row in queued["files"]}


def test_enabled_original_is_uploaded_without_transcode(data_dir, monkeypatch):
    source.record_input_origin("proj", "file")
    consent.update(diagnostics=True, media=True, full_original=True, informed=True)
    raw = data_dir / "projects" / "proj" / "raw"
    raw.mkdir(parents=True)
    (raw / "input.mp4").write_bytes(b"abcd")
    called = {"cut": False}

    def boom(*args, **kwargs):
        called["cut"] = True
        raise AssertionError("original must not be transcoded")

    monkeypatch.setattr(media, "default_cut", boom)
    queued = service.background_enqueue("proj", _receipt(finished_at="2999-01-01T00:00:00+00:00"))
    assert called["cut"] is False
    assert queued["files"][0]["role"] == "original"
    assert queued["files"][0]["path"].endswith("input.mp4")


def test_observe_cuts_around_the_failure_time(data_dir, monkeypatch):
    source.record_input_origin("proj", "file")
    consent.update(diagnostics=True, media=True, full_original=False, informed=True)
    raw = data_dir / "projects" / "proj" / "raw"
    raw.mkdir(parents=True)
    (raw / "input.mp4").write_bytes(b"v")
    seen = {}

    def record(source, dest, *, start_sec=0, duration_sec=60):
        seen["span"] = (start_sec, duration_sec)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"clip")
        return dest

    monkeypatch.setattr(media, "default_cut", record)
    row = _receipt(finished_at="2999-01-01T00:00:00+00:00", media_time_sec=100)
    observe.schedule_new_failures(
        "proj", {"attempts": [{"attempt_id": TOKEN, "state": "open"}]}, {"attempts": [row]},
    )
    observe.deliver_pending()
    assert seen["span"] == (85.0, 60.0)
    stored = queue.list_items()[0]
    assert stored["files"][0]["role"] == "excerpt"
    assert "media_time_sec" not in json.dumps(stored["manifest"])


def _failed_local_project():
    from backend.services.studio import store
    project = 'diagnostic-save'
    root = store.directory(project)
    (root / 'metadata').mkdir(parents=True)
    (root / 'raw').mkdir()
    (root / 'raw' / 'input.mp4').write_bytes(b'synthetic video')
    (root / 'metadata' / 'studio.json').write_text(json.dumps({'attempts': [_receipt()]}))
    source.record_input_origin(project, 'file')
    return project


def test_saving_then_uploading_are_distinct_idempotent_commands(data_dir, monkeypatch):
    project = _failed_local_project()
    monkeypatch.delenv('AUTOCLIP_DIAGNOSTICS_SYNC')
    monkeypatch.setattr(upload, 'wake', lambda: None)
    def submit(local):
        return service.submit(project, TOKEN, roles=[], informed=True, save_local=local)
    local, remote = submit(True), submit(False)
    assert local['id'] != remote['id']
    assert submit(True)['id'] == local['id']
    assert submit(False)['id'] == remote['id']
    assert [row['disposition'] for row in queue.list_items()] == ['local', 'upload']


@pytest.mark.parametrize('full', [False, True])
def test_unclaimed_excerpts_removed_on_dedup_and_queue_full(data_dir, monkeypatch, full):
    project = _failed_local_project()
    monkeypatch.setattr(upload, 'wake', lambda: None)
    monkeypatch.delenv('AUTOCLIP_DIAGNOSTICS_SYNC')
    def cut(_, dest):
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'synthetic')
    def submit():
        return service.submit(project, TOKEN, roles=['excerpt'], informed=True, save_local=True, cut=cut)
    if full:
        monkeypatch.setattr(queue, 'MAX_ITEMS', 1)
        queue.enqueue({'id': 'first', 'idempotency_key': 'other', 'status': 'queued'})
        with pytest.raises(service.DiagnosticsError, match='queue_full'):
            submit()
    else:
        first, second = submit(), submit()
        assert first['id'] == second['id']
        service.delete_local(first['id'])
    assert not list((data_dir / 'diagnostics' / 'excerpts').glob('*/excerpt.mp4'))


def test_submit_offloads_sync_work_while_consent_request_finishes(data_dir, monkeypatch):
    import asyncio
    import httpx
    from backend.api.v1 import diagnostics as api

    app = FastAPI()
    app.include_router(api.router)
    entered, release = threading.Event(), threading.Event()
    def slow_submit(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return {'status': 'queued'}
    monkeypatch.setattr(api, 'submit', slow_submit)
    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1') as client:
            job = asyncio.create_task(client.post('/diagnostics/submit', json={'project_id': 'fixture', 'informed': True}))
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                assert (await client.get('/diagnostics/consent')).status_code == 200
                assert not job.done()
            finally:
                release.set()
                await job
    asyncio.run(exercise())


def test_desktop_startup_resumes_pending_deletion(data_dir, monkeypatch):
    from backend.app_factory import create_app
    called = []
    monkeypatch.setattr(upload, 'wake', lambda: called.append(True))
    queue.enqueue({'id': 'resume-deletion', 'idempotency_key': 'pending', 'status': 'delete_pending'})
    with TestClient(create_app('desktop'), base_url='http://127.0.0.1:8000') as client:
        assert client.get('/api/v1/diagnostics/cases').status_code == 200
    assert called == [True]


def test_upgrade_only_removes_stale_unclaimed_excerpt_staging(data_dir):
    import os
    folder = data_dir / 'diagnostics' / 'excerpts'
    def make(name, *, stale=True):
        directory = folder / name
        directory.mkdir(parents=True)
        clip = directory / 'excerpt.mp4'
        clip.write_bytes(b'fixture')
        if stale:
            os.utime(clip, (1, 1))
            os.utime(directory, (1, 1))
        return clip

    owner = queue.new_id()
    queue.enqueue({'id': owner, 'idempotency_key': 'existing', 'status': 'queued'})
    claimed = make(owner)
    older = make(queue.new_id())
    current = make(queue.new_id(), stale=False)
    unrelated = make('other')
    queue.clean_unclaimed_excerpts()
    assert not older.exists()
    assert claimed.exists() and current.exists() and unrelated.exists()
    unverified = make(queue.new_id())
    queue.queue_path().write_text('unreadable')
    with pytest.raises(ValueError):
        queue.clean_unclaimed_excerpts()
    assert unverified.exists()


def test_save_io_failure_is_visible_and_can_be_retried(data_dir, monkeypatch):
    project = _failed_local_project()
    original_export = upload._export_local
    def full_disk(item):
        original_export(item)
        raise OSError('disk full')
    monkeypatch.setattr(upload, '_export_local', full_disk)
    first = service.submit(project, TOKEN, roles=[], informed=True, save_local=True)
    assert first['status'] == 'failed'
    assert not (data_dir / 'diagnostics' / 'exports' / first['id']).exists()
    monkeypatch.setattr(upload, '_export_local', original_export)
    second = service.submit(project, TOKEN, roles=[], informed=True, save_local=True)
    assert second['status'] == 'saved_local'
    assert second['id'] != first['id']


def test_two_inflight_excerpt_producers_only_leave_the_queued_copy(data_dir, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    project = _failed_local_project()
    barrier = threading.Barrier(2)
    monkeypatch.setattr(upload, 'wake', lambda: None)
    monkeypatch.setattr(service, '_input_for_diagnostics', lambda _: ('file', None))
    monkeypatch.delenv('AUTOCLIP_DIAGNOSTICS_SYNC')
    def cut(_, dest):
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'synthetic')
        barrier.wait(timeout=5)
    def submit():
        return service.submit(project, TOKEN, roles=['excerpt'], informed=True, cut=cut)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(submit) for _ in range(2)]
        first, second = (future.result() for future in futures)
    assert first['id'] == second['id']
    assert len(queue.list_items()) == 1
    assert len(list((data_dir / 'diagnostics' / 'excerpts').glob('*/excerpt.mp4'))) == 1
