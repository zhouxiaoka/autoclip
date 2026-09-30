import pytest

from backend.services.studio import framing, jobs
from backend.services.studio.models import Draft, Scene


def _value():
    return Draft(id='d', title='T', scenes=[Scene(id='s1', label='S', start=0, end=10), Scene(id='s2', label='S', start=20, end=30)]).model_dump()


def test_burned_captions_keep_the_full_frame_without_running_detection(monkeypatch):
    monkeypatch.setattr(jobs, '_speaker_framing', lambda *_a, **_k: pytest.fail('must not detect faces'))
    value, framed = jobs._apply_framing('p1', _value(), 'tiktok', 'video.mp4', True, {})
    assert framed == 'full_frame_captions' and value['layout'] == 'blur'


def test_landscape_outputs_are_not_reframed(monkeypatch):
    monkeypatch.setattr(jobs, '_speaker_framing', lambda *_a, **_k: pytest.fail('landscape needs no vertical crop'))
    value, framed = jobs._apply_framing('p1', _value(), 'youtube_long', 'video.mp4', False, {})
    assert framed is None and value == _value()


def test_faces_give_speaker_crop_and_one_detection_serves_every_vertical_platform(monkeypatch):
    calls = []
    def detect(value, video):
        calls.append(video)
        return [{**scene, 'crop_x': .3, 'crop_track': [{'start': 0, 'crop_x': .3, 'mode': 'crop'}]} for scene in value['scenes']], 'speaker'
    monkeypatch.setattr(jobs, '_speaker_framing', detect)
    cache = {}
    for strategy_id in ('douyin', 'tiktok', 'youtube_shorts'):
        value, framed = jobs._apply_framing('p1', _value(), strategy_id, 'video.mp4', False, cache)
        draft = jobs._apply_strategy(value, strategy_id, layout=value['layout'])
        assert framed == 'speaker' and draft.layout == 'crop' and draft.scenes[0].crop_track[0].crop_x == .3
    assert len(calls) == 1


def test_missing_detector_falls_back_to_full_frame_and_says_so(monkeypatch):
    monkeypatch.setattr(framing, 'is_installed', lambda: False)
    monkeypatch.setattr(framing, 'get_status', lambda: {'status': 'not_installed'})
    value, framed = jobs._apply_framing('p1', _value(), 'douyin', 'video.mp4', False, {})
    assert framed == 'full_frame_pending' and value['layout'] == 'blur'


def test_detection_errors_never_fail_the_output(monkeypatch):
    monkeypatch.setattr(jobs, '_speaker_framing', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('cv2 crashed')))
    value, framed = jobs._apply_framing('p1', _value(), 'douyin', 'video.mp4', False, {})
    assert framed == 'full_frame' and value['layout'] == 'blur'
