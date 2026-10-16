"""R24 #415 (Dong R23): the three design-retro invariants, each through the real entry point.

1) a failure names ONE request (#290/#224/#291); 2) provider + config_source are one pair from one
connection, never stitched, never re-read from settings (#296/#297); 3) the instance ledger releases a
reference only after studio.json is durable, under the writers' lock (#293/#294/#295). Plus #292.
Every test fails on 1ba867f9."""
import json
import os
import threading
import urllib.error

import pytest

from backend.core import llm_emit
from backend.services import ai_model_settings as ai
from backend.services.studio import failure_identity, shutdown_marker, store

TEXT = {'provider': 'deepseek', 'config_source': 'preset'}
EYES = {'provider': 'kimi', 'config_source': 'customized'}
OTHER = {'provider': 'glm', 'config_source': 'customized'}
A, B = 'a' * 32, 'b' * 32


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


CONNECTIONS = [
    ai.Connection(id='text', name='Text', provider='deepseek', base_url='https://api.deepseek.com', api_key='fixture-key'),
    ai.Connection(id='eyes', name='Eyes', provider='kimi', base_url='https://vision.fixture.example/v1', api_key='fixture-key'),
    ai.Connection(id='other', name='Other', provider='glm', base_url='https://other.fixture.example/v1', api_key='fixture-key'),
]
MODELS = {'text': 'deepseek-flash', 'eyes': 'private-vision-model', 'other': 'private-other-model'}


def _settings(analysis='text', vision='eyes'):
    ai.save(ai.ModelSettings(
        connections=CONNECTIONS,
        analysis=ai.Assignment(connection_id=analysis, model=MODELS[analysis], capability='text'),
        vision=ai.Assignment(connection_id=vision, model=MODELS[vision], capability='multimodal'),
        analysis_mode='visual', allow_send_frame=True,
    ))


def _who(snap):
    return {k: snap.get(k) for k in ('provider', 'config_source', 'model', 'base_url_host', 'http_status')}


class _Status(Exception):
    def __init__(self, status):
        super().__init__('fixture')
        self.status_code = status


def _provider(base, model):
    return type('P', (), {'base_url': base, 'model_name': model})()


def _text(identity, base, model, status=None):
    def impl(*_a, **_k):
        if status:
            raise _Status(status)
        return None
    with llm_emit.bind_context(identity=identity):
        if status:
            with pytest.raises(_Status):
                llm_emit.observe_provider_call(_provider(base, model), impl, 'p')
        else:
            llm_emit.observe_provider_call(_provider(base, model), impl, 'p')


# --- invariant 1: a failure names ONE request ----------------------------------------------------

def test_290_same_role_second_request_fails_snapshot_and_sentry_name_that_request_whole(posted):
    with llm_emit.track_run():
        _text(TEXT, 'https://api.deepseek.com', 'deepseek-flash')                       # DeepSeek OK
        _text(OTHER, 'https://other.fixture.example/v1', 'glm-4', status=503)          # GLM 503
        snap = llm_emit.run_snapshot()
        tags = llm_emit.sentry_tags_for_error(None, 'analyze')
    assert _who(snap) == {**OTHER, 'model': 'glm-4', 'base_url_host': 'other.fixture.example', 'http_status': 503}
    assert tags.get('provider') == 'glm' and tags.get('model') == 'glm-4' and tags.get('http_status') == '503'


def test_290_a_later_success_clears_the_earlier_failure_of_another_connection(posted):
    with llm_emit.track_run():
        _text(OTHER, 'https://other.fixture.example/v1', 'glm-4', status=503)
        _text(TEXT, 'https://api.deepseek.com', 'deepseek-flash')
        snap = llm_emit.run_snapshot()
    assert _who(snap) == {**TEXT, 'model': 'deepseek-flash', 'base_url_host': 'api.deepseek.com', 'http_status': None}
    assert not snap.get('upstream_error_type')


def _vision(monkeypatch):
    from backend.services.studio import intelligence

    def urlopen(*_a, **_k):
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    with pytest.raises(intelligence.VisionRequestError):
        intelligence.vision_call([{'type': 'text', 'text': 'fixture'}])


def test_224_same_role_vision_requests_on_two_connections_name_the_latest_one_whole(monkeypatch, posted):
    _settings()
    with llm_emit.track_run():
        _vision(monkeypatch)
        _settings(vision='other')                       # the NEXT request really runs on GLM
        _vision(monkeypatch)
        snap = llm_emit.run_snapshot()
    assert _who(snap)['provider'] == 'glm' and _who(snap)['config_source'] == 'customized'
    assert snap.get('model') == 'private-other-model' and snap.get('base_url_host') == 'other.fixture.example'


