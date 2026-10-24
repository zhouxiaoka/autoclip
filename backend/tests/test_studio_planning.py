"""Behavior tests for studio planning routes and overlong sources."""
import pytest

from backend.services.studio import intelligence, planning
from backend.services.studio.models import ImportOptions
from backend.tests.test_auto_vision_fallback import (  # noqa: F401
    configure, isolated_offline_settings, source,
)
from backend.tests.test_studio import root  # noqa: F401
import json
import subprocess
from pathlib import Path
""": overlong sources route to subtitles with a visible tip; only vision-service
failures are classified as vision unavailable (S5)."""

TALK = {
    'content_type': 'talk', 'goal': 'content', 'reason': '访谈', 'confidence': 0.8,
    'aspect': 'original', 'duration': 30, 'suggested_goals': ['content'],
}


def _long_probe(monkeypatch, seconds=8000.0):
    monkeypatch.setattr(intelligence, '_probe', lambda _video: {
        'duration': seconds, 'width': 160, 'height': 90,
    })


@pytest.mark.parametrize('auto_start', [True, False])
def test_r3_manual_visual_overlong_routes_to_subtitles_with_tip(source, monkeypatch, auto_start):
    """>120 min must not hard-block; the explicit visual choice is switched visibly, not silently."""
    configure(monkeypatch, 'unavailable', mode='visual')
    monkeypatch.setattr(intelligence, 'vision_call', lambda *_a, **_k: TALK)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    _long_probe(monkeypatch)
    plan = planning.recommend(source, ImportOptions(auto_start=auto_start))
    assert plan['recommended_analysis'] == 'subtitle'
    assert planning.VISUAL_SOURCE_TOO_LONG_MESSAGE in plan['reason']
    assert '120' in plan['reason']


