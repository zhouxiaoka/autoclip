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


def test_clip_finder_accepts_english_titles_and_string_row_indices_for_english_video():
    from backend.pipeline import clip_finder
    from backend.pipeline.quality import to_srt_time

    entries = [
        {"index": i + 1, "start_time": to_srt_time(i * 5.0), "end_time": to_srt_time((i + 1) * 5.0), "text": f"English line {i}."}
        for i in range(120)
    ]
    calls = []

    def fake_call(prompt, payload):
        calls.append(payload)
        return {
            "clips": [
                {"start": "10", "end": 25.0, "title": "Why Startups Fail Early", "reason": "Clear punchline", "score": 0.9},
                {"start_row": "40", "end_row": "45", "title": "Twenty-five second insight", "reason": "Tight point", "score": 0.85},
                {"start": 100, "end": 120, "title": "End-of-window clamp", "reason": "Off-by-one end", "score": 0.8},
            ]
        }

    clips = clip_finder.find_clips(entries, fake_call, threshold=0.7)
    assert len(calls) == 1, "English video with English titles must succeed on first pass without retrying"
    assert len(clips) == 3
    assert clips[0]["generated_title"] == "Why Startups Fail Early"


def test_gemini_default_model_404_fallback_and_thinking_budget():
    import io
    import json
    import requests
    from backend.core import job_budget, llm_providers, model_catalog

    assert model_catalog.default_model_for("gemini") == "gemini-2.5-flash"
    provider = llm_providers.GeminiProvider("AIza-test-key", model_name="gemini-3.8-flash")
    assert llm_providers.GeminiProvider("AIza-test-key").model_name == "gemini-2.5-flash"

    seen = []

    def fake_post(url, headers=None, json=None, auth=None, timeout=None, stream=False):
        seen.append((url, json))
        resp = requests.Response()
        resp.url = url
        if "gemini-3.8-flash" in url:
            resp.status_code = 404
            resp.raw = io.BytesIO(b'{"error":{"message":"model not found"}}')
        else:
            resp.status_code = 200
            resp.raw = io.BytesIO(
                b'{"candidates":[{"content":{"parts":[{"text":"ok"}]},"finishReason":"STOP"}]}'
            )
        return resp

    with patch.object(requests, "post", side_effect=fake_post), job_budget.bound_clip_job():
        res = provider.call("hello")

    assert res.content == "ok"
    assert res.model == "gemini-2.5-flash"
    assert len(seen) == 2
    assert "gemini-3.8-flash" in seen[0][0]
    assert "gemini-2.5-flash" in seen[1][0]
    assert seen[1][1]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_ollama_thinking_disabled_and_job_budget_legacy_fallback():
    from backend.core import job_budget, llm_providers

    req = llm_providers._ollama_thinking_chat_kwargs(
        "http://127.0.0.1:11434/v1",
        {"model": "qwen3.5:4b", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert req["extra_body"]["think"] is False
    stripped = llm_providers._strip_thinking_extra_body(req)
    assert stripped is not None and "extra_body" not in stripped

    # Legacy settings fallback when ai_model_settings.load() returns None
    fake_mgr = type("Mgr", (), {"settings": {"llm_provider": "openai", "openai_base_url": "http://127.0.0.1:11434/v1"}})()
    with (
        patch("backend.services.ai_model_settings.load", return_value=None),
        patch("backend.core.llm_manager.get_llm_manager", return_value=fake_mgr),
    ):
        assert job_budget._is_local_analysis_provider() is True


def test_wave2_gemini_native_root_and_vision_404_and_thinking_budget():
    import io
    import json
    import urllib.error
    from backend.core import gemini_transport

    assert gemini_transport.native_root("https://generativelanguage.googleapis.com") == "https://generativelanguage.googleapis.com/v1beta"
    assert gemini_transport.native_root("https://generativelanguage.googleapis.com/v1beta/openai/v1") == "https://generativelanguage.googleapis.com/v1beta"
    assert gemini_transport.native_root("https://generativelanguage.googleapis.com/v1beta/openai/") == "https://generativelanguage.googleapis.com/v1beta"

    seen = []

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=None):
        seen.append((req.full_url, json.loads(req.data.decode("utf-8"))))
        if "gemini-3.8-flash" in req.full_url:
            raise urllib.error.HTTPError(
                req.full_url, 404, "Not Found", {},
                io.BytesIO(b'{"error":{"status":"NOT_FOUND","message":"model not found"}}'),
            )
        return FakeResp(
            b'{"candidates":[{"content":{"parts":[{"text":"{\\"goal\\":\\"highlight\\"}"}]},"finishReason":"STOP"}]}'
        )

    cfg = {
        "provider": "gemini",
        "api_key": "AIza-test",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-3.8-flash",
        "model_source": "user",
        "quick_screening": True,
    }
    with patch.object(intelligence.urllib.request, "urlopen", side_effect=fake_urlopen):
        ans = intelligence.vision_call([{"type": "text", "text": "check"}], config=cfg)

    assert ans == {"goal": "highlight"}
    assert len(seen) == 2
    assert "gemini-2.5-flash" in seen[1][0]
    assert seen[1][1]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}

    # select_highlights tolerates whole-number float watch_score from small models while rejecting strings
    scenes, _audit = intelligence.select_highlights(
        [{"id": "e1", "label": "Action", "start": 1.0, "end": 12.0, "watch_score": 85.0}],
        duration=30.0,
    )
    assert len(scenes) == 1 and scenes[0].id == "e1"


