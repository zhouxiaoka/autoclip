"""Regression tests for 0-clip fallback protection in clip_finder and youtube_long."""
from __future__ import annotations

import json

from backend.pipeline import clip_finder
from backend.pipeline.quality import SHORT_MIN_CLIP_SEC, to_srt_time
from backend.services.studio import jobs


def _cue(start: float, end: float, text: str = "完整观点讲解内容") -> dict:
    return {"start_time": to_srt_time(start), "end_time": to_srt_time(end), "text": text}


def test_clip_finder_relaxes_min_clip_sec_instead_of_returning_zero_clips(tmp_path):
    """On a >8 min video, isolated 30s highlights must not all be dropped by the 60s tier floor."""
    # Sparse cues spanning 15 minutes, with two isolated 30s speech islands separated by long silence.
    srt_entries = [
        _cue(0, 30, "开场核心观点"),
        _cue(300, 330, "中段精彩案例"),
        _cue(890, 900, "结尾总结"),
    ]

    def fake_call(_prompt, _payload):
        return {
            "clips": [
                {"start": 0, "end": 0, "title": "开场核心观点", "reason": "信息密度高", "score": 0.9},
                {"start": 1, "end": 1, "title": "中段精彩案例", "reason": "案例很具体", "score": 0.85},
            ]
        }

    chosen = clip_finder.find_clips(
        srt_entries,
        fake_call,
        threshold=0.7,
        metadata_dir=tmp_path,
        window=clip_finder.CLOUD_WINDOW,
    )
    assert len(chosen) == 2
    assert all(c["duration_sec"] >= SHORT_MIN_CLIP_SEC for c in chosen)
    report = json.loads((tmp_path / "quality_report.json").read_text(encoding="utf-8"))
    assert report["clip_finder"]["refine"]["relaxed_min_clip_sec"] == SHORT_MIN_CLIP_SEC


def test_clip_finder_preserves_top_clips_when_all_below_threshold_and_short(tmp_path):
    """Combined 0-clip protection: isolated 25s picks scoring below threshold still yield clips."""
    srt_entries = [
        _cue(0, 25, "第一段干货"),
        _cue(360, 385, "第二段干货"),
        _cue(715, 720, "结尾总结"),
    ]

    def fake_call(_prompt, _payload):
        return {
            "clips": [
                {"start": 0, "end": 0, "title": "第一段干货", "reason": "观点清晰", "score": 0.42},
                {"start": 1, "end": 1, "title": "第二段干货", "reason": "案例完整", "score": 0.58},
            ]
        }

    chosen = clip_finder.find_clips(
        srt_entries,
        fake_call,
        threshold=0.85,
        metadata_dir=tmp_path,
        window=clip_finder.CLOUD_WINDOW,
    )
    assert len(chosen) == 2
    assert all(c["selected_by"] == "fallback" for c in chosen)
    report = json.loads((tmp_path / "quality_report.json").read_text(encoding="utf-8"))
    assert report["clip_finder"]["refine"]["relaxed_min_clip_sec"] == SHORT_MIN_CLIP_SEC
    assert report["clip_finder"]["selection"]["fallback_selected"] == 2


def test_youtube_long_extends_short_drafts_when_source_duration_is_long(monkeypatch):
    """When source duration >= 180s, youtube_long extends short picks instead of returning 0 clips."""
    monkeypatch.setattr(jobs, "_known_source_duration", lambda _video: 300.0)
    monkeypatch.setattr(
        jobs,
        "_content_drafts",
        lambda _pid, _plan, _video, _platforms: (
            [
                {
                    "id": "d1",
                    "title": "Opening take",
                    "scenes": [{"id": "s1", "label": "Opening take", "start": 10.0, "end": 70.0}],
                    jobs.SCORE_KEY: 0.85,
                },
                {
                    "id": "d2",
                    "title": "Deep dive",
                    "scenes": [{"id": "s2", "label": "Deep dive", "start": 200.0, "end": 260.0}],
                    jobs.SCORE_KEY: 0.9,
                },
            ],
            [],
            None,
        ),
    )
    monkeypatch.setattr(jobs, "_source_has_burned_subtitles", lambda _pid, _video: False)
    monkeypatch.setattr(jobs, "_apply_framing", lambda _pid, val, *_a, **_k: (val, "none"))
    monkeypatch.setattr(jobs, "_prefetch_packaging", lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, "_posts_for", lambda *_a, **_k: {})
    monkeypatch.setattr(jobs, "_apply_packaging", lambda _pid, val, *_a, **_k: val)

    skipped = []
    drafts, variants, _events, _cov = jobs._initial_derive(
        "p1",
        {"content_type": "talk", "preferences": {"goal": "content"}},
        "video.mp4",
        {"features": {}},
        ["youtube_long"],
        {"outro_enabled": False},
        skipped,
    )
    assert skipped == []
    assert len(variants) == 1
    assert variants[0]["strategy_id"] == "youtube_long"
    matched = next(d for d in drafts if d["id"] == variants[0]["draft_id"])
    assert sum(s["end"] - s["start"] for s in matched["scenes"]) >= 180
