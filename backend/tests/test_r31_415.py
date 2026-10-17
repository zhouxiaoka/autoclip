"""R31 #415 full head (Dong R30 plan approval + 8f0e155c decisions + mid-review I620-I624, I566 X10).

Each fix test fails on 8f0e155c on an assertion (157/mut415-r30/before-8f0e155c-*.txt); tests marked LOCK
pass on 8f0e155c too and are proven by a targeted mutation instead (mut31.sh / Dong's mut30-dong.sh).
Nothing here imports a symbol that only exists after R31 at module level."""
import asyncio
import json
import socket
from types import SimpleNamespace

import httpx
import openai
import pytest
import requests

from backend.core import failure_attribution, llm_emit
from backend.core.failure_attribution import FailureKind, classify_failure
from backend.core.sentry_setup import studio_error_code
from backend.pipeline.failures import http_status_of
from backend.services.studio import failure_identity, store
from backend.tests.test_r25_415 import GLM, KIMI, _call, _project, isolated  # noqa: F401
from backend.tests.test_cloud_adapter_failure import cloud_adapter  # noqa: F401
from backend.tests.test_r30_415 import VISION, _fail_with_kimi_503, _snap, _unrelated_write_while_handling
from backend.tests.test_studio import client, root, source  # noqa: F401

SECRET_BODY = 'r31-private-provider-body sk-r31-SECRET-0000 /Users/someone/clip.mp4'
WHITELIST = {'provider', 'config_source', 'model', 'base_url_host', 'attribution_source', 'http_status',
             'upstream_error_type', 'failure_stage'}


def _frozen_code(error):
    return getattr(error, 'error_code', None)


# --- I561: a boundary snapshot names the connection THIS call used ------------------------------------

def test_i561_the_transcription_boundary_snapshot_carries_the_asr_connection_identity(cloud_adapter):
    case = cloud_adapter
    case.configure('qwen-audio-3.0-asr-flash', lambda request: httpx.Response(503, json={'error': {'message': SECRET_BODY}}, request=request))
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    found = result['result']['attribution'] if 'attribution' in (result.get('result') or {}) else result.get('attribution') or {}
    assert found.get('attribution_source') == 'phase', result
    assert found.get('provider') and found.get('config_source'), found  # was: no identity at all
    assert found.get('model') == 'qwen-audio-3.0-asr-flash', found
    assert found.get('http_status') == 503 and found.get('failure_stage') == 'subtitle', found


def _cover_call(raise_error, **kwargs):
    from backend.core import image_providers

    @image_providers._image_transport_errors
    def call(**_kwargs):
        raise_error()
    with pytest.raises(image_providers.ImageError) as raised:
        call(**{'provider': 'openai', 'base_url': 'https://api.openai.com/v1', 'model': 'gpt-image-1', **kwargs})
    return raised.value


def test_i561_the_cover_boundary_snapshot_carries_the_image_config_it_sent():
    def boom():
        raise requests.exceptions.ConnectionError(f'HTTPSConnectionPool {SECRET_BODY}')
    error = _cover_call(boom)
    snap = error.attribution
    assert (snap.attribution_source, snap.provider, snap.model, snap.base_url_host) == \
        ('phase', 'openai', 'gpt-image-1', 'api.openai.com'), snap


# --- I562: the controlled code survives the redaction wrap --------------------------------------------

def _openai_timeout():
    return openai.APITimeoutError(request=httpx.Request('POST', 'https://kimi.fixture.example/v1/chat'))


def _openai_connection():
    return openai.APIConnectionError(message='Connection error.', request=httpx.Request('POST', 'https://kimi.fixture.example/v1/chat'))


@pytest.mark.parametrize('make, code', [(_openai_timeout, 'timeout'), (_openai_connection, 'connection')])
def test_i562_log_safe_keeps_timeout_and_connection_apart(make, code):
    from backend.core.llm_telemetry import log_safe_exception
    safe = log_safe_exception(make())
    assert studio_error_code(safe) == code  # was: 'unexpected' for both
    from backend.pipeline.failures import model_call_error_code
    assert model_call_error_code(safe) == code


@pytest.mark.parametrize('reply, code', [
    (lambda request: (_ for _ in ()).throw(httpx.ConnectError('private-network-detail', request=request)), 'connection'),
    (lambda request: (_ for _ in ()).throw(httpx.ReadTimeout('private-network-detail', request=request)), 'timeout'),
], ids=['connect', 'read_timeout'])
def test_i562_cloud_transcription_keeps_timeout_and_connection_apart(cloud_adapter, reply, code):
    case = cloud_adapter
    case.configure('qwen-audio-3.0-asr-flash', reply)
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result['status'] == 'failed'
    assert result['error_code'] == code, result  # was: provider_error for both


