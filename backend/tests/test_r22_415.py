"""R22 #195/#198/#201/#220-#224 for #415. Behavioural: every test drives the real entry point
(inspect_project -> _inspect -> _auto_generate, vision_call, observe_provider_call, store.write,
shutdown_marker.prune, the final _post_event exit). Each fails on 9f3d0b62."""
import json
import os
import urllib.error

import pytest

from backend.core import llm_emit
from backend.services import ai_model_settings as ai
from backend.services.studio import failure_identity, jobs, shutdown_marker, store
from backend.services.studio.models import ImportOptions

TEXT = {'provider': 'deepseek', 'config_source': 'preset'}
EYES = {'provider': 'kimi', 'config_source': 'customized'}
OTHER = {'provider': 'glm', 'config_source': 'customized'}
A, B, C = 'a' * 32, 'b' * 32, 'c' * 32


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.delenv('AUTOCLIP_SHUTDOWN_MARKER_DIR', raising=False)
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    shutdown_marker._consumed.clear()


CONNECTIONS = [
    ai.Connection(id='text', name='Text', provider='deepseek', base_url='https://api.deepseek.com', api_key='fixture-key'),
    ai.Connection(id='eyes', name='Eyes', provider='kimi', base_url='https://vision.fixture.example/v1', api_key='fixture-key'),
    ai.Connection(id='other', name='Other', provider='glm', base_url='https://other.fixture.example/v1', api_key='fixture-key'),
]


def _settings(analysis='text', vision='eyes'):
    models = {'text': 'deepseek-flash', 'eyes': 'private-vision-model', 'other': 'private-other-model'}
    ai.save(ai.ModelSettings(
        connections=CONNECTIONS,
        analysis=ai.Assignment(connection_id=analysis, model=models[analysis], capability='text'),
        vision=ai.Assignment(connection_id=vision, model=models[vision], capability='multimodal'),
        analysis_mode='visual', allow_send_frame=True,
    ))


def _ident(record):
    return {k: (record or {}).get(k) for k in ('provider', 'config_source')}


# --- #222 / #194 / #220: the real automatic path ------------------------------------------------

@pytest.fixture
def automatic(monkeypatch):
    """inspect_project -> _inspect -> _auto_generate with only media/model work stubbed out."""
    _settings()
    store.directory('auto').mkdir(parents=True)
    submitted = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: submitted.append((fn, a, k)))
    monkeypatch.setattr('backend.services.studio.readiness.ensure_analysis_usable', lambda: None)
    monkeypatch.setattr(jobs, '_prepare_speaker_framing', lambda *_: None)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda _pid: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda _pid: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    plan = {'mode': 'local', 'recommended_analysis': 'subtitle', 'preferences': {'goal': 'highlight'}, 'selected_goals': ['highlight']}
    monkeypatch.setattr('backend.services.studio.planning.recommend', lambda *_: dict(plan))

    def run(next_worker=True):
        jobs.inspect_project('auto', ImportOptions(auto_start=True, platforms=['douyin']))
        screening = store.read('auto')
        fn, args, kwargs = submitted.pop(0)
        assert fn is jobs._inspect
        fn(*args, **kwargs)
        return screening, submitted
    return run


def test_222_automatic_start_persists_the_production_route_identity(automatic):
    """#194 behaviour: screening runs on vision (Kimi); the subtitle route's production on text (DeepSeek)."""
    screening, _ = automatic()
    assert _ident(screening['analysis']) == EYES
    state = store.read('auto')
    assert state['analysis']['phase'] == 'production'
    assert _ident(state['analysis']) == TEXT                     # mutation 194-auto-start-screening-id
    assert _ident(state['generation']) == TEXT


def test_222_automatic_production_failure_keeps_the_identity_frozen_at_its_start(automatic, monkeypatch):
    _, submitted = automatic()
    fn, args, kwargs = submitted.pop(0)
    assert fn is jobs._auto_generate
    _settings(analysis='other')                                  # settings change after production started
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_: (_ for _ in ()).throw(RuntimeError('fixture')))
    fn(*args, **kwargs)
    state = store.read('auto')
    assert state['generation']['status'] == 'failed'
    assert _ident(state['generation']) == TEXT and _ident(state['analysis']) == TEXT


def test_220_screening_identity_survives_production_refreeze(automatic):
    automatic()
    state = store.read('auto')
    assert state['analysis']['screening_identity'] == EYES       # screen_finished reads this
    assert state['generation']['screening_identity'] == EYES     # kept for the whole automatic run
    assert failure_identity.screening_identity(state['analysis']) == EYES


