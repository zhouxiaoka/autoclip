"""出片质量：时长画像、时间线校正、评分对齐与筛选兜底（不调模型）"""
import json
import sys
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.pipeline.quality import (
    align_scores, excerpt_between, profile_for, refine_timeline, select_clips,
    to_seconds, to_srt_time,
)


def _cue(s, e, text="x"):
    return {"start_time": to_srt_time(s), "end_time": to_srt_time(e), "text": text}


def test_profile_short_video_does_not_use_podcast_minimums():
    p = profile_for(5 * 60)
    assert p.tier == "short"
    assert p.min_clip_sec <= 30
    assert p.max_clip_sec <= 180
    assert p.topics_hint[1] <= 8
    hint = p.prompt_hint()
    assert "本次任务参数" in hint and "5 分" in hint
    assert "90 秒" in hint  # 明确覆盖旧规则


def test_profile_long_keeps_podcast_scale():
    p = profile_for(72 * 60)
    assert p.tier == "long"
    assert p.min_clip_sec >= 60
    assert p.topics_hint[0] >= 6


def test_refine_snaps_to_cue_and_drops_too_short():
    # 0–80s，每条 cue 2 秒。短视频档 min=20s。
    cues = [_cue(i, i + 2, f"c{i}") for i in range(0, 80, 2)]
    items = [
        {"outline": "可延长", "start_time": "00:00:20,200", "end_time": "00:00:28,000", "content": ["b"]},
        {"outline": "重叠甲", "start_time": "00:00:40,000", "end_time": "00:01:10,000", "content": ["c"]},
        {"outline": "重叠乙", "start_time": "00:00:50,000", "end_time": "00:01:08,000", "content": ["d"]},
        # 片尾 3 秒、与前一段空档 > 5s、后面没 cue 可延 → 丢弃
        {"outline": "太短", "start_time": "00:01:17,000", "end_time": "00:01:19,400", "content": ["a"]},
    ]
    out, report = refine_timeline(items, cues, profile_for(300))
    titles = [_t(x) for x in out]
    assert "太短" not in titles
    assert any(d.get("outline") == "太短" for d in report["dropped"])
    extend = next(x for x in out if x["outline"] == "可延长")
    assert extend["duration_sec"] >= 20
    assert "snap" in extend["refine"]["ops"]
    assert report["output"] <= 3
    assert any(m.get("absorbed") == "重叠乙" for m in report["merged"])
    for x in out:
        assert x["duration_sec"] >= 20
        assert abs(to_seconds(x["start_time"]) % 2) < 1e-6


def _t(x):
    o = x.get("outline")
    return o if isinstance(o, str) else str(o)


def test_merging_a_shifted_pick_does_not_drag_the_kept_clip_back_into_its_neighbour():
    # 小重叠把后一段的起点推到下一条 cue，它原本的区间仍压在前一段上。
    # 这时再合并，起点若仍取 min 就会越回前一段，导出的两条切片互相重叠。
    cues = [_cue(i, i + 2, f"c{i}") for i in range(0, 200, 2)]
    items = [
        {"outline": "前一段", "start_time": "00:00:10,000", "end_time": "00:00:40,000"},
        {"outline": "后一段", "start_time": "00:00:39,000", "end_time": "00:00:50,000"},
        {"outline": "再后一段", "start_time": "00:00:30,000", "end_time": "00:01:30,000"},
    ]
    out, _ = refine_timeline(items, cues, profile_for(200))
    spans = [(to_seconds(x["start_time"]), to_seconds(x["end_time"])) for x in out]
    assert spans == sorted(spans)
    for (_, previous_end), (current_start, _) in pairwise(spans):
        assert current_start >= previous_end


def test_merged_clips_never_overlap_even_when_picks_arrive_out_of_order():
    # 随机但固定的模型挑段：任何两条输出的时间轴都不允许互相覆盖（前端按顺序拼合集）。
    import random
    rng = random.Random(7)
    for _ in range(60):
        cues, cursor = [], 0.0
        for i in range(40):
            length = rng.choice([0.8, 1.5, 2.0, 3.0])
            cues.append(_cue(cursor, cursor + length, f"c{i}"))
            cursor += length + rng.choice([0.0, 0.1, 1.0, 6.0])
        items = []
        for i in range(rng.choice([3, 6, 10])):
            start = rng.uniform(0, cursor * 0.7)
            items.append({"outline": f"o{i}", "start_time": to_srt_time(start),
                          "end_time": to_srt_time(start + rng.choice([2.0, 12.0, 25.0, 40.0, 200.0]))})
        out, _ = refine_timeline(items, cues, profile_for(cursor))
        spans = [(to_seconds(x["start_time"]), to_seconds(x["end_time"])) for x in out]
        assert all(end > start for start, end in spans)
        for (_, previous_end), (current_start, _) in pairwise(spans):
            assert current_start >= previous_end


def test_align_scores_falls_back_when_count_mismatch():
    clips = [
        {"outline": "甲", "id": "1"},
        {"outline": "乙", "id": "2"},
        {"outline": "丙", "id": "3"},
    ]
    llm = [{"outline": "乙", "final_score": 0.9, "recommend_reason": "好"}]
    scored, stats = align_scores(clips, llm)
    assert stats["matched"] == 1 and stats["fallback"] == 2
    by = {c["outline"]: c for c in scored}
    assert by["乙"]["final_score"] == 0.9
    assert by["甲"]["score_source"] == "fallback"
    assert by["甲"]["final_score"] == 0.5


def test_align_scores_normalizes_0_10_scale():
    clips = [{"outline": "甲"}]
    scored, _ = align_scores(clips, [{"outline": "甲", "final_score": 8, "recommend_reason": "x"}])
    assert scored[0]["final_score"] == 0.8


def test_select_clips_keeps_top_k_when_all_below_threshold():
    scored = [
        {"id": "1", "final_score": 0.4, "outline": "a"},
        {"id": "2", "final_score": 0.3, "outline": "b"},
        {"id": "3", "final_score": 0.2, "outline": "c"},
    ]
    p = profile_for(300)  # min_keep=2
    chosen, info = select_clips(scored, 0.7, p)
    assert len(chosen) == 2
    assert info["fallback_selected"] == 2
    assert all(c["selected_by"] == "fallback" for c in chosen)
    assert {c["id"] for c in chosen} == {"1", "2"}


def test_excerpt_between_truncates():
    cues = [_cue(0, 2, "一二三四五六七八九十" * 20), _cue(2, 4, "后段")]
    text = excerpt_between(cues, 0, 3, max_chars=20)
    assert len(text) == 20


def test_to_srt_time_carries_into_minutes_and_hours():
    # 75.1 - 15.1 == 59.99999999999999（slice_srt 里平移时间轴就会得到这种值）
    assert to_srt_time(75.1 - 15.1) == "00:01:00,000"
    assert to_srt_time(3599.9999) == "01:00:00,000"
    assert to_srt_time(59.9994) == "00:00:59,999"
    assert to_srt_time(3723.5) == "01:02:03,500"
    assert to_srt_time(-1) == "00:00:00,000"
    for sec in (0.0, 1.25, 59.5, 61.001, 3599.999, 7384.12):
        assert to_seconds(to_srt_time(sec)) == round(sec, 3)
