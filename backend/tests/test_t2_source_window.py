"""T2: first-30-min source_window — planning duration, draft filter, SRT window."""
from pathlib import Path

import pysrt
import pytest

from backend.services.simple_pipeline_adapter import _apply_source_window_to_srt
from backend.services.studio import intelligence, jobs, planning
from backend.services.studio.models import ImportOptions, SourceWindow
from backend.tests.test_auto_vision_fallback import configure, isolated_offline_settings, source  # noqa: F401
from backend.tests.test_studio import root  # noqa: F401


def test_source_window_model_rejects_inverted():
    with pytest.raises(Exception):
        SourceWindow(start=100, end=50)


def test_planning_duration_uses_window(source, monkeypatch):
    configure(monkeypatch, 'unavailable', mode='subtitle')
    monkeypatch.setattr(intelligence, '_probe', lambda _v: {
        'duration': 5400.0, 'width': 1280, 'height': 720,
    })
    monkeypatch.setattr(planning, '_local_recommendation', lambda *a, **k: (
        None,
        planning.Recommendation(content_type='talk', goal='content', reason='访谈', confidence=0.8,
                                aspect='original', duration=30, suggested_goals=['content']),
    ))
    monkeypatch.setattr(planning, '_require_local_transcription', lambda *a, **k: None)
    monkeypatch.setattr(planning, '_subtitle_blockers', lambda *a, **k: (False, False))
    plan = planning.recommend(
        source,
        ImportOptions(auto_start=True, source_window=SourceWindow(start=0, end=1800)),
    )
    assert plan['source_duration'] == 1800.0
    assert plan['overrides']['source_window'] == {'start': 0.0, 'end': 1800.0}
    assert planning.planning_duration(5400.0, ImportOptions()) == 5400.0
    assert planning.planning_duration(5400.0, ImportOptions(source_window=SourceWindow(start=0, end=1800))) == 1800.0


def test_apply_source_window_to_srt_filters_and_shifts(tmp_path: Path):
    srt = tmp_path / 'full.srt'
    subs = pysrt.SubRipFile()
    for i, (s, e, text) in enumerate([
        (0, 2, 'early'),
        (100, 110, 'mid'),
        (2000, 2010, 'late'),
    ], start=1):
        item = pysrt.SubRipItem(index=i, start=pysrt.SubRipTime(seconds=s), end=pysrt.SubRipTime(seconds=e), text=text)
        subs.append(item)
    subs.save(str(srt), encoding='utf-8')

    out = _apply_source_window_to_srt(srt, 0, 1800, shift=0.0, dest=tmp_path / 'windowed.srt')
    kept = pysrt.open(str(out), encoding='utf-8')
    texts = [item.text for item in kept]
    assert texts == ['early', 'mid']
    assert 'late' not in texts

    # Cut starting at 90s: relative ASR times 10–20 map to absolute 100–110.
    cut = tmp_path / 'cut.srt'
    cut_subs = pysrt.SubRipFile()
    cut_subs.append(pysrt.SubRipItem(
        index=1,
        start=pysrt.SubRipTime(seconds=10),
        end=pysrt.SubRipTime(seconds=20),
        text='shifted',
    ))
    cut_subs.save(str(cut), encoding='utf-8')
    shifted = _apply_source_window_to_srt(cut, 90, 1800, shift=90.0, dest=tmp_path / 'shifted.srt')
    item = pysrt.open(str(shifted), encoding='utf-8')[0]
    assert abs(item.start.ordinal / 1000.0 - 100.0) < 0.05
    assert abs(item.end.ordinal / 1000.0 - 110.0) < 0.05


def test_content_drafts_filters_outside_window(monkeypatch, tmp_path: Path):
    video = tmp_path / 'input.mp4'
    video.write_bytes(b'x')

    clips = [
        {'start_time_seconds': 10, 'end_time_seconds': 40, 'generated_title': 'in', 'recommend_reason': 'a'},
        {'start_time_seconds': 2000, 'end_time_seconds': 2030, 'generated_title': 'out', 'recommend_reason': 'b'},
        {'start_time_seconds': 1700, 'end_time_seconds': 1900, 'generated_title': 'edge', 'recommend_reason': 'c'},
    ]

    monkeypatch.setattr(jobs, 'run_content', lambda *a, **k: clips)
    monkeypatch.setattr(jobs, '_complete_thought_bounds', lambda _pid, ranges: list(ranges))
    monkeypatch.setattr(intelligence, '_probe', lambda _v: {'duration': 4000.0})
    monkeypatch.setattr(intelligence, 'validate_scenes', lambda *a, **k: None)

    plan = {
        'recommended_analysis': 'subtitle',
        'preferences': {'goal': 'content', 'language': 'source', 'aspect': 'original', 'duration': 30},
        'overrides': {'source_window': {'start': 0, 'end': 1800}},
    }
    drafts = jobs._content_drafts('p-t2', plan, video, platforms=['douyin'])
    titles = [d['title'] for d in drafts]
    assert 'in' in titles
    assert 'out' not in titles
    assert 'edge' in titles
    edge = next(d for d in drafts if d['title'] == 'edge')
    assert edge['scenes'][0]['end'] <= 1800
