"""Event-list compatibility is restricted to visual scan and refinement."""
import io
import json
from pathlib import Path

import pytest

from backend.services.studio import intelligence as vision, vision_settings
from backend.services.studio.models import Preferences

CONFIG = {'base_url': 'https://fixture.example/v1', 'model': 'fixture-vision', 'api_key': 'fixture-key'}


def event(start=10, end=16):
    return {'id': 'event-1', 'label': '使用滑板躲避障碍', 'start': start, 'end': end,
            'evidence': '公开游戏静帧中的道具和障碍', 'event_type': 'gameplay',
            'watch_score': 90, 'selection_reason': '可见的道具与避险动作'}


def respond(monkeypatch, values, fenced=False):
    calls = []
    values = iter(values)
    monkeypatch.setattr(vision_settings, 'effective', lambda: CONFIG)
    def send(req, **_kwargs):
        calls.append(json.loads(req.data))
        content = json.dumps(next(values), ensure_ascii=False)
        if fenced:
            content = '```json\n' + content + '\n```'
        return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}).encode())
    monkeypatch.setattr(vision.urllib.request, 'urlopen', send)
    return calls


@pytest.mark.parametrize('phase', ['scan', 'refine'])
@pytest.mark.parametrize('fenced', [False, True])
def test_bare_event_arrays_are_accepted_only_for_event_phases(monkeypatch, phase, fenced):
    calls = respond(monkeypatch, [[event()]], fenced)
    assert vision.vision_call_at(phase, []) == {'events': [event()]}
    assert len(calls) == 1, 'Format compatibility must not replay a paid request'


@pytest.mark.parametrize('phase', ['screening', 'hooks', 'cover_frame'])
def test_other_phases_do_not_guess_the_meaning_of_arrays(monkeypatch, phase):
    respond(monkeypatch, [[event()]])
    with pytest.raises(vision.VisionRequestError) as caught:
        vision.vision_call_at(phase, [])
    assert caught.value.code == 'invalid_response' and caught.value.phase == phase


@pytest.mark.parametrize('value', [[1], ['text'], [event(), None], 'text'])
def test_event_array_compatibility_rejects_non_object_entries(monkeypatch, value):
    respond(monkeypatch, [value])
    with pytest.raises(vision.VisionRequestError, match='结构化'):
        vision.vision_call_at('scan', [])


def test_array_scan_and_refinement_still_validate_source_boundaries(monkeypatch):
    respond(monkeypatch, [[event()], [event(11, 15)]])
    monkeypatch.setattr(vision, '_probe', lambda _video: {'duration': 45})
    monkeypatch.setattr(vision, 'sample', lambda *args: [])
    scenes, coverage = vision.analyze(Path('fixture.mp4'), Preferences(goal='highlight', duration=45))
    assert [(s.start, s.end) for s in scenes] == [(11, 15)]
    assert coverage['refined_event_id'] == 'event-1'
    respond(monkeypatch, [[event()], [event(0, 44)]])
    with pytest.raises(ValueError, match='超出采样区间'):
        vision.analyze(Path('fixture.mp4'), Preferences(goal='highlight', duration=45))
