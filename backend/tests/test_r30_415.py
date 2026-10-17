"""R30 #415 (Dong R29 NO-GO, plan 157/415-r30-plan.md + Dong's 3 binding amendments): I560 (a store write
stamps a snapshot only on a record that became failed in THAT write), I563 (one HTTP-status rule: the
status frozen at the redaction boundary, else the explicit ``__cause__`` chain; never ``__context__``),
I567 (one classification: no ``sent`` override; the boundary classifies inside, raises ``from None``).
Each test fails on df53c89d on an assertion, or is proven by a mutation (157/mut415-r30). Nothing here
imports a symbol that only exists after R30."""
import asyncio
import inspect
import json
from types import SimpleNamespace

import httpx
import openai
import pytest
import requests

from backend.core import failure_attribution, llm_emit
from backend.core.failure_attribution import FailureKind, classify_failure
from backend.pipeline.failures import PipelineFailure, http_status_of
from backend.services.studio import failure_identity, store
from backend.tests.test_r25_415 import GLM, KIMI, _call, _project, isolated  # noqa: F401
from backend.tests.test_cloud_adapter_failure import cloud_adapter  # noqa: F401

VISION = {**GLM, 'model': 'glm-4v', 'base_url_host': 'glm.fixture.example'}
SECRET_URL = 'https://kimi.fixture.example/v1/chat?api_key=sk-r30-SECRET-0000'
SECRET_BODY = 'r30-private-provider-body'
SNAPSHOT_KEYS = ('attribution_source', 'provider', 'config_source', 'model', 'base_url_host', 'http_status',
                 'upstream_error_type', 'failure_stage', 'error_code')


class ProviderError(openai.APIStatusError):
    def __init__(self, message, status_code):
        Exception.__init__(self, message)
        self.status_code = status_code


def _snap(record):
    return {k: record.get(k) for k in SNAPSHOT_KEYS}


def _fail_with_kimi_503(pid, name='analysis', **extra):
    """A real failure: Kimi's request answers 503 and the record goes running -> failed in that write."""
    with llm_emit.track_run():
        try:
            _call(KIMI, 'https://kimi.fixture.example/v1', 'kimi-k2', status=503)
        except Exception:  # noqa: BLE001
            store.change(pid, lambda d: d[name].update(status='failed', error_code='provider_error', **extra))
    stored = store.read(pid)[name]
    assert (stored.get('attribution_source'), stored.get('provider'), stored.get('http_status')) == ('request', 'kimi', 503), stored
    return _snap(stored)


def _unrelated_write_while_handling(pid, error, mutate):
    """A store write inside an ``except`` that has nothing to do with the failed record (GLM phase)."""
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        try:
            raise error
        except BaseException:  # noqa: BLE001
            store.change(pid, mutate)


# --- I560: only a record that became failed IN THIS WRITE gets a snapshot --------------------------------