def test_i562_lock_undecided_error_freezes_no_snapshot_and_no_code():
    """LOCK (X2): an error the chain cannot decide gets neither a snapshot nor a code at the boundary;
    the call boundary's request record decides it later."""
    from backend.core.llm_telemetry import log_safe_exception
    safe = log_safe_exception(RuntimeError('who knows'))
    assert safe.attribution is None
    assert _frozen_code(safe) is None


# --- Dong 8f0e155c #1: the ASR user text depends only on error_code and status ---------------------------

def test_dong1_cloud_transcription_text_never_carries_upstream_text(cloud_adapter):
    """LOCK. Two 503s with different bodies give the same user text; a body that LOOKS like a key error
    ('invalid api key') never changes the code or hint. Only status and the frozen code decide."""
    from backend.pipeline.failures import cloud_transcription_failure
    from backend.services.cloud_transcription import CloudTranscriptionError
    texts = []
    for body in (SECRET_BODY, 'invalid api key: Incorrect API key provided'):
        case = cloud_adapter
        case.configure('qwen-audio-3.0-asr-flash', lambda request, b=body: httpx.Response(503, text=b, request=request))
        result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
        assert result['error_code'] == 'provider_error', result
        assert body not in json.dumps(result, ensure_ascii=False, default=str)
        texts.append(result['error'])
    assert texts[0] == texts[1] and 'HTTP 503' in texts[0]
    safe = CloudTranscriptionError('云端转写请求失败（HTTP 503），请检查密钥、额度和模型权限。')
    failure_attribution.attributed(safe, None, http_status=503)
    failure = cloud_transcription_failure(str(safe), safe)
    assert failure.code == 'provider_error'
    assert 'invalid api key' not in failure.user_message().lower()


# --- Dong 8f0e155c #2 + I621: the cover status is frozen; HTTP errors are not LOCAL ----------------------

def test_dong2_lock_cover_freezes_the_status_the_library_response_carries():
    """LOCK (D2/D3): requests supplies a real Response; its status is frozen on the safe error AND in the
    snapshot, with the controlled code."""
    response = requests.Response()
    response.status_code = 503
    response._content = SECRET_BODY.encode()

    def boom():
        raise requests.exceptions.HTTPError(SECRET_BODY, response=response)
    error = _cover_call(boom)
    assert error.http_status == 503 and http_status_of(error) == 503
    assert error.attribution.http_status == 503 and error.attribution.attribution_source == 'phase'
    assert classify_failure(error).kind is FailureKind.MODEL
    assert _frozen_code(error) in (None, 'provider_error')
    assert SECRET_BODY not in str(error) and error.__cause__ is None


def test_i621_cover_http_error_status_is_model_with_status_and_no_provider_body():
    from backend.core import image_providers
    resp = SimpleNamespace(status_code=503, json=lambda: {'error': {'message': SECRET_BODY}}, text=SECRET_BODY)
    with pytest.raises(image_providers.ImageError) as raised:
        image_providers._raise_for_status(resp)
    error = raised.value
    assert classify_failure(error).kind is FailureKind.MODEL  # was LOCAL (no snapshot)
    assert http_status_of(error) == 503
    assert error.attribution.http_status == 503 and error.attribution.failure_stage == 'cover'
    assert SECRET_BODY not in str(error) and 'HTTP 503' in str(error)


def test_i621_cover_unsupported_edit_is_still_detected_without_echoing_the_body():
    from backend.core import image_providers
    resp = SimpleNamespace(status_code=400, json=lambda: {'error': {'message': 'edits not supported for this model'}}, text='')
    with pytest.raises(image_providers.ImageError) as raised:
        image_providers._raise_for_status(resp, edit=True)
    assert raised.value.unsupported_edit is True
    assert 'not supported' not in str(raised.value)


def test_i621_a_2xx_that_is_not_an_object_is_an_invalid_model_response():
    from backend.core import image_providers
    resp = SimpleNamespace(status_code=200, json=lambda: [SECRET_BODY], text='')
    with pytest.raises(image_providers.ImageError) as raised:
        image_providers._raise_for_status(resp)
    assert classify_failure(raised.value).kind is FailureKind.MODEL
    assert studio_error_code(raised.value) == 'invalid_response'


# --- I566 X5 / X10: errors raised before anything was sent are LOCAL -----------------------------------

