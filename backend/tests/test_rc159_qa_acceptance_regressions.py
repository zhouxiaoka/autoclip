"""Regression tests for 1.5.9-rc dual-platform QA acceptance findings (2b9b1805).

Covers:
1. qwen4-max hybrid thinking guard on DashScope (text & vision paths).
2. cover_planner token budget (no 1000-token quick_screening cap), VisionRequestError
   logging, error_code persistence, and degrade_count accounting.
3. intelligence.vision_call safe single-line logging on success and failure.
4. allow_send_frame default True with explicit opt-out False preserved independently
   from allow_visual_screening.
5. publish_kit.design_cover placeholder does not stamp false frame_sending_disabled
   when allow_send_frame is True, and ai_cover invokes the selected image model.
6. Cloud ASR logs and records actual provider/model/route in autoclip.log,
   llm_usage.jsonl, and pipeline_stamp provenance.
"""
from __future__ import annotations

import io
import json
import logging
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.core import llm_emit, llm_providers as lp, llm_usage
from backend.services import ai_model_settings as ai, cover, cover_brief as cb, cover_planner
from backend.services.studio import cover_design as cd, framing, intelligence, jobs, publish_kit, store


CN = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _jpeg(color: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), color).save(buf, format="JPEG")
    return buf.getvalue()


