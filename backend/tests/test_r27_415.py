"""R27 #415 (Dong R26 design, 157/415-attribution-design.md): one classifier, one write-once snapshot,
one reader. I415-I418, I420-I422, I424 + design points. Each test fails on 49575864 on an assertion
(module-not-found aside: the failure_attribution tests also pin the rule's behaviour through llm_emit/store)."""
import json
import re
import subprocess
from pathlib import Path

import pytest

from backend.core import file_lock, llm_emit
from backend.pipeline.failures import PipelineFailure
from backend.services.studio import failure_identity, store
from backend.tests.test_r25_415 import GLM, KIMI, _call, _project, isolated  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
VISION = {**GLM, 'model': 'glm-4v', 'base_url_host': 'glm.fixture.example'}


def _kimi_503():
    try:
        _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
    except Exception as error:  # noqa: BLE001
        return error
    raise AssertionError('no 503')


# --- I415: decision order local -> model -> request record --------------------------------------------

def test_i415_lock_timeout_raised_while_handling_a_model_503_is_local():
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        inner = _kimi_503()
        try:
            try:
                raise inner
            except Exception:  # noqa: BLE001
                raise file_lock.LockTimeout()
        except file_lock.LockTimeout as outer:
            found = llm_emit.attribution(outer)
    assert found['attribution_source'] == 'local', found
    assert 'http_status' not in found and 'upstream_error_type' not in found
    assert found.get('provider') != 'kimi'


def test_i415_classify_failure_order_and_request_record():
    from backend.core.failure_attribution import FailureKind, classify_failure
    with llm_emit.track_run():
        error = _kimi_503()
        verdict = classify_failure(error)
        assert verdict.kind is FailureKind.MODEL and verdict.record is not None
        wrapped = PipelineFailure('INGEST', 'site', code='source_blocked')
        wrapped.__cause__ = error
        assert classify_failure(wrapped).kind is FailureKind.LOCAL  # decisive local link outside wins
        assert classify_failure(wrapped).record is None
    assert classify_failure(None).kind is FailureKind.NONE
    assert classify_failure(ValueError('x')).kind is FailureKind.LOCAL
    assert classify_failure(PipelineFailure('ANALYZE', 'x', code='timeout')).kind is FailureKind.MODEL


def test_i416_no_type_name_strings_and_one_classifier():
    source = (ROOT / 'backend/core/failure_attribution.py').read_text(encoding='utf-8')
    assert '__name__' not in source
    emit = (ROOT / 'backend/core/llm_emit.py').read_text(encoding='utf-8')
    assert '"PipelineFailure", "VisionRequestError"' not in emit
    sentry = (ROOT / 'backend/core/sentry_setup.py').read_text(encoding='utf-8')
    assert 'skip_upstream' not in sentry and 'build_attribution' in sentry
    assert not re.search(r'^\s*(from|import)\s+\S*llm_emit', source, re.M)  # no cycle: sentry_setup -> failure_attribution never pulls llm_emit

    class PipelineFailure2(Exception):
        code = 'timeout'
    PipelineFailure2.__name__ = 'PipelineFailure'  # a look-alike by name is not a model error
    assert llm_emit.is_model_error(PipelineFailure2()) is False


def test_i416_studio_failure_context_gives_a_lock_timeout_no_inner_upstream():
    from backend.core.sentry_setup import studio_failure_context
    with llm_emit.track_run():
        inner = _kimi_503()
    outer = file_lock.LockTimeout()
    outer.__context__ = inner
    context = studio_failure_context(outer, 'production')
    assert 'upstream_error_type' not in context, context


# --- snapshot: write once, whole, local without http/upstream ------------------------------------------

def test_snapshot_local_with_upstream_fields_raises_explicitly():
    from backend.core.failure_attribution import FailureAttribution
    with pytest.raises(ValueError):
        FailureAttribution('local', provider='glm', config_source='customized', http_status=503)
    with pytest.raises(ValueError):
        FailureAttribution('local', upstream_error_type='upstream_unavailable')
    with pytest.raises(ValueError):
        FailureAttribution('phase', provider='glm')  # half identity
    built = FailureAttribution._make('local', {**GLM, 'model': 'glm-4'}, http_status=503, upstream_error_type='x')
    assert 'http_status' not in built.to_fields() and built.to_fields()['attribution_source'] == 'local'


def test_snapshot_validation_is_not_an_assert():
    source = (ROOT / 'backend/core/failure_attribution.py').read_text(encoding='utf-8')
    assert not re.search(r'^\s*assert\b', source, re.M)


