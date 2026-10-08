"""RC156 Win QA #10 / #11: sources the subtitle route cannot use fail before any model call.

#10: a 10 s talk video spent 5 LLM calls (screening, clip finding, outline, timeline) and then
     failed with timeline_empty after 108 s.
#11: a video without an audio track went down the subtitle route; local Whisper raised
     IndexError and the UI showed "本地 Whisper 生成字幕失败（IndexError）…" with subtitle_setup.
"""
import asyncio
import shutil
import subprocess

import pytest

from backend.pipeline import media_precheck
from backend.pipeline.failures import PipelineFailure, failure_from_speech_error
from backend.pipeline.quality import profile_for
from backend.services.studio import analysis_preferences, intelligence, jobs, planning, store
from backend.services.studio.models import ConfirmPlan, ImportOptions
from backend.tests.test_studio import root, source, client  # noqa: F401  (fixtures)


def _video(path, seconds, audio=True):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=s=64x36:r=5:d={seconds}']
    if audio:
        cmd += ['-f', 'lavfi', '-i', f'sine=f=440:d={seconds}', '-shortest']
    subprocess.run(cmd + ['-y', str(path)], check=True)
    return path


class Immediate:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


def _preferences(monkeypatch, mode='auto', screening=True):
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences(
        analysis_mode=mode, allow_visual_screening=screening))


def _no_model_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('no model call is allowed for this source')
    monkeypatch.setattr(intelligence, 'vision_call', forbidden)
    monkeypatch.setattr(intelligence, 'sample', forbidden)


# ---------------------------------------------------------------- probe ---

def test_probe_tells_audio_and_duration_and_never_guesses(tmp_path):
    with_audio = _video(tmp_path / 'a.mp4', 2)
    silent = _video(tmp_path / 's.mp4', 2, audio=False)
    assert media_precheck.probe(with_audio)['audio'] is True
    info = media_precheck.probe(silent)
    assert info['audio'] is False and 1.5 < info['duration'] < 2.5
    # Unreadable input is "unknown", never "no audio".
    assert media_precheck.probe(tmp_path / 'missing.mp4') == {'duration': None, 'audio': None}
    (tmp_path / 'junk.mp4').write_bytes(b'not a video')
    assert media_precheck.probe(tmp_path / 'junk.mp4')['audio'] is None


def test_minimum_sentence_matches_the_short_profile():
    # Every source shorter than its minimum is in the short tier, so the fixed sentence holds.
    assert profile_for(19.9).min_clip_sec == media_precheck.SUBTITLE_MIN_SOURCE_SEC == 20
    assert '20 秒' in media_precheck.TOO_SHORT_MESSAGE
    assert media_precheck.too_short(10.05) and not media_precheck.too_short(20.0)
    assert not media_precheck.too_short(None) and not media_precheck.too_short(0)


def test_subtitle_route_failure_codes(tmp_path):
    short = _video(tmp_path / 'short.mp4', 3)
    silent = _video(tmp_path / 'silent.mp4', 21, audio=False)
    failure = media_precheck.subtitle_route_failure(short, srt_available=True)
    assert failure.code == 'source_too_short' and failure.stage == 'INGEST'
    assert str(failure) == media_precheck.TOO_SHORT_MESSAGE and failure.hint == ''
    failure = media_precheck.subtitle_route_failure(silent, srt_available=False)
    assert failure.code == 'source_no_audio' and str(failure) == media_precheck.NO_AUDIO_MESSAGE
    # An attached SRT replaces transcription: no audio is fine then.
    assert media_precheck.subtitle_route_failure(silent, srt_available=True) is None
    assert media_precheck.subtitle_route_failure(tmp_path / 'missing.mp4', srt_available=False) is None


# ---------------------------------------------------------- screening ---

def test_short_source_is_blocked_before_screening_even_with_vision(tmp_path, monkeypatch):
    video = _video(tmp_path / 'raw' / 'input.mp4', 3)
    _preferences(monkeypatch)
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, '_probe', lambda v: {'duration': 10.05, 'width': 960, 'height': 540})
    _no_model_calls(monkeypatch)
    with pytest.raises(PipelineFailure) as caught:
        planning.recommend(video, ImportOptions(auto_start=True))
    assert caught.value.code == 'source_too_short'
    with pytest.raises(PipelineFailure):
        planning.recommend(video, ImportOptions(auto_start=True, goal='content'))


def test_silent_source_without_visual_route_is_blocked_before_screening(tmp_path, monkeypatch):
    video = _video(tmp_path / 'raw' / 'input.mp4', 2, audio=False)
    monkeypatch.setattr(intelligence, '_probe', lambda v: {'duration': 45.0})
    _no_model_calls(monkeypatch)
    for mode, ready, goal in (('subtitle', True, 'auto'), ('auto', False, 'auto'), ('auto', True, 'content')):
        _preferences(monkeypatch, mode, mode != 'subtitle')
        monkeypatch.setattr(intelligence, 'ready', lambda ready=ready: ready)
        with pytest.raises(PipelineFailure) as caught:
            planning.recommend(video, ImportOptions(auto_start=True, goal=goal))
        assert caught.value.code == 'source_no_audio', (mode, ready, goal)
        assert '设置 → 转写' not in caught.value.user_message()