def test_qwen4_max_disables_thinking_on_dashscope_text_and_vision(monkeypatch):
    assert lp.disables_qwen_thinking("qwen4-max", CN) is True
    sent_text = lp.guarded_chat_kwargs(CN, {"model": "qwen4-max", "messages": []})
    assert sent_text["extra_body"] == {"enable_thinking": False}

    captured = []

    class FakeResp:
        headers = {"Content-Type": "application/json"}

        def __init__(self):
            self._buf = io.BytesIO(json.dumps({
                "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }).encode("utf-8"))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            return self._buf.read(size)

    def fake_urlopen(req, timeout=None):
        captured.append(json.loads(req.data.decode("utf-8")))
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    reply = intelligence.vision_call(
        [{"type": "text", "text": "check"}],
        {"base_url": CN, "api_key": "sk-test", "model": "qwen4-max", "quick_screening": True, "timeout": 30},
    )
    assert reply == {"ok": True}
    assert captured[0]["model"] == "qwen4-max"
    assert captured[0]["enable_thinking"] is False


def test_cover_planner_avoids_quick_screening_cap_and_records_vision_failure(monkeypatch, caplog):
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: True)
    monkeypatch.setattr(
        "backend.services.studio.vision_settings.effective",
        lambda: {"base_url": CN, "api_key": "sk-secret", "model": "qwen4-max", "timeout": 60},
    )
    seen_configs = []

    def failing_vision(content, config):
        seen_configs.append(dict(config))
        raise intelligence.VisionRequestError("output_truncated", "视觉模型输出被截断", http_status=200)

    monkeypatch.setattr(intelligence, "vision_call", failing_vision)
    ctx = cover_planner.context("测试标题", "douyin", (1080, 1920), cb.Options(mode="editorial_edit"), locked=True)
    token = llm_emit.set_degrade_count(0)
    try:
        with caplog.at_level(logging.WARNING):
            result = cover_planner.inspect([(_jpeg("#334455"), 0.5, 5.0, True, 1.0)], ctx, [])
        degrades = llm_emit.current_degrade_count()
    finally:
        llm_emit.reset_degrade_count(token)

    assert len(seen_configs) == 1
    assert not seen_configs[0].get("quick_screening"), "cover_planner must not reuse the 1000-token quick_screening cap"
    assert result["status"] == "vision_unavailable"
    assert result["error_type"] == "VisionRequestError"
    assert result["error_code"] == "output_truncated"
    assert degrades == 1
    assert any("VisionRequestError" in rec.message and "output_truncated" in rec.message for rec in caplog.records)
    assert not any("sk-secret" in rec.message for rec in caplog.records)


def test_vision_call_logs_safe_summary_on_success_and_error(monkeypatch, caplog, tmp_path):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))

    class OkResp:
        headers = {"Content-Type": "application/json"}
        payload = {
            "choices": [{"message": {"content": '{"best": 1}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 25},
        }

        def __init__(self):
            self._buf = io.BytesIO(json.dumps(self.payload).encode("utf-8"))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            return self._buf.read(size)

    class TruncatedResp(OkResp):
        payload = {
            "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 1000},
        }

    responses = iter([OkResp(), TruncatedResp()])
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: next(responses))

    content = [
        {"type": "text", "text": "pick frame"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,SECRET_IMAGE_PAYLOAD"}},
    ]
    cfg = {"base_url": CN, "api_key": "sk-secret-key", "model": "qwen4-max", "timeout": 30}

    with llm_usage.tracking("proj-vis"), llm_usage.stage("cover_frame"), caplog.at_level(logging.INFO):
        assert intelligence.vision_call(content, cfg) == {"best": 1}
        with pytest.raises(intelligence.VisionRequestError) as exc_info:
            intelligence.vision_call(content, cfg)
    assert exc_info.value.code == "output_truncated"
    messages = [rec.message for rec in caplog.records]
    assert any("cover_frame" in m and "qwen4-max" in m and "completion_tokens=25" in m for m in messages)
    assert any("cover_frame" in m and "qwen4-max" in m and "output_truncated" in m for m in messages)
    assert not any("sk-secret-key" in m or "SECRET_IMAGE_PAYLOAD" in m for m in messages)


def test_allow_send_frame_defaults_true_and_explicit_false_opt_out_works(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setattr(ai, "migrate_legacy", lambda: ai.ModelSettings())

    fresh = ai.ModelSettings()
    assert fresh.allow_send_frame is True
    assert cover.CoverConfig().allow_send_frame is True

    conn = ai.Connection(id="ds", name="Bailian", provider="dashscope", api_key="sk-test")
    opted_out = ai.ModelSettings(
        connections=[conn],
        analysis=ai.Assignment(connection_id="ds", model="qwen4-max", capability="multimodal"),
        cover=ai.Assignment(connection_id="ds", model="qwen-image-2.1-pro", capability="auto"),
        cover_enabled=True,
        cover_design_mode="editorial_edit",
        allow_send_frame=False,
        allow_visual_screening=True,
    )
    ai.save(opted_out)
    loaded = ai.load()
    assert loaded.allow_send_frame is False
    assert loaded.allow_visual_screening is True
    cfg = cover.load_config()
    assert cfg.allow_send_frame is False
    assert cfg.design_mode == "editorial_edit"


def test_design_cover_placeholder_does_not_stamp_false_frame_sending_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    frame = _jpeg("#446688")
    monkeypatch.setattr(framing, "detect_cuts", lambda *args: [])
    monkeypatch.setattr(cd, "_candidates", lambda *args, **kw: [(frame, 0.5, 8.0, True, 2.0)])
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: False)
    monkeypatch.setattr(publish_kit, "_scene_rows", lambda *a: [{"text": "测试标题", "start": 1.0, "end": 4.0}])
    monkeypatch.setattr("backend.services.publish_export._probe", lambda *a: {"width": 1280, "height": 720})
    monkeypatch.setattr(publish_kit, "_title_ok", lambda *a: True)

    cfg = cover.CoverConfig(
        enabled=True,
        provider="dashscope",
        api_key="sk-test",
        model="qwen-image-2.1-pro",
        design_mode="editorial_edit",
        allow_send_frame=True,
    )
    monkeypatch.setattr(cover, "load_config", lambda: cfg)

    calls = []
    monkeypatch.setattr(
        "backend.core.image_providers.generate_image",
        lambda *, request, **kw: calls.append(request) or frame,
    )

    store.directory("p1").mkdir(parents=True)
    store.write("p1", {"jobs": [{"job_id": "r1", "title": "测试标题"}]})
    draft = {"scenes": [{"start": 0.0, "end": 6.0}], "title": "测试标题"}

    publish_kit.design_cover("p1", None, draft, "r1", "douyin", "测试标题", "v1")
    placeholder_meta = json.loads(publish_kit.cd_meta_path("p1", "r1", "douyin", "v1").read_text(encoding="utf-8"))
    assert placeholder_meta["result"] == "local_design"
    assert placeholder_meta["fallback_reason"] is None, "sync placeholder must not falsely report frame_sending_disabled"
    assert not calls

    assert publish_kit.ai_cover("p1", "r1", "douyin", variant_id="v1", reuse=True) == "model"
    assert len(calls) == 1
    assert calls[0].model == "qwen-image-2.1-pro"
    assert calls[0].reference == frame
    final_meta = json.loads(publish_kit.cd_meta_path("p1", "r1", "douyin", "v1").read_text(encoding="utf-8"))
    assert final_meta["result"] == "model"
    assert final_meta["model"] == "qwen-image-2.1-pro"
    assert final_meta["provider"] == "dashscope"


def test_cloud_asr_logs_and_records_actual_provider_model_and_route(tmp_path, monkeypatch, caplog):
    from backend.services import cloud_transcription as ct

    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))

    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")
    output = tmp_path / "sample.srt"

    def fake_ffmpeg(cmd, **_kwargs):
        wav_path = Path(cmd[-1])
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_ffmpeg)
    monkeypatch.setattr(
        ct,
        "request_chunk",
        lambda client, connection, model, chunk, language: (
            [{"begin_time": 0, "end_time": 1000, "text": "测试转写句子", "sentence_end": True}],
            True,
        ),
    )

    conn = ai.Connection(id="ds", name="阿里云百炼", provider="dashscope", api_key="sk-super-secret")
    settings = ai.ModelSettings(
        connections=[conn],
        transcription=ai.Transcription(provider="cloud", connection_id="ds", model="qwen-audio-3.1-asr-flash"),
    )

    with llm_usage.tracking("proj-asr"), caplog.at_level(logging.INFO):
        srt = ct.transcribe(video, output, settings)

    assert srt == output and output.is_file()
    messages = [rec.message for rec in caplog.records]
    assert any("dashscope" in m and "qwen-audio-3.1-asr-flash" in m and "route=dashscope" in m for m in messages)
    assert not any("sk-super-secret" in m for m in messages)

    rows = [json.loads(line) for line in llm_usage.usage_path("proj-asr").read_text(encoding="utf-8").splitlines()]
    asr_rows = [r for r in rows if r.get("kind") == "asr"]
    assert len(asr_rows) == 1
    assert asr_rows[0]["provider"] == "dashscope"
    assert asr_rows[0]["model"] == "qwen-audio-3.1-asr-flash"
    assert asr_rows[0]["route"] == "dashscope"
    assert llm_usage.summary("proj-asr")["total"]["calls"] == 0

    info = ct.last_asr_info()
    assert info["asr_provider"] == "dashscope"
    assert info["asr_model"] == "qwen-audio-3.1-asr-flash"
    assert info["asr_route"] == "dashscope"
