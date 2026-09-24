"""
「失败要像失败」回归：LLM 不可用 / 字幕缺失 / 大纲为空 / 评分为空 / 切片没产出时，
流水线必须返回 failed 并带上阶段与用户提示，而不是一路 succeeded 到 `Completed · 0 切片`（#100 #11 #24）。
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.pipeline.failures import PipelineFailure

SRT = """1
00:00:01,000 --> 00:00:05,000
第一段内容，讨论产品定位

2
00:00:05,000 --> 00:00:12,000
第二段内容，讨论用户画像
"""


@pytest.fixture
def prompt_files(tmp_path):
    p = tmp_path / "outline.txt"
    p.write_text("提取大纲", encoding="utf-8")
    return {"outline": p}


def _extractor(tmp_path, prompt_files, monkeypatch, responses):
    """responses: 每个文本块对应的返回值；异常实例表示该块调用失败"""
    from backend.pipeline import step1_outline as step1

    calls = iter(responses)

    class FakeLLM:
        def call_with_retry(self, prompt, input_data=None, **kw):
            r = next(calls)
            if isinstance(r, BaseException):
                raise r
            return r

    monkeypatch.setattr(step1, "LLMClient", lambda: FakeLLM())
    return step1.OutlineExtractor(metadata_dir=tmp_path / "meta", prompt_files=prompt_files)


def test_step1_empty_srt_is_a_subtitle_failure(tmp_path, prompt_files, monkeypatch):
    srt = tmp_path / "empty.srt"
    srt.write_text("", encoding="utf-8")
    extractor = _extractor(tmp_path, prompt_files, monkeypatch, [])

    with pytest.raises(PipelineFailure) as exc:
        extractor.extract_outline(srt)

    assert exc.value.stage == "SUBTITLE"
    assert "为空" in exc.value.message
    assert "转写" in exc.value.hint


def test_step1_all_chunks_failing_surfaces_llm_error(tmp_path, prompt_files, monkeypatch):
    srt = tmp_path / "a.srt"
    srt.write_text(SRT, encoding="utf-8")
    extractor = _extractor(tmp_path, prompt_files, monkeypatch,
                           [ValueError("未配置LLM提供商，请在设置页面配置API密钥")])

    with pytest.raises(PipelineFailure) as exc:
        extractor.extract_outline(srt)

    assert exc.value.stage == "ANALYZE"
    assert "1/1" in exc.value.message
    assert "未配置LLM提供商" in exc.value.message
    assert exc.value.code == "llm_not_configured"
    assert "自备" in exc.value.hint
    assert "设置 → 模型" in exc.value.hint
    assert "测试连接" in exc.value.hint


def test_step1_unparseable_response_is_a_failure_not_empty_list(tmp_path, prompt_files, monkeypatch):
    srt = tmp_path / "a.srt"
    srt.write_text(SRT, encoding="utf-8")
    extractor = _extractor(tmp_path, prompt_files, monkeypatch, ["抱歉，我无法完成这个任务。"])

    with pytest.raises(PipelineFailure) as exc:
        extractor.extract_outline(srt)

    assert exc.value.stage == "ANALYZE"
    assert "无法解析" in exc.value.message


def test_step1_partial_chunk_failure_still_returns_outline(tmp_path, prompt_files, monkeypatch):
    """长视频某一块超时不该毁掉整条；只有全部失败才报错"""
    from backend.pipeline import step1_outline as step1

    srt = tmp_path / "a.srt"
    srt.write_text(SRT, encoding="utf-8")
    extractor = _extractor(tmp_path, prompt_files, monkeypatch,
                           [TimeoutError("read timeout"), "1. **产品定位**\n- 面向创作者"])
    # 强制切成两块
    monkeypatch.setattr(extractor.text_processor, "chunk_srt_data",
                        lambda data, interval_minutes, max_chars=None: [
                            {"chunk_index": 0, "text": "块0", "srt_entries": data[:1]},
                            {"chunk_index": 1, "text": "块1", "srt_entries": data[1:]},
                        ])

    outlines = extractor.extract_outline(srt)

    assert [o["title"] for o in outlines] == ["产品定位"]
    assert step1  # keep import used


# ----------------------------------------------------------------- adapter ---

@pytest.fixture
def adapter(tmp_path, monkeypatch):
    from backend.core import path_utils
    from backend.services import simple_pipeline_adapter as mod

    monkeypatch.delenv("AUTOCLIP_LLM_CACHE_DIR", raising=False)
    monkeypatch.setattr(path_utils, "get_project_directory", lambda pid: tmp_path / "projects" / pid)
    monkeypatch.setattr(mod, "clear_progress", lambda pid: None)
    events = []
    monkeypatch.setattr(mod, "emit_progress", lambda pid, stage, message="", subpercent=None: events.append((stage, message)))
    monkeypatch.setattr(mod.SimplePipelineAdapter, "_prompt_files", lambda self, project_dir: {})
    a = mod.SimplePipelineAdapter("proj-1", "task-1")
    a._events = events
    return a


def _fake_manager(monkeypatch, available: bool, display_name="Google Gemini", model="gemini-2.5-flash"):
    from backend.core import llm_manager
    info = {"provider": "gemini", "model": model, "available": available, "display_name": display_name}
    monkeypatch.setattr(llm_manager, "get_llm_manager",
                        lambda: SimpleNamespace(get_current_provider_info=lambda: info))


def test_adapter_fails_fast_when_llm_not_configured(adapter, monkeypatch, tmp_path):
    _fake_manager(monkeypatch, available=False)
    srt = tmp_path / "in.srt"
    srt.write_text(SRT, encoding="utf-8")

    result = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), str(srt)))

    assert result["status"] == "failed"
    assert result["stage"] == "ANALYZE"
    assert result["error_code"] == "llm_not_configured"
    assert "Google Gemini · gemini-2.5-flash" in result["error"]
    assert "设置 → 模型" in result["error"]
    assert "自备 API Key" in result["error"]
    assert "控制台" in result["error"]
    assert result["message"] == result["error"]
    # 进度事件带着失败阶段，前端失败态 / 反馈对话框能拿到
    assert adapter._events[-1][0] == "ANALYZE"
    assert adapter._events[-1][1].startswith("处理失败：")


def _whisper_status(monkeypatch, status: str, message: str = ""):
    monkeypatch.setattr(
        "backend.services.whisper_runtime.get_status",
        lambda: {"status": status, "message": message},
    )


def test_adapter_fails_when_no_subtitle_and_auto_transcribe_yields_nothing(adapter, monkeypatch, tmp_path):
    _fake_manager(monkeypatch, available=True)
    _whisper_status(monkeypatch, "not_installed")

    async def no_srt(self, video, metadata_dir):
        return None

    monkeypatch.setattr(type(adapter), "_generate_subtitle_automatically", no_srt)

    result = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), ""))

    assert result["status"] == "failed"
    assert result["stage"] == "SUBTITLE"
    assert result["error_code"] == "whisper_not_installed"
    assert "还没安装" in result["error"]
    assert "设置 → 转写" in result["error"]
    assert ".srt" in result["error"]
    # 以前会写一个空大纲然后「成功」；现在不该再产出 step1_outline.json
    assert not (tmp_path / "projects" / "proj-1" / "metadata" / "step1_outline.json").exists()


def test_adapter_distinguishes_install_failure_from_empty_transcript(adapter, monkeypatch, tmp_path):
    _fake_manager(monkeypatch, available=True)

    async def no_srt(self, video, metadata_dir):
        return None

    monkeypatch.setattr(type(adapter), "_generate_subtitle_automatically", no_srt)

    _whisper_status(monkeypatch, "error", "安装失败（pip 退出码 1）")
    failed = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), ""))
    assert failed["error_code"] == "whisper_install_failed"
    assert "上次安装没有成功" in failed["error"]
    assert ".srt" in failed["error"]

    _whisper_status(monkeypatch, "installed")
    empty = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), ""))
    assert empty["error_code"] == "transcription_empty"
    assert "已安装" in empty["error"]
    assert ".srt" in empty["error"]


def test_adapter_surfaces_whisper_error_on_the_subtitle_stage(adapter, monkeypatch, tmp_path):
    """转写失败要把可读原因带回失败态，而不是只留「没有字幕」。"""
    from backend.utils.speech_recognizer import SpeechRecognitionError

    _fake_manager(monkeypatch, available=True)
    video = tmp_path / "in.mp4"
    video.write_bytes(b"x")

    def fail(*_args, **_kwargs):
        raise SpeechRecognitionError("本地 Whisper 在显卡上转写失败。请重试。")

    monkeypatch.setattr("backend.utils.speech_recognizer.generate_subtitle_for_video", fail)

    result = asyncio.run(adapter.process_project_sync(str(video), ""))

    assert result["status"] == "failed"
    assert result["stage"] == "SUBTITLE"
    assert result["error_code"] == "subtitle_setup"
    assert "显卡" in result["error"]
    assert "设置 → 转写" in result["error"]
    assert result["message"] == result["error"]


def test_adapter_fails_when_scoring_keeps_nothing(adapter, monkeypatch, tmp_path):
    from backend.services import simple_pipeline_adapter as mod

    _fake_manager(monkeypatch, available=True)
    srt = tmp_path / "in.srt"
    srt.write_text(SRT, encoding="utf-8")
    monkeypatch.setattr(mod, "run_step1_outline", lambda *a, **k: [{"title": "t"}])
    monkeypatch.setattr(mod, "run_step2_timeline", lambda *a, **k: [{"id": 1}, {"id": 2}])
    monkeypatch.setattr(mod, "run_step3_scoring", lambda *a, **k: [])

    result = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), str(srt)))

    assert result["status"] == "failed"
    assert result["stage"] == "ANALYZE"
    assert "2 个候选" in result["error"]
    assert "最低评分阈值" in result["error"]


def test_adapter_fails_when_ffmpeg_produced_no_clip(adapter, monkeypatch, tmp_path):
    from backend.services import simple_pipeline_adapter as mod

    _fake_manager(monkeypatch, available=True)
    srt = tmp_path / "in.srt"
    srt.write_text(SRT, encoding="utf-8")
    monkeypatch.setattr(mod, "run_step1_outline", lambda *a, **k: [{"title": "t"}])
    monkeypatch.setattr(mod, "run_step2_timeline", lambda *a, **k: [{"id": 1}])
    monkeypatch.setattr(mod, "run_step3_scoring", lambda *a, **k: [{"id": 1, "final_score": 0.9}])
    monkeypatch.setattr(mod, "run_step4_title", lambda *a, **k: [{"id": 1, "generated_title": "x"}])
    monkeypatch.setattr(mod, "run_step5_clustering", lambda *a, **k: [])
    monkeypatch.setattr(mod, "run_step6_video", lambda *a, **k: {"clips_generated": 0, "clip_paths": []})

    result = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), str(srt)))

    assert result["status"] == "failed"
    assert result["stage"] == "EXPORT"
    assert "ffmpeg" in result["error"]


def test_adapter_happy_path_still_succeeds(adapter, monkeypatch, tmp_path):
    from backend.services import simple_pipeline_adapter as mod

    _fake_manager(monkeypatch, available=True)
    srt = tmp_path / "in.srt"
    srt.write_text(SRT, encoding="utf-8")
    monkeypatch.setattr(mod, "run_step1_outline", lambda *a, **k: [{"title": "t"}])
    monkeypatch.setattr(mod, "run_step2_timeline", lambda *a, **k: [{"id": 1}])
    monkeypatch.setattr(mod, "run_step3_scoring", lambda *a, **k: [{"id": 1, "final_score": 0.9}])
    monkeypatch.setattr(mod, "run_step4_title", lambda *a, **k: [{"id": 1, "generated_title": "x"}])
    monkeypatch.setattr(mod, "run_step5_clustering", lambda *a, **k: [{"id": "c1"}])
    monkeypatch.setattr(mod, "run_step6_video", lambda *a, **k: {"clips_generated": 1, "clip_paths": ["/x/1.mp4"]})

    class _DB:
        def close(self): pass

    monkeypatch.setattr("backend.core.database.SessionLocal", lambda: _DB())
    monkeypatch.setattr("backend.services.data_sync_service.DataSyncService",
                        lambda db: SimpleNamespace(sync_project_from_filesystem=lambda pid, d: {"success": True}))

    result = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), str(srt)))

    assert result["status"] == "succeeded"
    assert result["result"]["video_result"]["clips_generated"] == 1
    assert adapter._events[-1] == ("DONE", "处理完成")


def test_adapter_replay_mode_skips_llm_preflight(adapter, monkeypatch, tmp_path):
    """backend/eval 用 AUTOCLIP_LLM_CACHE_DIR 回放，不需要真实提供商"""
    from backend.services import simple_pipeline_adapter as mod

    monkeypatch.setenv("AUTOCLIP_LLM_CACHE_DIR", str(tmp_path / "cache"))
    _fake_manager(monkeypatch, available=False)
    srt = tmp_path / "in.srt"
    srt.write_text(SRT, encoding="utf-8")
    monkeypatch.setattr(mod, "run_step1_outline", lambda *a, **k: [{"title": "t"}])
    monkeypatch.setattr(mod, "run_step2_timeline", lambda *a, **k: [{"id": 1}])
    monkeypatch.setattr(mod, "run_step3_scoring", lambda *a, **k: [])

    result = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), str(srt)))

    # 走过了 preflight，死在评分为空——说明 preflight 确实被跳过
    assert result["stage"] == "ANALYZE" and "候选" in result["error"]


# ------------------------------------------------------- error surfacing ---

def test_project_response_exposes_latest_task_error(monkeypatch):
    from backend.services.project_service import ProjectService

    class Q:
        def __init__(self, rows): self.rows = rows
        def filter(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def first(self): return self.rows[0] if self.rows else None

    task = SimpleNamespace(error_message="没有片段通过评分筛选（3 个候选，阈值 0.7）。到「设置 → 模型 → 最低评分阈值」调低后重试。")
    svc = ProjectService.__new__(ProjectService)
    svc.db = SimpleNamespace(query=lambda model: Q([task]))
    project = SimpleNamespace(id="p1", status="failed", project_metadata={})

    assert svc.latest_error_message(project) == task.error_message
    assert svc.latest_error_code(project) is None
    assert svc.latest_error_message(SimpleNamespace(id="p1", status="completed", project_metadata={})) is None

    keyed = SimpleNamespace(
        error_message="没有可用的 LLM 提供商，缺少 API Key。",
        result_data={"error_code": "llm_not_configured"},
    )
    svc.db = SimpleNamespace(query=lambda model: Q([keyed]))
    assert svc.latest_error_code(project) == "llm_not_configured"


def test_project_response_falls_back_to_metadata_for_cli_runs():
    from backend.services.project_service import ProjectService

    class Q:
        def filter(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def first(self): return None

    svc = ProjectService.__new__(ProjectService)
    svc.db = SimpleNamespace(query=lambda model: Q())
    project = SimpleNamespace(id="p1", status=SimpleNamespace(value="failed"),
                              project_metadata={"last_error": "没有可用的 LLM 提供商", "last_error_code": "llm_not_configured"})

    assert svc.latest_error_message(project) == "没有可用的 LLM 提供商"
    assert svc.latest_error_code(project) == "llm_not_configured"


def test_project_response_exposes_subtitle_error_code():
    from backend.services.project_service import ProjectService

    class Q:
        def __init__(self, row): self.row = row
        def filter(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def first(self): return self.row

    task = SimpleNamespace(
        error_message="没有字幕可分析",
        result_data={"error_code": "whisper_not_installed"},
    )
    svc = ProjectService.__new__(ProjectService)
    svc.db = SimpleNamespace(query=lambda model: Q(task))
    project = SimpleNamespace(id="p1", status="failed", project_metadata={})

    assert svc.latest_error_code(project) == "whisper_not_installed"

    svc.db = SimpleNamespace(query=lambda model: Q(None))
    cli_project = SimpleNamespace(
        id="p1",
        status="failed",
        project_metadata={"last_error": "没有字幕", "last_error_code": "transcription_empty"},
    )
    assert svc.latest_error_code(cli_project) == "transcription_empty"


def test_processing_task_reads_error_field_from_adapter_result():
    """tasks/processing.py 以前只读 message，adapter 返回的是 error → 用户永远只看到「处理失败」"""
    src = (Path(__file__).resolve().parents[1] / "tasks" / "processing.py").read_text(encoding="utf-8")
    assert 'result.get("error") or result.get("message")' in src
