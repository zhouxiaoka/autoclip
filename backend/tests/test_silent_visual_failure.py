"""RC156 Win QA #19: a silent video that the visual route cannot cut says it has no sound.

The blocking policy is unchanged (auto mode with visual allowed still tries the visual route);
only the failure sentence and code change, and only for a definite "no audio track" without SRT.
"""
import pytest

from backend.pipeline import media_precheck
from backend.pipeline.failures import PipelineFailure


@pytest.fixture
def visual(tmp_path, monkeypatch):
    from backend.services.studio import jobs, intelligence
    video = tmp_path / 'source.mp4'
    video.write_bytes(b'')
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, '_probe', lambda v: {'duration': 45.0})
    plan = {'recommended_analysis': 'visual', 'preferences': {'goal': 'highlight'}, 'overrides': {}}
    calls = []
    monkeypatch.setattr(jobs, 'make_drafts', lambda *a, **k: calls.append('drafts') or [])
    return jobs, video, plan, calls


def _analyze_raises(monkeypatch, jobs, error):
    def analyze(video, prefs):
        raise error
    monkeypatch.setattr(jobs, 'analyze', analyze)


def test_silent_source_visual_failure_names_the_missing_sound(visual, monkeypatch):
    from backend.core.sentry_setup import studio_error_code
    jobs, video, plan, _ = visual
    _analyze_raises(monkeypatch, jobs, ValueError('没有找到可用镜头'))
    monkeypatch.setattr(media_precheck, 'has_audio', lambda v: False)

    with pytest.raises(PipelineFailure) as raised:
        jobs._content_drafts('p', plan, video)

    assert raised.value.code == 'source_no_audio'
    assert str(raised.value) == media_precheck.NO_AUDIO_VISUAL_MESSAGE
    assert '没有声音' in str(raised.value) and 'SRT' in str(raised.value)
    assert studio_error_code(raised.value) == 'source_no_audio'
    assert isinstance(raised.value.__cause__, ValueError)


@pytest.mark.parametrize('audio', [True, None])
def test_sound_or_unknown_audio_keeps_the_original_error(visual, monkeypatch, audio):
    jobs, video, plan, _ = visual
    _analyze_raises(monkeypatch, jobs, ValueError('没有找到可用镜头'))
    monkeypatch.setattr(media_precheck, 'has_audio', lambda v: audio)
    with pytest.raises(ValueError, match='没有找到可用镜头'):
        jobs._content_drafts('p', plan, video)


def test_attached_srt_keeps_the_original_error(visual, monkeypatch):
    jobs, video, plan, _ = visual
    (video.parent / 'input.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nx\n', encoding='utf-8')
    _analyze_raises(monkeypatch, jobs, ValueError('没有找到可用镜头'))
    monkeypatch.setattr(media_precheck, 'has_audio', lambda v: False)
    with pytest.raises(ValueError, match='没有找到可用镜头'):
        jobs._content_drafts('p', plan, video)


def test_vision_model_errors_are_not_relabelled(visual, monkeypatch):
    from backend.services.studio.intelligence import VisionRequestError
    jobs, video, plan, _ = visual
    _analyze_raises(monkeypatch, jobs, VisionRequestError('timeout', '视觉模型响应超时'))
    monkeypatch.setattr(media_precheck, 'has_audio', lambda v: False)
    with pytest.raises(VisionRequestError):
        jobs._content_drafts('p', plan, video)


def test_silent_source_with_usable_visual_result_still_succeeds(visual, monkeypatch):
    jobs, video, plan, calls = visual
    monkeypatch.setattr(jobs, 'analyze', lambda video, prefs: ([], {'duration': 45.0}))
    monkeypatch.setattr(media_precheck, 'has_audio', lambda v: pytest.fail('only probed on failure'))
    drafts, events, coverage = jobs._content_drafts('p', plan, video)
    assert calls == ['drafts'] and events == [] and coverage == {'duration': 45.0}
