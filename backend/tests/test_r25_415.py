"""R25 #415 (Dong R24 design v2): one immutable record per request; a failure carries ITS record;
persistence, snapshots and Sentry read only it; identity is written whole or not at all; the ledger
never commits after a failed prepare or shrinks without durability; one cross-process store lock.
Every test fails on 156bc36a on an assertion (not an import)."""
import json
import os
import subprocess
import sys
import textwrap
import threading
import time
import types
import urllib.error
from pathlib import Path

import pytest

from backend.core import llm_emit
from backend.services import ai_model_settings as ai
from backend.services.studio import shutdown_marker, store

KIMI = {'provider': 'kimi', 'config_source': 'customized'}
GLM = {'provider': 'glm', 'config_source': 'customized'}
A, B = 'a' * 32, 'b' * 32
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.delenv('AUTOCLIP_SHUTDOWN_MARKER_DIR', raising=False)
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    shutdown_marker._consumed.clear()


@pytest.fixture
def posted(monkeypatch):
    events = []
    monkeypatch.setattr(llm_emit, '_post_event', lambda event, props: events.append((event, props)))
    return events


class _Status(Exception):
    def __init__(self, status):
        super().__init__('fixture')
        self.status_code = status


def _provider(base, model):
    return type('P', (), {'base_url': base, 'model_name': model})()


def _call(identity, base, model, *, status=None, delay=0.0, started=None):
    def impl(*_a, **_k):
        if started:
            started.wait(2)
        time.sleep(delay)
        if status:
            raise _Status(status)
    with llm_emit.bind_context(identity=identity):
        return llm_emit.observe_provider_call(_provider(base, model), impl, 'p')


def _who(record):
    return {k: record.get(k) for k in ('provider', 'config_source', 'model', 'base_url_host', 'http_status')}


KIMI_503 = {**KIMI, 'model': 'kimi-k2', 'base_url_host': 'kimi.fixture.example', 'http_status': 503}


def _project(pid, analysis):
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    if analysis.get('status') == 'running':
        analysis = {'instance': store.INSTANCE, **analysis}           # a live worker, not a restart
    store.write(pid, {'id': pid, 'analysis': analysis}, _recover_previous=False)


# --- #331: concurrent map_chunks, A fails 503, B succeeds later ---------------------------------