@pytest.mark.parametrize('error', [
    requests.exceptions.InvalidHeader('Invalid leading whitespace in header value'),
    requests.exceptions.InvalidJSONError('Object of type bytes is not JSON serializable'),
    requests.exceptions.URLRequired('no url'),
    requests.exceptions.MissingSchema('no scheme'),       # X5 (LOCK)
    requests.exceptions.InvalidURL('bad url'),            # X5 (LOCK)
], ids=['InvalidHeader', 'InvalidJSONError', 'URLRequired', 'MissingSchema', 'InvalidURL'])
def test_x10_cover_request_never_sent_is_local(error):
    def boom():
        raise error
    safe = _cover_call(boom)
    assert safe.attribution.attribution_source == 'local'
    assert classify_failure(safe).kind is FailureKind.LOCAL
    assert safe.http_status is None and _frozen_code(safe) is None


def test_x10_a_response_that_failed_to_parse_is_the_models_side():
    def boom():
        raise requests.exceptions.JSONDecodeError('Expecting value', 'not json', 0)
    safe = _cover_call(boom)
    assert classify_failure(safe).kind is FailureKind.MODEL
    assert studio_error_code(safe) == 'invalid_response'


# --- I566 X9: a request identity never lands on a LOCAL snapshot ----------------------------------------

def test_x9_lock_request_record_does_not_reidentify_a_local_snapshot():
    from backend.core.failure_attribution import AttributedError, FailureAttribution, attributed, with_request_record

    class Safe(AttributedError, RuntimeError):
        pass
    local = FailureAttribution._make('local', GLM, failure_stage='cover')
    error = attributed(Safe('x'), local)
    record = SimpleNamespace(attribution=lambda: {**KIMI, 'attribution_source': 'request', 'http_status': 503})
    with_request_record(error, record)
    assert error.attribution.attribution_source == 'local'
    assert error.attribution.provider == GLM['provider'] and error.attribution.http_status is None


# --- Dong 8f0e155c #3: Retry-After and DNS kind follow only __cause__ -----------------------------------

class _RateLimited(Exception):
    def __init__(self):
        super().__init__('429')
        self.headers = {'retry-after': '7'}


def test_dong3_retry_after_never_comes_from_an_earlier_unrelated_429():
    from backend.core.llm_retry import retry_after_from_error
    try:
        try:
            raise _RateLimited()
        except _RateLimited:
            raise ConnectionError('new failure')  # noqa: B904 - the implicit context IS the case
    except ConnectionError as error:
        assert isinstance(error.__context__, _RateLimited)
        assert retry_after_from_error(error) is None  # was 7.0


def test_dong3_retry_after_still_follows_an_explicit_cause():
    from backend.core.llm_retry import retry_after_from_error
    try:
        try:
            raise _RateLimited()
        except _RateLimited as original:
            raise RuntimeError('wrapped') from original
    except RuntimeError as error:
        assert retry_after_from_error(error) == 7.0


def test_dong3_network_kind_never_comes_from_an_earlier_dns_failure():
    from backend.core.upstream_errors import network_kind_of
    try:
        try:
            raise socket.gaierror(-2, 'Name or service not known')
        except socket.gaierror:
            raise ConnectionRefusedError('refused')  # noqa: B904
    except ConnectionRefusedError as error:
        assert network_kind_of(error) == ''  # was 'dns'


def test_dong3_network_kind_real_httpx_dns_failure_is_still_dns(monkeypatch):
    """httpx/httpcore attach the gaierror as an explicit cause: the real library still reads as dns."""
    from backend.core.upstream_errors import network_kind_of

    def no_dns(*_a, **_k):
        raise socket.gaierror(-2, 'Name or service not known')
    monkeypatch.setattr(socket, 'getaddrinfo', no_dns)
    with httpx.Client(trust_env=False) as client:
        with pytest.raises(httpx.ConnectError) as raised:
            client.get('https://autoclip-r31.invalid/')
    assert network_kind_of(raised.value) == 'dns'


# --- I568: only the reply's shape is the model's fault --------------------------------------------------

def test_i568_our_own_type_error_in_the_rewrite_route_is_not_invalid_response(client, monkeypatch):
    from backend.api.v1 import studio as studio_api
    from backend.services.studio import intelligence
    draft = client.post('/studio/p1/drafts', json={'clip_ids': ['c1'], 'title': 'Original'}).json()
    seen = []
    monkeypatch.setattr(studio_api, 'capture_studio_exception', lambda error, phase: seen.append(error))
    monkeypatch.setattr(intelligence, 'text_json', lambda *a, **k: {'title': 'T', 'hook': 'H'})

    def broken(*_a, **_k):
        raise TypeError('a bug in our own code')
    monkeypatch.setattr(studio_api, 'Draft', SimpleNamespace(model_validate=broken))
    response = client.post('/studio/p1/rewrite', json={'draft': draft, 'instruction': 'shorter'})
    assert response.status_code == 502
    assert len(seen) == 1 and isinstance(seen[0], TypeError), seen  # was: ModelResponseInvalid
    assert classify_failure(seen[0]).kind is not FailureKind.MODEL
    assert studio_error_code(seen[0]) != 'invalid_response'


