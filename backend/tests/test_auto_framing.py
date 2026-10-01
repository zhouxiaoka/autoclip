import pytest

from backend.services.studio import framing, jobs
from backend.services.studio.models import Draft, Scene


def _value():
    return Draft(id='d', title='T', scenes=[Scene(id='s1', label='S', start=0, end=10), Scene(id='s2', label='S', start=20, end=30)]).model_dump()


def test_burned_captions_keep_the_full_frame_without_running_detection(monkeypatch):
    monkeypatch.setattr(jobs, '_speaker_framing', lambda *_a, **_k: pytest.fail('must not detect faces'))
    value, framed = jobs._apply_framing('p1', _value(), 'tiktok', 'video.mp4', True, {})
    assert framed == 'full_frame_captions' and value['layout'] == 'blur'
    value, framed = jobs._apply_framing('p1', _value(), 'douyin', 'video.mp4', True, {})
    assert framed == 'full_frame_captions' and value['layout'] == 'window'


def test_landscape_outputs_are_not_reframed(monkeypatch):
    monkeypatch.setattr(jobs, '_speaker_framing', lambda *_a, **_k: pytest.fail('landscape needs no vertical crop'))
    value, framed = jobs._apply_framing('p1', _value(), 'youtube_long', 'video.mp4', False, {})
    assert framed is None and value == _value()


def test_faces_give_speaker_crop_and_one_detection_per_window_shape(monkeypatch):
    calls = []
    def detect(value, video, *, window=None, scans=None):
        calls.append(window)
        return [{**scene, 'crop_x': .3, 'crop_track': [{'start': 0, 'crop_x': .3, 'mode': 'crop'}]} for scene in value['scenes']], 'speaker'
    monkeypatch.setattr(jobs, '_speaker_framing', detect)
    cache = {}
    expected = {'douyin': 'window', 'xiaohongshu': 'window', 'tiktok': 'crop', 'youtube_shorts': 'crop'}
    for strategy_id, layout in expected.items():
        value, framed = jobs._apply_framing('p1', _value(), strategy_id, 'video.mp4', False, cache)
        draft = jobs._apply_strategy(value, strategy_id, layout=value['layout'])
        assert framed == 'speaker' and draft.layout == layout and draft.scenes[0].crop_track[0].crop_x == .3
    assert calls == [jobs.INTERVIEW_WINDOW, None]  # 4:3 interview window once, 9:16 once


def test_both_window_shapes_share_one_face_detection_pass(monkeypatch):
    from backend.services import publish_export
    from backend.services.studio import framing
    scans = []
    monkeypatch.setattr(framing, 'is_installed', lambda: True)
    monkeypatch.setattr(publish_export, '_probe', lambda _v: {'width': 1920, 'height': 1080})
    monkeypatch.setattr(framing, 'scan_speakers', lambda _v, scenes: scans.append(1) or [{'shots': [(0.0, 10.0, [(1.0, .3), (5.0, .3)])], 'faces': 2, 'samples': 2} for _ in scenes])
    cache = {}
    for strategy_id in ('douyin', 'tiktok'):
        _, framed = jobs._apply_framing('p1', _value(), strategy_id, 'video.mp4', False, cache)
        assert framed == 'speaker'
    assert len(scans) == 1


@pytest.mark.parametrize('strategy_id', ['douyin', 'tiktok', 'instagram_reels', 'youtube_shorts', 'youtube_long', 'bilibili', 'xiaohongshu', 'original'])
def test_redirecting_a_derived_draft_to_any_platform_keeps_a_valid_title_version(strategy_id):
    derived = {**_value(), 'title_style': 'comic', 'title_template_version': 6}  # e.g. an earlier Douyin variant
    draft = jobs._apply_strategy(derived, strategy_id)
    assert draft.title_style and draft.title_template_version in (1, 2, 3, 4, 5, 6)


def test_one_packaging_call_per_content_and_template(monkeypatch, tmp_path):
    from backend.services import publish_export
    from backend.services.studio import packaging, store
    calls = []
    monkeypatch.setattr(publish_export, '_load_srt_entries', lambda _pid: [])
    monkeypatch.setattr(store, 'read', lambda _pid: {'source_meta': {'title': 'Sam Altman', 'channel': 'YC'}})
    monkeypatch.setattr(packaging, 'build_packaging', lambda value, lines, strategy, **kw: calls.append(strategy.template) or {'template': strategy.template})
    cache = {}
    for strategy_id in ('douyin', 'xiaohongshu', 'tiktok', 'youtube_shorts', 'instagram_reels'):
        value = jobs._apply_packaging('p1', _value(), strategy_id, False, cache)
        assert value['packaging']['template'] in ('interview_zh', 'podcast_en')
    assert calls == ['interview_zh', 'podcast_en']
    landscape = jobs._apply_packaging('p1', {**_value(), 'packaging': {'template': 'interview_zh'}}, 'bilibili', False, cache)
    assert 'packaging' not in landscape  # never inherit a vertical template on landscape


def test_missing_detector_falls_back_to_full_frame_and_says_so(monkeypatch):
    monkeypatch.setattr(framing, 'is_installed', lambda: False)
    monkeypatch.setattr(framing, 'get_status', lambda: {'status': 'not_installed'})
    value, framed = jobs._apply_framing('p1', _value(), 'tiktok', 'video.mp4', False, {})
    assert framed == 'full_frame_pending' and value['layout'] == 'blur'


def test_detection_errors_never_fail_the_output_and_drop_inherited_tracks(monkeypatch):
    monkeypatch.setattr(jobs, '_speaker_framing', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('cv2 crashed')))
    inherited = _value()
    inherited['scenes'][0]['crop_track'] = [{'start': 0, 'crop_x': .9, 'mode': 'crop'}]
    value, framed = jobs._apply_framing('p1', inherited, 'douyin', 'video.mp4', False, {})
    assert framed == 'full_frame' and value['layout'] == 'window'
    assert value['scenes'][0]['crop_track'] is None  # 9:16 tracks must not drive the 4:3 window


def test_packaging_of_a_batch_runs_side_by_side_once_per_content(monkeypatch):
    import threading
    import time
    from backend.services import publish_export
    from backend.services.studio import packaging, store
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '4')
    monkeypatch.setattr(publish_export, '_load_srt_entries', lambda _pid: [])
    monkeypatch.setattr(store, 'read', lambda _pid: {'source_meta': {}})
    calls, active, peak, lock = [], [0], [0], threading.Lock()

    def build(value, lines, strategy, **kw):
        with lock:
            calls.append(value['scenes'][0]['start'])
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return {'template': strategy.template}

    monkeypatch.setattr(packaging, 'build_packaging', build)
    clips = [{**_value(), 'scenes': [{**_value()['scenes'][0], 'start': float(n), 'end': n + 60.0}]} for n in range(6)]
    items = [(platform, clip) for clip in clips for platform in ('douyin', 'xiaohongshu')]  # same template twice
    cache = {}
    jobs._prefetch_packaging('p1', items, False, cache)
    assert sorted(calls) == [float(n) for n in range(6)] and peak[0] > 1
    assert jobs._apply_packaging('p1', clips[0], 'xiaohongshu', False, cache)['packaging'] == {'template': 'interview_zh'}
    assert len(calls) == 6  # served from the cache
