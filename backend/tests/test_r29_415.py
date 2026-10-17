"""R29 #415 (Dong R28 I500-I506 + the redaction-boundary decision): the layer closest to the provider call,
where the exception chain is still intact, builds the attribution snapshot ONCE; dicts, threads, store
writes and events carry it unchanged. Every test here fails on 9ce045c2 on an assertion, or is proven by a
mutation (157/mut415-r29). Nothing here imports a symbol that only exists after R29."""
import ast
import json
from pathlib import Path

import openai
import pytest

from backend.core import llm_emit
from backend.core.failure_attribution import FailureKind, classify_failure
from backend.core.sentry_setup import studio_error_code, studio_failure_context
from backend.pipeline.failures import PipelineFailure
from backend.services.studio import failure_identity, store
from backend.tests.test_r25_415 import GLM, KIMI, _call, _project, _provider, isolated  # noqa: F401
from backend.tests.test_content_failure_http_status import _outline_raises, pipeline  # noqa: F401
from backend.tests.test_cloud_adapter_failure import cloud_adapter  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
SECRET_URL = 'https://kimi.fixture.example/v1/chat?api_key=sk-r29-SECRET-0000'
SECRET_BODY = 'r29-private-provider-body'


class ProviderError(openai.APIStatusError):
    """The SDK's status error (constructed without a live response)."""
    def __init__(self, message, status_code):
        Exception.__init__(self, message)
        self.status_code = status_code


def _status_error(status, message=f'Error code: 503 {SECRET_URL} {SECRET_BODY}'):
    return ProviderError(message, status)


def _connection_error():
    import httpx
    return openai.APIConnectionError(message=f'Connection error. {SECRET_URL}', request=httpx.Request('POST', SECRET_URL))


def _timeout_error():
    import httpx
    return openai.APITimeoutError(request=httpx.Request('POST', SECRET_URL))


def _attr(error, phase=GLM):
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: phase, **phase})
        return llm_emit.attribution(error)


# --- I501: the adapter builds the snapshot; it crosses apply().get() whole ----------------------------

def _wrapped(outer, inner):
    try:
        try:
            raise inner
        except BaseException as cause:
            raise outer from cause
    except BaseException as error:  # noqa: BLE001
        return error


def test_i501_uncoded_wrapper_over_a_provider_503_stays_model_across_run_content(pipeline, monkeypatch):
    """probe P2 ①: PipelineFailure('unexpected') from APIStatusError(503) was rebuilt as LOCAL."""
    from backend.services.studio import jobs
    mod, video = pipeline
    _outline_raises(mod, monkeypatch, _wrapped(PipelineFailure('ANALYZE', '大纲失败', code='unexpected'), _status_error(503)))
    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)
    assert classify_failure(raised.value).kind is FailureKind.MODEL
    assert studio_failure_context(raised.value, 'production').get('http_status') == 503


def test_i501_provider_error_code_over_a_local_permission_error_stays_local(pipeline, monkeypatch):
    """②: the adapter judged LOCAL on the live chain; the rebuilt error must not become MODEL."""
    from backend.services.studio import jobs
    mod, video = pipeline
    _outline_raises(mod, monkeypatch, _wrapped(PipelineFailure('ANALYZE', '写缓存失败', code='provider_error'), PermissionError(13, 'fixture')))
    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)
    assert classify_failure(raised.value).kind is FailureKind.LOCAL
    assert 'http_status' not in studio_failure_context(raised.value, 'production')


def test_i501_the_failing_requests_record_crosses_the_bridge(pipeline, monkeypatch):
    """③: Kimi's 503 record must not be swapped for GLM's phase identity after apply().get()."""
    from backend.services.studio import jobs
    mod, video = pipeline

    def outline(*_a, **_k):
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception as error:  # noqa: BLE001
            raise PipelineFailure('ANALYZE', '大纲失败', code='') from error
    monkeypatch.setattr(mod, 'run_step1_outline', outline)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: GLM, **GLM})
        with pytest.raises(PipelineFailure) as raised:
            jobs.run_content('p', video)
        found = llm_emit.attribution(raised.value)
    assert (found.get('attribution_source'), found.get('provider'), found.get('http_status')) == ('request', 'kimi', 503), found


def test_i501_restored_non_model_code_wrapping_a_503_is_model(pipeline, monkeypatch):
    """Restored (R28 deleted it): a non-model code (llm_connection) over the SDK's 503 keeps model + 503."""
    from backend.services.studio import jobs
    mod, video = pipeline
    failure = PipelineFailure('ANALYZE', '无法连接模型服务。', code='llm_connection')
    failure.__cause__ = ProviderError('boom', 503)
    _outline_raises(mod, monkeypatch, failure)
    with pytest.raises(PipelineFailure) as raised:
        jobs.run_content('p', video)
    assert (raised.value.code, raised.value.http_status) == ('llm_connection', 503)
    assert classify_failure(raised.value).kind is FailureKind.MODEL
    assert studio_failure_context(raised.value, 'production') == {
        'failure_stage': 'analyze', 'http_status': 503, 'upstream_error_type': 'upstream_unavailable'}


