"""Actual upload route: one operation must not create/dispatch twice; no provider calls."""
import pytest
from backend.tests.test_studio import root, source, client
from backend.services.studio import jobs, readiness
from backend.core import database
from backend.models.project import Project


@pytest.fixture(autouse=True)
def ready(monkeypatch):
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)
    # Same shared 3s media fixture as existing import tests; duration refusal has its own regression.
    monkeypatch.setattr('backend.pipeline.media_precheck.too_short', lambda duration: False)


def upload(client, source, operation='operation-one', **options):
    return client.post('/studio/import', data={'goal': 'auto', 'auto_start': 'true',
        'import_operation_id': operation, **options},
        files={'video': ('fixture.mp4', source.read_bytes(), 'video/mp4')})


def test_repeated_upload_returns_one_persistent_receipt_and_dispatch(client, source, monkeypatch):
    calls = []
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *args, **kwargs: calls.append(pid) or 'run-one')
    first = upload(client, source)
    second = upload(client, source)
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json() == second.json()
    assert len(calls) == 1
    with database.session_scope() as db:
        assert db.query(Project).filter(Project.id != 'p1').count() == 1
    # Readiness may change after the initial upload; a completed operation still returns its receipt.
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: pytest.fail('must not re-validate/re-dispatch'))
    assert upload(client, source).json() == first.json()


@pytest.mark.parametrize('option', [{'instruction': 'different'}, {'platforms': 'tiktok'}, {'name': 'different'}])
def test_same_operation_rejects_changed_settings(client, source, monkeypatch, option):
    calls = []
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *a, **k: calls.append(pid) or 'run-one')
    assert upload(client, source).status_code == 200
    conflict = upload(client, source, **option)
    assert conflict.status_code == 409 and conflict.json()['detail']['import_state'] == 'unknown'
    assert len(calls) == 1


def test_distinct_operations_create_independent_projects_even_for_same_file(client, source, monkeypatch):
    calls = []
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *a, **k: calls.append(pid) or 'run-one')
    first = upload(client, source, 'operation-one').json()
    second = upload(client, source, 'operation-two').json()
    assert first['project_id'] != second['project_id'] and len(calls) == 2


def test_concurrent_repeat_returns_unknown_until_first_receipt_commits(client, source, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    entered, release = threading.Event(), threading.Event()
    calls = []
    def dispatch(pid, *a, **k):
        calls.append(pid); entered.set()
        assert release.wait(15)
        return 'run-one'
    monkeypatch.setattr(jobs, 'inspect_project', dispatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(upload, client, source)
        try:
            assert entered.wait(10)
            # Separate portals model separate API workers; the synchronous dispatch fixture
            # deliberately blocks its own loop and must not block the duplicate worker.
            from fastapi.testclient import TestClient
            with TestClient(client.app) as other:
                pending = upload(other, source)
            assert pending.status_code == 409 and pending.json()['detail']['import_state'] == 'unknown'
            assert len(calls) == 1
        finally:
            release.set()
        receipt = first.result(timeout=15)
    assert upload(client, source).json() == receipt.json()
    assert len(calls) == 1


def test_failure_after_project_creation_never_replays_pending_operation(client, source, monkeypatch):
    calls = []
    def dispatch(pid, *a, **k):
        calls.append(pid)
        raise RuntimeError('fixture dispatch uncertainty')
    monkeypatch.setattr(jobs, 'inspect_project', dispatch)
    with pytest.raises(RuntimeError, match='fixture dispatch uncertainty'):
        upload(client, source)
    pending = upload(client, source)
    assert pending.status_code == 409 and len(calls) == 1
    with database.session_scope() as db:
        assert db.query(Project).filter(Project.id != 'p1').count() == 1


def test_receipt_survives_new_process_and_stores_only_hashes(client, source, monkeypatch):
    import hashlib, json, subprocess, sys
    from backend.services.studio import import_receipts as receipts
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *a, **k: 'run-one')
    expected = upload(client, source).json()
    conn = receipts.connect(receipts.ledger_path())
    try:
        operation, payload, saved = conn.execute('SELECT operation,payload,receipt FROM import_receipts').fetchone()
    finally:
        conn.close()
    assert operation == hashlib.sha256(b'operation-one').hexdigest()
    assert len(payload) == 64 and json.loads(saved) == expected and 'fixture.mp4' not in saved
    code = 'from pathlib import Path; import json,sys; from backend.services.studio.import_receipts import claim; print(json.dumps(claim(Path(sys.argv[1]),sys.argv[2],sys.argv[3])))'
    actual = subprocess.check_output([sys.executable, '-c', code, str(receipts.ledger_path()), operation, payload], text=True, timeout=30)
    assert json.loads(actual) == expected


def test_corrupt_ledger_is_preserved_and_refuses_all_side_effects(client, source, monkeypatch):
    from backend.services.studio import import_receipts as receipts
    path = receipts.ledger_path(); path.write_bytes(b'not a database')
    monkeypatch.setattr(jobs, 'inspect_project', lambda *a, **k: pytest.fail('must not dispatch'))
    response = upload(client, source)
    assert response.status_code == 503 and response.json()['detail']['import_state'] == 'unknown'
    assert path.read_bytes() == b'not a database'
    with database.session_scope() as db:
        assert db.query(Project).filter(Project.id != 'p1').count() == 0


def test_corrupt_saved_receipt_never_recreates_a_project(client, source, monkeypatch):
    from backend.services.studio import import_receipts as receipts
    calls = []
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *a, **k: calls.append(pid) or 'run-one')
    assert upload(client, source).status_code == 200
    conn = receipts.connect(receipts.ledger_path())
    try:
        conn.execute("UPDATE import_receipts SET receipt='{}'"); conn.commit()
    finally:
        conn.close()
    assert upload(client, source).status_code == 503 and len(calls) == 1


