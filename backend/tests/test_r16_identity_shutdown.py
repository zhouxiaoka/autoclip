"""R16 #40 (attempt identity from start to every terminal), #43 (restart mid-render records
shutdown_kind), #42 (clean marker only from the shell's shutdown intent; parent loss is its own kind)."""
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.studio import store

START = {'provider': 'deepseek', 'config_source': 'preset'}
LATER = {'provider': 'kimi', 'config_source': 'customized'}  # settings changed mid-run


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    from backend.services.studio import failure_identity, shutdown_marker
    monkeypatch.setattr(failure_identity, 'provider_identity', lambda: dict(LATER))
    shutdown_marker._consumed.clear()


def _variant(vid, status, code=None):
    row = {'id': vid, 'status': status}
    if code:
        row['error_code'] = code
    return row


# --- #40 ------------------------------------------------------------------------------------

def test_attempt_identity_prefers_start_and_ignores_junk():
    assert store.attempt_identity({**START, 'x': 1}, LATER) == START
    assert store.attempt_identity(None, {'provider': ''}, {'config_source': 'preset'}) == {'config_source': 'preset'}


@pytest.mark.parametrize('statuses,outcome', [
    (('completed', 'completed'), 'completed'),
    (('completed', 'failed'), 'partial'),
    (('failed', 'failed'), 'failed'),
])
def test_render_settle_carries_start_identity(statuses, outcome):
    data = {'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', **START},
            'generation': {'status': 'rendering', 'auto_start': True},
            'output_variants': [_variant(str(i), s, 'render' if s == 'failed' else None) for i, s in enumerate(statuses)],
            'jobs': []}
    store.settle_generation(data)
    assert data['generation']['status'] == outcome
    for record in (data['analysis'], data['generation']):
        assert {k: record.get(k) for k in START} == START


def test_restart_recovery_carries_start_identity():
    data = {'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r', 'instance': 'e' * 32, **START},
            'generation': {'status': 'production', 'auto_start': True}}
    assert store._recover_interrupted_run(data)
    for record in (data['analysis'], data['generation']):
        assert {k: record.get(k) for k in START} == START
        assert record['failure_stage'] == 'production'


def test_screening_start_records_identity_and_failure_keeps_it(monkeypatch):
    """Real inspect_project -> studio.json -> worker failure, with settings changed mid-run."""
    from backend.services.studio import failure_identity, jobs, readiness
    from backend.services.studio.models import ImportOptions
    monkeypatch.setattr(failure_identity, 'provider_identity', lambda: dict(START))
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    submitted = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, _io_receipt=None, **k: submitted.append((fn, a)))
    (store.directory('p40') / 'metadata').mkdir(parents=True)
    store.write('p40', {'id': 'p40'})
    jobs.inspect_project('p40', ImportOptions(auto_start=True, platforms=['original']))
    state = store.read('p40')
    for record in (state['analysis'], state['generation']):
        assert {k: record.get(k) for k in START} == START
    monkeypatch.setattr(failure_identity, 'provider_identity', lambda: dict(LATER))
    from backend.services.studio import planning
    monkeypatch.setattr(planning, 'recommend', lambda *a, **k: (_ for _ in ()).throw(TimeoutError('slow upstream')))
    monkeypatch.setattr(jobs, 'source', lambda *a, **k: None)
    fn, args = submitted[0]
    fn(*args)
    state = store.read('p40')
    assert state['analysis']['status'] == 'failed'
    for record in (state['analysis'], state['generation']):
        assert {k: record.get(k) for k in START} == START, record


# --- #43 ------------------------------------------------------------------------------------

@pytest.mark.parametrize('marker,kind', [(None, 'crash'), ('user_quit', 'clean'), ('update', 'clean'), ('parent_lost', 'parent_lost')])
def test_restart_midway_through_rendering_records_shutdown_kind(marker, kind):
    from backend.services.studio.shutdown_marker import mark
    old = 'f' * 32
    if marker:
        mark(marker, old)
    data = {'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', 'instance': old, **START},
            'generation': {'status': 'rendering', 'auto_start': True},
            'output_variants': [_variant('a', 'completed'), _variant('b', 'queued')], 'jobs': []}
    assert store._recover_interrupted_run(data)
    assert data['generation']['status'] == 'partial'
    assert data['generation']['error_code'] == store.RESTART_CODE
    assert data['generation']['shutdown_kind'] == kind
    assert data['analysis']['shutdown_kind'] == kind
    assert data['analysis']['failure_stage'] == 'render'
    assert data['analysis']['provider'] == 'deepseek'


def test_finished_render_without_restart_has_no_shutdown_kind():
    data = {'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', 'instance': '1' * 32},
            'generation': {'status': 'rendering', 'auto_start': True},
            'output_variants': [_variant('a', 'completed'), _variant('b', 'failed', 'render')], 'jobs': []}
    assert store._recover_interrupted_run(data)
    assert 'shutdown_kind' not in data['generation']


# --- #42 ------------------------------------------------------------------------------------

TOKEN = 'local-test-token-0123456789'


