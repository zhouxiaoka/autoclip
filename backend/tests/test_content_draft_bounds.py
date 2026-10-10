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


def test_small_overlap_between_neighbours_is_kept(monkeypatch):
    clips = [
        {'generated_title': 'a', 'start_time_seconds': 0, 'end_time_seconds': 30, 'final_score': 0.5},
        {'generated_title': 'b', 'start_time_seconds': 28, 'end_time_seconds': 60, 'final_score': 0.6},
    ]
    result = _content(monkeypatch, clips, [(0.0, 31.0), (27.0, 60.0)])
    assert [(d['scenes'][0]['start'], d['scenes'][0]['end']) for d in result] == [(0.0, 31.0), (27.0, 60.0)]