def test_readonly_receipt_directory_refuses_creation(client, source, monkeypatch):
    import os
    from backend.services.studio import import_receipts as receipts
    path = receipts.ledger_path()
    monkeypatch.setattr(jobs, 'inspect_project', lambda *a, **k: pytest.fail('must not dispatch'))
    mode = path.parent.stat().st_mode
    if os.name != 'nt' and os.geteuid() != 0:
        path.parent.chmod(0o555)
    else:
        # CI's privileged/Windows account cannot reproduce POSIX permission denial this way.
        def denied(*a): raise PermissionError('fixture permission denial')
        monkeypatch.setattr(receipts, 'connect', denied)
    try:
        response = upload(client, source)
        assert response.status_code == 503 and response.json()['detail']['import_state'] == 'unknown'
    finally:
        if os.name != 'nt': path.parent.chmod(mode & 0o777)
    with database.session_scope() as db:
        assert db.query(Project).filter(Project.id != 'p1').count() == 0


@pytest.mark.parametrize('key', ['', ' ', '../other', 'x' * 129])
def test_invalid_operation_id_cannot_silently_become_unkeyed(client, source, monkeypatch, key):
    monkeypatch.setattr(jobs, 'inspect_project', lambda *a, **k: pytest.fail('must not dispatch'))
    assert upload(client, source, key).status_code == 422


def test_same_key_rejects_changed_video_and_subtitle(client, source, monkeypatch):
    calls = []
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *a, **k: calls.append(pid) or 'run-one')
    assert upload(client, source).status_code == 200
    changed = client.post('/studio/import', data={'goal':'auto','auto_start':'true','import_operation_id':'operation-one'},
        files={'video': ('fixture.mp4', b'different file contents', 'video/mp4')})
    assert changed.status_code == 409
    with_subtitle = client.post('/studio/import', data={'goal':'auto','auto_start':'true','import_operation_id':'operation-one'},
        files={'video': ('fixture.mp4', source.read_bytes(), 'video/mp4'), 'subtitle': ('fixture.srt', b'1\n00:00:00,000 --> 00:00:02,000\nfixture\n', 'text/plain')})
    assert with_subtitle.status_code == 409 and len(calls) == 1


def test_unkeyed_import_remains_an_independent_operation(client, source, monkeypatch):
    calls = []
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *a, **k: calls.append(pid) or 'run-one')
    for _ in range(2):
        response = client.post('/studio/import', data={'goal':'auto','auto_start':'true'},
            files={'video': ('fixture.mp4', source.read_bytes(), 'video/mp4')})
        assert response.status_code == 200
    assert len(set(calls)) == 2


def test_foreign_database_and_future_ledger_are_not_modified(client, source, monkeypatch):
    import sqlite3
    from backend.services.studio import import_receipts as receipts
    path = receipts.ledger_path()
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE unrelated (value TEXT)'); conn.commit(); conn.close()
    before = path.read_bytes()
    monkeypatch.setattr(jobs, 'inspect_project', lambda *a, **k: pytest.fail('must not dispatch'))
    assert upload(client, source).status_code == 503 and path.read_bytes() == before
    path.unlink()
    conn = receipts.connect(path); conn.execute('PRAGMA user_version=3'); conn.close()
    before = path.read_bytes()
    assert upload(client, source).status_code == 503 and path.read_bytes() == before


def test_duplicate_receipt_fields_are_invalid_not_last_value_wins(client, source, monkeypatch):
    import json
    from backend.services.studio import import_receipts as receipts
    calls=[]
    monkeypatch.setattr(jobs,'inspect_project',lambda pid,*a,**k:calls.append(pid) or 'run-one')
    expected=upload(client,source).json()
    duplicate='{"project_id":"wrong","project_id":'+json.dumps(expected['project_id'])+',"analysis_run_id":"run-one"}'
    conn=receipts.connect(receipts.ledger_path())
    conn.execute('UPDATE import_receipts SET receipt=?',(duplicate,));conn.commit();conn.close()
    assert upload(client,source).status_code==503 and len(calls)==1


