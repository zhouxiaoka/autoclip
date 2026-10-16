"""R3/R4 (R10): overlong sources route to subtitles with a visible tip; only vision-service
failures are classified as vision unavailable (S5)."""
import pytest

from backend.services.studio import intelligence, planning
from backend.services.studio.models import ImportOptions
from backend.tests.test_auto_vision_fallback import (  # noqa: F401
    configure, isolated_offline_settings, source,
)
from backend.tests.test_studio import root  # noqa: F401

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
