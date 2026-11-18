"""Unknown create outcomes, durable cancellation, and expired upload grants."""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.services.diagnostics import consent, queue, service, source, upload
from backend.services.diagnostics.manifest import build_manifest
from backend.services.studio import store


@pytest.fixture
def item(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_DIAGNOSTICS_SYNC", "1")
    monkeypatch.setenv("AUTOCLIP_DIAGNOSTICS_ENDPOINT", "http://127.0.0.1:9")
    consent.update(diagnostics=True, media=False, full_original=False, informed=True)
    source.record_input_origin("recovery", "file")
    path = store.directory("recovery") / "raw" / "input.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"abcdef")
    receipt = {"attempt_id": "t-" + "ab" * 16, "state": "failed", "kind": "generation", "trigger": "initial",
               "sequence": 1, "error_code": "timeout", "failure_stage": "analyze"}
    return queue.enqueue({
        "id": "c-recovery", "idempotency_key": "ab" * 32, "status": "queued", "epoch": consent.load().epoch,
        "explicit": True, "project_id": "recovery", "manifest": build_manifest(receipt), "attempts": 0, "upload": {},
        "files": [{"role": "original", "path": str(path), "size_bytes": 6,
                   "sha256": hashlib.sha256(b"abcdef").hexdigest(), "content_type": "video/mp4"}],
    })


class Transport:
    def __init__(self):
        self.creates = self.puts = self.deletes = self.cancels = 0
        self.remote = False
        self.key = self.secret = ""

    def create_case(self, base, body, key):
        self.creates += 1
        self.key, self.secret = key, body.get("recovery_token")
        self.remote = True
        return {"case_id": "remote", "capability": "cap", "uploads": [{
            "object_id": "object", "role": "original", "parts": [
                {"number": number, "offset": offset, "length": 3, "url": f"http://127.0.0.1:9/{self.creates}/{number}", "headers": {}}
                for number, offset in ((1, 0), (2, 3))
            ],
        }]}

    def cancel_creation(self, base, key, secret):
        self.cancels += 1
        assert key == self.key and secret == self.secret
        self.remote = False
        return {"deleted": True}

    def delete(self, *args):
        self.deletes += 1
        self.remote = False

    def put_part(self, url, data, headers):
        self.puts += 1
        return f"etag-{url.rsplit('/', 1)[-1]}"

    def complete(self, base, case_id, capability, body):
        return {"ok": True, "bytes": body["bytes"]}


@pytest.mark.parametrize("during_create", [False, True])
def test_lost_response_then_delete_never_replays_create_or_forgets_erasure(item, during_create):
    class Lost(Transport):
        def create_case(self, base, body, key):
            super().create_case(base, body, key)
            if during_create:
                service.delete_local(item["id"], transport=self)
            raise upload.Offline("response_lost_after_commit")
    transport = Lost()
    upload.pump_once(transport)
    service.delete_local(item["id"], transport=transport)
    upload.pump_once(transport)
    assert not transport.remote
    assert transport.creates == 1 and transport.puts == 0 and transport.cancels == 1
    assert queue.get(item["id"])["status"] == "deleted"
    assert transport.secret and transport.secret not in queue.queue_path().read_text()


def _exit_after_remote_create(server_file):
    class Crashed:
        def create_case(self, base, body, key):
            Path(server_file).write_text(json.dumps({"base": base, "key": key, "secret": body.get("recovery_token"), "remote": True}))
            os._exit(0)
    upload.pump_once(Crashed())


def test_process_exit_before_response_keeps_cleanup_retryable_after_restart(item, tmp_path, monkeypatch):
    remote = tmp_path / "server.json"
    child = multiprocessing.get_context("spawn").Process(target=_exit_after_remote_create, args=(str(remote),))
    child.start()
    child.join(15)
    if child.is_alive():
        child.kill()
        child.join()
        pytest.fail("child did not reach create checkpoint")
    assert child.exitcode == 0
    server = json.loads(remote.read_text())
    assert server["remote"] is True
    monkeypatch.setenv("AUTOCLIP_DIAGNOSTICS_ENDPOINT", "http://127.0.0.1:1")
    class Restarted(Transport):
        def cancel_creation(self, base, key, secret):
            self.cancels += 1
            assert base == server["base"] and key == server["key"] and secret == server["secret"]
            if self.cancels == 1:
                raise upload.Offline("cleanup_offline")
            server["remote"] = False
            return {"deleted": True}
    transport = Restarted()
    service.delete_local(item["id"], transport=transport)
    assert queue.get(item["id"])["status"] == "delete_pending"
    recovery = tmp_path / "diagnostics/recovery/c-recovery"
    if os.name != "nt":
        assert recovery.stat().st_mode & 0o777 == 0o600
    upload.pump_once(transport)
    assert server["remote"] is False
    assert transport.creates == 0 and transport.puts == 0 and transport.cancels == 2
    assert queue.get(item["id"])["status"] == "deleted"
    assert not recovery.exists()


def test_expired_part_grant_refreshes_same_objects_and_keeps_completed_parts(item):
    class Expired(Transport):
        def __init__(self):
            super().__init__()
            self.sent = []
            self.parts = []
        def put_part(self, url, data, headers):
            self.puts += 1
            if url.endswith('/1/2'):
                raise upload.Offline("http_403")
            self.sent.append(bytes(data))
            return "etag-" + url.rsplit('/', 1)[-1]
        def complete(self, base, case_id, capability, body):
            self.parts = body['parts']
            return super().complete(base, case_id, capability, body)
    transport = Expired()
    upload.pump_once(transport)
    assert queue.get(item['id'])['status'] != 'uploaded'
    upload.pump_once(transport, now=datetime.now(timezone.utc) + timedelta(hours=1))
    assert queue.get(item['id'])['status'] == 'uploaded'
    assert transport.creates == 2 and transport.sent == [b'abc', b'def']
    assert transport.parts == [{'partNumber': 1, 'etag': 'etag-1'}, {'partNumber': 2, 'etag': 'etag-2'}]


def test_auth_rejections_are_bounded_even_when_new_signatures_also_fail(item):
    class Rejected(Transport):
        def put_part(self, *args):
            self.puts += 1
            raise upload.Offline('http_403')
    transport = Rejected()
    for _ in range(10):
        upload.pump_once(transport, now=datetime.now(timezone.utc) + timedelta(hours=1))
    assert queue.get(item['id'])['status'] == 'failed'
    assert transport.creates == transport.puts == 3


def test_delete_during_refresh_wins_and_does_not_resume_parts(item):
    class Expired(Transport):
        def create_case(self, base, body, key):
            result = super().create_case(base, body, key)
            if self.creates == 2:
                service.delete_local(item['id'], transport=self)
            return result
        def put_part(self, *args):
            self.puts += 1
            raise upload.Offline('http_403')
    transport = Expired()
    upload.pump_once(transport)
    upload.pump_once(transport)
    assert queue.get(item['id'])['status'] == 'deleted'
    assert transport.puts == 1 and transport.remote is False


@pytest.mark.parametrize('scenario', ['lost', 'expired'])
def test_urllib_client_and_sql_api_recover_over_real_loopback_http(item, monkeypatch, tmp_path, scenario):
    """Exercise the shipped Python transport against the shipped Worker handler and SQL."""
    import subprocess
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    runner = Path(__file__).resolve().parents[2] / 'services/diagnostics-api/test/loopback.ts'
    with (tmp_path / 'worker.log').open('w') as log:
        child = subprocess.Popen(['node', '--experimental-transform-types', str(runner), scenario],
                                 stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                try:
                    line = executor.submit(child.stdout.readline).result(timeout=15)
                except TimeoutError:
                    child.kill()
                    raise AssertionError('loopback API did not start') from None
            assert line, (tmp_path / 'worker.log').read_text()
            base = json.loads(line)['endpoint']
            monkeypatch.setenv('AUTOCLIP_DIAGNOSTICS_ENDPOINT', base)
            upload.pump_once()  # real UrllibTransport
            assert queue.get(item['id'])['status'] != 'uploaded'
            if scenario == 'lost':
                service.delete_local(item['id'])
            else:
                upload.pump_once(now=datetime.now(timezone.utc) + timedelta(seconds=10))
            with urllib.request.urlopen(base + '/__state', timeout=5) as response:
                state = json.load(response)
            if scenario == 'lost':
                assert queue.get(item['id'])['status'] == 'deleted'
                assert state['requests']['POST /v1/cases'] == 1
                assert state['requests']['POST /v1/cases/cancel'] == 1
                assert state['cases'] == [{'state': 'deleted'}]
                assert state['objects'] == [] and state['quota'] == {'landed': 0, 'reserved': 0}
            else:
                assert queue.get(item['id'])['status'] == 'uploaded'
                assert state['requests']['POST /v1/cases'] == 2
                assert state['requests']['PUT /grants/1'] == state['requests']['PUT /grants/2'] == 1
                assert state['cases'] == [{'state': 'complete'}]
                stored = next(row for row in state['objects'] if row['key'].endswith('/original'))
                assert bytes(stored['bytes']) == b'abcdef'
                assert state['quota']['reserved'] == 0
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()


def test_bounded_queue_keeps_the_identity_of_an_unknown_create_even_after_retry_exhaustion(item):
    queue.update(item['id'], status='failed', inflight_create=True)
    for index in range(queue.MAX_ITEMS + 5):
        queue.enqueue({'id': f'local-{index}', 'idempotency_key': f'local-{index}', 'status': 'saved_local'})
    assert queue.get(item['id'])['inflight_create'] is True
    assert len(queue.list_items()) == queue.MAX_ITEMS