def _client(monkeypatch, token=TOKEN):
    from backend.api.internal import TOKEN_ENV, router
    if token is None:
        monkeypatch.delenv(TOKEN_ENV, raising=False)
    else:
        monkeypatch.setenv(TOKEN_ENV, token)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _kind_now():
    from backend.services.studio import shutdown_marker
    shutdown_marker._consumed.clear()
    return shutdown_marker.shutdown_kind(store.INSTANCE)


def test_begin_shutdown_writes_no_clean_marker():
    from backend.core import project_cancellation
    project_cancellation.begin_shutdown()
    try:
        assert _kind_now() == 'crash'
    finally:
        project_cancellation._shutting_down = False


@pytest.mark.parametrize('kind', ['user_quit', 'update'])
def test_shell_shutdown_intent_marks_clean_and_does_not_shut_down(monkeypatch, kind):
    from backend.core import project_cancellation
    with _client(monkeypatch) as client:
        response = client.post('/internal/shutdown-intent', json={'kind': kind}, headers={'X-AutoClip-Local-Token': TOKEN})
    assert response.status_code == 200 and response.json() == {'ok': True}
    assert project_cancellation.shutting_down() is False  # the shell kills us; we never start it
    from backend.services.studio.shutdown_marker import _root
    assert (_root() / store.INSTANCE).read_text() == kind
    assert _kind_now() == 'clean'
    assert not (_root() / store.INSTANCE).exists()  # read once and deleted


@pytest.mark.parametrize('kind', ['parent_lost', 'clean', 'crash', '', 'USER_QUIT', '../x'])
def test_invalid_kind_is_rejected(monkeypatch, kind):
    with _client(monkeypatch) as client:
        response = client.post('/internal/shutdown-intent', json={'kind': kind}, headers={'X-AutoClip-Local-Token': TOKEN})
    assert response.status_code == 422
    assert _kind_now() == 'crash'


@pytest.mark.parametrize('header,env', [(None, TOKEN), ('wrong', TOKEN), (TOKEN, None), ('', '')])
def test_only_the_local_token_is_accepted_and_never_echoed(monkeypatch, caplog, header, env):
    headers = {} if header is None else {'X-AutoClip-Local-Token': header}
    with _client(monkeypatch, env) as client:
        response = client.post('/internal/shutdown-intent', json={'kind': 'user_quit'}, headers=headers)
    assert response.status_code == 403
    assert TOKEN not in response.text and TOKEN not in caplog.text
    assert _kind_now() == 'crash'


def test_intent_router_is_mounted_in_the_app(monkeypatch):
    from backend.app_factory import create_app
    monkeypatch.setenv('AUTOCLIP_SHUTDOWN_TOKEN', TOKEN)
    client = TestClient(create_app(mode='web'))
    assert client.post('/internal/shutdown-intent', json={'kind': 'user_quit'}).status_code == 403
    response = client.post('/internal/shutdown-intent', json={'kind': 'update'}, headers={'X-AutoClip-Local-Token': TOKEN})
    assert response.status_code == 200
    assert _kind_now() == 'clean'


def test_parent_loss_marks_parent_lost(monkeypatch):
    from backend.core import parent_watch

    class _Gone:
        def __init__(self, pid):
            pass

        def alive(self):
            return False
    monkeypatch.setattr(parent_watch, 'ParentProbe', _Gone)
    done = threading.Event()
    parent_watch.start(lambda pid: done.set(), pid=12345, interval=0.01)
    assert done.wait(5)
    assert _kind_now() == 'parent_lost'


@pytest.mark.parametrize('first', ['user_quit', 'update'])
def test_parent_watch_after_quit_intent_stays_clean(first):
    from backend.services.studio.shutdown_marker import mark
    assert mark(first)
    mark('parent_lost')
    assert mark('clean') is False and mark('garbage') is False
    assert _kind_now() == 'clean'


@pytest.mark.parametrize('content', [b'', b'garbage', b'clean', b'\xff\xfe\x00'])
def test_corrupted_or_legacy_marker_reads_unknown(content):
    from backend.services.studio.shutdown_marker import _root, shutdown_kind
    _root().mkdir(parents=True, exist_ok=True)
    (_root() / ('2' * 32)).write_bytes(content)
    assert shutdown_kind('2' * 32) == 'unknown'


def test_unreadable_marker_reads_unknown():
    from backend.services.studio.shutdown_marker import _root, shutdown_kind
    (_root() / ('3' * 32)).mkdir(parents=True)  # a directory cannot be read as a marker
    assert shutdown_kind('3' * 32) == 'unknown'


def test_marker_write_is_atomic(monkeypatch):
    import os
    from backend.services.studio import shutdown_marker
    calls = []
    real = os.replace
    monkeypatch.setattr(shutdown_marker.os, 'replace', lambda a, b: (calls.append((str(a), str(b))), real(a, b)))
    assert shutdown_marker.mark('update')
    assert calls and calls[0][1].endswith(store.INSTANCE) and calls[0][0].endswith('.tmp')