def test_331_concurrent_chunk_failure_is_attributed_to_the_failing_request_everywhere(monkeypatch, posted):
    from backend.pipeline import concurrency
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '2')
    concurrency.reset_limiter()
    _project('p331', {'status': 'running', 'phase': 'production', 'run_id': 'r', **KIMI})
    gate = threading.Event()

    def chunk(name):
        if name == 'A':
            try:
                return _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
            finally:
                gate.set()                                   # B finishes AFTER A failed
        return _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', started=gate, delay=0.05)

    with llm_emit.track_run():
        try:
            concurrency.map_chunks(chunk, ['A', 'B'])
        except _Status as error:
            tags = llm_emit.sentry_tags_for_error(error, 'production')
            store.change('p331', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    analysis = store.read('p331')['analysis']
    assert _who(analysis) == KIMI_503
    assert (tags.get('provider'), tags.get('model'), tags.get('http_status')) == ('kimi', 'kimi-k2', '503')
    assert tags.get('base_url_host') == 'kimi.fixture.example'


def test_331_rewrapped_failure_keeps_its_request_record(posted):
    """R25-a: the record is found up __cause__/__context__ (raise from, raise from None, implicit)."""
    from backend.pipeline.failures import PipelineFailure
    _project('pwrap', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    with llm_emit.track_run():
        try:
            try:
                try:
                    _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
                except _Status as inner:
                    _call(GLM, 'https://glm.fixture.example/v1', 'glm-4')   # a later success (fallback probe)
                    raise PipelineFailure('ANALYZE', 'fixture', code='provider_error') from inner
            except PipelineFailure:
                raise RuntimeError('wrapped') from None                     # context only
        except RuntimeError as outer:
            tags = llm_emit.sentry_tags_for_error(outer, 'production')
            store.change('pwrap', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    assert _who(store.read('pwrap')['analysis']) == KIMI_503
    assert tags.get('provider') == 'kimi' and tags.get('http_status') == '503'


def test_331_failure_without_request_record_falls_back_to_phase_and_says_so():
    from backend.services.studio import failure_identity
    phase = {**GLM, 'model': 'glm-4', 'base_url_host': 'glm.fixture.example'}
    _project('pphase', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: phase, **GLM})
        from backend.pipeline.failures import PipelineFailure
        try:  # R26 #392: only a MODEL failure without a record falls back to the phase identity
            raise PipelineFailure('ANALYZE', 'model timed out before a record existed', code='timeout')
        except PipelineFailure:
            store.change('pphase', lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('pphase')['analysis']
    assert {k: analysis.get(k) for k in phase} == phase
    assert analysis.get('attribution_source') == 'phase' and 'http_status' not in analysis


# --- #332: persisted identity is ONE record, never merged field by field -------------------------

def test_332_failure_write_never_stitches_attempt_identity_with_another_requests_fields(posted):
    _project('p332', {'status': 'running', 'phase': 'production', 'run_id': 'r', 'provider': 'kimi', 'config_source': 'preset'})
    with llm_emit.track_run():
        try:
            _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', status=503)
        except _Status:
            store.change('p332', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    data = store.read('p332')
    whole = {**GLM, 'model': 'glm-4', 'base_url_host': 'glm.fixture.example', 'http_status': 503}
    assert _who(data['analysis']) == whole
    assert 'called_provider' not in data['analysis']
    row = data['analysis_history'][-1]['analysis']
    assert (row.get('provider'), row.get('config_source')) == ('glm', 'customized')


def test_332_unpaired_legacy_identity_reads_as_empty_not_half():
    _project('plegacy', {'status': 'completed', 'phase': 'production', 'run_id': 'r',
                         'provider': 'kimi', 'model': 'glm-4', 'base_url_host': 'glm.fixture.example'})
    store.change('plegacy', lambda d: d.update(note=1))
    analysis = store.read('plegacy')['analysis']
    assert not any(analysis.get(k) for k in ('provider', 'config_source', 'model', 'base_url_host'))


# --- #333: a write without requests (render) never re-reads settings ----------------------------

def test_333_render_write_keeps_the_stored_failure_identity_when_settings_changed():
    ai.save(ai.ModelSettings(
        connections=[ai.Connection(id='g', name='G', provider='glm', base_url='https://glm.fixture.example/v1', api_key='fixture-key')],
        analysis=ai.Assignment(connection_id='g', model='glm-4', capability='text')))
    _project('p333', {'status': 'failed', 'phase': 'production', 'run_id': 'r', 'error_code': 'provider_error', **KIMI_503})
    with llm_emit.track_run():                                    # the render worker: no request, no phase
        store.change('p333', lambda d: d.setdefault('jobs', []).append({'job_id': 'j', 'status': 'running'}))
    assert _who(store.read('p333')['analysis']) == KIMI_503


# --- #334: a failed ledger prepare blocks the studio.json commit --------------------------------

def test_334_failed_ledger_prepare_does_not_commit_studio_json(monkeypatch):
    _project('p334', {'status': 'running', 'phase': 'production', 'instance': A})
    state = store.directory('p334') / 'metadata' / 'studio.json'
    real = store._publish

    def ledger_down(path, text, encoding):
        if path.name == store.REFS_NAME:
            raise OSError('fixture: ledger not writable')
        return real(path, text, encoding)
    monkeypatch.setattr(store, '_publish', ledger_down)
    with pytest.raises(OSError):
        store.write('p334', {'id': 'p334', 'analysis': {'status': 'running', 'phase': 'production', 'instance': B}}, _recover_previous=False)
    assert json.loads(state.read_text(encoding='utf-8'))['analysis']['instance'] == A
    ledger = store._read_refs(state.with_name(store.REFS_NAME))
    assert A in ledger and B not in ledger                         # every reference on disk is protected


# --- #335: the store lock excludes other processes (CLI / MCP children) -------------------------

def _hold_lock_in_child(tmp_path, seconds):
    ready = tmp_path / 'child-ready'
    code = textwrap.dedent(f'''
        import time, pathlib
        from backend.services.studio import store
        with store.lock:
            pathlib.Path({str(ready)!r}).write_text('1')
            time.sleep({seconds})
    ''')
    env = {**os.environ, 'PYTHONPATH': str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')}
    child = subprocess.Popen([sys.executable, '-c', code], cwd=str(ROOT), env=env)
    deadline = time.monotonic() + 30
    while not ready.exists():
        assert child.poll() is None and time.monotonic() < deadline, 'child did not take the lock'
        time.sleep(0.02)
    return child


def _records(root, count):
    root.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (root / f'{i:032x}').write_text('unacked', encoding='ascii')
        os.utime(root / f'{i:032x}', (1000 + i, 1000 + i))


def test_335_prune_waits_for_a_writer_in_another_process(tmp_path):
    root = shutdown_marker._root()
    _records(root, shutdown_marker._KEEP + 2)
    child = _hold_lock_in_child(tmp_path, 1.5)
    done = threading.Event()
    worker = threading.Thread(target=lambda: (shutdown_marker.prune(root), done.set()))
    worker.start()
    try:
        assert not done.wait(0.6), 'prune scanned/deleted while another process held the store lock'
    finally:
        child.wait(30)
        worker.join(30)
    assert done.is_set()


def test_335_release_waits_for_a_writer_in_another_process(tmp_path):
    """Closes R24 m5 (release without store.lock survived)."""
    root = shutdown_marker._root()
    _records(root, 1)
    name = f'{0:032x}'
    shutdown_marker._consumed[(str(root), name)] = 'unacked'
    child = _hold_lock_in_child(tmp_path, 1.5)
    done = threading.Event()
    worker = threading.Thread(target=lambda: (shutdown_marker.release(name), done.set()))
    worker.start()
    try:
        assert not done.wait(0.6), 'release deleted a record while another process held the store lock'
        assert (root / name).exists()
    finally:
        child.wait(30)
        worker.join(30)
    assert done.is_set()


def test_335_lock_timeout_raises_a_coded_error(tmp_path, monkeypatch):
    from backend.core.sentry_setup import studio_error_code
    child = _hold_lock_in_child(tmp_path, 1.5)
    monkeypatch.setattr(store.lock, 'timeout', 0.2)
    try:
        with pytest.raises(OSError) as caught:
            with store.lock:
                pass
    finally:
        child.wait(30)
    assert getattr(caught.value, 'code', None) == 'store_lock_timeout'
    assert studio_error_code(caught.value) == 'store_lock_timeout'  # R26 #390


# --- #336: the settings-page vision test carries the tested connection's identity ---------------

def test_336_settings_vision_test_uses_the_connection_identity_not_its_hostname(monkeypatch, posted):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.services import provider_validation
    from backend.services.studio import intelligence
    ok = types.SimpleNamespace(ok=True, normalized_base_url=None, as_api=lambda: {'ok': True, 'success': True})
    monkeypatch.setattr(provider_validation, 'validate_connection', lambda *a, **k: ok)

    def urlopen(*_a, **_k):
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    connection = ai.Connection(id='eyes', name='Eyes', provider='kimi', base_url='https://vision.fixture.example/v1', api_key='fixture-key')
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        client.post('/settings/ai-models/test', json={'connection': connection.model_dump(), 'model': 'private-vision-model', 'vision': True})
    vision = [p for e, p in posted if e == 'llm_request_finished' and p.get('kind') == 'vision']
    assert vision and vision[-1]['provider'] == 'kimi'


# --- #337: unknown directory durability keeps the ledger union ----------------------------------

@pytest.mark.skipif(os.name == 'nt', reason='Windows has no directory fsync')
def test_337_dir_fsync_failure_keeps_the_ledger_union(monkeypatch):
    _project('p337', {'status': 'running', 'phase': 'production', 'instance': A})
    real_open = os.open

    def no_dir_fsync(path, flags, *args):
        if os.path.isdir(path):
            raise OSError('fixture: directory fsync unavailable')
        return real_open(path, flags, *args)
    monkeypatch.setattr(store.os, 'open', no_dir_fsync)
    store.write('p337', {'id': 'p337', 'analysis': {'status': 'running', 'phase': 'production', 'instance': B}}, _recover_previous=False)
    monkeypatch.setattr(store.os, 'open', real_open)
    ledger = store._read_refs(store.directory('p337') / 'metadata' / store.REFS_NAME)
    assert ledger == {A, B}


# --- #338: the write-only accumulator fields and the old doc rule are gone ----------------------

def test_338_run_accumulator_has_no_write_only_identity_fields():
    fields = set(llm_emit._RunAcc.__dataclass_fields__)
    assert not fields & {'identities', 'provider', 'model', 'host', 'last_http_status', 'last_upstream', 'last_request'}


def test_338_tracking_plan_states_the_failing_request_rule():
    text = (ROOT / 'docs' / 'analytics' / 'TRACKING_PLAN.md').read_text(encoding='utf-8')
    assert '每个 role 以第一个请求为准' not in text and '取最近一次请求' not in text
    assert 'attribution_source=request' in text


# --- R24 m4: Windows fsync needs a writable descriptor (platform independent check) ---------------

def test_295_file_fsync_opens_read_write(monkeypatch, tmp_path):
    seen = []
    real_open = os.open
    monkeypatch.setattr(store.os, 'open', lambda path, flags, *a: (seen.append(flags), real_open(path, flags, *a))[1])
    target = tmp_path / 'f'
    target.write_text('x')
    store._fsync_file(target)
    assert seen and seen[0] & os.O_RDWR


def test_331_an_outer_observed_layer_never_replaces_the_failing_requests_record(posted):
    """The same exception may pass through an outer observed call; the request that failed keeps it."""
    def outer(*_a, **_k):
        _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
    with llm_emit.track_run():
        with llm_emit.bind_context(identity=GLM), pytest.raises(_Status) as caught:
            llm_emit.observe_provider_call(_provider('https://glm.fixture.example/v1', 'glm-4'), outer, 'p')
        tags = llm_emit.sentry_tags_for_error(caught.value, 'analyze')
    assert (tags.get('provider'), tags.get('model'), tags.get('http_status')) == ('kimi', 'kimi-k2', '503')


def test_335_release_deletes_only_while_holding_the_store_lock(monkeypatch):
    """R24 m5: the reference scan alone being locked is not enough; the unlink must be too."""
    root = shutdown_marker._root()
    _records(root, 1)
    name = f'{0:032x}'
    shutdown_marker._consumed[(str(root), name)] = 'unacked'
    held = []
    real = Path.unlink

    def spy(self, *a, **k):
        if self.name == name:
            held.append(store.lock._is_owned())
        return real(self, *a, **k)
    monkeypatch.setattr(Path, 'unlink', spy)
    shutdown_marker.release(name)
    assert held == [True]