def test_291_failure_before_any_request_names_the_frozen_phase_connection_whole():
    _settings()
    start = failure_identity.phase_identity('production', {'confirmed_analysis': 'subtitle'})
    _settings(analysis='other')                         # today's settings differ
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity(start)
        snap = llm_emit.run_snapshot()
    assert _who(snap) == {**TEXT, 'model': 'deepseek-flash', 'base_url_host': 'api.deepseek.com', 'http_status': None}


def test_291_unknown_phase_connection_stays_empty_not_filled_from_settings():
    _settings()
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({'provider': 'kimi'})   # incomplete -> unknown
        snap = llm_emit.run_snapshot()
    assert not snap.get('provider') and not snap.get('model') and not snap.get('base_url_host')


# --- invariant 2: one pair from one connection, never settings ----------------------------------

def test_296_frozen_takes_one_complete_source_never_stitches():
    assert failure_identity.frozen({'provider': 'kimi'}, {'provider': 'deepseek', 'config_source': 'preset'}) == TEXT
    assert failure_identity.frozen({'config_source': 'customized'}, {'provider': 'kimi'}) == {}
    assert failure_identity.screening_identity({'screening_identity': {'provider': 'kimi'}, 'phase': 'screening', **TEXT}) == TEXT


def _no_settings(monkeypatch):
    """Settings stay readable (a misattribution would then show up) but every read is recorded."""
    reads = []
    real = ai.load

    def load(*a, **k):
        reads.append(1)
        return real(*a, **k)
    monkeypatch.setattr(ai, 'load', load)
    return reads


def test_297_text_request_without_frozen_identity_uses_the_config_it_sent(monkeypatch, posted):
    _settings(analysis='other')                         # saved analysis = GLM; the request sends DeepSeek
    reads = _no_settings(monkeypatch)
    with llm_emit.track_run():
        with pytest.raises(_Status):
            llm_emit.observe_provider_call(_provider('https://api.deepseek.com', 'deepseek-flash'),
                                           lambda *_a, **_k: (_ for _ in ()).throw(_Status(503)), 'p')
        snap = llm_emit.run_snapshot()
    assert {k: snap.get(k) for k in TEXT} == TEXT
    assert [p for e, p in posted if e == 'llm_request_finished'][-1]['provider'] == 'deepseek'
    assert reads == []


def test_297_vision_test_of_an_unsaved_form_is_attributed_to_the_form_not_saved_settings(monkeypatch, posted):
    _settings()                                         # saved vision = kimi
    from backend.services.studio import intelligence

    def urlopen(*_a, **_k):
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    reads = _no_settings(monkeypatch)
    form = {'api_key': 'fixture-key', 'base_url': 'https://api.deepseek.com', 'model': 'deepseek-flash'}
    with llm_emit.track_run():
        with pytest.raises(intelligence.VisionRequestError):
            intelligence.vision_call([{'type': 'text', 'text': 'fixture'}], config=form)
        snap = llm_emit.run_snapshot()
    request = [p for e, p in posted if e == 'llm_request_finished'][-1]
    assert request['provider'] == 'deepseek'
    assert {k: snap.get(k) for k in TEXT} == TEXT
    assert reads == []


# --- #292: screening identity survives settle, restart recovery and history replay -------------

SCREEN = {'screening_identity': EYES}


def test_292_settle_generation_keeps_screening_identity():
    data = {'analysis': {**TEXT, **SCREEN, 'status': 'running', 'phase': 'rendering', 'run_id': 'r'},
            'generation': {'status': 'rendering', 'auto_start': True, **SCREEN},
            'output_variants': [{'id': 'v', 'status': 'completed'}]}
    store.settle_generation(data)
    assert data['analysis']['screening_identity'] == EYES


def test_292_restart_recovery_keeps_screening_identity():
    data = {'analysis': {**TEXT, **SCREEN, 'status': 'running', 'phase': 'production', 'run_id': 'r', 'instance': A},
            'generation': {'status': 'production', 'auto_start': True, **SCREEN}, 'output_variants': [], 'jobs': []}
    assert store._recover_interrupted_run(data)
    assert data['analysis']['screening_identity'] == EYES


def test_220_history_receipt_of_a_settled_run_carries_its_own_screening_identity():
    store.directory('h').mkdir(parents=True)
    data = {'id': 'h', 'analysis': {**TEXT, **SCREEN, 'status': 'running', 'phase': 'rendering', 'run_id': 'r1'},
            'generation': {'status': 'rendering', 'auto_start': True, **SCREEN},
            'output_variants': [{'id': 'v', 'status': 'completed'}]}
    store.settle_generation(data)
    store.write('h', data, _recover_previous=False)
    saved = json.loads((store.directory('h') / 'metadata' / 'studio.json').read_text(encoding='utf-8'))
    receipt = next(r for r in saved['analysis_history'] if r['run_id'] == 'r1')
    assert receipt['analysis']['screening_identity'] == EYES


