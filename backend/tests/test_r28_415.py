"""R28 #415 (Dong R27 I450-I458, I460): model only when a request was sent and the provider answered with
an error; a local error in any layer first; one snapshot factory; no value inference; one-record readers;
completed+partial is a failure terminal; render receipts are local. Fail-before evidence: before-*.txt in
mut415-r28 (run against 9ce045c2)."""
import errno
import json
from pathlib import Path

import pytest

from backend.core import file_lock, llm_emit
from backend.core.sentry_setup import studio_failure_context
from backend.pipeline.failures import PipelineFailure
from backend.services.studio import failure_identity, store
from backend.tests.test_r25_415 import GLM, KIMI, _call, _project, _provider, isolated  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
VISION = {**GLM, 'model': 'glm-4v', 'base_url_host': 'glm.fixture.example'}


def _kimi_503():
    try:
        _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
    except Exception as error:  # noqa: BLE001
        return error
    raise AssertionError('no 503')


def _attr(error):
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        return llm_emit.attribution(error)


class _NotAProvider(Exception):
    """Some library error that happens to carry an HTTP status (e.g. a 404 from a download)."""
    def __init__(self, status):
        super().__init__('fixture')
        self.status_code = status


# --- I450: no "status code or record means model" fallback; local in any layer first -----------------

def test_i450_status_code_alone_is_not_a_model_failure():  # kills M1
    wrapped = PipelineFailure('ANALYZE', 'x', code='unexpected')
    wrapped.__cause__ = _NotAProvider(404)
    assert _attr(wrapped)['attribution_source'] == 'local'
    assert _attr(PipelineFailure('ANALYZE', 'x', code='unexpected', http_status=502))['attribution_source'] == 'local'


@pytest.mark.parametrize('local', [OSError(errno.ENOSPC, 'disk full'), PermissionError('denied'),
                                   FileNotFoundError('gone')], ids=['enospc', 'permission', 'not-found'])
def test_i450_local_error_raised_while_handling_a_model_503_is_local(local):
    with llm_emit.track_run():
        inner = _kimi_503()
        try:
            try:
                raise inner
            except Exception:  # noqa: BLE001
                raise local
        except OSError as outer:
            llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
            found = llm_emit.attribution(outer)
    assert found['attribution_source'] == 'local' and found.get('provider') != 'kimi', found
    assert 'http_status' not in found


def test_i450_request_record_without_a_provider_answer_is_local():
    """A PermissionError inside the provider call before any network I/O gets a request record too."""
    def impl(*_a, **_k):
        raise PermissionError('fixture: cannot read the prompt file')
    with llm_emit.track_run():
        try:
            with llm_emit.bind_context(identity=KIMI):
                llm_emit.observe_provider_call(_provider('https://kimi.fixture.example/v1', 'kimi-k2'), impl, 'p')
        except PermissionError as error:
            found = llm_emit.attribution(error)
    assert found['attribution_source'] == 'local' and found.get('provider') != 'kimi', found


def test_i450_answered_request_stays_model():
    with llm_emit.track_run():
        error = _kimi_503()
        found = llm_emit.attribution(error)
    assert found['attribution_source'] == 'request' and found['provider'] == 'kimi' and found['http_status'] == 503


# --- I460: the chain skips layers that cannot decide (behaviour, through llm_emit) --------------------

def test_i460_walk_passes_non_deciding_layers_to_the_model_failure():
    inner = PipelineFailure('ANALYZE', 'slow', code='timeout')
    middle = RuntimeError('wrapped')
    middle.__cause__ = inner
    outer = PipelineFailure('ANALYZE', 'x', code='unexpected')
    outer.__cause__ = middle
    found = _attr(outer)
    assert found['attribution_source'] == 'phase' and found['provider'] == 'glm', found


def test_i460_store_lock_timeout_code_is_local_even_over_a_model_failure():  # kills M5
    outer = PipelineFailure('ANALYZE', 'lock', code='store_lock_timeout')
    outer.__cause__ = PipelineFailure('ANALYZE', 'slow', code='timeout')
    assert _attr(outer)['attribution_source'] == 'local'


def test_i460_record_without_status_keeps_its_failure_fields():  # kills M3
    from backend.core.failure_attribution import read_attribution
    row = {'attribution_source': 'phase', **GLM, 'http_status': 503, 'failure_stage': 'analyze'}
    assert read_attribution(row)['http_status'] == 503 and read_attribution(row)['failure_stage'] == 'analyze'


# --- I451: completed + outcome=partial keeps its failure fields through read -> unrelated save --------

def test_i451_partial_survives_read_and_an_unrelated_save():
    partial = {'status': 'completed', 'outcome': 'partial', 'phase': 'rendering', 'run_id': 'r1', **GLM,
               'attribution_source': 'phase', 'failure_stage': 'render', 'http_status': 503,
               'upstream_error_type': 'upstream_unavailable', 'error_code': 'provider_error'}
    root = store.directory('p451') / 'metadata'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'studio.json').write_text(json.dumps({'id': 'p451', 'analysis': partial, 'analysis_history': [
        {'run_id': 'r0', 'analysis': {**partial, 'run_id': 'r0'}}]}), encoding='utf-8')
    assert store.read('p451', recover=False)['analysis']['failure_stage'] == 'render'
    store.change('p451', lambda d: d['jobs'].append({'job_id': 'j', 'status': 'completed'}))
    state = store.read('p451', recover=False)
    for row in (state['analysis'], state['analysis_history'][0]['analysis']):
        assert row['failure_stage'] == 'render' and row['http_status'] == 503, row


