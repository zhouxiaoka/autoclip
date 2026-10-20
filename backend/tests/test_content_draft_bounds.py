"""Transcript/video duration mismatch cannot discard valid clips in the automatic batch."""
from backend.services.studio import jobs


def test_clamp_the_tail_and_skip_invalid_ranges_without_losing_other_clips(monkeypatch):
    monkeypatch.setattr(jobs, 'run_content', lambda *_: [
        {'generated_title': 'valid', 'start_time_seconds': 10, 'end_time_seconds': 70},
        {'generated_title': 'tail', 'start_time_seconds': 70, 'end_time_seconds': 101},
        {'generated_title': 'outside', 'start_time_seconds': 105, 'end_time_seconds': 120},
    ])
    monkeypatch.setattr(jobs, '_complete_thought_bounds', lambda _, bounds: bounds)
    monkeypatch.setattr(jobs.intelligence, '_probe', lambda _: {'duration': 100})
    result = jobs._content_drafts('p', {'preferences': {'goal': 'content'}}, 'video.mp4')
    assert [draft['title'] for draft in result] == ['valid', 'tail']
    assert [draft['scenes'][0]['end'] for draft in result] == [70, 100]


def test_content_drafts_keep_the_existing_reason_on_the_scene(monkeypatch):
    monkeypatch.setattr(jobs, 'run_content', lambda *_: [
        {'generated_title': 'kept', 'start_time_seconds': 1, 'end_time_seconds': 20, 'recommend_reason': '完整讲完一个例子' + '。' * 2000},
    ])
    monkeypatch.setattr(jobs, '_complete_thought_bounds', lambda _, bounds: bounds)
    monkeypatch.setattr(jobs.intelligence, '_probe', lambda _: {'duration': 100})
    result = jobs._content_drafts('p', {'preferences': {'goal': 'content'}}, 'video.mp4')
    assert result[0]['scenes'][0]['evidence'].startswith('完整讲完一个例子')
    assert len(result[0]['scenes'][0]['evidence']) == 1000


def _content(monkeypatch, clips, bounds):
    monkeypatch.setattr(jobs, 'run_content', lambda *_: clips)
    monkeypatch.setattr(jobs, '_complete_thought_bounds', lambda _, picked: bounds)
    monkeypatch.setattr(jobs.intelligence, '_probe', lambda _: {'duration': 600})
    return jobs._content_drafts('p', {'preferences': {'goal': 'content'}}, 'video.mp4')


def test_clips_polished_onto_the_same_span_do_not_become_duplicate_drafts(monkeypatch):
    # RC156 Win QA #7: both clips came back as 0.0-57.766s.
    clips = [
        {'generated_title': 'admits', 'start_time_seconds': 0, 'end_time_seconds': 28.94, 'final_score': 0.8},
        {'generated_title': 'rebound', 'start_time_seconds': 29.36, 'end_time_seconds': 58.88, 'final_score': 0.9},
    ]
    result = _content(monkeypatch, clips, [(0.0, 57.766), (0.0, 57.766)])
    # The polished span already holds both thoughts: one draft, the higher-scored one.
    assert [(d['title'], d['scenes'][0]['start'], d['scenes'][0]['end']) for d in result] == [('rebound', 0.0, 57.766)]


def test_a_lower_scored_clip_falls_back_to_its_own_range_when_that_is_distinct(monkeypatch):
    clips = [
        {'generated_title': 'first', 'start_time_seconds': 0, 'end_time_seconds': 30, 'final_score': 0.4},
        {'generated_title': 'second', 'start_time_seconds': 40, 'end_time_seconds': 70, 'final_score': 0.9},
    ]
    # Polishing pulled the first clip deep into the second one.
    result = _content(monkeypatch, clips, [(0.0, 65.0), (40.0, 70.0)])
    assert [(d['title'], d['scenes'][0]['start'], d['scenes'][0]['end']) for d in result] == [('first', 0, 30), ('second', 40.0, 70.0)]


def test_overlapping_clips_keep_only_the_higher_scored_draft(monkeypatch):
    clips = [
        {'generated_title': 'low', 'start_time_seconds': 0, 'end_time_seconds': 50, 'final_score': 0.4},
        {'generated_title': 'high', 'start_time_seconds': 5, 'end_time_seconds': 55, 'final_score': 0.9},
        {'generated_title': 'other', 'start_time_seconds': 100, 'end_time_seconds': 150, 'final_score': 0.1},
    ]
    result = _content(monkeypatch, clips, [(0.0, 55.0), (0.0, 55.0), (100.0, 150.0)])
    assert [d['title'] for d in result] == ['high', 'other']