def test_i568_a_reply_that_is_not_an_object_is_still_invalid_response(client, monkeypatch):
    from backend.api.v1 import studio as studio_api
    from backend.services.studio import intelligence
    draft = client.post('/studio/p1/drafts', json={'clip_ids': ['c1'], 'title': 'Original'}).json()
    seen = []
    monkeypatch.setattr(studio_api, 'capture_studio_exception', lambda error, phase: seen.append(error))
    monkeypatch.setattr(intelligence, 'text_json', lambda *a, **k: 'just a string')
    assert client.post('/studio/p1/rewrite', json={'draft': draft, 'instruction': 'x'}).status_code == 502
    assert studio_error_code(seen[0]) == 'invalid_response'


# --- I620: a rollback write is not a transition ---------------------------------------------------------

def _refusing_executor(monkeypatch):
    from backend.services.studio import jobs

    class Refusing:
        def submit(self, *_a, **_k):
            raise RuntimeError('executor shut down')
    monkeypatch.setattr(jobs, 'executor', Refusing())


def test_i620_real_inspect_dispatch_rejection_keeps_the_previous_failure_snapshot(monkeypatch):
    from backend.services.studio import jobs, readiness
    _project('p620i', {'status': 'running', 'phase': 'screening', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p620i')
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda *a, **k: None)
    _refusing_executor(monkeypatch)
    options = SimpleNamespace(platforms=['douyin'], branding=SimpleNamespace(model_dump=lambda: {}), auto_start=False,
                              portrait_style=None, html_template=None, recommended_template=None)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        with pytest.raises(ValueError):
            jobs.inspect_project('p620i', options)
    after = store.read('p620i')['analysis']
    assert after.get('run_id') == 'r1'
    assert _snap(after) == before  # was: overwritten with local/glm


def test_i620_real_confirm_dispatch_rejection_writes_the_previous_state_back_unchanged(monkeypatch):
    from backend.services.studio import intelligence, jobs, readiness
    from backend.services.studio.models import ConfirmPlan
    store.directory('p620c').mkdir(parents=True, exist_ok=True)
    store.write('p620c', {'id': 'p620c', 'analysis': {'status': 'awaiting_confirmation', 'run_id': 'r1', 'phase': 'screening'},
                          'plan': {'id': 'plan', 'recommended_analysis': 'visual', 'preferences': {}}}, _recover_previous=False)
    before = store.read('p620c')['analysis']
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda *a, **k: None)
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    _refusing_executor(monkeypatch)
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity({failure_identity.PHASE_KEY: VISION, **GLM})
        with pytest.raises(ValueError):
            jobs.confirm_project('p620c', ConfirmPlan(plan_id='plan', goals=['highlight'], analysis_mode='visual'))
    after = store.read('p620c')['analysis']
    assert after.get('run_id') == 'r1' and after.get('status') == 'awaiting_confirmation'
    assert _snap(after) == _snap(before)  # was: the dispatch error's local/glm identity written onto it


# --- I622: failed -> failed in the same attempt carries the STORED group forward ------------------------

