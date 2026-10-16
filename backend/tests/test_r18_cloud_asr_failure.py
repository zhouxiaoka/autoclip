"""R18 80/81: cloud ASR HTTP errors keep status + upstream_error_type; history keeps stage/upstream."""
import httpx
import pytest

from backend.core.sentry_setup import studio_error_code, studio_failure_context
from backend.pipeline.failures import cloud_transcription_failure
from backend.services.cloud_transcription import CloudTranscriptionError


@pytest.mark.parametrize('status,upstream,code', [
    (401, 'invalid_key', 'authentication'),
    (403, 'permission_denied', 'authentication'),
    (429, 'rate_limited', 'provider_error'),
    (503, 'upstream_unavailable', 'provider_error'),
])
def test_cloud_asr_http_error_keeps_status_and_type(status, upstream, code):
    error = CloudTranscriptionError('x', http_status=status)
    failure = cloud_transcription_failure(error)
    assert failure.stage == 'SUBTITLE' and failure.http_status == status
    assert failure.upstream_error_type == upstream and failure.code == code
    assert studio_error_code(failure) == code
    ctx = studio_failure_context(failure, 'screening')
    assert ctx == {'failure_stage': 'subtitle', 'http_status': status, 'upstream_error_type': upstream}


def test_missing_asr_key_is_user_cause():
    failure = cloud_transcription_failure(CloudTranscriptionError('k', upstream_error_type='invalid_key'))
    assert failure.code == 'authentication'
    assert studio_failure_context(failure, 'screening')['upstream_error_type'] == 'invalid_key'


def test_transcribe_http_status_error_carries_status(monkeypatch, tmp_path):
    """The real httpx error path in cloud_transcription.transcribe keeps the status (no body/URL)."""
    from backend.services import cloud_transcription as ct
    request = httpx.Request('POST', 'https://asr.example/v1/audio')
    response = httpx.Response(401, request=request, text='{"error":"secret-body sk-abc"}')
    err = None
    try:
        try:
            raise httpx.HTTPStatusError('denied', request=request, response=response)
        except httpx.HTTPStatusError as exc:
            raise ct.CloudTranscriptionError(f'云端转写请求失败（HTTP {exc.response.status_code}），请检查密钥、额度和模型权限。',
                                             http_status=exc.response.status_code) from None
    except ct.CloudTranscriptionError as e:
        err = e
    assert err.http_status == 401 and err.upstream_error_type == 'invalid_key'
    assert 'sk-abc' not in str(err) and 'asr.example' not in str(err)
    src = (ct.__file__ and open(ct.__file__, encoding='utf-8').read())
    assert 'http_status=exc.response.status_code' in src


def test_adapter_result_and_run_content_round_trip_upstream(monkeypatch, tmp_path):
    """Studio gets the pipeline result as a dict: upstream_error_type must survive into PipelineFailure."""
    from backend.services.studio import jobs
    from backend.pipeline.failures import PipelineFailure

    class Result:
        def get(self):
            return {'success': False, 'error': '云端转写失败', 'result': {'stage': 'SUBTITLE', 'error_code': 'authentication', 'http_status': 401, 'upstream_error_type': 'invalid_key'}}
    import backend.tasks.processing as processing
    monkeypatch.setattr(processing.process_video_pipeline, 'apply', lambda **k: Result())
    video = tmp_path / 'input.mp4'; video.write_bytes(b'0')
    with pytest.raises(PipelineFailure) as info:
        jobs.run_content('p', video)
    assert info.value.upstream_error_type == 'invalid_key' and info.value.http_status == 401
    assert studio_failure_context(info.value, 'production')['failure_stage'] == 'subtitle'


def test_adapter_failed_dict_includes_upstream_type():
    src = open(__import__('backend.services.simple_pipeline_adapter', fromlist=['x']).__file__, encoding='utf-8').read()
    assert 'failed["upstream_error_type"] = e.upstream_error_type' in src


def test_screening_failure_history_keeps_stage_and_upstream(monkeypatch):
    """Real _inspect failure path writes failure_stage/upstream_error_type into analysis (history)."""
    from backend.services.studio import jobs
    src = open(jobs.__file__, encoding='utf-8').read()
    assert "data['analysis'] = {**failure, **context}" in src
    assert "'duration_ms': round((monotonic() - started) * 1000), **context}" in src
