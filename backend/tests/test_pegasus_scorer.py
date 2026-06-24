"""Tests for the optional TwelveLabs Pegasus scoring backend (Step 3)."""

import os

import pytest

from backend.pipeline.pegasus_scorer import PegasusClipScorer

# ---- No-network unit tests -------------------------------------------------


def test_parse_result_extracts_score_and_reason():
    data = (
        '{"name":"highlight_score","schema":{"type":"object"},'
        '"score":8.5,"reason":"高信息密度，画面有张力"}'
    )
    score, reason = PegasusClipScorer._parse_result(data)
    assert score == 8.5
    assert reason == "高信息密度，画面有张力"


def test_parse_result_defaults_reason_when_missing():
    score, reason = PegasusClipScorer._parse_result('{"score":3}')
    assert score == 3
    assert reason == "无推荐理由"


def test_parse_result_raises_on_empty():
    with pytest.raises(ValueError):
        PegasusClipScorer._parse_result(None)


def test_parse_result_raises_without_score():
    with pytest.raises(ValueError):
        PegasusClipScorer._parse_result('{"reason":"x"}')


def test_missing_api_key_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("TWELVELABS_API_KEY", raising=False)
    video = tmp_path / "input.mp4"
    video.write_bytes(b"fake")
    with pytest.raises(ValueError):
        PegasusClipScorer(video, api_key=None)


def test_missing_video_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        PegasusClipScorer(tmp_path / "nope.mp4", api_key="dummy")


# ---- Live API test (skipped unless TWELVELABS_API_KEY is set) --------------


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("TWELVELABS_API_KEY"),
    reason="需要 TWELVELABS_API_KEY 才能调用真实的 Pegasus API",
)
def test_pegasus_scores_real_segment(tmp_path):
    """端到端：上传一段视频并用 Pegasus 评分。需要 ffmpeg 与有效的 API key。"""
    import subprocess

    video = tmp_path / "input.mp4"
    rc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=6:size=640x360:rate=24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        capture_output=True,
    ).returncode
    if rc != 0 or not video.exists():
        pytest.skip("ffmpeg 不可用，无法生成测试视频")

    scorer = PegasusClipScorer(video)
    clips = [{"id": 1, "start_time": "00:00:00,000", "end_time": "00:00:06,000"}]
    scored = scorer.score_clips(clips)
    assert "final_score" in scored[0]
    assert "recommend_reason" in scored[0]
    assert 0 <= scored[0]["final_score"] <= 10