def test_220_screening_identity_reaches_the_terminal_history_receipt(automatic, monkeypatch):
    _, submitted = automatic()
    fn, args, kwargs = submitted.pop(0)
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_: (_ for _ in ()).throw(RuntimeError('fixture')))
    fn(*args, **kwargs)
    receipt = store.read('auto')['analysis_history'][-1]['analysis']
    assert receipt['screening_identity'] == EYES and _ident(receipt) == TEXT


@pytest.mark.parametrize('plan,role', [
    ({'recommended_analysis': 'visual', 'confirmed_analysis': 'subtitle', 'preferences': {'goal': 'highlight'}}, 'analysis'),
    ({'recommended_analysis': 'subtitle', 'confirmed_analysis': 'visual', 'preferences': {'goal': 'highlight'}}, 'vision'),
])
def test_194_the_confirmed_route_wins_over_the_recommendation(plan, role):
    assert failure_identity.role_for('production', plan) == role  # mutation 194-confirmed-ignored


# --- #223: before any request the run reads the phase's frozen identity --------------------------

def test_223_snapshot_and_sentry_before_any_request_use_the_phase_identity(automatic, monkeypatch):
    _, submitted = automatic()
    fn, args, kwargs = submitted.pop(0)
    _settings(analysis='other')                                  # today's analysis connection differs
    seen = {}

    def no_request_yet(*_):
        seen['snapshot'] = llm_emit.run_snapshot()
        seen['tags'] = llm_emit.sentry_tags_for_error(None, 'production')
        raise RuntimeError('fixture')
    monkeypatch.setattr(jobs, '_content_drafts', no_request_yet)
    fn(*args, **kwargs)
    assert _ident(seen['snapshot']) == TEXT
    assert seen['tags'].get('provider') == 'deepseek'


# --- #195: the request's identity is frozen when the request STARTS ------------------------------

@pytest.fixture
def posted(monkeypatch):
    events = []
    monkeypatch.setattr(llm_emit, '_post_event', lambda event, props: events.append((event, props)))
    return events


def _vision_request(monkeypatch, during=None):
    from backend.services.studio import intelligence

    def urlopen(*_a, **_k):
        if during:
            during()
        raise urllib.error.URLError(TimeoutError())
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    with pytest.raises(intelligence.VisionRequestError) as caught:
        intelligence.vision_call([{'type': 'text', 'text': 'fixture'}])
    return caught.value  # R25 #415: a failure is attributed through the record its exception carries (not 'latest request').


def test_195_settings_changed_while_a_vision_request_is_in_flight_do_not_move_it(monkeypatch, posted):
    _settings()
    with llm_emit.track_run():
        error = _vision_request(monkeypatch, during=lambda: _settings(vision='other'))
        snap = llm_emit.run_snapshot(error=error)
    assert _ident(snap) == EYES
    assert posted[-1][1]['provider'] == 'kimi'                   # the request event too


def test_195_each_request_freezes_its_own_identity_and_the_latest_request_is_named(monkeypatch, posted):
    # R24 #224/#290: this used to assert "first request of the role wins" (EYES), which pinned the bug:
    # the second request really ran on GLM, so the run names GLM, with GLM's model/host.
    _settings()
    with llm_emit.track_run():
        _vision_request(monkeypatch)
        _settings(vision='other')
        error = _vision_request(monkeypatch)
        snap = llm_emit.run_snapshot(error=error)
    assert _ident(snap) == OTHER
    assert snap.get('base_url_host') == 'other.fixture.example' 


class _TextProvider:
    base_url = 'https://api.deepseek.com'
    model_name = 'deepseek-flash'


def _text_request():
    def impl(*_a, **_k):
        raise RuntimeError('fixture')
    with llm_emit.bind_context(identity=TEXT), pytest.raises(RuntimeError) as caught:  # R23: route identity
        llm_emit.observe_provider_call(_TextProvider(), impl, 'p')
    return caught.value


@pytest.mark.parametrize('order,expected', [(('vision', 'text'), TEXT), (('text', 'vision'), EYES)])
def test_195_snapshot_names_the_latest_requests_role(order, expected, monkeypatch, posted):
    _settings()
    with llm_emit.track_run():
        for kind in order:
            error = _vision_request(monkeypatch) if kind == 'vision' else _text_request()
        snap = llm_emit.run_snapshot(error=error)
    assert _ident(snap) == expected                              # mutation 195-role-not-latest


