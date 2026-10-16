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


def test_missing_asr_key_real_transcribe_path_is_user_cause(tmp_path):
    """R19 #109: real cloud_transcription.transcribe with an empty key; dropping the invalid_key tag must fail this."""
    from backend.services import ai_model_settings as ai
    from backend.services import cloud_transcription as ct
    settings = ai.ModelSettings(connections=[ai.Connection(id='asr', name='ASR', provider='openai', api_key='')],
                                transcription=ai.Transcription(provider='cloud', model='whisper-1', connection_id='asr'))
    video = tmp_path / 'v.mp4'; video.write_bytes(b'0')
    with pytest.raises(CloudTranscriptionError) as info:
        ct.transcribe(video, None, settings)
    assert info.value.upstream_error_type == 'invalid_key' and info.value.http_status is None
    failure = cloud_transcription_failure(info.value)
    assert failure.code == 'authentication'
    assert studio_failure_context(failure, 'screening') == {'failure_stage': 'subtitle', 'upstream_error_type': 'invalid_key'}


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




class _Store:
    def __init__(self, state):
        self.state = state

    def change(self, pid, fn):
        return fn(self.state)

    def read(self, pid, **k):
        return self.state


def _fake_jobs(monkeypatch, state, tmp_path):
    from backend.services.studio import jobs
    fake = _Store(state)
    monkeypatch.setattr(jobs.store, 'change', fake.change)
    monkeypatch.setattr(jobs.store, 'read', fake.read)
    monkeypatch.setattr(jobs.store, 'raise_owned_read_error', lambda e: None)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    video = tmp_path / 'input.mp4'; video.write_bytes(b'0')
    monkeypatch.setattr(jobs, 'source', lambda pid: video)
    return jobs


def _asr_401():
    return cloud_transcription_failure(CloudTranscriptionError('HTTP 401', http_status=401))


def test_screening_failure_history_keeps_stage_status_upstream(monkeypatch, tmp_path):
    """R19 #110 (behavior): a real _inspect failure writes stage/status/upstream into analysis history."""
    state = {'analysis': {'status': 'running', 'phase': 'screening'}, 'generation': {}}
    jobs = _fake_jobs(monkeypatch, state, tmp_path)
    import backend.services.studio.planning as planning
    def boom(*a, **k):
        raise _asr_401()
    monkeypatch.setattr(planning, 'recommend', boom)
    from backend.services.studio.models import ImportOptions
    jobs._inspect('p', ImportOptions(), None, None)
    a = state['analysis']
    assert a['status'] == 'failed' and a['error_code'] == 'authentication'
    assert (a['failure_stage'], a['http_status'], a['upstream_error_type']) == ('subtitle', 401, 'invalid_key')
    assert 'secret' not in str(a)


@pytest.mark.parametrize('goals', [['content'], ['content', 'highlight']])
def test_manual_produce_selected_failure_keeps_stage_status_upstream(monkeypatch, tmp_path, goals):
    """R19 #106: manual-mode _produce_selected persists the context so 「去设置」 can point at speech."""
    state = {'analysis': {'status': 'running', 'phase': 'production'}, 'drafts': []}
    jobs = _fake_jobs(monkeypatch, state, tmp_path)
    def fail(*a, **k):
        raise _asr_401()
    monkeypatch.setattr(jobs, 'run_content', fail)
    jobs._produce_selected('p', {'selected_goals': goals, 'confirmed_preferences': {}, 'confirmed_analysis': 'subtitle'})
    a = state['analysis']
    assert a['status'] == 'failed' and a['error_code'] == 'authentication'
    assert (a['failure_stage'], a['http_status'], a['upstream_error_type']) == ('subtitle', 401, 'invalid_key')
