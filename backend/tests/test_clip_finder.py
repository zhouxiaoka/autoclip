"""One-pass clip finding: windows, validation, dedupe and the legacy titled-clip shape (no model calls)."""
import pytest

from backend.pipeline import clip_finder
from backend.pipeline.quality import to_srt_time


def _entries(minutes: float, row_sec: float = 5.0):
    count = int(minutes * 60 / row_sec)
    return [{'index': i + 1, 'start_time': to_srt_time(i * row_sec), 'end_time': to_srt_time((i + 1) * row_sec), 'text': f'sentence {i}.'}
            for i in range(count)]


def test_short_videos_are_one_window_and_long_ones_overlap():
    rows = [{'start': i * 5.0, 'end': (i + 1) * 5.0, 'text': 'x'} for i in range(int(150 * 60 / 5))]  # 2.5 h
    spans = clip_finder.windows(rows)
    assert len(spans) == 3 and spans[0][0] == 0 and spans[-1][1] == len(rows) - 1
    for (_, last), (first, _) in zip(spans, spans[1:]):
        assert first < last and rows[last]['end'] - rows[first]['start'] >= clip_finder.OVERLAP_SEC - 5
    assert clip_finder.windows(rows[:200]) == [(0, 199)]


def test_clips_come_back_in_the_legacy_titled_shape(tmp_path):
    sent = []

    def call(prompt, data):
        sent.append((prompt, data))
        return {'clips': [{'start': 10, 'end': 40, 'title': '好的投资人像飞行教练', 'reason': '比喻精准，一句话讲透投资人的价值', 'score': 0.9},
                          {'start': 60, 'end': 95, 'title': '第二段', 'reason': '理由', 'score': 0.8},
                          {'start': 5, 'end': 3, 'title': '倒序无效', 'score': 0.9},
                          {'start': 100, 'end': 101, 'title': '太短', 'score': 0.9}]}

    clips = clip_finder.find_clips(_entries(12), call, threshold=0.7, metadata_dir=tmp_path)
    assert [c['generated_title'] for c in clips] == ['好的投资人像飞行教练', '第二段']
    first = clips[0]
    assert first['start_time'] == '00:00:50,000' and first['final_score'] == 0.9 and first['recommend_reason']
    assert len(sent) == 1 and sent[0][1]['rows'].startswith('0|0:00|sentence 0.')  # compact rows, no SRT timestamps
    assert (tmp_path / 'step4_titles.json').exists()


def test_the_same_moment_picked_in_two_windows_is_kept_once():
    picks = [{'start_row': 10, 'end_row': 40, 'title': 'a', 'reason': '', 'score': 0.8},
             {'start_row': 12, 'end_row': 42, 'title': 'b', 'reason': '', 'score': 0.9},
             {'start_row': 60, 'end_row': 90, 'title': 'c', 'reason': '', 'score': 0.7}]
    rows = [{'start': i * 5.0, 'end': (i + 1) * 5.0} for i in range(100)]
    assert [c['title'] for c in clip_finder._dedupe(picks, rows)] == ['b', 'c']


def test_a_bad_response_is_retried_with_the_reason_then_fails_for_fallback():
    sent = []

    def broken(prompt, data):
        sent.append(data)
        return {'oops': True}

    with pytest.raises(clip_finder.ClipFinderError):
        clip_finder.find_clips(_entries(12), broken, threshold=0.7)
    assert len(sent) == 2 and 'previous_error' in sent[1]