def test_write_attribution_replaces_the_group_whole():
    from backend.core.failure_attribution import FailureAttribution, write_attribution
    record = {'status': 'failed', **KIMI, 'model': 'kimi-k2', 'http_status': 503,
              'upstream_error_type': 'upstream_unavailable', 'attribution_source': 'request', 'error_code': 'x'}
    write_attribution(record, FailureAttribution._make('phase', {**GLM}, failure_stage='analyze'))
    assert record == {'status': 'failed', 'error_code': 'x', **GLM, 'failure_stage': 'analyze',
                      'attribution_source': 'phase'}


# --- I417: a new phase failure keeps nothing of an older request's status ------------------------------

def test_i417_new_phase_failure_drops_the_older_request_status():
    _project('p417', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        error = _kimi_503()
        try:
            raise error
        except Exception:  # noqa: BLE001
            store.change('p417', lambda d: d['analysis'].update(status='failed', error_code='provider_error'))
    assert store.read('p417')['analysis']['attribution_source'] == 'request'
    store.change('p417', lambda d: d['analysis'].update(status='running'))  # R30 I560: the retry starts (a real transition)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise PipelineFailure('ANALYZE', 'slow', code='timeout')
        except PipelineFailure:
            store.change('p417', lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('p417')['analysis']
    assert analysis['attribution_source'] == 'phase' and analysis['provider'] == 'glm'
    assert 'http_status' not in analysis and 'upstream_error_type' not in analysis, analysis


def test_i452_one_mechanism_no_jobs_clearing_no_value_inference():
    """R28 I452: old data is handled only by wholesale snapshot replacement."""
    store_src = (ROOT / 'backend/services/studio/store.py').read_text(encoding='utf-8')
    jobs = (ROOT / 'backend/services/studio/jobs.py').read_text(encoding='utf-8')
    assert 'clear_failure_fields' not in store_src + jobs
    assert "older.get('attribution_source') == 'request'" not in store_src


# --- I418: lock-timeout receipt recovery writes local -------------------------------------------------

def test_i418_receipt_recovery_writes_a_local_snapshot():
    _project('p418', {'status': 'running', 'phase': 'production', 'run_id': 'r1', **GLM, 'model': 'glm-4',
                      'http_status': 503})
    path = store.directory('p418') / 'metadata' / 'studio.json'
    store._append_receipt(path, {'identity': ('analysis', 'r1', 'production'), 'pending': {},
                                 'message': file_lock.LOCK_TIMEOUT_MESSAGE, 'error_code': file_lock.LOCK_TIMEOUT_CODE})
    analysis = store.recover('p418')['analysis']
    assert analysis['status'] == 'failed' and analysis['error_code'] == 'store_lock_timeout'
    assert analysis['attribution_source'] == 'local' and analysis['provider'] == 'glm'
    assert 'http_status' not in analysis
    on_disk = json.loads(path.read_text(encoding='utf-8'))['analysis']
    assert on_disk['attribution_source'] == 'local'


# --- I421 / read-time cleanup, never written back ------------------------------------------------------

def _raw(pid, data):
    root = store.directory(pid) / 'metadata'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'studio.json').write_text(json.dumps({'id': pid, **data}), encoding='utf-8')
    return root / 'studio.json'


def test_i421_history_half_identity_and_local_status_are_cleaned_on_read_only():
    legacy = {'run_id': 'r0', 'analysis': {'run_id': 'r0', 'status': 'failed', 'provider': 'kimi',
                                           'http_status': 503, 'attribution_source': 'local'}}
    path = _raw('p421', {'analysis': {'status': 'failed', 'run_id': 'r1', 'provider': 'glm',
                                      'attribution_source': 'local', 'upstream_error_type': 'invalid_key'},
                         'analysis_history': [legacy]})
    before = path.read_text(encoding='utf-8')
    state = store.read('p421', recover=False)
    row = state['analysis_history'][0]['analysis']
    assert 'provider' not in row and 'http_status' not in row and row['attribution_source'] == 'local'
    assert 'provider' not in state['analysis'] and 'upstream_error_type' not in state['analysis']
    assert path.read_text(encoding='utf-8') == before, 'the read wrote the cleanup back'


def test_history_summary_comes_from_read_attribution():
    _project('ph', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise file_lock.LockTimeout()
        except file_lock.LockTimeout:
            store.change('ph', lambda d: d['analysis'].update(status='failed', error_code='store_lock_timeout',
                                                              http_status=503))
    summary = store.read('ph')['analysis_history'][-1]['analysis']
    assert summary['attribution_source'] == 'local' and 'http_status' not in summary


# --- the only readers: guard (R28 I456: every snapshot field, .get and [] reads, any variable name) ------

import ast  # noqa: E402

SNAPSHOT = {'provider', 'config_source', 'model', 'base_url_host', 'http_status', 'upstream_error_type',
            'failure_stage', 'attribution_source'}
# Functions that read these names but are NOT readers of a failure-attribution snapshot, each with why.
# (Exempt by location, never by variable name.)
NOT_SNAPSHOT_READERS = {
    ('backend/core/llm_emit.py', '_remember_run'): 'builds the request record from the request event',
    ('backend/core/llm_emit.py', '_request_properties'): 'builds the llm_request_finished event',
    ('backend/core/llm_emit.py', 'request_finished'): 'request event context',
    ('backend/core/llm_emit.py', 'emit_vision_request'): 'request event context',
    ('backend/core/llm_emit.py', 'emit_asr_readiness_checked'): 'asr probe event',
    ('backend/core/llm_emit.py', 'sent_vision_identity'): 'vision settings -> sent identity',
    ('backend/core/llm_emit.py', '_provider_label'): 'provider object label',
    ('backend/core/llm_emit.py', 'run_snapshot'): 'sanitized pair check on the already built snapshot fields',
    ('backend/core/llm_emit.py', 'sentry_tags_for_error'): 'R31 I565: reads the output of export_attribution only',
    ('backend/core/sentry_setup.py', 'before_send'): 'Sentry tag sanitizer on outgoing tags',
    ('backend/services/studio/intelligence.py', 'vision_call'): 'vision settings model',
    ('backend/services/studio/intelligence.py', 'visual_config'): 'vision settings model',
    ('backend/services/studio/jobs.py', 'run_content'): "the adapter result's HTTP status -> PipelineFailure",
    ('backend/services/studio/jobs.py', '_produce_selected'): 'ranks multi-goal causes; does not assemble a snapshot',
    ('backend/services/studio/attempts.py', '_cause'): 'copies a settled cause onto the attempt receipt',
    ('backend/services/studio/attempts.py', 'settle'): 'writes the ranked cause onto the attempt receipt',
    ('backend/services/studio/attempts.py', '_terminal_event'): 'copies fields already stored on the settled receipt',
    ('backend/services/studio/store.py', 'settle_attempt'): 'writes the caller failure_stage onto the one terminal record',
    ('backend/services/studio/store.py', 'settle_generation'): 'ranks variant failures for the generation cause',
    ('backend/services/studio/store.py', '_ensure_failure_identity'): "normalizes the job's own error_code/stage",
    ('backend/services/studio/store.py', 'fill'): "normalizes the job's own error_code/stage",
    ('backend/services/studio/vision_settings.py', '*'): 'vision settings',
    ('backend/api/v1/settings.py', 'get_settings'): 'model settings page',
    ('backend/api/v1/settings.py', 'get_current_provider'): 'model settings page',
}


def _py_reads(path):
    rel = str(path.relative_to(ROOT))
    out = []
    for fn in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (rel, fn.name) in NOT_SNAPSHOT_READERS or (rel, '*') in NOT_SNAPSHOT_READERS:
            continue
        for node in ast.walk(fn):
            key = None
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get'
                    and node.args and isinstance(node.args[0], ast.Constant)):
                key = node.args[0].value
            elif (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)
                  and isinstance(node.slice, ast.Constant)):
                key = node.slice.value
            if key in SNAPSHOT:
                out.append(f'{rel}:{node.lineno} {fn.name}: {key}')
    return sorted(set(out))


