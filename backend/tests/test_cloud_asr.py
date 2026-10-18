"""Behavior tests for cloud ASR failure attribution."""
import httpx
import pytest

from backend.core.sentry_setup import studio_error_code, studio_failure_context
from backend.pipeline.failures import cloud_transcription_failure
from backend.services.cloud_transcription import CloudTranscriptionError
from backend.services.studio import jobs
"""R18 80/81: cloud ASR HTTP errors keep status + upstream_error_type; history keeps stage/upstream."""


@pytest.mark.parametrize('status,upstream,code', [
    (401, 'invalid_key', 'llm_auth_invalid'),
    (403, 'permission_denied', 'llm_auth_invalid'),
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
    assert failure.code == 'llm_auth_invalid'
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




def _real_store_jobs(monkeypatch, state, tmp_path):
    """R20 #110: the REAL studio store (atomic write to metadata/studio.json + analysis_history summaries)."""
    from backend.services.studio import store
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    store.directory('p').mkdir(parents=True, exist_ok=True)
    state['analysis']['instance'] = store.INSTANCE  # a live run of this process (not a restart leftover)
    store.write('p', {'drafts': [], 'events': [], 'jobs': [], 'output_variants': [], **state})
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    video = tmp_path / 'input.mp4'; video.write_bytes(b'0')
    monkeypatch.setattr(jobs, 'source', lambda pid: video)
    return store


def _on_disk(store):
    import json
    return json.loads((store.directory('p') / 'metadata' / 'studio.json').read_text(encoding='utf-8'))


def _assert_history_row(data, run_id):
    rows = [r for r in data['analysis_history'] if r['run_id'] == run_id]
    assert len(rows) == 1, data['analysis_history']
    assert rows[0]['analysis']['status'] == 'failed' and rows[0]['analysis']['error_code'] == 'llm_auth_invalid'
    # R22 110: the history row itself (what 107/the observer reads for an older run) keeps the context
    row = rows[0]['analysis']
    assert (row.get('failure_stage'), row.get('http_status'), row.get('upstream_error_type')) == ('subtitle', 401, 'invalid_key'), row


def _asr_401():
    return cloud_transcription_failure(CloudTranscriptionError('HTTP 401', http_status=401))


def test_screening_failure_history_keeps_stage_status_upstream(monkeypatch, tmp_path):
    """R19 #110 (behavior): a real _inspect failure writes stage/status/upstream into analysis history."""
    store = _real_store_jobs(monkeypatch, {'analysis': {'status': 'running', 'phase': 'screening', 'run_id': 'run-s'}, 'generation': {}}, tmp_path)
    import backend.services.studio.planning as planning
    def boom(*a, **k):
        raise _asr_401()
    monkeypatch.setattr(planning, 'recommend', boom)
    from backend.services.studio.models import ImportOptions
    jobs._inspect('p', ImportOptions(), None, None)
    data = _on_disk(store)
    a = data['analysis']
    _assert_history_row(data, 'run-s')
    assert a['status'] == 'failed' and a['error_code'] == 'llm_auth_invalid'
    assert (a['failure_stage'], a['http_status'], a['upstream_error_type']) == ('subtitle', 401, 'invalid_key')
    assert 'secret' not in str(a)


@pytest.mark.parametrize('goals', [['content'], ['content', 'highlight']])
def test_manual_produce_selected_failure_keeps_stage_status_upstream(monkeypatch, tmp_path, goals):
    """R19 #106: manual-mode _produce_selected persists the context so 「去设置」 can point at speech."""
    store = _real_store_jobs(monkeypatch, {'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run-p'}}, tmp_path)
    def fail(*a, **k):
        raise _asr_401()
    monkeypatch.setattr(jobs, 'run_content', fail)
    jobs._produce_selected('p', {'selected_goals': goals, 'confirmed_preferences': {}, 'confirmed_analysis': 'subtitle'})
    data = _on_disk(store)
    a = data['analysis']
    _assert_history_row(data, 'run-p')
    assert a['status'] == 'failed' and a['error_code'] == 'llm_auth_invalid'
    assert (a['failure_stage'], a['http_status'], a['upstream_error_type']) == ('subtitle', 401, 'invalid_key')


@pytest.mark.parametrize('where', ['source', 'mark_project'])
def test_r20_126_produce_selected_outer_exception_keeps_stage_status_upstream(monkeypatch, tmp_path, where):
    """R20 #126: an error outside the per-goal loop (source lookup / project marking) takes the outer branch;
    it must persist the same context, so manual-mode 「去设置」 still points at speech."""
    store = _real_store_jobs(monkeypatch, {'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run-o'}}, tmp_path)
    calls = []
    def boom(*a, **k):
        calls.append(a)
        if len(calls) == 1:  # first call fails; the outer branch's own mark_project('failed') still works
            raise _asr_401()
        return None
    monkeypatch.setattr(jobs, where, boom)
    monkeypatch.setattr(jobs, 'run_content', lambda *a, **k: pytest.fail('outer failure must stop before the goal loop'))
    jobs._produce_selected('p', {'selected_goals': ['content'], 'confirmed_preferences': {}, 'confirmed_analysis': 'subtitle'})
    data = _on_disk(store)
    a = data['analysis']
    assert a['status'] == 'failed' and a['outcome'] == 'failed' and a['error_code'] == 'llm_auth_invalid'
    assert a['failed_goals'] == ['content'] and a['succeeded_goals'] == []
    assert (a['failure_stage'], a['http_status'], a['upstream_error_type']) == ('subtitle', 401, 'invalid_key')
    _assert_history_row(data, 'run-o')


def test_r20_126_outer_exception_without_upstream_keeps_production_stage(monkeypatch, tmp_path):
    store = _real_store_jobs(monkeypatch, {'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run-x'}}, tmp_path)
    def missing(pid):
        raise FileNotFoundError('源视频不存在')
    monkeypatch.setattr(jobs, 'source', missing)
    jobs._produce_selected('p', {'selected_goals': ['content'], 'confirmed_preferences': {}, 'confirmed_analysis': 'subtitle'})
    a = _on_disk(store)['analysis']
    assert a['status'] == 'failed' and a.get('failure_stage') == 'production'
    assert 'http_status' not in a and 'upstream_error_type' not in a