def test_i501_no_model_failure_boolean_and_no_rebuild_in_run_content():
    adapter = (ROOT / 'backend/services/simple_pipeline_adapter.py').read_text(encoding='utf-8')
    jobs = (ROOT / 'backend/services/studio/jobs.py').read_text(encoding='utf-8')
    assert 'model_failure' not in adapter and 'model_failure' not in jobs
    assert "'provider_error' if" not in jobs


# --- I500: only the explicit __cause__ chain ------------------------------------------------------------

def test_i500_a_503_sent_while_handling_a_cache_miss_is_model():
    try:
        try:
            raise FileNotFoundError('cache miss')
        except FileNotFoundError:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
    except Exception as error:  # noqa: BLE001
        assert isinstance(error.__context__, FileNotFoundError)
        verdict = classify_failure(error)
        found = _attr(error)
    assert verdict.kind is FailureKind.MODEL
    assert (found.get('attribution_source'), found.get('provider'), found.get('http_status')) == ('request', 'kimi', 503)


def test_i500_an_explicit_local_cause_still_wins():
    error = _wrapped(RuntimeError('wrapper'), PermissionError(13, 'fixture'))
    assert classify_failure(error).kind is FailureKind.LOCAL


# --- I503: no "same failure" inference in the store ------------------------------------------------------

