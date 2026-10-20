"""#345: unreadable duration vs too short vs ffmpeg fallback."""
import subprocess
from types import SimpleNamespace

import pytest

from backend.core import sentry_setup
from backend.pipeline import media_precheck
from backend.pipeline.failures import PipelineFailure
from backend.services.studio import preflight


pytestmark = pytest.mark.real_media_probe  # #418: these tests fake ffprobe/ffmpeg themselves

def _fake_run(probe_out, probe_err, ffmpeg_err):
    def run(cmd, **kwargs):
        if 'ffprobe' in str(cmd[0]):
            return SimpleNamespace(returncode=1 if probe_err else 0, stdout=probe_out, stderr=probe_err)
        return SimpleNamespace(returncode=0, stdout='', stderr=ffmpeg_err)
    return run


@pytest.fixture(autouse=True)
def _paths(monkeypatch):
    import backend.utils.ffmpeg_utils as fu
    monkeypatch.setattr(fu, 'get_ffprobe_path', lambda: 'ffprobe')
    monkeypatch.setattr(fu, 'get_ffmpeg_path', lambda: 'ffmpeg')


def test_unreadable_is_its_own_code_with_sanitized_stderr(monkeypatch):
    video = 'C:\\Users\\alice\\Videos\\我的 视频.mp4'
    monkeypatch.setattr(subprocess, 'run', _fake_run('{}', f'{video}: Invalid data found when processing input', 'Invalid data'))
    error = preflight.classify_source(preflight.probe_material(video), srt_available=True, subtitle_route=False)
    assert error.code == 'source_unreadable'
    assert str(error) == media_precheck.UNREADABLE_MESSAGE
    assert "找不到源文件" in str(error) and "可能已被移动或删除" in str(error)
    assert "文件已损坏" in str(error)
    assert 'Invalid data found' in error.probe_detail
    assert 'alice' not in error.probe_detail and '我的 视频' not in error.probe_detail
    assert sentry_setup.studio_error_code(error) == 'source_unreadable'
    assert 'source_unreadable' not in sentry_setup.UNREPORTED_STUDIO_ERROR_CODES


def test_truly_short_source_is_source_too_short_and_unreported(monkeypatch):
    # #373: the under-1-second branch of classify_source, through a real probe, on a non-subtitle route.
    monkeypatch.setattr(subprocess, 'run', _fake_run('{"format": {"duration": "0.4"}, "streams": [{"codec_type": "video"}]}', '', ''))
    probe = preflight.probe_material('clip.mp4')
    assert probe.duration == pytest.approx(0.4)
    error = preflight.classify_source(probe, srt_available=True, subtitle_route=False)
    assert isinstance(error, PipelineFailure)
    assert error.code == 'source_too_short'
    assert preflight.classify_source(preflight.MaterialProbe(preflight.ProbeState.READABLE, None, 1.0, True), srt_available=True, subtitle_route=False) is None
    info = SimpleNamespace(value=error)
    assert info.value.code == 'source_too_short'
    assert str(info.value) == media_precheck.TOO_SHORT_1S_MESSAGE
    assert 'source_too_short' in sentry_setup.UNREPORTED_STUDIO_ERROR_CODES


def test_ffmpeg_decode_fallback_recovers_duration(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', _fake_run('{"format": {}}', '', 'frame=  10 time=00:01:05.40 bitrate=N/A\nframe= 20 time=00:02:03.50 bitrate=N/A'))
    probe = preflight.probe_material('clip.mkv')
    assert probe.duration == pytest.approx(123.5)
    assert (probe.ffprobe_runs, probe.decode_runs) == (1, 1)


def test_recommend_uses_split_codes(monkeypatch):
    from backend.services.studio import planning, intelligence
    monkeypatch.setattr(intelligence, '_probe', lambda video: {})
    monkeypatch.setattr(subprocess, 'run', _fake_run('{}', 'moov atom not found', ''))
    with pytest.raises(PipelineFailure) as info:
        planning.recommend('x.mp4', SimpleNamespace(goal='auto', auto_start=True, instruction=''))
    assert info.value.code == 'source_unreadable'


def test_i18n_keys_present_in_all_locales():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / 'frontend/src/i18n/locales'
    files = list(root.glob('*.json'))
    assert len(files) == 8
    for f in files:
        data = json.loads(f.read_text(encoding='utf-8'))
        assert media_precheck.UNREADABLE_MESSAGE in data and media_precheck.TOO_SHORT_1S_MESSAGE in data
