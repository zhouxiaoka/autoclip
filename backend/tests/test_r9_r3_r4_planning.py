"""R3/R4: manual visual overlong hard-block; AUTO non-parse failures carry tips."""
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


def test_r3_manual_visual_overlong_hard_blocks_auto_start(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='visual')
    monkeypatch.setattr(intelligence, 'vision_call', lambda *_a, **_k: TALK)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    _long_probe(monkeypatch)
    with pytest.raises(ValueError, match='画面分析最长支持'):
        planning.recommend(source, ImportOptions(auto_start=True))


def test_r3_manual_visual_overlong_hard_blocks_review(source, monkeypatch):
    """Review must not silently recommend subtitle for an explicit visual choice."""
    configure(monkeypatch, 'unavailable', mode='visual')
    monkeypatch.setattr(intelligence, 'vision_call', lambda *_a, **_k: TALK)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    _long_probe(monkeypatch)
    with pytest.raises(ValueError, match='请改用字幕分析'):
        planning.recommend(source, ImportOptions(auto_start=False))


def test_r3_auto_mode_overlong_still_allows_subtitle_route(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')
    monkeypatch.setattr(intelligence, 'vision_call', lambda *_a, **_k: TALK)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    _long_probe(monkeypatch)
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['recommended_analysis'] == 'subtitle'


def test_r4_auto_oserror_falls_back_with_unavailable_tip(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')

    def boom(*_a, **_k):
        raise OSError('ffmpeg sample failed: /secret/path/clip.mp4')

    monkeypatch.setattr(intelligence, 'vision_call', boom)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['recommended_analysis'] == 'subtitle'
    assert plan['degrade_reason'] == planning.VISION_FALLBACK_CODE
    assert planning.VISION_FALLBACK_MESSAGE in plan['reason']
    assert '/secret/path' not in plan['reason']


def test_r4_auto_parse_failure_still_uses_invalid_tip(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')

    def bad(*_a, **_k):
        raise intelligence.VisionRequestError('invalid_response', '视觉模型返回了无法解析的响应')

    monkeypatch.setattr(intelligence, 'vision_call', bad)
    monkeypatch.setattr(intelligence, 'sample', lambda *_a, **_k: [])
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['degrade_reason'] == planning.VISION_INVALID_FALLBACK_CODE
    assert planning.VISION_INVALID_FALLBACK_MESSAGE in plan['reason']