TS_EXEMPT = ('export function pickAttribution(', 'export function isFailedTerminal(',
             'export function safeStudioProperties(', 'export function screeningIdentity(',
             'export function receiptEventCauses(', 'export function pageFailureAction(',
             'export function analysisPageFailure(')
_TS_READ = re.compile(r"""(\.\s*|\[\s*['"])(attribution_source|upstream_error_type|http_status|failure_stage|provider|config_source|base_url_host)\b(?!\s*[?]?:)""")


def _ts_reads(path):
    text = path.read_text(encoding='utf-8')
    for marker in TS_EXEMPT:
        if marker in text:
            start = text.index(marker)
            end = text.index('\n}\n', start)
            text = text[:start] + '\n' * text[start:end].count('\n') + text[end:]
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        code = line.split('//')[0]
        if code.lstrip().startswith(('*', '/*')):
            continue  # doc comments
        if re.match(r'\s*(type |export type |\w+\?: \{|  (analysis|generation)\?:)', code):
            continue  # type declarations
        if re.match(r'\s*(export )?const [A-Z_]+ = ', code):
            continue  # R31 I565: a key-list constant (ATTRIBUTION_KEYS) names keys, it reads no record
        if _TS_READ.search(code):
            out.append(f'{path.relative_to(ROOT)}:{no}: {line.strip()}')
    return out


