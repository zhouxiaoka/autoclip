"""Regression cases for #197 / #198 / #195 / #217; no network or model calls."""
import json
from types import SimpleNamespace
import pytest
from backend.pipeline.quality import profile_for, refine_timeline, to_srt_time
from backend.pipeline.step2_timeline import TimelineExtractor
from backend.utils.text_processor import TextProcessor


def cue(s, e):
    return {"start_time": to_srt_time(s), "end_time": to_srt_time(e), "text": "speech"}


def test_adjacent_short_topics_can_merge_before_being_dropped():
    cues = [cue(i, i + 5) for i in range(0, 30, 5)]
    items = [dict(outline=str(i), start_time=to_srt_time(i), end_time=to_srt_time(i + 10)) for i in (0, 10, 20)]
    out, report = refine_timeline(items, cues, profile_for(30))
    assert len(out) == 1
    assert out[0]["duration_sec"] == 30
    assert not report["dropped"]


def test_isolated_short_topics_are_not_merged_across_long_silence():
    cues = [cue(0, 5), cue(30, 35)]
    items = [dict(outline=str(i), start_time=to_srt_time(i), end_time=to_srt_time(i + 5)) for i in (0, 30)]
    out, _ = refine_timeline(items, cues, profile_for(300))
    assert out == []


def extractor(tmp_path):
    obj = TimelineExtractor.__new__(TimelineExtractor)
    obj.metadata_dir = tmp_path
    obj.text_processor = TextProcessor()
    obj.llm_client = SimpleNamespace(parse_json_response=json.loads, _validate_json_structure=lambda x: True)
    return obj


@pytest.mark.parametrize("start,end", [("00:00:01.500", "00:00:25.5"), ("00:01,5", "00:25,500"), ("00:00:01", "00:00:25")])
def test_standard_timestamp_variants_are_normalized(tmp_path, start, end):
    out = extractor(tmp_path)._parse_and_validate_response(json.dumps([dict(outline="topic", start_time=start, end_time=end)]), "00:00:00,000", "00:00:30,000", 0)
    assert len(out) == 1
    assert out[0]["start_time"] == ("00:00:01,000" if start == "00:00:01" else "00:00:01,500")
    assert out[0]["end_time"] == ("00:00:25,000" if end == "00:00:25" else "00:00:25,500")


@pytest.mark.parametrize("start,end", [("00:00:40,000", "00:00:50,000"), ("00:00:20,000", "00:00:10,000"), ("00:60:01,000", "00:61:01,000"), ("NaN", "00:00:25,000")])
def test_invalid_or_outside_chunk_ranges_are_rejected(tmp_path, start, end):
    assert extractor(tmp_path)._parse_and_validate_response(json.dumps([dict(outline="topic", start_time=start, end_time=end)]), "00:00:00,000", "00:00:30,000", 0) == []


def test_full_extraction_normalizes_and_merges_model_topics(tmp_path):
    obj = extractor(tmp_path)
    obj.timeline_prompt = "Extract topics"
    obj.srt_chunks_dir = tmp_path / "step1_srt_chunks"
    obj.timeline_chunks_dir = tmp_path / "step2_timeline_chunks"
    obj.llm_raw_output_dir = tmp_path / "step2_llm_raw_output"
    obj.srt_chunks_dir.mkdir()
    cues = [dict(cue(i, i + 5), index=i // 5 + 1) for i in range(0, 30, 5)]
    (obj.srt_chunks_dir / "chunk_0.json").write_text(json.dumps(cues))
    response = json.dumps([dict(outline=str(i), start_time=to_srt_time(i).replace(",", "."), end_time=to_srt_time(i + 10).replace(",", ".")) for i in (0, 10, 20)])
    obj.llm_client.call_with_retry = lambda *a, **k: response
    out = obj.extract_timeline([dict(title="topic", subtopics=[], chunk_index=0)])
    assert len(out) == 1
    assert out[0]["start_time"] == "00:00:00,000"
    assert out[0]["end_time"] == "00:00:30,000"
    assert out[0]["duration_sec"] == 30
    assert json.loads((tmp_path / "quality_report.json").read_text())["step2"]["output"] == 1


def test_short_source_remains_below_existing_minimum():
    # This fix does not silently lower the product's 20-second minimum.
    out, report = refine_timeline([dict(outline="short", **{k: v for k, v in cue(0, 10).items() if k != "text"})], [cue(0, 10)], profile_for(10))
    assert out == []
    assert len(report["dropped"]) == 1


def test_merge_does_not_exceed_maximum():
    from dataclasses import replace
    profile = replace(profile_for(300), min_clip_sec=20, max_clip_sec=25)
    out, _ = refine_timeline([dict(outline=str(i), start_time=to_srt_time(i), end_time=to_srt_time(i + 15)) for i in (0, 15)], [cue(0, 15), cue(15, 30)], profile)
    assert out == []


def test_partial_overlap_is_clamped_to_chunk(tmp_path):
    out = extractor(tmp_path)._parse_and_validate_response(json.dumps([dict(outline="topic", start_time="00:00:05.5", end_time="00:00:40")]), "00:00:10,000", "00:00:30,000", 1)
    assert out[0]["start_time"] == "00:00:10,000"
    assert out[0]["end_time"] == "00:00:30,000"