def test_i622_a_writer_that_rebuilds_the_failed_record_keeps_the_stored_snapshot():
    _project('p622', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p622')

    def rebuild(data):
        data['analysis'] = {'status': 'failed', 'phase': 'production', 'run_id': 'r1', 'error_code': 'provider_error'}
    store.change('p622', rebuild)
    assert _snap(store.read('p622')['analysis']) == before  # was: no snapshot at all


def test_i622_lock_same_attempt_error_code_change_keeps_the_snapshot_and_takes_the_new_code():
    """LOCK of the current rule (Dong I622 B/C): the snapshot stays the stored one; error_code is the
    writer's. No inference reconciles them."""
    _project('p622b', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    before = _fail_with_kimi_503('p622b')
    _unrelated_write_while_handling('p622b', RuntimeError('local'), lambda d: d['analysis'].update(error_code='timeout'))
    after = _snap(store.read('p622b')['analysis'])
    assert after == {**before, 'error_code': 'timeout'}


# --- I623: one construction, one valid status range -----------------------------------------------------

def test_i623_cloud_transcription_failure_freezes_the_status_on_itself():
    from backend.pipeline.failures import cloud_transcription_failure
    from backend.services.cloud_transcription import CloudTranscriptionError
    safe = failure_attribution.attributed(CloudTranscriptionError('x'), None, http_status=503)
    failure = cloud_transcription_failure('x', safe)
    assert failure.__cause__ is None
    assert failure.http_status == 503  # was None (only reachable through a caller's ``from e``)


@pytest.mark.parametrize('status', [200, 302, 399, True])
def test_i623_a_non_error_status_is_never_frozen(status):
    from backend.core.failure_attribution import AttributedError, ProviderTransportError, attributed

    class Safe(AttributedError, RuntimeError):
        pass
    assert attributed(Safe('x'), None, http_status=status).http_status is None
    assert ProviderTransportError('HTTPStatus', http_status=status).http_status is None


def test_i623_run_content_freezes_the_adapter_status_through_attributed(monkeypatch, tmp_path):
    """LOCK (mut31 M623-2): run_content freezes through attributed(), so a 302 never lands."""
    from backend.services.studio import jobs
    from backend.tasks import processing
    result = {'success': False, 'error': '内容切片失败', 'result': {'http_status': 302, 'attribution': None}}
    monkeypatch.setattr(processing.process_video_pipeline, 'apply', lambda **_k: SimpleNamespace(get=lambda: result))
    video = tmp_path / 'input.mp4'
    video.write_bytes(b'')
    with pytest.raises(jobs.ContentRunError) as raised:
        jobs.run_content('p623', video)
    assert raised.value.http_status is None  # 302 is not an error status (was frozen by hand: 302)


# --- I624: Dong's D1 / D4 -------------------------------------------------------------------------------

def test_i624_d1_a_generation_failure_of_another_run_replaces_the_snapshot():
    """LOCK, kills Dong D1."""
    store.directory('p624g').mkdir(parents=True, exist_ok=True)
    store.write('p624g', {'id': 'p624g', 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r1', 'instance': store.INSTANCE},
                          'generation': {'status': 'production', 'created_at': '2026-10-17T03:00:00Z'}}, _recover_previous=False)
    _fail_with_kimi_503('p624g', name='generation', finished_at='2026-10-17T03:01:00Z')
    _unrelated_write_while_handling('p624g', RuntimeError('local GLM'),
                                    lambda d: d['generation'].update(status='failed', created_at='2026-10-17T04:00:00Z'))
    generation = store.read('p624g')['generation']
    assert (generation.get('attribution_source'), generation.get('provider'), generation.get('http_status')) == ('local', 'glm', None), generation


def test_i624_d4_a_request_record_fills_its_own_failure_stage():
    """LOCK, kills Dong D4."""
    from backend.core.failure_attribution import AttributedError, FailureAttribution, attributed, with_request_record

    class Safe(AttributedError, RuntimeError):
        pass
    error = attributed(Safe('x'), FailureAttribution._make('phase', None, http_status=503))
    record = SimpleNamespace(attribution=lambda: {**KIMI, 'attribution_source': 'request', 'failure_stage': 'analyze'})
    with_request_record(error, record)
    assert (error.attribution.attribution_source, error.attribution.failure_stage) == ('request', 'analyze')


def test_i562_the_pipeline_code_reader_takes_the_code_the_cover_boundary_froze():
    """model_call_error_code reads the frozen code first: the safe ImageError's own text/type says nothing."""
    from backend.pipeline.failures import model_call_error_code

    def boom():
        raise requests.exceptions.ReadTimeout(f'HTTPSConnectionPool read timed out {SECRET_BODY}')
    error = _cover_call(boom)
    assert model_call_error_code(error) == 'timeout'  # was provider_error
    assert studio_error_code(error) == 'timeout'


def test_x4_lock_the_asr_pipeline_wrapper_carries_the_boundary_snapshot_itself():
    """LOCK (X4): the snapshot rides on the wrapper by THE construction, not via a caller's ``from e``."""
    from backend.core.failure_attribution import FailureAttribution
    from backend.pipeline.failures import cloud_transcription_failure
    from backend.services.cloud_transcription import CloudTranscriptionError
    snap = FailureAttribution._make('phase', {'provider': 'dashscope', 'config_source': 'preset', 'model': 'qwen-audio-3.0-asr-flash'},
                                    http_status=503, failure_stage='subtitle')
    safe = failure_attribution.attributed(CloudTranscriptionError('x'), snap, http_status=503)
    failure = cloud_transcription_failure('x', safe)
    assert failure.__cause__ is None
    assert failure.attribution == snap
    assert classify_failure(failure).kind is FailureKind.MODEL