# --- invariant 3: the ledger releases only after studio.json is durable ------------------------

def _project(pid, instance):
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {'id': pid, 'analysis': {'status': 'running', 'phase': 'production', 'instance': instance}}, _recover_previous=False)
    meta = store.directory(pid) / 'metadata'
    return meta / 'studio.json', meta / store.REFS_NAME


def test_293_failed_studio_replace_keeps_the_ledger_protecting_the_surviving_state(monkeypatch):
    state, ledger = _project('p', A)
    real = store._replace_state

    def failing(tmp, dest):
        if dest.name == 'studio.json':
            raise OSError('fixture')
        return real(tmp, dest)
    monkeypatch.setattr(store, '_replace_state', failing)
    with pytest.raises(OSError):
        store.write('p', {'id': 'p', 'analysis': {'status': 'failed', 'phase': 'production'}}, _recover_previous=False)
    assert store._read_refs(ledger) == {A}
    state.write_text('{not json', encoding='utf-8')     # studio.json briefly unreadable
    assert A in store.reference_index()


def test_293_failed_replace_rolls_the_ledger_back_to_exactly_what_the_surviving_state_needs(monkeypatch):
    _state, ledger = _project('p', A)
    real = store._replace_state

    def failing(tmp, dest):
        if dest.name == 'studio.json':
            raise OSError('fixture')
        return real(tmp, dest)
    monkeypatch.setattr(store, '_replace_state', failing)
    with pytest.raises(OSError):
        store.write('p', {'id': 'p', 'analysis': {'status': 'running', 'phase': 'production', 'instance': B}}, _recover_previous=False)
    assert store._read_refs(ledger) == {A}               # B never reached disk: it must not pin a record


def test_293_a_wrong_ledger_heals_on_the_next_write_even_if_references_did_not_change():
    state, ledger = _project('p', A)
    ledger.write_text('[]', encoding='ascii')           # e.g. an earlier failed ledger write
    store.write('p', json.loads(state.read_text(encoding='utf-8')), _recover_previous=False)
    assert store._read_refs(ledger) == {A}


def test_293_ledger_holds_old_and_new_references_while_studio_json_is_replaced(monkeypatch):
    _state, ledger = _project('p', A)
    seen = {}
    real = store._replace_state

    def spy(tmp, dest):
        if dest.name == 'studio.json':
            seen['ledger'] = store._read_refs(ledger)
        return real(tmp, dest)
    monkeypatch.setattr(store, '_replace_state', spy)
    store.write('p', {'id': 'p', 'analysis': {'status': 'running', 'phase': 'production', 'instance': B}}, _recover_previous=False)
    assert seen['ledger'] == {A, B}
    assert store._read_refs(ledger) == {B}


def test_294_prune_scans_and_deletes_under_the_writers_lock(monkeypatch):
    root = shutdown_marker._root()
    root.mkdir(parents=True, exist_ok=True)
    for i in range(shutdown_marker._KEEP + 2):
        (root / f'{i:032x}').write_text('unacked', encoding='ascii')
        os.utime(root / f'{i:032x}', (1000 + i, 1000 + i))
    owned = []
    real = store.index_protects
    monkeypatch.setattr(store, 'index_protects', lambda index, name: (owned.append(store.lock._is_owned()), real(index, name))[1])
    real_index = store._reference_index
    monkeypatch.setattr(store, '_reference_index', lambda: (owned.append(store.lock._is_owned()), real_index())[1])
    blocked = threading.Event()
    store.lock.acquire()
    worker = threading.Thread(target=lambda: (shutdown_marker.prune(root), blocked.set()))
    worker.start()
    try:
        assert not blocked.wait(0.3), 'prune ran while a writer held the store lock'
    finally:
        store.lock.release()
    worker.join(5)
    assert blocked.is_set() and owned and all(owned)


def test_295_state_and_ledger_are_fsynced_before_and_after_the_replace(monkeypatch):
    synced = []
    real = os.fsync

    def spy(fd):
        synced.append(fd)
        return real(fd)
    monkeypatch.setattr(store.os, 'fsync', spy)
    _project('p', A)
    expected = 4 if os.name != 'nt' else 2               # tmp studio + ledger tmp (+ their dirs)
    assert len(synced) >= expected