def test_wave2_whisper_runtime_409_and_mirror_retry(tmp_path):
    import asyncio
    from fastapi import HTTPException
    from backend.api.v1 import speech_recognition
    from backend.services import whisper_model_manager as wmm

    # Missing Whisper runtime returns 409 instead of HTTP 500
    class FakeManager:
        async def download_model(self, name):
            raise RuntimeError("请先安装 Whisper 运行时")

    with patch("backend.api.v1.speech_recognition.get_model_manager", return_value=FakeManager()):
        try:
            asyncio.run(speech_recognition.download_whisper_model(speech_recognition.DownloadModelRequest(model="base")))
            raise AssertionError("expected HTTPException 409")
        except HTTPException as exc:
            assert exc.status_code == 409
            assert isinstance(exc.detail, dict) and exc.detail.get("code") == "whisper_not_installed"

    # Transient network error retries once on the same source before failing over
    mgr = wmm.WhisperModelManager()
    calls = []

    def fake_fetch(_sd, args, repo_id, endpoint):
        calls.append(endpoint)
        if len(calls) == 1:
            raise ConnectionResetError("connection reset by peer")
        return str(tmp_path)

    fake_hf = type("HF", (), {"snapshot_download": lambda **kw: str(tmp_path)})()
    with (
        patch.object(wmm.whisper_runtime, "ensure_on_path", lambda: None),
        patch.object(wmm.whisper_runtime, "get_models_dir", lambda: tmp_path),
        patch.object(wmm, "download_plan", lambda: [("mirror", "https://hf-mirror.com"), ("official", "https://huggingface.co")]),
        patch.object(wmm, "_fetch_snapshot", side_effect=fake_fetch),
        patch.object(wmm.time, "sleep", lambda _s: None),
        patch.dict("sys.modules", {"huggingface_hub": fake_hf}),
    ):
        mgr._download_blocking("base")

    assert calls == ["https://hf-mirror.com", "https://hf-mirror.com"]
    assert mgr._download_state["base"]["status"] == "downloaded"


def test_wave2_download_hls_fallback_and_step1_step2_resilience(tmp_path):
    # HLS fragment failure triggers non-HLS mp4 fallback once
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
                raise download_recovery.yt_dlp.utils.DownloadError("ERROR: fragment 3 failed: OSError")
            return 0

    with patch.object(download_recovery.yt_dlp, "YoutubeDL", FakeYDL):
        assert download_recovery.download_with_recovery("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {"format": "best"}) == 0
    assert len(seen_formats) == 2
    assert "[ext=mp4]" in seen_formats[1]

    # Classify retry exhaustion and Windows fragment append lock
    assert download_failure_observe.observe_download_failure("ERROR: Giving up after 5 retries")["code"] == "connection"
    assert download_failure_observe.observe_download_failure("ERROR: unable to download video data: HTTP Error 503")["code"] == "connection"
    assert download_failure_observe.observe_download_failure("ERROR: unable to open for writing: [WinError 32] sharing violation")["code"] == "file_locked"

    # step1_outline strips <think> before parsing JSON/Markdown
    from backend.pipeline.step1_outline import OutlineExtractor
    ext = OutlineExtractor.__new__(OutlineExtractor)
    outlines = ext._parse_outline_response('<think>consider topics</think>\n[{"title": "Intro", "subtopics": ["A"]}]', 0)
    assert len(outlines) == 1 and outlines[0]["title"] == "Intro"

    # step2_timeline unwraps {"clips": [...]} and start/end aliases
    from backend.pipeline.step2_timeline import TimelineExtractor
    from backend.utils.llm_client import LLMClient
    tl = TimelineExtractor.__new__(TimelineExtractor)
    tl.llm_client = LLMClient.__new__(LLMClient)
    tl.llm_raw_output_dir = tmp_path
    tl._save_debug_response = lambda *a, **kw: None
    items = tl._parse_and_validate_response(
        '{"clips": [{"title": "Intro", "start": "00:00:05,000", "end": "00:00:45,000"}]}',
        "00:00:00,000",
        "00:02:00,000",
        0,
    )
    assert len(items) == 1 and items[0]["outline"] == "Intro"