def test_silent_source_with_srt_keeps_the_subtitle_route(tmp_path, monkeypatch):
    video = _video(tmp_path / 'raw' / 'input.mp4', 2, audio=False)
    (video.parent / 'input.srt').write_text('1\n00:00:00,000 --> 00:00:30,000\n你好\n', encoding='utf-8')
    _preferences(monkeypatch, 'subtitle', False)
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    monkeypatch.setattr(intelligence, '_probe', lambda v: {'duration': 45.0})
    plan = planning.recommend(video, ImportOptions(auto_start=True))
    assert plan['recommended_analysis'] == 'subtitle'


def test_silent_source_goes_visual_when_screening_picks_a_visual_goal(tmp_path, monkeypatch):
    video = _video(tmp_path / 'raw' / 'input.mp4', 2, audio=False)
    _preferences(monkeypatch)
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, '_probe', lambda v: {'duration': 45.0, 'width': 64, 'height': 36})
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **k: [])
    prompts = []
    answer = {'goal': 'highlight'}
    def vision_call(content, config=None):
        prompts.append(content[0]['text'])
        return {'content_type': 'gameplay', 'goal': answer['goal'], 'reason': '画面', 'confidence': .8,
                'suggested_goals': ['highlight', 'content']}
    monkeypatch.setattr(intelligence, 'vision_call', vision_call)
    plan = planning.recommend(video, ImportOptions(auto_start=True))
    assert plan['recommended_analysis'] == 'visual' and 'content' not in plan['suggested_goals']
    assert '没有音轨' in prompts[0]
    # Screening still chose the subtitle route: fail with the after-screening sentence.
    answer['goal'] = 'content'
    with pytest.raises(PipelineFailure) as caught:
        planning.recommend(video, ImportOptions(auto_start=True))
    assert caught.value.code == 'source_no_audio'
    assert str(caught.value) == media_precheck.NO_AUDIO_AFTER_SCREENING_MESSAGE


def test_import_of_a_short_video_fails_fast_with_a_translated_unreported_code(client, monkeypatch):
    from backend.core import sentry_setup
    short = _video(store.directory('p1').parent / 'upload' / 'short.mp4', 10)
    _preferences(monkeypatch)
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    _no_model_calls(monkeypatch)
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(jobs, 'run_content', lambda *a: pytest.fail('content pipeline must not start'))
    reported = []
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda error, phase, **kw: reported.append(
        sentry_setup.studio_error_code(error)))
    response = client.post('/studio/import', data={'auto_start': 'true'},
                           files={'video': ('short.mp4', short.read_bytes(), 'video/mp4')})
    assert response.status_code == 200, response.text
    state = store.read(response.json()['project_id'])
    assert state['analysis']['status'] == 'failed'
    assert state['analysis']['error_code'] == 'source_too_short'
    assert state['analysis']['error'] == media_precheck.TOO_SHORT_MESSAGE
    generation = state['generation']
    assert generation['status'] == 'failed' and generation['error_code'] == 'source_too_short'
    assert generation['failure_stage'] == 'ingest'
    assert reported == ['source_too_short']  # handed to the reporter, which drops it (below)


def test_import_of_a_silent_video_without_vision_fails_fast(client, monkeypatch):
    silent = _video(store.directory('p1').parent / 'upload' / 'silent.mp4', 21, audio=False)
    _preferences(monkeypatch, 'subtitle', False)
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    _no_model_calls(monkeypatch)
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(jobs, 'run_content', lambda *a: pytest.fail('content pipeline must not start'))
    response = client.post('/studio/import', data={'auto_start': 'true'},
                           files={'video': ('silent.mp4', silent.read_bytes(), 'video/mp4')})
    assert response.status_code == 200, response.text
    state = store.read(response.json()['project_id'])
    assert state['analysis']['error_code'] == 'source_no_audio'
    assert state['analysis']['error'] == media_precheck.NO_AUDIO_MESSAGE
    assert 'IndexError' not in state['analysis']['error']


