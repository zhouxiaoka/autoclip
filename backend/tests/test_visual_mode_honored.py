"""E2: an explicit visual analysis mode must not be overridden by the recommendation."""
import pytest

from backend.services import ai_model_settings as ai
from backend.services.studio import analysis_preferences, intelligence, planning
from backend.services.studio.models import ImportOptions
from backend.tests.test_auto_vision_fallback import (  # noqa: F401
    configure, isolated_offline_settings, source,
)
from backend.tests.test_studio import root  # noqa: F401


def _visual(monkeypatch, answer, allow_screening=True):
    original = configure(monkeypatch, 'unavailable', mode='visual')
    if not allow_screening:
        consent = analysis_preferences.load().model_copy(update={'allow_visual_screening': False})
        monkeypatch.setattr(analysis_preferences, 'load', lambda: consent)
    calls = []

    def vision(*_a, **_k):
        calls.append(1)
        return answer

    monkeypatch.setattr(intelligence, 'vision_call', vision)
    return original, calls


TALK = {'content_type': 'talk', 'goal': 'content', 'reason': '访谈', 'confidence': 0.8,
        'aspect': 'original', 'duration': 30, 'suggested_goals': ['content']}


def test_visual_mode_runs_visual_even_when_screening_prefers_content(source, monkeypatch):
    original, calls = _visual(monkeypatch, TALK)
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert calls, 'visual mode must issue the screening image request'
    assert plan['recommended_analysis'] == 'visual'
    assert plan['goal'] != 'content'
    assert plan['suggested_goals'] and 'content' not in plan['suggested_goals'][:1]
    assert ai.path().read_bytes() == original


def test_visual_mode_without_screening_consent_still_routes_visual(source, monkeypatch):
    _, calls = _visual(monkeypatch, TALK, allow_screening=False)
    plan = planning.recommend(source, ImportOptions(auto_start=True))
    assert plan['recommended_analysis'] == 'visual'
    assert plan['goal'] != 'content'


def test_explicit_content_goal_keeps_subtitle_route(source, monkeypatch):
    _visual(monkeypatch, TALK)
    plan = planning.recommend(source, ImportOptions(goal='content', auto_start=True))
    assert plan['recommended_analysis'] == 'subtitle'


def test_auto_mode_still_follows_recommendation(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='auto')
    monkeypatch.setattr(intelligence, 'vision_call', lambda *_a, **_k: TALK)
    plan = planning.recommend(source, ImportOptions())
    assert plan['recommended_analysis'] == 'subtitle'


def test_review_screen_shows_the_route_that_will_run(source, monkeypatch):
    _visual(monkeypatch, TALK)
    plan = planning.recommend(source, ImportOptions(auto_start=False))
    assert plan['recommended_analysis'] == 'visual'
    assert plan['goal'] == 'highlight' and plan['preferences']['goal'] == 'highlight'
