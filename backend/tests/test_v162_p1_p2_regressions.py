"""Regression tests for v1.6.2 P1 & P2 success-rate and clip-completion fixes."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.services.studio import intelligence, jobs, preflight
from backend.utils import download_failure_observe, download_recovery
from backend.utils.llm_client import LLMClient, strip_thinking_blocks


def test_thinking_model_json_extraction_strips_think_and_thought_blocks():
    client = LLMClient.__new__(LLMClient)

    # Qwen 3.5 / DeepSeek reasoning: <think> contains brackets [1, 2] before fenced JSON
    qwen_raw = (
        "<think>\nLet's compare segments [1, 2] and pick the strongest clip.\n</think>\n"
        "Here is the result:\n"
        "```json\n"
        '[{"outline": "Core argument", "start_time": "00:00:10", "end_time": "00:01:05"}]\n'
        "```\n"
        "Hope this helps [note]."
    )
    parsed_qwen = client.parse_json_response(qwen_raw)
    assert isinstance(parsed_qwen, list)
    assert parsed_qwen[0]["outline"] == "Core argument"

    # Gemma 4 / Gemini: <thought>...</thought> before raw JSON with trailing prose brackets
    gemma_raw = '<thought>Check {foo} first.</thought>\n{"clips": [{"id": 1}]}\nDone [ok].'
    parsed_gemma = client.parse_json_response(gemma_raw)
    assert parsed_gemma == {"clips": [{"id": 1}]}
    assert intelligence.decode_json('<thought>Reasoning</thought>\n{"goal": "highlight"}') == {"goal": "highlight"}

    # Unclosed leading <think> tag before JSON
    assert strip_thinking_blocks('<think>{"a": 1}') == '{"a": 1}'


def test_transcription_empty_falls_back_to_visual_when_auto_and_vision_allowed(tmp_path):
    video = tmp_path / "gameplay.mp4"
    video.write_bytes(b"fake")
    plan = {
        "recommended_analysis": "subtitle",
        "analysis_preferences": {"analysis_mode": "auto"},
        "preferences": {"goal": "highlight", "language": "source", "aspect": "original", "duration": 30},
        "overrides": {"goal": "auto"},
    }
    fake_event = type("Evt", (), {"model_dump": lambda self: {"start": 5, "end": 25}})()
    fake_drafts = [{"id": "d1", "title": "Highlight", "scenes": [{"id": "s1", "start": 5, "end": 25}]}]

    with (
        patch.object(
            jobs,
            "run_content",
            side_effect=jobs.ContentPipelineFailure("SUBTITLE", "empty", code="transcription_empty"),
        ),
        patch.object(intelligence, "_probe", return_value={"duration": 180.0}),
        patch.object(intelligence, "source_frame_analysis_allowed", return_value=True),
        patch.object(intelligence, "ready", return_value=True),
        patch.object(jobs, "analyze", return_value=([fake_event], {"frames": 4})) as mock_analyze,
        patch.object(jobs, "make_drafts", return_value=fake_drafts),
    ):
        result = jobs._content_drafts("proj-1", plan, video, platforms=("douyin",))

    assert mock_analyze.called
    drafts, events, coverage = result
    assert drafts == fake_drafts
    assert events == [{"start": 5, "end": 25}]
    assert coverage == {"frames": 4}

    # Explicit subtitle mode must NOT fall back to visual
    subtitle_plan = {**plan, "analysis_preferences": {"analysis_mode": "subtitle"}}
    with (
        patch.object(
            jobs,
            "run_content",
            side_effect=jobs.ContentPipelineFailure("SUBTITLE", "empty", code="transcription_empty"),
        ),
        patch.object(intelligence, "_probe", return_value={"duration": 180.0}),
        patch.object(intelligence, "source_frame_analysis_allowed", return_value=True),
    ):
        with pytest.raises(jobs.ContentPipelineFailure) as exc_info:
            jobs._content_drafts("proj-1", subtitle_plan, video, platforms=("douyin",))
        assert exc_info.value.code == "transcription_empty"


def test_download_recovery_and_error_classification_p1():
    # New yt-dlp error classifications reduce opaque `unexpected` errors
    assert download_failure_observe.observe_download_failure("ERROR: Use --cookies-from-browser for authentication")["code"] == "source_blocked"
    assert download_failure_observe.observe_download_failure("ERROR: Sign in to view this video")["code"] == "source_blocked"
    assert download_failure_observe.observe_download_failure("ERROR: Incomplete YouTube ID abc")["code"] == "source_not_found"
    assert download_failure_observe.observe_download_failure("ERROR: Connection refused by peer")["code"] == "connection"
    assert download_failure_observe.observe_download_failure("ERROR: Incomplete read (1024 bytes)")["code"] == "connection"

    # YouTube format fallback triggers on 503 and empty downloaded file
    seen_formats = []

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            seen_formats.append(self.opts.get("format"))
            if len(seen_formats) == 1:
                raise download_recovery.yt_dlp.utils.DownloadError("ERROR: The downloaded file is empty")
            return 0

    with patch.object(download_recovery.yt_dlp, "YoutubeDL", FakeYDL):
        assert download_recovery.download_with_recovery("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {"format": "best"}) == 0
    assert len(seen_formats) == 2
    assert "m3u8" in seen_formats[1]


def test_extended_video_extensions_in_studio_and_preflight(tmp_path):
    raw = tmp_path / "proj-ext" / "raw"
    raw.mkdir(parents=True)
    m4v = raw / "input.m4v"
    m4v.write_bytes(b"video")

    with patch("backend.core.path_utils.get_project_raw_directory", return_value=raw):
        inputs = preflight.project_inputs("proj-ext")
    assert inputs is not None
    assert inputs.video == m4v

    # Verify studio.py accepts .m4v/.flv/.ts/.wmv and strips whitespace on URLs
    studio_src = Path("backend/api/v1/studio.py").read_text(encoding="utf-8")
    for ext in (".m4v", ".flv", ".ts", ".wmv"):
        assert f"'{ext}'" in studio_src
    assert "url = url.strip()" in studio_src
