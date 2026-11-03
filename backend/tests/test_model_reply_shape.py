"""Model replies that are the wrong shape are invalid_response, and the payload stays out of the error.

The visual refine pass still raises. Subtitle translation aligns numbered cues, retries once,
and keeps the source line for any cue the model still did not return.
"""
import logging
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


def _cues():
    return [
        {'start_time': '00:00:00,200', 'end_time': '00:00:01,000', 'text': 'hello'},
        {'start_time': '00:00:01,000', 'end_time': '00:00:02,000', 'text': 'world'},
    ]


def _translate(monkeypatch, replies, caplog):
    from backend.services.studio import render
    pending = list(replies)
    calls = []

    def fake(prompt, data):
        calls.append((prompt, data))
        reply = pending.pop(0)
        if not pending:
            pending.append(reply)
        return reply

    monkeypatch.setattr(render, 'text_json', fake)
    entries = _cues()
    warnings = []
    with caplog.at_level(logging.WARNING, logger='backend.services.studio.render'):
        hook = render._translate_hook_and_cues('zh', 'Opening', entries, warnings)
    return hook, entries, calls, caplog.text, warnings


def test_subtitle_translation_exact_numbered_match(monkeypatch, caplog):
    hook, entries, calls, logged, warnings = _translate(monkeypatch, [
        {'title': '标题', 'cues': [{'n': 1, 'text': '你好'}, {'n': 2, 'text': '世界'}]},
    ], caplog)
    assert hook == '标题'
    assert [entry['text'] for entry in entries] == ['你好', '世界']
    assert len(calls) == 1
    assert calls[0][1]['cues'] == [{'n': 1, 'text': 'hello'}, {'n': 2, 'text': 'world'}]
    assert 'n' in calls[0][0]
    assert 'mismatch' not in logged
    assert warnings == []


def test_subtitle_translation_fewer_cues_keeps_the_source_line(monkeypatch, caplog):
    hook, entries, calls, logged, warnings = _translate(monkeypatch, [
        {'title': '标题', 'cues': [{'n': 2, 'text': '世界'}]},
    ], caplog)
    assert hook == '标题'
    assert [entry['text'] for entry in entries] == ['hello', '世界']
    assert len(calls) == 2
    assert 'source_count=2 returned_count=1 missing_count=1' in logged
    assert 'hello' not in logged and '世界' not in logged and SECRET not in logged
    assert warnings == ['部分字幕未能翻译，已保留原文']


def test_subtitle_translation_more_cues_ignores_the_extra(monkeypatch, caplog):
    hook, entries, calls, logged, warnings = _translate(monkeypatch, [
        {'title': '标题', 'cues': [{'n': 1, 'text': '你好'}, {'n': 2, 'text': '世界'}, {'n': 9, 'text': '多余'}]},
    ], caplog)
    assert hook == '标题'
    assert [entry['text'] for entry in entries] == ['你好', '世界']
    assert len(calls) == 2
    assert 'source_count=2 returned_count=3 missing_count=0' in logged
    assert '多余' not in logged
    assert warnings == []


def test_subtitle_translation_merged_line_keeps_the_other_source(monkeypatch, caplog):
    _hook, entries, calls, logged, warnings = _translate(monkeypatch, [
        {'title': '标题', 'cues': [{'n': 1, 'text': '你好世界'}]},
    ], caplog)
    assert [entry['text'] for entry in entries] == ['你好世界', 'world']
    assert len(calls) == 2
    assert 'returned_count=1 missing_count=1' in logged
    assert '你好世界' not in logged and 'world' not in logged
    assert warnings == ['部分字幕未能翻译，已保留原文']


def test_subtitle_translation_retries_once_then_falls_back(monkeypatch, caplog):
    hook, entries, calls, logged, warnings = _translate(monkeypatch, [
        {'title': SECRET, 'subtitles': None, 'leak': SECRET},
        {'title': '标题', 'cues': 'not-a-list', 'leak': SECRET},
    ], caplog)
    assert hook == '标题'
    assert [entry['text'] for entry in entries] == ['hello', 'world']
    assert len(calls) == 2
    assert 'source_count=2 returned_count=0 missing_count=2' in logged
    assert SECRET not in hook and SECRET not in logged
    assert warnings == ['部分字幕未能翻译，已保留原文']
    assert '2' not in warnings[0] and SECRET not in warnings[0]
