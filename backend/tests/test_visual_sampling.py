"""Real low-frame-rate seeks and failed screening must not invent speech output."""
import subprocess
from pathlib import Path

import pytest

from backend.tests.test_studio import root, source, client
from backend.services.studio import analysis_preferences, intelligence, jobs, planning
from backend.services.studio.models import ImportOptions
from backend.utils.ffmpeg_utils import get_ffmpeg_path


def make_video(tmp_path, fps=8, *, audio_duration=None):
    video = tmp_path / '低帧率 游戏.mp4'
    command = [get_ffmpeg_path(), '-v', 'error', '-threads', '1', '-f', 'lavfi', '-i',
               f'testsrc2=size=160x90:rate={fps}:duration=2']
    if audio_duration:
        command += ['-f', 'lavfi', '-i', f'sine=frequency=440:duration={audio_duration}']
    subprocess.run([*command, '-threads', '1', '-filter_threads', '1', '-y', str(video)],
                   check=True, capture_output=True, timeout=30)
    return video


@pytest.mark.parametrize('fps', [1, 8, 30])
def test_screening_reads_the_last_sample_of_low_fps_video(tmp_path, fps):
    video = make_video(tmp_path, fps)
    folder = tmp_path / 'frames'
    folder.mkdir()
    times = [round(1.9 * i / 3, 3) for i in range(4)]
    content = intelligence.sample(video, times, folder, width=160)
    assert sum(item['type'] == 'image_url' for item in content) == 4
    assert len(list(folder.glob('*.jpg'))) == 4
    actual_times = [float(item['text'].split()[1]) for item in content if item['type'] == 'text']
    assert max(actual_times) <= 2 - 1 / fps


def test_audio_tail_does_not_define_video_sampling_bounds(tmp_path):
    video = make_video(tmp_path, audio_duration=3)
    folder = tmp_path / 'frames'
    folder.mkdir()
    content = intelligence.sample(video, [0, 1, 2, 2.9], folder, width=160)
    actual_times = [float(item['text'].split()[1]) for item in content if item['type'] == 'text']
    assert max(actual_times) <= 1.875
    assert len([item for item in content if item['type'] == 'image_url']) == 4


@pytest.mark.parametrize('failure', ['once', 'persistent', 'timeout'])
def test_tail_recovery_is_bounded_and_never_sends_a_partial_or_stale_set(tmp_path, monkeypatch, failure):
    video = make_video(tmp_path)
    folder = tmp_path / 'frames'
    folder.mkdir()
    real_run = subprocess.run
    tail_seeks = []
    def run(command, **kwargs):
        if command[-1] == str(folder / '3.jpg'):
            tail_seeks.append(float(command[command.index('-ss') + 1]))
            if failure == 'timeout':
                raise subprocess.TimeoutExpired(command, 30)
            if failure == 'persistent' or len(tail_seeks) == 1:
                (folder / '3.jpg').write_bytes(b'stale-invalid-frame')
                raise subprocess.CalledProcessError(1, command, stderr=b'private-video-path')
        return real_run(command, **kwargs)
    monkeypatch.setattr(intelligence.subprocess, 'run', run)
    if failure == 'once':
        content = intelligence.sample(video, [0, .5, 1, 1.9], folder, width=160)
        assert len(tail_seeks) == 2 and tail_seeks[1] < tail_seeks[0]
        assert content[-2]['text'] == f'原片时间 {tail_seeks[1]:.2f} 秒'
        assert (folder / '3.jpg').read_bytes().startswith(b'\xff\xd8')
        assert sum(item['type'] == 'image_url' for item in content) == 4
    else:
        with pytest.raises(intelligence.VisionRequestError) as caught:
            intelligence.sample(video, [0, .5, 1, 1.9], folder, width=160)
        assert caught.value.code == ('timeout' if failure == 'timeout' else 'missing_resource')
        assert len(tail_seeks) == (1 if failure == 'timeout' else 2)
        assert 'private-' not in str(caught.value)
        assert not (folder / '3.jpg').exists()


@pytest.mark.parametrize('error', [
    subprocess.CalledProcessError(1, ['ffmpeg', 'private-input']),
    intelligence.VisionRequestError('provider_error', '视觉模型请求失败', http_status=500),
    intelligence.VisionRequestError('timeout', '视觉模型请求超时'),
])
def test_automatic_screening_failure_stops_before_speech_production(client, source, monkeypatch, error):
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences(
        analysis_mode='auto', allow_visual_screening=True))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **k: [])
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(intelligence, 'vision_call', fail)
    class Immediate:
        def submit(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)
    monkeypatch.setattr(jobs, 'executor', Immediate())
    content_calls = []
    monkeypatch.setattr(jobs, 'run_content', lambda *a: content_calls.append(a) or [])
    response = client.post('/studio/import', data={'auto_start': 'true', 'platforms': 'douyin'},
                           files={'video': ('source.mp4', source.read_bytes(), 'video/mp4')})
    assert response.status_code == 200, response.text
    pid = response.json()['project_id']
    state = client.get('/studio/' + pid).json()
    assert state['generation']['status'] == state['analysis']['status'] == 'failed'
    assert state['analysis']['phase'] == 'screening'
    assert not content_calls and state['drafts'] == [] and state['output_variants'] == []
    assert client.get('/studio/' + pid + '/source').content == source.read_bytes()
    # The same import can be screened again after correcting the visual service.
    monkeypatch.setattr(intelligence, 'vision_call', lambda *a, **k: {
        'content_type': 'gameplay', 'goal': 'highlight', 'reason': 'Visible game action',
        'confidence': .8, 'duration': 30})
    submitted = []
    monkeypatch.setattr(jobs, '_auto_generate', jobs._tracked('production')(lambda project_id, plan: submitted.append((project_id, plan))))
    retried = client.post('/studio/' + pid + '/analyze')
    assert retried.status_code == 200, retried.text
    assert submitted[0][0] == pid and submitted[0][1]['recommended_analysis'] == 'visual'
    assert not content_calls
    assert client.get('/studio/' + pid + '/source').content == source.read_bytes()


def test_manual_screening_failure_still_offers_an_unselected_plan(monkeypatch):
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences(
        analysis_mode='auto', allow_visual_screening=True))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, '_probe', lambda _: {'duration': 45})
    error = intelligence.VisionRequestError('timeout', '视觉模型请求超时')
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(intelligence, 'sample', fail)
    plan = planning.recommend(Path('synthetic.mp4'), ImportOptions())
    assert plan['mode'] == 'fallback' and plan['suggested_goals'] == []
    assert plan['diagnostics']['code'] == 'timeout'


def test_forced_unconfigured_visual_stops_auto_but_default_auto_keeps_subtitles(tmp_path, monkeypatch):
    mode = 'visual'
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences(
        analysis_mode=mode, allow_visual_screening=True))
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    monkeypatch.setattr(intelligence, '_probe', lambda _: {'duration': 45})
    monkeypatch.setattr(intelligence, 'vision_call', lambda *a, **k: pytest.fail('unconfigured model called'))
    video = tmp_path / 'public-game.mp4'
    with pytest.raises(ValueError, match='视觉模型'):
        planning.recommend(video, ImportOptions(auto_start=True))
    # A normal auto/text-only configuration still uses the existing subtitle route.
    mode = 'auto'
    plan = planning.recommend(video, ImportOptions(auto_start=True))
    assert plan['mode'] == 'local' and plan['recommended_analysis'] == 'subtitle'
    assert plan['local_evidence']['subtitle_status'] == 'missing'