def test_i503_a_new_local_error_in_the_same_run_with_the_same_code_replaces_the_old_503():
    _project('p503', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    with llm_emit.track_run():
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception:  # noqa: BLE001
            store.change('p503', lambda d: d['analysis'].update(status='failed', error_code='unexpected'))
        assert store.read('p503')['analysis'].get('http_status') == 503
        # R30 I560: the retry of the same run starts (a real transition), then fails with the same code.
        store.change('p503', lambda d: d['analysis'].update(status='running'))
        try:
            raise PermissionError(13, 'fixture: a new local failure, same run, same code')
        except PermissionError:
            store.change('p503', lambda d: d['analysis'].update(status='failed', error_code='unexpected', error='new'))
    analysis = store.read('p503')['analysis']
    assert analysis.get('attribution_source') == 'local'
    assert analysis.get('http_status') is None and analysis.get('upstream_error_type') is None, analysis


def test_i503_store_has_no_same_failure_rule():
    text = (ROOT / 'backend/services/studio/store.py').read_text(encoding='utf-8')
    assert "prior.get('error_code') == record.get('error_code')" not in text
    assert 'same_failure' not in text and 'prior_snapshot' not in text


# --- redaction boundaries: the snapshot is built before ``from None`` and rides on the safe error ------

def test_guard_a_provider_error_wrapped_once_by_the_redaction_boundary_is_still_model():
    from backend.core.llm_telemetry import log_safe_exception
    try:
        try:
            raise _status_error(503)
        except ProviderError as original:
            raise log_safe_exception(original) from None
    except RuntimeError as safe:
        wrapped = safe
    assert wrapped.__cause__ is None and wrapped.__suppress_context__  # the raw chain is cut
    assert classify_failure(wrapped).kind is FailureKind.MODEL
    found = _attr(wrapped)
    assert (found.get('attribution_source'), found.get('http_status')) == ('phase', 503), found
    assert SECRET_BODY not in json.dumps(found) and 'sk-r29' not in json.dumps(found)


def test_guard_a_connection_error_through_the_real_call_boundary_is_model_without_status():
    """I505 + boundary: openai APIConnectionError wrapped by log_safe_exception inside the observed call."""
    from backend.core.llm_telemetry import log_safe_exception

    def impl(*_a, **_k):
        try:
            raise _connection_error()
        except openai.APIConnectionError as original:
            raise log_safe_exception(original) from None
    with llm_emit.track_run():
        try:
            with llm_emit.bind_context(identity=KIMI):
                llm_emit.observe_provider_call(_provider('https://kimi.fixture.example/v1', 'kimi-k2'), impl, 'p')
        except RuntimeError as error:
            verdict = classify_failure(error)
            found = llm_emit.attribution(error)
    assert verdict.kind is FailureKind.MODEL
    assert (found.get('attribution_source'), found.get('provider')) == ('request', 'kimi'), found
    assert 'http_status' not in found  # I505: no HTTP response, no status


def test_guard_sentry_event_of_a_wrapped_provider_error_has_no_message_or_url_and_is_model():
    import sentry_sdk
    from sentry_sdk.utils import event_from_exception
    from backend.core.llm_telemetry import log_safe_exception
    try:
        try:
            raise _status_error(503)
        except ProviderError as original:
            raise log_safe_exception(original) from None
    except RuntimeError as safe:
        wrapped = safe
    options = {**sentry_sdk.get_client().options, 'include_local_variables': False, 'include_source_context': False}
    event, _hint = event_from_exception(wrapped, client_options=options)
    text = json.dumps(event, default=str)
    assert SECRET_BODY not in text and 'sk-r29-SECRET' not in text and 'kimi.fixture.example/v1/chat' not in text
    assert len(event['exception']['values']) == 1  # no raw provider exception in the chain
    with llm_emit.track_run():
        tags = llm_emit.sentry_tags_for_error(wrapped, 'analyze')
    assert tags.get('http_status') == '503', tags


def test_cloud_transcription_http_failure_carries_a_model_snapshot_through_the_adapter(cloud_adapter):
    import asyncio
    import httpx
    case = cloud_adapter
    case.configure('qwen-audio-3.0-asr-flash', lambda request: httpx.Response(
        503, json={'error': {'message': SECRET_BODY}}, request=request))
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result['error_code'] == 'provider_error'
    carried = result.get('attribution') or {}
    assert (carried.get('attribution_source'), carried.get('http_status')) == ('phase', 503), result
    assert SECRET_BODY not in json.dumps(result, ensure_ascii=False)


def test_cloud_transcription_connection_failure_is_model_without_status(cloud_adapter):
    import asyncio
    import httpx
    case = cloud_adapter

    def reply(request):
        raise httpx.ConnectError('private-network-detail', request=request)
    case.configure('qwen-audio-3.0-asr-flash', reply)
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    carried = result.get('attribution') or {}
    assert carried.get('attribution_source') == 'phase' and 'http_status' not in carried, result


# --- ModelResponseInvalid: 200 + content failed our validation is MODEL (invalid_response) ---------------

_INVALID_SITES = {
    'backend/services/studio/intelligence.py': ('文字模型返回的内容不是有效 JSON', '视觉模型返回的候选格式无效', '模型返回重复候选标识',
                                               '模型选段超出期望时长', '模型复核边界超出采样区间', '模型未返回成片方案'),
    'backend/services/studio/subtitle_promo.py': ('推广方案格式无效', '推广方案引用了无效片段', '推广文案为空'),
    'backend/services/studio/render.py': ('字幕翻译格式不完整', '翻译后的开头文字过长'),
    'backend/utils/llm_client.py': ('无法从响应中解析出有效的JSON',),
}


def test_model_response_invalid_raise_sites():
    """Every listed site raises the explicit type (intelligence 7 incl. 2 duration sites, promo 3, render 2,
    llm_client 2); none raises a bare ValueError any more."""
    count = 0
    for rel, needles in _INVALID_SITES.items():
        tree = ast.parse((ROOT / rel).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
                continue
            text = ast.unparse(node.exc)
            if any(n in text for n in needles):
                name = node.exc.func.id if isinstance(node.exc.func, ast.Name) else ast.unparse(node.exc.func)
                assert name == 'ModelResponseInvalid', f'{rel}:{node.lineno}: {name}'
                count += 1
    assert count == 14, count


def test_model_response_invalid_is_model_with_invalid_response(monkeypatch):
    from backend.services.studio import intelligence
    with pytest.raises(ValueError) as dup:
        intelligence.select_highlights([{'id': 'a', 'label': 'x', 'start': 0, 'end': 2},
                                        {'id': 'a', 'label': 'y', 'start': 3, 'end': 5}], 10)
    assert classify_failure(dup.value).kind is FailureKind.MODEL
    assert studio_error_code(dup.value) == 'invalid_response'
    from backend.utils.llm_client import LLMClient
    with pytest.raises(ValueError) as unparsable:
        LLMClient.parse_json_response(object.__new__(LLMClient), 'no json here at all')
    assert classify_failure(unparsable.value).kind is FailureKind.MODEL
    assert studio_error_code(unparsable.value) == 'invalid_response'
    found = _attr(unparsable.value)
    assert found.get('attribution_source') == 'phase' and 'http_status' not in found


def test_model_response_invalid_from_text_json(monkeypatch):
    from backend.services.studio import intelligence
    from backend.utils import llm_client
    fake = type('C', (), {'llm_manager': type('M', (), {'get_current_provider_info': lambda self: {'available': True}})(),
                          'call': lambda self, p, d: 'certainly! not json'})
    monkeypatch.setattr(llm_client, 'LLMClient', fake)
    with pytest.raises(ValueError) as caught:
        intelligence.text_json('p', {})
    assert classify_failure(caught.value).kind is FailureKind.MODEL
    assert studio_error_code(caught.value) == 'invalid_response'


# --- I502: the single factory / single reader guard is an AST scan ----------------------------------------

# R31 (Dong I565): the variable-name reader heuristic (REC / READ_KEYS, ~60 lines) is deleted: the runtime
# payload tests (test_r31_415_payload.py, frontend r31-415-payload.test.cjs) are the guarantee now. What
# stays here is the cheap structural part: one factory, one restore point.
FACTORY_NAMES = {'FailureAttribution', '_make', 'from_fields'}
RESTORE_ALLOWED = {('backend/services/studio/jobs.py', 'run_content')}


def py_offences(source, rel='<memory>'):
    tree = ast.parse(source)
    out = []
    funcs = {}
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(f):
                funcs.setdefault(id(n), f.name)
    for n in ast.walk(tree):
        name = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else \
            n.name if isinstance(n, ast.alias) else n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None
        if name in FACTORY_NAMES:
            out.append((getattr(n, 'lineno', 0), f'factory: {name}'))
        if name == 'restore_attribution' and isinstance(n, (ast.Name, ast.Attribute, ast.alias)) \
                and (rel, funcs.get(id(n))) not in RESTORE_ALLOWED:
            out.append((getattr(n, 'lineno', 0), 'restore outside its one restore point'))
    return out


def test_i502_ast_guard_backend_has_one_factory_and_one_reader():
    offenders = []
    for path in sorted((ROOT / 'backend').rglob('*.py')):
        rel = path.relative_to(ROOT).as_posix()
        if '/tests/' in rel or rel == 'backend/core/failure_attribution.py':
            continue
        offenders += [f'{rel}:{line}: {what}' for line, what in py_offences(path.read_text(encoding='utf-8'), rel)]
    assert not offenders, '\n'.join(offenders)


@pytest.mark.parametrize('source', [
    # D3 (Dong): a second constructor through an alias
    'from backend.core.failure_attribution import FailureAttribution as _FA\n_bypass = lambda **k: _FA._make(**k)\n',
    # astra/sol: an alias of the class, then a direct construction
    'from backend.core import failure_attribution as fa\nSnapshot = fa.FailureAttribution\nsnap = Snapshot("local")\n',
    # a dynamic getattr on the module
    'import importlib\nm = importlib.import_module("backend.core.failure_attribution")\nS = getattr(m, "FailureAttribution")\n',
    # a restore under an import alias, outside run_content (R29 mutation G5)
    'from backend.core.failure_attribution import restore_attribution as _ra\n_y = lambda f: _ra(f)\n',
])
def test_i502_ast_guard_catches_every_bypass(source):
    assert py_offences(source), source


def test_i502_ast_guard_allows_plain_writes():
    assert not py_offences("def f(record, s):\n    record['http_status'] = s\n    record.pop('attribution_source', None)\n")


# --- I505 / I506 ----------------------------------------------------------------------------------------

@pytest.mark.parametrize('make, code', [(_connection_error, 'connection'), (_timeout_error, 'timeout')])
def test_i505_connection_errors_and_timeouts_are_model_without_a_status(make, code):
    error = make()
    assert classify_failure(error).kind is FailureKind.MODEL
    assert studio_error_code(error) == code
    found = _attr(error)
    assert found.get('attribution_source') == 'phase' and 'http_status' not in found


def test_i505_status_only_on_the_implicit_context_is_not_written():
    try:
        try:
            raise _status_error(503)
        except ProviderError:
            raise _connection_error()  # noqa: B904 - implicit context on purpose
    except openai.APIConnectionError as error:
        found = _attr(error)
    assert 'http_status' not in found, found


def test_i506_monitoring_doc_says_source_blocked_keeps_no_site_status():
    text = (ROOT / 'docs/analytics/STUDIO_MONITORING.md').read_text(encoding='utf-8')
    assert '`failure_stage=ingest` 和 `http_status`' not in text
    assert '**不记录**站点状态码' in text


def test_redaction_boundary_returns_an_error_with_no_raw_chain():
    """log_safe_exception is also used without `raise … from None` (step1_outline), so the safe error itself
    must not link back to the raw provider error: no __cause__, and the formatted traceback has no raw text."""
    import traceback
    from backend.core.llm_telemetry import log_safe_exception
    try:
        raise _connection_error()
    except Exception as raw:
        safe = log_safe_exception(raw)
    assert safe.__cause__ is None
    text = ''.join(traceback.format_exception(type(safe), safe, safe.__traceback__))
    assert SECRET_URL not in text and 'Connection error' not in text
    assert classify_failure(safe).kind is FailureKind.MODEL
