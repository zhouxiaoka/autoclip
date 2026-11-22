"""ASR readiness, persisted subtitles and runtime failures agree on usable input."""
import asyncio

import pytest

from backend.core import path_utils
from backend.core.job_budget import JobDurationExceeded
from backend.core.project_cancellation import JobStopped, ProjectDeleted, ServiceRestarted
from backend.pipeline.failures import PipelineFailure
from backend.services import simple_pipeline_adapter as pipeline, simple_progress, whisper_runtime
from backend.services.studio import preflight, readiness, pipeline_resume
from backend.utils import speech_recognizer

SRT = '1\n00:00:00,000 --> 00:01:00,000\n有效的人声字幕。\n'
BAD_SRT = ['', '\n', 'not a subtitle', '1\n00:00:00,000 --> 00:01:00,000\n\n']


@pytest.fixture
def case(tmp_path, monkeypatch):
    video = tmp_path / 'input.mp4'
    video.write_bytes(b'controlled-video')
    srt = tmp_path / 'input.srt'
    calls = []
    monkeypatch.setattr(path_utils, 'get_project_directory', lambda _: tmp_path / 'project')
    monkeypatch.setattr(pipeline, 'clear_progress', lambda *a: None)
    monkeypatch.setattr(pipeline, 'emit_progress', lambda *a, **k: None)
    monkeypatch.setattr(simple_progress, 'emit_progress', lambda *a, **k: None)
    monkeypatch.setattr(pipeline, '_plan_source_window', lambda _: None)
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda: {'status': 'installed'})
    monkeypatch.setattr(preflight, 'probe_material', lambda v: preflight.MaterialProbe(preflight.ProbeState.READABLE, v, 60, True))
    monkeypatch.setattr(preflight, 'snapshot_settings', lambda: preflight.SettingsSnapshot('whisper_local', None, True, 'subtitle', False))
    adapter = pipeline.SimplePipelineAdapter('asr-boundary', 'asr-task')
    monkeypatch.setattr(adapter, '_prompt_files', lambda _: {})
    monkeypatch.setattr(adapter, '_preflight_llm', lambda: calls.append('llm_check'))
    def analyse(path, *_args):
        calls.append(('analyse', path.read_text()))
        raise PipelineFailure('ANALYZE', 'stop after subtitle acceptance', code='fixture_stop')
    monkeypatch.setattr(adapter, '_find_clips_in_one_pass', analyse)
    def transcribe(_video, output_path, **kwargs):
        calls.append('asr')
        output_path.write_text(SRT, encoding='utf-8')
        return output_path
    monkeypatch.setattr(speech_recognizer, 'generate_subtitle_for_video', transcribe)
    return adapter, video, srt, calls


@pytest.mark.parametrize('raw', BAD_SRT)
@pytest.mark.parametrize('resume', [True, False])
def test_unusable_subtitle_is_transcribed_not_reused(case, raw, resume):
    adapter, video, srt, calls = case
    srt.write_text(raw, encoding='utf-8')
    result = asyncio.run(adapter.process_project_sync(str(video), str(srt), clips_only=True, resume=resume))
    assert result['error_code'] == 'fixture_stop'
    assert calls.count('asr') == 1
    assert ('analyse', SRT) in calls
    assert srt.read_text() == raw  # Preserve the imported file; generated output lives in metadata.
    assert not pipeline_resume.srt_reusable(video, srt, None)


@pytest.mark.parametrize('raw', BAD_SRT)
def test_unusable_subtitle_cannot_bypass_missing_asr(case, monkeypatch, raw):
    adapter, video, srt, calls = case
    srt.write_text(raw, encoding='utf-8')
    monkeypatch.setattr(preflight, 'snapshot_settings', lambda: preflight.SettingsSnapshot('whisper_local', 'whisper_not_installed', False, 'subtitle', False))
    monkeypatch.setattr(readiness, 'transcription_check', lambda: {'ok': False, 'code': 'whisper_not_installed'})
    result = asyncio.run(adapter.process_project_sync(str(video), str(srt), clips_only=True))
    assert result['error_code'] == 'whisper_not_installed'
    assert calls == []


def test_valid_numeric_cue_is_preserved_without_transcription(case):
    adapter, video, srt, calls = case
    srt.write_text(SRT.replace('有效的人声字幕。', '123'), encoding='utf-8')
    result = asyncio.run(adapter.process_project_sync(str(video), str(srt), clips_only=True))
    assert result['error_code'] == 'fixture_stop'
    assert 'asr' not in calls


def test_unexpected_asr_error_is_not_reported_as_silent_source(case, monkeypatch):
    adapter, video, srt, calls = case
    def broken(*a, **k):
        raise RuntimeError('private runtime details')
    monkeypatch.setattr(speech_recognizer, 'generate_subtitle_for_video', broken)
    result = asyncio.run(adapter.process_project_sync(str(video), '', clips_only=True))
    assert result['error_code'] == 'subtitle_setup'
    assert result['stage'] == 'SUBTITLE'
    assert 'private runtime details' not in result['error']
    assert not any(isinstance(c, tuple) for c in calls)


@pytest.mark.parametrize('error', [ProjectDeleted(), JobStopped(), ServiceRestarted(), JobDurationExceeded()])
def test_transcription_preserves_stop_signals(case, monkeypatch, tmp_path, error):
    adapter, video, srt, calls = case
    def stopped(*a, **k):
        raise error
    monkeypatch.setattr(speech_recognizer, 'generate_subtitle_for_video', stopped)
    with pytest.raises(type(error)) as caught:
        asyncio.run(adapter._generate_subtitle_automatically(str(video), tmp_path))
    assert caught.value is error


def test_empty_generated_subtitle_is_not_accepted_or_stamped(case, monkeypatch, tmp_path):
    adapter, video, srt, calls = case
    def empty(_video, output_path, **kwargs):
        output_path.write_text('\n')
        return output_path
    monkeypatch.setattr(speech_recognizer, 'generate_subtitle_for_video', empty)
    stamps = []
    monkeypatch.setattr(pipeline_resume, 'write_stamp', lambda *a, **k: stamps.append(1))
    result = asyncio.run(adapter.process_project_sync(str(video), '', clips_only=True))
    assert result['error_code'] == 'transcription_empty'
    assert result['stage'] == 'SUBTITLE'
    assert not stamps
    assert not any(isinstance(c, tuple) for c in calls)
