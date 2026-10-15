"""E1: AUTO mode + unparseable screening -> subtitles with notice; manual visual hard-blocks."""
import pytest

from backend.services import ai_model_settings as ai
from backend.services.studio import intelligence, planning
from backend.services.studio.models import ImportOptions
from backend.tests.test_auto_vision_fallback import (  # noqa: F401
    configure, isolated_offline_settings, source,
)
from backend.tests.test_studio import root  # noqa: F401

CODE = 'vision_invalid_subtitle_fallback'
NOTICE = '画面结果不可用，已改用字幕继续制作。'


def _mode(monkeypatch, mode, behaviour):
    original = configure(monkeypatch, 'unavailable', mode=mode)
    monkeypatch.setattr(intelligence, 'vision_call', behaviour)
    return original


def invalid(*_a, **_k):
    raise intelligence.VisionRequestError('invalid_response', '视觉模型返回了无法解析的响应')


def malformed(*_a, **_k):
    return {'content_type': 'not-a-type', 'goal': 42}


@pytest.mark.parametrize('auto_start', [True, False])
@pytest.mark.parametrize('behaviour', [invalid, malformed])
def test_auto_mode_parse_failure_falls_back_to_subtitles(source, monkeypatch, auto_start, behaviour):
    original = _mode(monkeypatch, 'auto', behaviour)
    plan = planning.recommend(source, ImportOptions(auto_start=auto_start))
    assert plan['recommended_analysis'] == 'subtitle'
    assert plan['degrade_reason'] == CODE
    assert plan['mode'] == 'fallback'
    assert plan['reason'].startswith(NOTICE)
    assert ai.path().read_bytes() == original  # never switch provider


@pytest.mark.parametrize('behaviour', [invalid, malformed])
def test_manual_visual_parse_failure_hard_blocks(source, monkeypatch, behaviour):
    original = _mode(monkeypatch, 'visual', behaviour)
    with pytest.raises((intelligence.VisionRequestError, ValueError)):
        planning.recommend(source, ImportOptions(auto_start=True))
    assert ai.path().read_bytes() == original


@pytest.mark.parametrize('behaviour', [invalid, malformed])
def test_manual_visual_review_screen_keeps_visual_route(source, monkeypatch, behaviour):
    _mode(monkeypatch, 'visual', behaviour)
    plan = planning.recommend(source, ImportOptions(auto_start=False))
    assert plan['recommended_analysis'] == 'visual'
    assert 'degrade_reason' not in plan


def test_auto_mode_connection_failure_keeps_s5_notice(source, monkeypatch):
    _mode(monkeypatch, 'auto', lambda *_a, **_k: (_ for _ in ()).throw(
        intelligence.VisionRequestError('connection', 'down')))
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['degrade_reason'] == 'vision_unavailable_subtitle_fallback'