def test_grep_no_attribution_reads_outside_the_one_reader():
    offenders = []
    for path in [*(ROOT / 'backend/services/studio').glob('*.py'), ROOT / 'backend/core/llm_emit.py',
                 ROOT / 'backend/core/sentry_setup.py', *(ROOT / 'backend/api').rglob('*.py')]:
        offenders += _py_reads(path)
    for path in [ROOT / 'frontend/src/analytics/workflow.ts', *(ROOT / 'frontend/src/features/studio').rglob('*.ts*')]:
        offenders += _ts_reads(path)
    assert offenders == [], '\n'.join(offenders)


def test_grep_guard_catches_direct_reads_of_every_field(tmp_path):
    probe = ROOT / 'backend/services/studio/_guard_probe_tmp.py'
    probe.write_text("def f(snapshot, found, record):\n    a = snapshot.get('http_status')\n"
                     "    b = found.get('attribution_source')\n    c = record.get('failure_stage')\n"
                     "    d = record['provider']\n    record['model'] = 1\n", encoding='utf-8')
    try:
        hits = _py_reads(probe)
    finally:
        probe.unlink()
    assert [h.rsplit(': ', 1)[1] for h in hits] == ['http_status', 'attribution_source', 'failure_stage', 'provider']
    assert _TS_READ.search('snapshot.analysis?.upstream_error_type')
    assert _TS_READ.search("run['failure_stage']")
    assert not _TS_READ.search('failure_stage?: string')


# --- I422 / I424 --------------------------------------------------------------------------------------

def test_i422_release_validation_splits_by_attribution_source():
    sql = (ROOT / 'docs/analytics/release_validation.sql').read_text(encoding='utf-8')
    block = sql[sql.index('1.5.7 成功率埋点'):sql.index('ORDER BY event, events DESC;')]
    assert 'properties.attribution_source AS attribution_source' in block
    assert "if(toString(properties.attribution_source) = 'local', NULL, properties.provider)" in block
    assert 'GROUP BY event, attribution_source, provider' in block


LOCALES = ('zh', 'en', 'ja', 'ko', 'es', 'fr', 'pt', 'ru')


def test_i424_lock_timeout_notice_in_all_8_locales():
    key = file_lock.LOCK_TIMEOUT_MESSAGE
    for lang in LOCALES:
        data = json.loads((ROOT / f'frontend/src/i18n/locales/{lang}.json').read_text(encoding='utf-8'))
        value = data.get(key)
        assert isinstance(value, str) and value.strip(), lang
        if lang != 'zh':
            assert value != key and '进程' not in value and '原素材已保留' not in value, lang  # translated, not the Chinese
    ts = (ROOT / 'frontend/src/utils/llmFailure.ts').read_text(encoding='utf-8')
    assert key in ts and "STORE_LOCK_TIMEOUT = 'store_lock_timeout'" in ts


def test_i415_a_non_decisive_wrapper_is_looked_through():
    """The walk goes INWARD past non-decisive links (unexpected/OSError) to the model failure."""
    from backend.core.failure_attribution import FailureKind, classify_failure
    with llm_emit.track_run():
        inner = _kimi_503()
    wrapper = PipelineFailure('ANALYZE', 'x', code='unexpected')
    wrapper.__cause__ = OSError('socket')
    wrapper.__cause__.__cause__ = inner
    verdict = classify_failure(wrapper)
    assert verdict.kind is FailureKind.MODEL and verdict.record is not None
    # R28 I450: a local error in ANY layer is judged first, even under a model-coded wrapper
    outer = PipelineFailure('ANALYZE', 'x', code='provider_error')
    outer.__cause__ = subprocess.CalledProcessError(1, ['ffmpeg'])
    assert classify_failure(outer).kind is FailureKind.LOCAL
