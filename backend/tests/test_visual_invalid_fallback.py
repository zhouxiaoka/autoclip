"""E1: visual mode + unparseable screening answer degrades to subtitles with a notice."""
import pytest

from backend.services import ai_model_settings as ai
from backend.services.studio import intelligence, planning, readiness
from backend.services.studio.models import ImportOptions
from backend.tests.test_auto_vision_fallback import (  # noqa: F401
    configure, isolated_offline_settings, source, SUBTITLES,
)
from backend.tests.test_studio import root  # noqa: F401

CODE = 'vision_invalid_subtitle_fallback'
NOTICE = '画面结果不可用，已改用字幕继续制作。'


def _visual(monkeypatch, behaviour):
    original = configure(monkeypatch, 'unavailable', mode='visual')
    monkeypatch.setattr(intelligence, 'vision_call', behaviour)
    return original


def invalid(*_a, **_k):
    raise intelligence.VisionRequestError('invalid_response', '视觉模型返回了无法解析的响应')


def malformed(*_a, **_k):
    return {'content_type': 'not-a-type', 'goal': 42}


@pytest.mark.parametrize('auto_start', [True, False])
@pytest.mark.parametrize('behaviour', [invalid, malformed])
def test_visual_mode_parse_failure_falls_back_to_subtitles(source, monkeypatch, auto_start, behaviour):
    original = _visual(monkeypatch, behaviour)
    plan = planning.recommend(source, ImportOptions(auto_start=auto_start))
    assert plan['recommended_analysis'] == 'subtitle'
    assert plan['degrade_reason'] == CODE
    assert plan['mode'] == 'fallback'
    assert plan['reason'].startswith(NOTICE)
    # Never silently switch provider: model settings untouched.
    assert ai.path().read_bytes() == original


def test_visual_mode_connection_failure_still_hard_fails(source, monkeypatch):
    _visual(monkeypatch, lambda *_a, **_k: (_ for _ in ()).throw(
        intelligence.VisionRequestError('connection', 'down')))
    with pytest.raises(intelligence.VisionRequestError):
        planning.recommend(source, ImportOptions(auto_start=True))


def test_visual_mode_parse_failure_without_subtitle_route_keeps_failure(source, monkeypatch):
    (source.parent / 'input.srt').unlink()
    _visual(monkeypatch, invalid)

    def not_ready(**_k):
        raise RuntimeError('asr not ready')

    monkeypatch.setattr(readiness, 'require_transcription', not_ready)
    with pytest.raises(intelligence.VisionRequestError) as caught:
        planning.recommend(source, ImportOptions(auto_start=True))
    assert caught.value.code == 'invalid_response'