def _span(start, end, score=0.5, title='片段'):
    return {'id': f'{start:g}-{end:g}', 'title': title, 'language': 'source', 'aspect': 'landscape',
            'scenes': [{'id': 's', 'label': title, 'start': start, 'end': end, 'evidence': '例子'}],
            jobs.SCORE_KEY: score}


def test_short_picks_on_a_long_source_gain_one_span_of_at_least_180s():
    drafts = [_span(10, 50, 0.4, '甲'), _span(80, 120, 0.9, '乙'), _span(200, 240, 0.5, '丙')]
    out = jobs._ensure_long_coverage(drafts, 531, 180)
    assert [draft['title'] for draft in out[:3]] == ['甲', '乙', '丙']
    added = out[-1]
    start, end = added['scenes'][0]['start'], added['scenes'][0]['end']
    assert added[jobs.LONG_ONLY_KEY] is True
    assert end - start >= 180 and 0 <= start and end <= 531


def test_adjacent_short_picks_are_merged_until_the_span_reaches_180s():
    drafts = [_span(0, 40, 0.2), _span(50, 90, 0.3), _span(100, 140, 0.8, '合并')]
    added = jobs._ensure_long_coverage(drafts, 200, 180)[-1]
    start, end = added['scenes'][0]['start'], added['scenes'][0]['end']
    assert added['title'] == '合并'
    assert end - start >= 180 and end <= 200


def test_a_clip_near_the_end_grows_backward_inside_the_source():
    added = jobs._ensure_long_coverage([_span(500, 530)], 531, 180)[-1]
    start, end = added['scenes'][0]['start'], added['scenes'][0]['end']
    assert end - start >= 180 and start >= 0 and end <= 531


def test_a_source_shorter_than_180s_is_not_stretched():
    drafts = [_span(0, 40)]
    assert jobs._ensure_long_coverage(drafts, 90, 180) is drafts


def test_an_existing_long_draft_is_left_alone():
    drafts = [_span(0, 200, 0.2), _span(210, 250, 0.9)]
    assert jobs._ensure_long_coverage(drafts, 531, 180) is drafts


def test_youtube_long_passes_its_minimum_into_content_selection(monkeypatch):
    seen = []
    monkeypatch.setattr(jobs, 'run_content', lambda *args: seen.append(args) or [
        {'generated_title': '已够长', 'start_time_seconds': 0, 'end_time_seconds': 200},
    ])
    monkeypatch.setattr(jobs, '_complete_thought_bounds', lambda _, bounds: bounds)
    monkeypatch.setattr(jobs.intelligence, '_probe', lambda _: {'duration': 600})
    jobs._content_drafts('p', {'preferences': {'goal': 'content'}}, 'video.mp4', ['youtube_long', 'douyin'])
    assert seen == [('p', 'video.mp4', 180, 'YouTube 横屏')]


def test_short_platforms_do_not_pass_a_long_minimum(monkeypatch):
    seen = []
    monkeypatch.setattr(jobs, 'run_content', lambda *args: seen.append(args) or [
        {'generated_title': '短', 'start_time_seconds': 0, 'end_time_seconds': 30},
    ])
    monkeypatch.setattr(jobs, '_complete_thought_bounds', lambda _, bounds: bounds)
    monkeypatch.setattr(jobs.intelligence, '_probe', lambda _: {'duration': 600})
    jobs._content_drafts('p', {'preferences': {'goal': 'content'}}, 'video.mp4', ['douyin', 'bilibili'])
    assert seen == [('p', 'video.mp4')]


def test_small_overlap_between_neighbours_is_kept(monkeypatch):
    clips = [
        {'generated_title': 'a', 'start_time_seconds': 0, 'end_time_seconds': 30, 'final_score': 0.5},
        {'generated_title': 'b', 'start_time_seconds': 28, 'end_time_seconds': 60, 'final_score': 0.6},
    ]
    result = _content(monkeypatch, clips, [(0.0, 31.0), (27.0, 60.0)])
    assert [(d['scenes'][0]['start'], d['scenes'][0]['end']) for d in result] == [(0.0, 31.0), (27.0, 60.0)]