def test_confirm_refuses_the_subtitle_route_for_a_short_source(client, monkeypatch):
    # The review flow (auto_start=false) keeps the visual route open; confirming subtitles is refused.
    short = _video(store.directory('p1').parent / 'upload' / 'short.mp4', 10)
    _preferences(monkeypatch)
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **k: [])
    monkeypatch.setattr(intelligence, 'vision_call', lambda content, config=None: {
        'content_type': 'talk', 'goal': 'content', 'reason': '口播', 'confidence': .7})
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(jobs, 'run_content', lambda *a: pytest.fail('content pipeline must not start'))
    response = client.post('/studio/import', files={'video': ('short.mp4', short.read_bytes(), 'video/mp4')})
    pid = response.json()['project_id']
    state = store.read(pid)
    assert state['analysis']['status'] == 'awaiting_confirmation'
    assert 'content' not in state['plan']['suggested_goals']
    plan_id = state['plan']['id']
    with pytest.raises(ValueError) as caught:
        jobs.confirm_project(pid, ConfirmPlan(plan_id=plan_id, goals=['content'], analysis_mode='subtitle'))
    assert str(caught.value) == media_precheck.TOO_SHORT_MESSAGE
    assert store.read(pid)['analysis']['status'] == 'awaiting_confirmation'


# ------------------------------------------------------------ pipeline ---

def test_content_pipeline_stops_before_llm_and_transcription(tmp_path, monkeypatch):
    from backend.services import simple_pipeline_adapter as adapter_module
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    adapter = adapter_module.SimplePipelineAdapter('p-pre', 't-pre')
    monkeypatch.setattr(adapter, '_preflight_llm', lambda: pytest.fail('no LLM preflight for this source'))
    async def no_transcription(*args, **kwargs):
        pytest.fail('no transcription for this source')
    monkeypatch.setattr(adapter, '_generate_subtitle_automatically', no_transcription)
    silent = _video(tmp_path / 'silent.mp4', 21, audio=False)
    result = asyncio.run(adapter.process_project_sync(str(silent), None, clips_only=True))
    assert result['status'] == 'failed' and result['error_code'] == 'source_no_audio'
    assert result['error'] == media_precheck.NO_AUDIO_MESSAGE and result['stage'] == 'INGEST'
    short = _video(tmp_path / 'short.mp4', 3)
    srt = tmp_path / 'short.srt'
    srt.write_text('1\n00:00:00,000 --> 00:00:03,000\n你好\n', encoding='utf-8')
    result = asyncio.run(adapter.process_project_sync(str(short), str(srt), clips_only=True))
    assert result['error_code'] == 'source_too_short' and result['error'] == media_precheck.TOO_SHORT_MESSAGE


def test_transcription_refuses_a_silent_video_before_any_provider(tmp_path, monkeypatch):
    from backend.utils import speech_recognizer
    silent = _video(tmp_path / 'silent.mp4', 2, audio=False)
    monkeypatch.setattr(speech_recognizer, 'SpeechRecognizer', lambda *a, **k: pytest.fail('no provider call'))
    with pytest.raises(speech_recognizer.SpeechRecognitionError) as caught:
        speech_recognizer.generate_subtitle_for_video(silent)
    assert str(caught.value) == media_precheck.NO_AUDIO_MESSAGE
    failure = failure_from_speech_error(str(caught.value))
    assert failure.code == 'source_no_audio' and failure.hint == ''
    assert '设置 → 转写' not in failure.user_message()


def test_whisper_failure_text_never_names_the_exception():
    from backend.utils.speech_recognizer import describe_whisper_failure
    message = describe_whisper_failure(IndexError('tuple index out of range'))
    assert 'IndexError' not in message and 'tuple index' not in message
    assert '本地 Whisper 生成字幕失败。' in message


# --------------------------------------------------------------- sentry ---

@pytest.mark.parametrize('code', ['source_too_short', 'source_no_audio'])
def test_source_input_failures_are_classified_and_never_sent(monkeypatch, tmp_path, code):
    import sentry_sdk
    from backend.core import sentry_setup
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    error = PipelineFailure('INGEST', 'x', code=code)
    assert code in sentry_setup.STUDIO_ERROR_CODES and code in sentry_setup.UNREPORTED_STUDIO_ERROR_CODES
    assert sentry_setup.studio_error_code(error) == code
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    sent = []
    monkeypatch.setattr(sentry_sdk, 'capture_exception', lambda e: sent.append(e) or 'event-id')
    assert sentry_setup.capture_studio_exception(error, 'screening') is None and sent == []
    event = {'exception': {'values': [{'type': 'PipelineFailure', 'value': 'x'}]},
             'tags': {'area': 'studio', 'phase': 'screening', 'error_code': code}}
    assert sentry_setup.before_send(event) is None


def test_legacy_source_input_import_failures_are_never_sent(monkeypatch, tmp_path):
    from backend.core import sentry_setup
    from backend.tasks.import_processing import ImportSourceUnusable
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    error = ImportSourceUnusable('x')
    event = {'exception': {'values': [{'type': 'ImportSourceUnusable', 'value': 'x'}]}}
    assert sentry_setup.before_send(event, {'exc_info': (type(error), error, None)}) is None
    assert sentry_setup.before_send(event) is None