def test_r3_auto_mode_overlong_still_allows_subtitle_route(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')
    monkeypatch.setattr(intelligence, 'vision_call', lambda *_a, **_k: TALK)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    _long_probe(monkeypatch)
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['recommended_analysis'] == 'subtitle'


def test_r4_auto_local_oserror_is_not_vision_unavailable(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')

    def boom(*_a, **_k):
        raise OSError('ffmpeg sample failed: /secret/path/clip.mp4')

    monkeypatch.setattr(intelligence, 'vision_call', boom)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['recommended_analysis'] == 'subtitle'
    # S5: a local ffmpeg/OS error is not a vision outage.
    assert 'degrade_reason' not in plan
    assert planning.VISION_FALLBACK_MESSAGE not in plan['reason']
    assert '/secret/path' not in plan['reason']


def test_r4_auto_vision_request_error_carries_unavailable_tip(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')

    def down(*_a, **_k):
        raise intelligence.VisionRequestError('timeout', '视觉模型请求超时')

    monkeypatch.setattr(intelligence, 'vision_call', down)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['degrade_reason'] == planning.VISION_FALLBACK_CODE
    assert planning.VISION_FALLBACK_MESSAGE in plan['reason']


def test_r4_auto_parse_failure_still_uses_invalid_tip(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')

    def bad(*_a, **_k):
        raise intelligence.VisionRequestError('invalid_response', '视觉模型返回了无法解析的响应')

    monkeypatch.setattr(intelligence, 'vision_call', bad)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['degrade_reason'] == planning.VISION_INVALID_FALLBACK_CODE
    assert planning.VISION_INVALID_FALLBACK_MESSAGE in plan['reason']
""">120 min routes to subtitles before any vision check; frame-extract failures
inside the real sample have their own code; new hints are reason codes with 8 locales."""


def _long(monkeypatch, seconds=8000.0):
    monkeypatch.setattr(intelligence, '_probe', lambda _v: {'duration': seconds, 'width': 160, 'height': 90})


def _vision_must_not_run(monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append('vision')
        raise intelligence.VisionRequestError('connection', 'down')

    def not_ready():
        calls.append('ready')
        raise ValueError('vision not configured')

    monkeypatch.setattr(intelligence, 'vision_call', boom)
    monkeypatch.setattr(intelligence, 'ready', not_ready)
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **k: calls.append('sample') or [])
    return calls


@pytest.mark.parametrize('mode', ['visual', 'auto'])
def test_overlong_routes_to_subtitles_before_vision_check_and_screening(source, monkeypatch, mode):
    configure(monkeypatch, 'unavailable', mode=mode)
    calls = _vision_must_not_run(monkeypatch)
    _long(monkeypatch)
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert calls == []  # neither the vision config check nor screening/sampling ran
    assert plan['recommended_analysis'] == 'subtitle'
    assert plan['degrade_reason'] == planning.SOURCE_TOO_LONG_CODE
    assert planning.VISUAL_SOURCE_TOO_LONG_MESSAGE in plan['reason']


def test_overlong_verifies_transcription_is_ready(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='visual')
    _vision_must_not_run(monkeypatch)
    _long(monkeypatch)
    (source.parent / 'input.srt').unlink()
    from backend.services.studio import readiness
    monkeypatch.setattr(readiness, 'transcription_check',
                        lambda: {'ok': False, 'code': 'whisper_not_installed', 'repair': 'install'})
    with pytest.raises(Exception) as caught:
        planning.recommend(source, ImportOptions(auto_start=True))
    assert 'vision' not in str(caught.value).lower()


def test_real_sample_ffmpeg_failure_has_its_own_code(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')
    monkeypatch.setattr(intelligence, 'sample', _real_sample)  # undo configure()'s stub
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    vision = []
    monkeypatch.setattr(intelligence, 'vision_call', lambda *a, **k: vision.append(1) or {})
    real_run = subprocess.run

    def ffmpeg_fails(cmd, *a, **k):
        if any('ffmpeg' in str(part) for part in cmd[:1]) and '-frames:v' in cmd:
            raise subprocess.CalledProcessError(1, ['ffmpeg'])
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(intelligence.subprocess, 'run', ffmpeg_fails)
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert vision == []
    assert plan['recommended_analysis'] == 'subtitle'
    assert plan['degrade_reason'] == planning.FRAME_EXTRACT_FALLBACK_CODE
    assert planning.VISION_FALLBACK_MESSAGE not in plan['reason']
    assert plan['diagnostics']['code'] == 'frame_extract_failed'


def test_real_sample_raises_frame_extract_error(source, tmp_path, monkeypatch):
    real_run = subprocess.run

    def ffmpeg_fails(cmd, *a, **k):
        if '-frames:v' in cmd:
            raise subprocess.CalledProcessError(1, ['ffmpeg'])
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(intelligence.subprocess, 'run', ffmpeg_fails)
    with pytest.raises(intelligence.FrameExtractError) as caught:
        _real_sample(source, [1.0], tmp_path)
    assert caught.value.code == 'frame_extract_failed'


_real_sample = intelligence.sample

KEYS = (
    planning.VISUAL_SOURCE_TOO_LONG_MESSAGE,
    planning.FRAME_EXTRACT_FALLBACK_MESSAGE,
)


def test_new_hints_exist_in_all_eight_locales():
    from backend.services.whisper_model_manager import WHISPER_DOWNLOAD_USER_ERROR
    root_dir = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'i18n' / 'locales'
    for lang in ('zh', 'en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru'):
        catalog = json.loads((root_dir / f'{lang}.json').read_text(encoding='utf-8'))
        for key in KEYS + (WHISPER_DOWNLOAD_USER_ERROR,):
            assert catalog.get(key), (lang, key)
            if lang != 'zh':
                assert catalog[key] != key, (lang, key)
    summary = (Path(__file__).resolve().parents[2] / 'frontend/src/features/studio/PlanSummary.tsx').read_text(encoding='utf-8')
    for code, key in ((planning.SOURCE_TOO_LONG_CODE, KEYS[0]), (planning.FRAME_EXTRACT_FALLBACK_CODE, KEYS[1])):
        assert f"degrade_reason==='{code}'" in summary and f"t('{key}')" in summary