def test_i560_an_unrelated_write_in_an_except_keeps_the_existing_failure_snapshot():
    _project('p560a', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p560a')
    _unrelated_write_while_handling('p560a', RuntimeError('local GLM failure'), lambda d: d.update(note='unrelated'))
    assert _snap(store.read('p560a')['analysis']) == before


def test_i560_a_permission_error_while_updating_something_else_keeps_the_snapshot():
    _project('p560p', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p560p')
    _unrelated_write_while_handling('p560p', PermissionError(13, 'fixture'), lambda d: d.update(jobs=[{'job_id': 'j', 'status': 'failed'}]))
    assert _snap(store.read('p560p')['analysis']) == before


def test_i560_a_partial_terminal_keeps_its_snapshot_on_an_unrelated_write():
    """completed + outcome=partial is a failed terminal (I451): it is not 'non-failed' before the write."""
    _project('p560q', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    _fail_with_kimi_503('p560q')
    store.change('p560q', lambda d: d['analysis'].update(status='completed', outcome='partial'))
    before = _snap(store.read('p560q')['analysis'])
    assert before['http_status'] == 503
    _unrelated_write_while_handling('p560q', RuntimeError('local'), lambda d: d.update(note='x'))
    assert _snap(store.read('p560q')['analysis']) == before


def test_i560_the_generation_snapshot_is_kept_too():
    store.directory('p560g').mkdir(parents=True, exist_ok=True)
    store.write('p560g', {'id': 'p560g', 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r1', 'instance': store.INSTANCE},
                          'generation': {'status': 'production', 'created_at': '2026-10-17T03:00:00Z'}}, _recover_previous=False)
    before = _fail_with_kimi_503('p560g', name='generation', finished_at='2026-10-17T03:01:00Z')
    _unrelated_write_while_handling('p560g', RuntimeError('local'), lambda d: d.update(note='x'))
    assert _snap(store.read('p560g')['generation']) == before


def test_i560_cover_dispatch_failure_does_not_rewrite_the_run_snapshot(monkeypatch):
    """jobs.request_ai_cover: cover_executor.submit fails -> _update_cover_job inside the except (jobs.py:952)."""
    from backend.services import cover
    from backend.services.studio import jobs
    _project('p560c', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    store.change('p560c', lambda d: d.update(output_variants=[{'id': 'v1', 'status': 'completed'}]))
    before = _fail_with_kimi_503('p560c')
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=True))

    class Refusing:
        def submit(self, *_a, **_k):
            raise RuntimeError('executor shut down')
    monkeypatch.setattr(jobs, 'cover_executor', Refusing())
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        jobs.request_ai_cover('p560c', 'v1')
    data = store.read('p560c')
    assert data['output_variants'][0]['cover_job']['status'] == 'failed'
    assert _snap(data['analysis']) == before


def test_i560_a_real_transition_still_stamps_the_snapshot():
    _project('p560t', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    _fail_with_kimi_503('p560t')  # running -> failed with the 503 in hand: request/kimi/503


def test_i560_same_run_retry_goes_running_then_fails_again_replaces_the_snapshot():
    """Dong amendment 3: same run_id fails, the retry goes to running, fails again -> the 2nd failure's."""
    _project('p560r', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    _fail_with_kimi_503('p560r')
    store.change('p560r', lambda d: d['analysis'].update(status='running'))
    _unrelated_write_while_handling('p560r', PipelineFailure('ANALYZE', 'slow', code='timeout'),
                                    lambda d: d['analysis'].update(status='failed', error_code='timeout'))
    analysis = store.read('p560r')['analysis']
    assert (analysis.get('attribution_source'), analysis.get('provider'), analysis.get('run_id')) == ('phase', 'glm', 'r1'), analysis
    assert analysis.get('http_status') is None and analysis.get('error_code') == 'timeout', analysis


def test_i560_a_failure_of_another_run_replaces_the_snapshot_without_passing_running():
    _project('p560n', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    _fail_with_kimi_503('p560n')
    _unrelated_write_while_handling('p560n', PipelineFailure('ANALYZE', 'slow', code='timeout'),
                                    lambda d: d['analysis'].update(status='failed', run_id='r2', error_code='timeout'))
    analysis = store.read('p560n')['analysis']
    assert (analysis.get('attribution_source'), analysis.get('provider'), analysis.get('http_status')) == ('phase', 'glm', None), analysis


# --- I563: one status rule; an old 503 never leaks into a new request --------------------------------

def _connection_error_while_handling_a_503():
    try:
        try:
            raise ProviderError(f'Error code: 503 {SECRET_BODY}', 503)
        except ProviderError:
            raise openai.APIConnectionError(message=f'Connection error. {SECRET_URL}', request=httpx.Request('POST', SECRET_URL))  # noqa: B904
    except openai.APIConnectionError as error:
        return error


def test_i563_http_status_of_never_reads_the_implicit_context():
    error = _connection_error_while_handling_a_503()
    assert isinstance(error.__context__, ProviderError) and error.__cause__ is None
    assert http_status_of(error) is None


def test_i563_an_old_503_does_not_leak_into_the_new_requests_record(monkeypatch):
    posted = []
    monkeypatch.setattr(llm_emit, '_post_event', lambda event, props: posted.append((event, props)))

    def impl(*_a, **_k):
        raise _connection_error_while_handling_a_503()
    with llm_emit.track_run():
        with pytest.raises(openai.APIConnectionError) as raised:
            with llm_emit.bind_context(identity=KIMI):
                llm_emit.observe_provider_call(type('P', (), {'base_url': 'https://kimi.fixture.example/v1', 'model_name': 'kimi-k2'})(), impl, 'p')
        found = llm_emit.attribution(raised.value)
    assert (found.get('attribution_source'), found.get('provider')) == ('request', 'kimi'), found
    assert 'http_status' not in found, found
    requests_posted = [props for event, props in posted if event == 'llm_request_finished']
    assert requests_posted and all(props.get('http_status') in (None, 0) for props in requests_posted), requests_posted


def test_i563_the_status_frozen_at_the_transcription_boundary_survives_from_none(cloud_adapter):
    case = cloud_adapter
    case.configure('qwen-audio-3.0-asr-flash', lambda request: httpx.Response(
        503, json={'error': {'message': SECRET_BODY}}, request=request))
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result.get('http_status') == 503, result  # the dict the run_content bridge reads (RC156 Win QA #1)
    assert SECRET_BODY not in json.dumps(result, ensure_ascii=False)


def test_i563_the_log_safe_boundary_freezes_the_status_and_cuts_the_chain():
    from backend.core.llm_telemetry import log_safe_exception
    try:
        try:
            raise ProviderError(f'Error code: 429 {SECRET_BODY}', 429)
        except ProviderError as original:
            raise log_safe_exception(original) from None
    except RuntimeError as safe:
        assert safe.__cause__ is None
        assert http_status_of(safe) == 429
        assert getattr(safe, 'http_status', None) == 429


# --- I567: one classification; boundaries classify inside and raise from None -------------------------

def _recording_factory(monkeypatch, module):
    calls = []
    real = module.build_attribution

    def record(error=None, **kwargs):
        calls.append((error, kwargs))
        return real(error, **kwargs)
    monkeypatch.setattr(module, 'build_attribution', record)
    return calls


def test_i567_the_cover_boundary_lets_the_classifier_decide(monkeypatch):
    from backend.core import image_providers
    calls = _recording_factory(monkeypatch, image_providers)

    @image_providers._image_transport_errors
    def send():
        raise requests.exceptions.ConnectionError(f'HTTPSConnectionPool {SECRET_URL}')
    with pytest.raises(image_providers.ImageError) as raised:
        send()
    (seen, kwargs), = calls
    assert 'sent' not in kwargs, kwargs  # no second judgement path in the factory
    assert classify_failure(seen).kind is FailureKind.MODEL  # THE classifier decides the boundary's view
    assert SECRET_URL not in str(seen) and raised.value.__cause__ is None
    assert raised.value.attribution.attribution_source == 'phase'


def test_i567_the_transcription_boundary_lets_the_classifier_decide(cloud_adapter, monkeypatch):
    from backend.services import cloud_transcription
    calls = _recording_factory(monkeypatch, cloud_transcription)
    case = cloud_adapter

    def reply(request):
        raise httpx.ConnectError(f'private-network-detail {SECRET_URL}', request=request)
    case.configure('qwen-audio-3.0-asr-flash', reply)
    asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert calls, 'the transcription boundary did not build a snapshot'
    for seen, kwargs in calls:
        assert 'sent' not in kwargs, kwargs
        assert classify_failure(seen).kind is FailureKind.MODEL
        assert SECRET_URL not in str(seen)


def test_i567_build_attribution_has_no_sent_override_and_with_request_record_uses_the_factory():
    assert 'sent' not in inspect.signature(failure_attribution.build_attribution).parameters
    source = inspect.getsource(failure_attribution.with_request_record)
    assert '_make(' not in source and 'replace(' not in source
    assert 'replace(' not in inspect.getsource(failure_attribution.build_attribution)


class _Collect:
    """A fake Sentry transport: the envelopes stay in this process (no DSN, nothing is sent)."""
    def __init__(self, options=None):
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)

    def flush(self, *_a, **_k):
        pass

    def kill(self):
        pass

    def is_healthy(self):
        return True

    def record_lost_event(self, *_a, **_k):
        pass


def _envelope_events(error, *, with_product_filter):
    import sentry_sdk
    from sentry_sdk.transport import Transport
    from backend.core import sentry_setup

    class Collect(_Collect, Transport):
        def __init__(self, options=None):
            Transport.__init__(self, options)
            _Collect.__init__(self)
    transport = Collect()
    client = sentry_sdk.Client(dsn='https://public@sentry.invalid/1', transport=transport, default_integrations=False,
                               include_local_variables=False, include_source_context=False,
                               before_send=sentry_setup.before_send if with_product_filter else None)
    with sentry_sdk.isolation_scope() as scope:
        scope.set_client(client)
        scope.capture_exception(error)
    client.flush(timeout=2)
    events = []
    for envelope in transport.envelopes:
        for item in envelope.items:
            if item.type == 'event':
                events.append(json.loads(item.payload.get_bytes()))
    return events


def _boundary_errors():
    from backend.core import image_providers
    from backend.core.llm_telemetry import log_safe_exception

    @image_providers._image_transport_errors
    def cover():
        raise requests.exceptions.ConnectionError(f'HTTPSConnectionPool {SECRET_URL} {SECRET_BODY}')
    out = []
    try:
        cover()
    except image_providers.ImageError as error:
        out.append(error)
    try:
        try:
            raise ProviderError(f'Error code: 503 {SECRET_URL} {SECRET_BODY}', 503)
        except ProviderError as original:
            raise log_safe_exception(original) from None
    except RuntimeError as error:
        out.append(error)
    return out


@pytest.mark.parametrize('with_product_filter', [True, False])
def test_i567_sentry_envelope_of_a_boundary_error_has_no_message_url_or_key_in_any_exception(monkeypatch, with_product_filter):
    """Dong amendment 1: classification inside the boundary, ``from None`` outward. Every exception in the
    envelope, chained ones included, is checked; also with the SDK's raw serialization (no before_send)."""
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    for error in _boundary_errors():
        events = _envelope_events(error, with_product_filter=with_product_filter)
        assert len(events) == 1
        values = events[0]['exception']['values']
        assert len(values) == 1, [v.get('type') for v in values]  # no raw exception chained in
        text = json.dumps(events[0], ensure_ascii=False, default=str)
        # The redacted text keeps only the bare host (the same value base_url_host carries); the product
        # filter omits even that. Never the URL, its path or query, the key, or the provider's body.
        secrets = [SECRET_URL, 'kimi.fixture.example/v1', 'sk-r30-SECRET', SECRET_BODY, 'api_key', 'Error code: 503']
        if with_product_filter:
            secrets.append('kimi.fixture.example')
        for secret in secrets:
            assert secret not in text, (type(error).__name__, secret)
