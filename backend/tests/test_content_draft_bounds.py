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
