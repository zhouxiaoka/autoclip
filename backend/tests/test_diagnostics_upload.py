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
    key = "帮助改进 AutoClip"
    purpose = "失败后在后台上传脱敏诊断，只用于排查问题并改进产品，不会用于训练模型。默认关闭。不含 API 密钥、字幕正文、项目名或个人路径。未配置上传地址时不会发送。关闭后会停掉尚未完成的上传。"
    for lang in ("zh", "en", "ja", "ko", "es", "pt", "ru", "fr"):
        data = json.loads((ROOT / "frontend/src/i18n/locales" / f"{lang}.json").read_text(encoding="utf-8"))
        assert data[key]
        assert data[purpose]
        if lang != "zh":
            assert data[purpose] != purpose


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
    assert consent.load().diagnostics is False
    with pytest.raises(PermissionError):
        consent.update(diagnostics=True, media=True, full_original=True, informed=False)
    granted = consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    assert granted.epoch == 1 and granted.diagnostics_at
    item = queue.enqueue({
        "id": "c-1", "idempotency_key": "k1", "status": "queued", "epoch": granted.epoch,
        "manifest": build_manifest(_receipt()), "files": [], "explicit": False,
    })
    assert item["status"] == "queued"
    service.set_consent(diagnostics=False, media=False, full_original=False, informed=True)
    assert queue.list_items()[0]["status"] == "cancelled"
    assert consent.load().epoch == 2


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
    upload.pump_once()
    rows = queue.list_items()
    assert len(rows) == 1
    assert rows[0]["attempt_id"] == TOKEN
    assert rows[0]["status"] == "needs_endpoint"
    assert rows[0]["files"] == []
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
        "id": "c-race", "idempotency_key": "race", "status": "queued", "epoch": 1,
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
    assert queue.read_capability("c-late") == "late-secret"
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