def test_195_text_identity_is_read_before_the_request_is_sent(posted):
    _settings()

    def impl(*_a, **_k):
        _settings(analysis='other')
        raise RuntimeError('fixture')
    with llm_emit.track_run():
        with llm_emit.bind_context(identity=TEXT), pytest.raises(RuntimeError) as caught:
            llm_emit.observe_provider_call(_TextProvider(), impl, 'p')
        snap = llm_emit.run_snapshot(error=caught.value)
    assert _ident(snap) == TEXT


# --- #221 / #198 / #224: a reference ledger, not file times --------------------------------------

def _records(names, base=1000):
    root = shutdown_marker._root()
    root.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(names):
        (root / name).write_text('unacked', encoding='ascii')
        os.utime(root / name, (base + i, base + i))
    return root


def _write_project(pid, instance):
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {'id': pid, 'analysis': {'status': 'running', 'phase': 'production', 'instance': instance}}, _recover_previous=False)
    return store.directory(pid) / 'metadata' / 'studio.json'


def _corrupt(path, mtime):
    path.write_text('{not json', encoding='utf-8')
    os.utime(path, (mtime, mtime))


def test_221_a_worker_write_after_the_marker_still_protects_the_record(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = _records([A], base=1000)                              # marker written at quit
    _corrupt(_write_project('late', A), 2000)                    # the worker wrote later, then the file broke
    shutdown_marker.prune()
    assert (root / A).exists()


def test_221_a_long_broken_project_does_not_pin_records_forever(monkeypatch):
    monkeypatch.setattr(shutdown_marker, '_KEEP', 3)
    names = [f'{i:032x}' for i in range(1, 41)]
    root = _records(names, base=5000)
    (store.directory('ancient') / 'metadata').mkdir(parents=True)
    _corrupt(store.directory('ancient') / 'metadata' / 'studio.json', 1)   # broken since long ago, no ledger
    shutdown_marker.prune()
    assert sorted(p.name for p in root.iterdir()) == names[-3:]


def test_224_every_unreadable_project_contributes_its_references(monkeypatch):
    """Replaces 198-floor-max: with several broken projects, each one's ledger counts (union)."""
    monkeypatch.setattr(shutdown_marker, '_KEEP', 0)
    root = _records([A, B, C])
    _corrupt(_write_project('first', A), 10)
    _corrupt(_write_project('second', B), 99999)
    shutdown_marker.prune()
    assert sorted(p.name for p in root.iterdir()) == [A, B]


def test_221_ledger_follows_the_state_and_release_uses_it():
    root = _records([A])
    assert shutdown_marker.shutdown_kind(A) == 'unknown'
    _write_project('p', A)
    ledger = store.directory('p') / 'metadata' / store.REFS_NAME
    assert json.loads(ledger.read_text()) == [A]
    shutdown_marker.release(A)
    assert (root / A).exists()                                   # still referenced
    store.write('p', {'id': 'p', 'analysis': {'status': 'failed', 'phase': 'production'}}, _recover_previous=False)
    assert json.loads(ledger.read_text()) == []
    shutdown_marker.release(A)
    assert not (root / A).exists()


# --- #201: the final send exit ------------------------------------------------------------------

def test_201_every_preset_provider_leaves_through_the_real_sender(monkeypatch):
    from backend.core.provider_presets import iter_providers
    from backend.services.studio.qa import telemetry as qa_telemetry
    bodies, warnings = [], []
    monkeypatch.setattr(qa_telemetry, '_key', lambda: 'phc_fixture')
    monkeypatch.setattr(qa_telemetry, '_analytics_allowed', lambda: True)

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen(request, timeout=None):
        bodies.append(json.loads(request.data))
        return _Response()
    monkeypatch.setattr(llm_emit.urllib.request, 'urlopen', urlopen)
    monkeypatch.setattr(llm_emit.logger, 'warning', lambda *a, **k: warnings.append(a))
    presets = [p.id for p in iter_providers()]
    for preset in presets:
        llm_emit.request_finished(provider=preset, model='m', kind='text', outcome='success')
    assert [b['properties']['provider'] for b in bodies] == presets
    assert {b['event'] for b in bodies} == {'llm_request_finished'}
    assert warnings == []                                        # catalog checks passed on the wire
