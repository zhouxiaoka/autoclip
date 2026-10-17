"""Model replies that are the wrong shape are invalid_response, and the payload stays out of the error.

Locks the two consumption sites the connection-test / attribution work still left open:
the visual refine pass, and subtitle translation of null or a short list.
"""
from pathlib import Path

import pytest

from backend.core.failure_attribution import FailureKind, ModelResponseInvalid, classify_failure
from backend.core.sentry_setup import studio_error_code
from backend.services.studio import intelligence as vision
from backend.services.studio.models import Draft, Preferences, Scene

SECRET = 'sk-reply-shape-secret'


def _draft(**values):
    return Draft(id='d1', title='First cut', scenes=[Scene(id='s1', start=.2, end=1.2)], **values)


def _assert_invalid(error: BaseException):
    assert isinstance(error, ModelResponseInvalid)
    assert classify_failure(error).kind is FailureKind.MODEL
    assert studio_error_code(error) == 'invalid_response'
    assert SECRET not in str(error)
    assert error.__cause__ is None


def test_refine_schema_failure_is_invalid_response_without_the_payload(monkeypatch):
    monkeypatch.setattr(vision, '_probe', lambda _: {'duration': 100})
    monkeypatch.setattr(vision, 'sample', lambda *a: [])
    bad = {'id': 'e5', 'start': 50, 'end': 55, 'label': SECRET, 'event_type': 'gameplay', 'watch_score': 'no'}
    responses = iter([
        {'events': [{'id': 'e5', 'start': 50, 'end': 55, 'label': 'play', 'event_type': 'gameplay', 'watch_score': 90}]},
        {'events': [bad]},
    ])
    monkeypatch.setattr(vision, 'vision_call', lambda *a, **k: next(responses))
    with pytest.raises(ModelResponseInvalid) as caught:
        vision.analyze(Path('unused'), Preferences(goal='highlight'))
    _assert_invalid(caught.value)


def test_refine_null_events_is_invalid_response(monkeypatch):
    monkeypatch.setattr(vision, '_probe', lambda _: {'duration': 100})
    monkeypatch.setattr(vision, 'sample', lambda *a: [])
    responses = iter([
        {'events': [{'id': 'e5', 'start': 50, 'end': 55, 'label': 'play', 'event_type': 'gameplay', 'watch_score': 90}]},
        {'events': None, 'leak': SECRET},
    ])
    monkeypatch.setattr(vision, 'vision_call', lambda *a, **k: next(responses))
    with pytest.raises(ModelResponseInvalid) as caught:
        vision.analyze(Path('unused'), Preferences(goal='highlight'))
    _assert_invalid(caught.value)


def test_refine_empty_list_keeps_the_scanned_event(monkeypatch):
    monkeypatch.setattr(vision, '_probe', lambda _: {'duration': 100})
    monkeypatch.setattr(vision, 'sample', lambda *a: [])
    responses = iter([
        {'events': [{'id': 'e5', 'start': 50, 'end': 55, 'label': 'play', 'event_type': 'gameplay', 'watch_score': 90}]},
        {'events': []},
    ])
    monkeypatch.setattr(vision, 'vision_call', lambda *a, **k: next(responses))
    found, coverage = vision.analyze(Path('unused'), Preferences(goal='highlight'))
    assert [scene.id for scene in found] == ['e5']
    assert coverage['refined_event_id'] is None


@pytest.mark.parametrize('subtitles', [None, [], 'not-a-list'])
def test_subtitle_translation_wrong_shape_is_invalid_response(monkeypatch, subtitles):
    from backend.services.studio import audio, render

    monkeypatch.setattr(render, '_probe', lambda video: {'duration': 10, 'width': 320, 'height': 180})
    monkeypatch.setattr(audio, 'has_audio', lambda video: False)
    monkeypatch.setattr(render, '_load_srt_entries', lambda project_id: [
        {'start_time': '00:00:00,200', 'end_time': '00:00:01,000', 'text': '你好'},
    ])
    monkeypatch.setattr(render, 'text_json', lambda *a, **k: {'title': SECRET, 'subtitles': subtitles})
    draft = _draft(language='en', hook='新开头', subtitles=True, original_audio=False)
    with pytest.raises(ModelResponseInvalid) as caught:
        render.render_draft('p1', Path('unused'), draft, 'job', lambda _percent: None)
    _assert_invalid(caught.value)