# --- I452: no inference from equal values; wholesale replacement only ---------------------------------

def test_i452_a_new_phase_failure_keeps_its_own_503_after_an_old_kimi_503():
    _project('p452', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        error = _kimi_503()
        try:
            raise error
        except Exception:  # noqa: BLE001
            store.change('p452', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    store.change('p452', lambda d: d['analysis'].update(status='running'))  # R30 I560: the retry starts (a real transition)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise PipelineFailure('ANALYZE', 'glm down', code='rate_limited', http_status=503)
        except PipelineFailure:
            store.change('p452', lambda d: d['analysis'].update(status='failed', error_code='rate_limited'))
    analysis = store.read('p452')['analysis']
    assert analysis['provider'] == 'glm' and analysis['attribution_source'] == 'phase'
    assert analysis['http_status'] == 503, analysis


def test_i452_old_phase_503_is_replaced_by_a_new_failure_without_status():
    _project('p452b', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise PipelineFailure('ANALYZE', 'glm 503', code='provider_error', http_status=503)
        except PipelineFailure:
            store.change('p452b', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
        assert store.read('p452b')['analysis']['http_status'] == 503
        store.change('p452b', lambda d: d['analysis'].update(status='running'))  # R30 I560: the retry starts (a real transition)
        try:
            raise PipelineFailure('ANALYZE', 'slow', code='timeout')
        except PipelineFailure:
            store.change('p452b', lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('p452b')['analysis']
    assert 'http_status' not in analysis and 'upstream_error_type' not in analysis, analysis


# --- I454: a render receipt is a local failure of the generation --------------------------------------

def test_i454_render_lock_timeout_receipt_writes_local_on_the_generation():
    store.directory('p454').mkdir(parents=True, exist_ok=True)
    store.write('p454', {'id': 'p454', 'generation': {'status': 'rendering', **GLM, 'model': 'glm-4'},
                         'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r1', 'instance': store.INSTANCE, **GLM},
                         'jobs': [{'job_id': 'j1', 'status': 'running', 'instance': store.INSTANCE}],
                         'output_variants': [{'id': 'v1', 'status': 'running', 'render_job_id': 'j1'}]},
                _recover_previous=False)
    path = store.directory('p454') / 'metadata' / 'studio.json'
    store._append_receipt(path, {'identity': ('render', 'j1'), 'pending': {},
                                 'message': file_lock.LOCK_TIMEOUT_MESSAGE, 'error_code': file_lock.LOCK_TIMEOUT_CODE})
    state = store.read('p454')
    generation = state['generation']
    assert generation['status'] == 'failed' and generation['error_code'] == 'store_lock_timeout'
    assert generation['attribution_source'] == 'local' and generation['provider'] == 'glm', generation
    assert state['analysis']['attribution_source'] == 'local'


# --- I455 / I457 / I458 --------------------------------------------------------------------------------

def test_i455_local_context_has_no_http_status_either():
    with llm_emit.track_run():
        inner = _kimi_503()
    outer = file_lock.LockTimeout()
    outer.__context__ = inner
    context = studio_failure_context(outer, 'production')
    assert 'http_status' not in context and 'upstream_error_type' not in context, context


def test_i457_no_unreachable_code_after_the_return():
    import ast
    import inspect
    from backend.core import sentry_setup
    fn = ast.parse(inspect.getsource(sentry_setup.studio_failure_context)).body[0]
    assert isinstance(fn.body[-1], ast.Return), 'statements after the final return'
    assert 'classify_run_upstream' not in inspect.getsource(sentry_setup.studio_failure_context)


def test_i458_release_validation_comment_says_local_is_not_responsibility():
    sql = (ROOT / 'docs/analytics/release_validation.sql').read_text(encoding='utf-8')
    assert 'local = 产品原因' not in sql
    assert 'local = 非模型归因，统计责任仍按错误码判断' in sql


# --- design: one factory --------------------------------------------------------------------------------

def test_one_snapshot_factory():
    for path in ('backend/core/llm_emit.py', 'backend/core/sentry_setup.py', 'backend/services/studio/store.py'):
        text = (ROOT / path).read_text(encoding='utf-8')
        assert 'FailureAttribution(' not in text and 'FailureAttribution._make' not in text and '.build(' not in text, path
    assert 'build_attribution' in (ROOT / 'backend/core/sentry_setup.py').read_text(encoding='utf-8')
    assert 'build_attribution' in (ROOT / 'backend/core/llm_emit.py').read_text(encoding='utf-8')
    assert 'build_attribution' in (ROOT / 'backend/services/studio/store.py').read_text(encoding='utf-8')


def test_i450_record_of_a_request_that_got_no_answer_is_not_a_model_failure():
    """Not a local error type either: a plain RuntimeError raised inside the call (no status, no SDK error)."""
    def impl(*_a, **_k):
        raise RuntimeError('fixture: client bug before the answer')
    with llm_emit.track_run():
        try:
            with llm_emit.bind_context(identity=KIMI):
                llm_emit.observe_provider_call(_provider('https://kimi.fixture.example/v1', 'kimi-k2'), impl, 'p')
        except RuntimeError as error:
            found = llm_emit.attribution(error)
    assert found['attribution_source'] == 'local' and found.get('provider') != 'kimi', found


def test_factory_local_names_the_phase_identity_before_the_start_identity():
    from backend.core.failure_attribution import build_attribution
    snap = build_attribution(PermissionError('fixture'), phase_identity=GLM, start_identity=KIMI)
    assert (snap.attribution_source, snap.provider, snap.http_status) == ('local', GLM['provider'], None)
