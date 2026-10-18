"""R26 #415 (Dong R25 review #390-#394): without a request record only a MODEL failure takes the
phase identity, everything else is local; store_lock_timeout is its own product code; a
non-blocking lock attempt returns at once; a new phase-only failure replaces an older request
attribution. Every test fails on 6e11ce73 on an assertion."""
import json
import subprocess
import time
from pathlib import Path

import pytest

from backend.core import file_lock, llm_emit
from backend.core.sentry_setup import STUDIO_ERROR_CODES, studio_error_code
from backend.pipeline.failures import PipelineFailure
from backend.services.studio import failure_identity, store
from backend.tests.test_r25_415 import GLM, KIMI, _call, _hold_lock_in_child, _project, isolated, posted  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
VISION = {**GLM, 'model': 'glm-4v', 'base_url_host': 'glm.fixture.example'}
IDENTITY = ('provider', 'config_source', 'model', 'base_url_host', 'http_status')


def _fail_with(pid, error, code):
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise error
        except Exception as caught:  # noqa: BLE001
            tags = llm_emit.sentry_tags_for_error(caught, 'production')
            store.change(pid, lambda d: d['analysis'].update(status='failed', error_code=code))
    return store.read(pid)['analysis'], tags


@pytest.mark.parametrize('error', [
    file_lock.LockTimeout(),                                               # #390 store lock
    subprocess.CalledProcessError(1, ['ffmpeg']),                          # ffmpeg
    subprocess.TimeoutExpired(['ffmpeg'], 5),                              # local render timeout
    ValueError('text step rejected its input before any request'),         # mixed goals, visual route
    PipelineFailure('EXPORT', 'render produced no file', code='timeline_empty'),
], ids=['lock', 'ffmpeg', 'render-timeout', 'text-before-request', 'local-pipeline-code'])
def test_392_non_model_failure_without_record_is_local(error):
    _project('ploc', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    analysis, tags = _fail_with('ploc', error, 'unexpected')
    assert analysis.get('attribution_source') == 'local' and analysis.get('http_status') is None, analysis
    assert tags.get('attribution_source') == 'local' and 'http_status' not in tags


def test_392_local_failure_raised_while_handling_a_model_error_is_still_local():
    _project('pctx', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            try:
                raise PipelineFailure('ANALYZE', 'slow', code='timeout')
            except PipelineFailure:
                raise file_lock.LockTimeout()      # saving the failure hit the store lock
        except file_lock.LockTimeout:
            store.change('pctx', lambda d: d['analysis'].update(status='failed', error_code='store_lock_timeout'))
    analysis = store.read('pctx')['analysis']
    assert analysis.get('attribution_source') == 'local' and analysis.get('http_status') is None


def test_392_model_failure_without_record_still_takes_phase_identity():
    _project('pmod', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    analysis, tags = _fail_with('pmod', PipelineFailure('ANALYZE', 'slow', code='timeout'), 'timeout')
    assert analysis.get('attribution_source') == 'phase' and analysis.get('provider') == 'glm'
    assert tags.get('provider') == 'glm' and tags.get('attribution_source') == 'phase'


def test_390_store_lock_timeout_is_its_own_product_code_not_a_model_timeout():
    error = file_lock.LockTimeout()
    assert studio_error_code(error) == 'store_lock_timeout' and 'store_lock_timeout' in STUDIO_ERROR_CODES
    assert '模型' not in str(error) and '服务商' not in str(error) and '提供商' not in str(error)
    for path in ('backend/core/event_catalog.json', 'docs/analytics/event_catalog.json'):
        attr = json.loads((ROOT / path).read_text(encoding='utf-8'))['attribution']
        assert 'store_lock_timeout' in attr['product_error_codes'], path
        assert 'store_lock_timeout' not in attr['user_caused_error_codes'] + attr['environment_error_codes']
    assert 'store_lock_timeout' in (ROOT / 'docs/analytics/TRACKING_PLAN.md').read_text(encoding='utf-8')
    from backend.core.failure_codes import error_code_pattern
    assert error_code_pattern().fullmatch('store_lock_timeout')
    for path in ('frontend/src/analytics/feedbackDraft.ts', 'frontend/src/analytics/workflow.ts'):
        assert "failureCodes" in (ROOT / path).read_text(encoding='utf-8'), path
    assert 'error_code_pattern' in (ROOT / 'scripts/ingest_app_feedback.py').read_text(encoding='utf-8')


def test_394_new_phase_only_failure_replaces_older_request_attribution():
    _project('p394', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception:  # noqa: BLE001
            store.change('p394', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    first = store.read('p394')['analysis']
    assert first['provider'] == 'kimi' and first['attribution_source'] == 'request'
    # R29 I503: no "same failure" inference; without an error in hand the snapshot stays.
    store.change('p394', lambda d: d['analysis'].update(message='no error in hand'))
    assert store.read('p394')['analysis']['provider'] == 'kimi'
    # R30 I560 (Dong R29, assertion changed from 'glm'): an unrelated write of an already-failed record
    # with another error in hand is NOT a new failure: the snapshot stays (R29 overwrote it).
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise PipelineFailure('ANALYZE', 'again', code='provider_error')
        except PipelineFailure:
            store.change('p394', lambda d: d['analysis'].update(message='still failed'))
    assert store.read('p394')['analysis']['provider'] == 'kimi'
    # a NEW failure (retry run r2) with only the phase identity: the old request value must go
    store.change('p394', lambda d: d['analysis'].update(status='running', run_id='r2', error_code=None))
    analysis, _ = _fail_with('p394', PipelineFailure('ANALYZE', 'slow', code='timeout'), 'timeout')
    assert analysis['attribution_source'] == 'phase' and analysis['provider'] == 'glm'
    assert analysis.get('http_status') != 503


# --- second pass (Dong R25-b): #393 P2, #397-#402, #394 status, #392 source surfaces ----------------

def test_394_new_local_failure_drops_the_old_request_status():
    _project('p394l', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception:  # noqa: BLE001
            store.change('p394l', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    with llm_emit.track_run():  # the next run fails locally straight away (no running write between)
        try:
            raise file_lock.LockTimeout()
        except file_lock.LockTimeout:
            store.change('p394l', lambda d: d['analysis'].update(status='failed', run_id='r2', error_code='store_lock_timeout'))
    analysis = store.read('p394l')['analysis']
    assert analysis['attribution_source'] == 'local' and analysis.get('http_status') is None


def test_397_failed_goal_request_survives_a_later_successful_goal(monkeypatch):
    from backend.services.studio import intelligence, jobs
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda *a, **k: Path('video.mp4'))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(jobs, 'analyze', lambda *a, **k: _call(GLM, 'https://glm.fixture.example/v1', 'glm-4v', status=503))
    monkeypatch.setattr(jobs, 'run_content', lambda *a, **k: (_call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2'), [])[1])
    _project('p397', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    plan = {'selected_goals': ['highlight', 'content'], 'confirmed_preferences': {}, 'confirmed_analysis': 'visual'}
    with llm_emit.track_run():
        jobs._produce_selected('p397', plan)
    analysis = store.read('p397')['analysis']
    assert analysis['status'] == 'failed' and analysis['succeeded_goals'] == ['content']
    assert (analysis.get('provider'), analysis.get('http_status')) == ('glm', 503), analysis
    assert analysis.get('attribution_source') == 'request'


def test_398_r29_i500_record_on_the_implicit_context_only_is_not_this_failures():
    """R29 I500 (Dong): only the explicit __cause__ chain is walked; a record that is only on the
    implicit __context__ belongs to an error that was merely being handled."""
    with llm_emit.track_run():
        try:
            _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', status=503)
        except Exception as failed:  # noqa: BLE001
            try:
                raise RuntimeError('cleanup') from ValueError('unrelated cause')   # cause set, record on context
            except RuntimeError as outer:
                assert outer.__context__ is failed
                found = llm_emit.attribution(outer)
    assert found.get('provider') != 'glm' and found.get('attribution_source') == 'local', found


def test_399_half_identity_is_empty_on_read():
    store.directory('p399').mkdir(parents=True, exist_ok=True)
    path = store.directory('p399') / 'metadata' / 'studio.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'id': 'p399', 'analysis': {'status': 'completed', 'provider': 'kimi', 'model': 'kimi-k2'},
                                'generation': {'status': 'completed', 'config_source': 'preset'}}), encoding='utf-8')
    data = store.read('p399', recover=False)
    for name in ('analysis', 'generation'):
        assert not any(data[name].get(k) for k in ('provider', 'config_source', 'model', 'base_url_host')), data[name]


def test_400_history_keeps_model_host_and_source():
    _project('p400', {'status': 'running', 'phase': 'production', 'run_id': 'r'})
    with llm_emit.track_run():
        try:
            _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', status=503)
        except Exception:  # noqa: BLE001
            store.change('p400', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    row = store.read('p400')['analysis_history'][-1]['analysis']
    assert (row.get('model'), row.get('base_url_host'), row.get('attribution_source')) == ('glm-4', 'glm.fixture.example', 'request')


def test_401_render_that_cannot_write_its_failure_leaves_a_receipt_not_a_queued_job(monkeypatch):
    from backend.services.studio import jobs
    store.directory('p401').mkdir(parents=True, exist_ok=True)
    store.write('p401', {'id': 'p401', 'jobs': [{'job_id': 'j1', 'status': 'queued', 'instance': store.INSTANCE}]},
                _recover_previous=False)
    real_change = store.change
    monkeypatch.setattr(store, 'change', lambda *a, **k: (_ for _ in ()).throw(file_lock.LockTimeout()))
    with pytest.raises(file_lock.LockTimeout):
        with store.worker_read_scope('p401', ('render', 'j1')):
            jobs._render.__wrapped__('p401', {'id': 'd'}, 'j1') if hasattr(jobs._render, '__wrapped__') else jobs._render('p401', {'id': 'd'}, 'j1')
    monkeypatch.setattr(store, 'change', real_change)
    job = store.recover('p401')['jobs'][0]
    assert job['status'] == 'failed' and job['error_code'] == 'store_lock_timeout', job


def test_402_attribution_does_not_need_python_311():
    source = (ROOT / 'backend/core/llm_emit.py').read_text(encoding='utf-8')
    assert 'sys.exception()' not in source
    with llm_emit.track_run():
        try:
            _call(GLM, 'https://glm.fixture.example/v1', 'glm-4', status=503)
        except Exception:  # noqa: BLE001
            assert llm_emit.attribution().get('provider') == 'glm'