def test_actual_readiness_advertises_the_keyed_import_protocol(client,monkeypatch):
    monkeypatch.setattr(readiness,'report',lambda:{'checks':{},'ready':False})
    assert client.get('/studio/readiness').json()['batch_import_receipts'] is True


@pytest.mark.parametrize('damage',['truncate','drop_table'])
def test_existing_ledger_damage_refuses_reinitialization_and_replay(client,source,monkeypatch,damage):
    from backend.services.studio import import_receipts as receipts
    calls=[]
    monkeypatch.setattr(jobs,'inspect_project',lambda pid,*a,**k:calls.append(pid) or 'run-one')
    first=upload(client,source)
    assert first.status_code==200 and upload(client,source).json()==first.json()
    if damage=='truncate': receipts.ledger_path().write_bytes(b'')
    else:
        conn=receipts.connect(receipts.ledger_path());conn.execute('DROP TABLE import_receipts');conn.commit();conn.close()
    response=upload(client,source)
    assert response.status_code==503 and response.json()['detail']['import_state']=='unknown'
    assert len(calls)==1
    with database.session_scope() as db:
        assert db.query(Project).filter(Project.id!='p1').count()==1


@pytest.mark.parametrize('damage',['delete_rows','delete_file','delete_file_and_marker'])
def test_lost_receipt_records_cannot_repeat_a_known_project(client,source,monkeypatch,damage):
    from backend.services.studio import import_receipts as receipts
    calls=[]
    monkeypatch.setattr(jobs,'inspect_project',lambda pid,*a,**k:calls.append(pid) or 'run-one')
    first=upload(client,source);assert first.status_code==200
    assert first.json()['project_id']==receipts.operation_project_id('operation-one')
    if damage=='delete_rows':
        conn=receipts.connect(receipts.ledger_path());conn.execute('DELETE FROM import_receipts');conn.commit();conn.close()
    else:
        receipts.ledger_path().unlink()
        if damage=='delete_file_and_marker':receipts.initialized_marker(receipts.ledger_path()).unlink()
    response=upload(client,source)
    assert response.status_code==503 and response.json()['detail']['import_state']=='unknown'
    assert len(calls)==1
    if damage!='delete_rows':assert not receipts.ledger_path().exists()
    with database.session_scope() as db:assert db.query(Project).filter(Project.id!='p1').count()==1


def test_unreleased_v1_ledger_is_preserved_not_automatically_migrated(client,source,monkeypatch):
    from backend.services.studio import import_receipts as receipts
    conn=receipts.connect(receipts.ledger_path());conn.execute('PRAGMA user_version=1');conn.close()
    before=receipts.ledger_path().read_bytes()
    monkeypatch.setattr(jobs,'inspect_project',lambda *a,**k:pytest.fail('must not dispatch'))
    assert upload(client,source).status_code==503 and receipts.ledger_path().read_bytes()==before


def test_source_directory_still_blocks_replay_when_project_and_receipt_rows_are_missing(client,source,monkeypatch):
    from backend.services.studio import import_receipts as receipts
    calls=[]
    monkeypatch.setattr(jobs,'inspect_project',lambda pid,*a,**k:calls.append(pid) or 'run-one')
    first=upload(client,source).json()
    conn=receipts.connect(receipts.ledger_path());conn.execute('DELETE FROM import_receipts');conn.commit();conn.close()
    with database.session_scope() as db:
        db.delete(db.get(Project,first['project_id']));db.commit()
    assert upload(client,source).status_code==503 and len(calls)==1


def test_receipt_marker_and_ledger_open_in_binary_mode_on_windows(tmp_path, monkeypatch):
    """Windows os.open() defaults to O_TEXT (CRLF translation), which corrupts the LF marker unless O_BINARY is passed."""
    import os
    from backend.services.studio import import_receipts as receipts

    fake_o_binary = 0x8000
    real_open = os.open
    seen_flags: list[tuple[str, int]] = []

    def tracking_open(path, flags, mode=0o777):
        seen_flags.append((os.path.basename(str(path)), flags))
        return real_open(path, flags & ~fake_o_binary, mode)

    monkeypatch.setattr(os, 'O_BINARY', fake_o_binary, raising=False)
    monkeypatch.setattr(os, 'open', tracking_open)

    ledger = tmp_path / 'studio-import-receipts.sqlite3'
    assert receipts.claim(ledger, 'op-win', 'payload-win') is None
    receipts.complete(ledger, 'op-win', 'payload-win', {'project_id': 'proj-win', 'analysis_run_id': None})
    assert receipts.claim(ledger, 'op-win', 'payload-win') == {'project_id': 'proj-win', 'analysis_run_id': None}
    assert seen_flags, 'expected os.open calls'
    for name, flags in seen_flags:
        if name.startswith('studio-import-receipts'):
            assert flags & fake_o_binary, f'{name} opened without O_BINARY (Windows CRLF hazard)'
