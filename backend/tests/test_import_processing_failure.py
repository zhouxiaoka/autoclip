"""导入任务失败必须能被 Celery 结果后端解码（#20）。

以前 process_import_task 用 update_state(state='FAILURE', meta={'error': ...})
然后 return。结果里没有 exc_type，worker 随后 mark_as_done / mark_as_failure
时会抛 ValueError: Exception information must include the exception type。
"""

import traceback
from contextlib import contextmanager
from pathlib import Path

import pytest
from celery import Celery

from backend.tasks import import_processing as mod
from backend.tasks.import_processing import (
    ImportMissingCredential,
    ImportProcessingError,
    ImportSubtitleUnavailable,
    classify_import_failure,
    process_import_task,
)


class _Query:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _DB:
    def query(self, *args, **kwargs):
        return _Query()

    def close(self):
        return None


class _Project:
    def __init__(self):
        self.thumbnail = "already-set"
        self.project_metadata = {}
        self.status = "pending"


class _ProjectService:
    def __init__(self, db=None):
        self.project = _Project()

    def get(self, project_id):
        return self.project

    def update_project_status(self, project_id, status):
        self.project.status = status
        return True

    def update(self, project_id, **kwargs):
        for key, value in kwargs.items():
            setattr(self.project, key, value)
        return self.project


@pytest.fixture
def memory_backend():
    """真实 Celery 结果后端（内存），走和 Redis 后端同一套异常解码。"""
    app = Celery(
        "import-failure-test",
        broker="memory://",
        backend="cache+memory://",
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
    )
    from backend.core.celery_app import celery_app

    previous_cache = getattr(celery_app, "_backend_cache", None)
    previous_local = getattr(celery_app._local, "backend", None)
    celery_app._backend = app.backend
    try:
        yield app.backend
    finally:
        celery_app._backend_cache = previous_cache
        if previous_local is None:
            if hasattr(celery_app._local, "backend"):
                del celery_app._local.backend
        else:
            celery_app._local.backend = previous_local


@pytest.fixture
def project_service(monkeypatch):
    service = _ProjectService()

    @contextmanager
    def _scope():
        db = _DB()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(mod, "session_scope", _scope)
    monkeypatch.setattr(mod, "ProjectService", lambda db: service)
    return service


def _whisper_not_installed(monkeypatch):
    monkeypatch.setattr(
        "backend.services.whisper_runtime.get_status",
        lambda: {"status": "not_installed"},
    )


def _finish_like_worker(backend, task_id, call):
    """模仿 celery.app.trace：正常返回走 mark_as_done，抛异常走 mark_as_failure。

    旧实现正是在这一步读回不完整的 FAILURE meta，抛出 ValueError。
    """
    raised = None
    try:
        retval = call()
    except Exception as exc:
        raised = exc
        backend.mark_as_failure(task_id, exc, traceback.format_exc())
    else:
        backend.mark_as_done(task_id, retval)
    return raised, backend.get_task_meta(task_id)


def _run_import(backend, task_id, project_id, video_path, srt_file_path):
    def call():
        process_import_task.push_request(id=task_id)
        try:
            return process_import_task.run(project_id, video_path, srt_file_path)
        finally:
            process_import_task.pop_request()

    return _finish_like_worker(backend, task_id, call)


def test_incomplete_failure_meta_is_what_celery_rejects(memory_backend):
    """锁定 Celery 的解码契约：只有 error、没有 exc_type 的 FAILURE 必须失败。"""
    memory_backend.store_result("bad-meta", {"error": "字幕文件不存在"}, "FAILURE")
    with pytest.raises(ValueError, match="exception type"):
        memory_backend.mark_as_done("bad-meta", {"status": "completed"})


def test_missing_subtitle_failure_roundtrips_with_exc_type(memory_backend, project_service, tmp_path, monkeypatch, caplog):
    _whisper_not_installed(monkeypatch)
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")

    with caplog.at_level("ERROR"):
        raised, meta = _run_import(
            memory_backend,
            "task-missing-srt",
            "proj-1",
            str(video),
            str(tmp_path / "missing.srt"),
        )

    assert type(raised) is ImportSubtitleUnavailable
    assert "kind=missing-subtitle" in caplog.text
    assert type(meta["result"]) is ImportSubtitleUnavailable
    message = str(raised)
    assert "没有字幕可分析" in message
    assert "设置 → 转写" in message
    assert meta["status"] == "FAILURE"
    assert isinstance(meta["result"], BaseException)
    assert "没有字幕可分析" in str(meta["result"])
    # 再读一次：worker 写结果时会解码当前 meta，这里不能再抛 ValueError
    again = memory_backend._get_task_meta_for("task-missing-srt")
    assert again["status"] == "FAILURE"
    assert "设置 → 转写" in str(again["result"])

    assert project_service.project.status == "failed"
    assert project_service.project.project_metadata["last_error_code"] == "whisper_not_installed"
    assert "设置 → 转写" in project_service.project.project_metadata["last_error"]


def test_speech_error_roundtrips_as_structured_subtitle_failure(memory_backend, project_service, tmp_path, monkeypatch):
    """转写失败时不要再收成一句「字幕文件不存在」。"""
    _whisper_not_installed(monkeypatch)
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")
    monkeypatch.setattr(
        mod,
        "_generate_import_subtitle",
        lambda task, project_id, video_path: (None, "没有可用的语音识别"),
    )

    raised, meta = _run_import(
        memory_backend,
        "task-speech-failed",
        "proj-speech",
        str(video),
        None,
    )

    assert type(raised) is ImportSubtitleUnavailable
    assert type(meta["result"]) is ImportSubtitleUnavailable
    assert "还没安装" in str(raised)
    assert "设置 → 转写" in str(raised)
    assert meta["status"] == "FAILURE"
    assert project_service.project.status == "failed"
    assert project_service.project.project_metadata["last_error_code"] == "whisper_not_installed"
    assert "设置 → 转写" in project_service.project.project_metadata["last_error"]


def test_pipeline_submit_error_is_kept_on_the_project(memory_backend, project_service, tmp_path, monkeypatch):
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")
    srt = tmp_path / "input.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "submit_video_pipeline_task",
        lambda **kwargs: {"success": False, "error": "队列已满"},
    )

    raised, meta = _run_import(
        memory_backend,
        "task-submit-failed",
        "proj-2",
        str(video),
        str(srt),
    )

    assert type(raised) is ImportProcessingError
    assert not isinstance(raised, (ImportSubtitleUnavailable, ImportMissingCredential))
    assert str(raised) == "队列已满"
    assert meta["status"] == "FAILURE"
    assert str(meta["result"]) == "队列已满"
    assert project_service.project.status == "failed"
    assert project_service.project.project_metadata["last_error"] == "队列已满"


def test_unexpected_import_error_does_not_store_bare_failure_meta(memory_backend, project_service, tmp_path, monkeypatch, caplog):
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")
    srt = tmp_path / "input.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    def boom(**kwargs):
        raise RuntimeError("broker down")

    monkeypatch.setattr(mod, "submit_video_pipeline_task", boom)

    with caplog.at_level("ERROR"):
        raised, meta = _run_import(
            memory_backend,
            "task-unexpected",
            "proj-3",
            str(video),
            str(srt),
        )

    assert type(raised) is ImportProcessingError
    assert not isinstance(raised, (ImportSubtitleUnavailable, ImportMissingCredential))
    assert "broker down" in str(raised)
    assert "kind=unexpected" in caplog.text
    assert "exc=ImportProcessingError" in caplog.text
    assert meta["status"] == "FAILURE"
    assert "broker down" in str(meta["result"])
    assert project_service.project.status == "failed"
    assert project_service.project.project_metadata["last_error"] == "broker down"


def test_successful_import_still_completes(memory_backend, project_service, tmp_path, monkeypatch):
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")
    srt = tmp_path / "input.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "submit_video_pipeline_task",
        lambda **kwargs: {"success": True, "task_id": "pipe-1"},
    )

    raised, meta = _run_import(
        memory_backend,
        "task-ok",
        "proj-ok",
        str(video),
        str(srt),
    )

    assert raised is None
    assert meta["status"] == "SUCCESS"
    assert meta["result"]["status"] == "completed"
    assert meta["result"]["project_id"] == "proj-ok"
    assert project_service.project.status == "processing"
    assert "last_error" not in project_service.project.project_metadata


def test_unhandled_exception_is_stored_as_a_real_failure(memory_backend, project_service, tmp_path):
    """任务体里没预料到的异常也不能先写一份没有 exc_type 的 FAILURE。"""
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")

    def broken_get(project_id):
        raise RuntimeError("db down")

    project_service.get = broken_get

    raised, meta = _run_import(
        memory_backend,
        "task-unhandled",
        "proj-4",
        str(video),
        None,
    )

    assert isinstance(raised, RuntimeError)
    assert str(raised) == "db down"
    assert meta["status"] == "FAILURE"
    assert isinstance(meta["result"], RuntimeError)
    assert str(meta["result"]) == "db down"
    assert project_service.project.status == "failed"


def test_import_whisper_options_reach_the_recognizer(tmp_path, monkeypatch):
    """默认本地导入会把设置里的时间戳和超时传给转写。不能在进 Whisper 之前 TypeError。"""
    _whisper_not_installed(monkeypatch)
    monkeypatch.setattr("backend.services.whisper_runtime.is_installed", lambda: False)
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")

    class _Task:
        def update_state(self, **kwargs):
            return None

    srt_path, speech_error = mod._generate_import_subtitle(_Task(), "proj-whisper", str(video))

    assert srt_path is None
    assert speech_error is not None
    assert "unexpected keyword" not in speech_error
    assert "未安装" in speech_error
    assert "设置 → 转写" in speech_error
    failure = mod.import_subtitle_failure(speech_error)
    assert failure.code == "whisper_not_installed"


def test_import_blank_whisper_result_is_transcription_empty(tmp_path, monkeypatch):
    """Whisper 声称跑完但只有空白片段时，导入关卡记 transcription_empty，而不是当成有字幕。"""
    import sys
    import types
    from types import SimpleNamespace

    from backend.services import whisper_runtime

    module = types.ModuleType("faster_whisper")

    class FakeModel:
        def __init__(self, model, device="auto", compute_type="int8", download_root=None):
            pass

        def transcribe(self, path, language=None, vad_filter=False, word_timestamps=False):
            assert word_timestamps is True
            return [SimpleNamespace(start=0.0, end=1.0, text="   ")], None

    module.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: True)
    monkeypatch.setattr(whisper_runtime, "ensure_on_path", lambda: None)
    monkeypatch.setattr(whisper_runtime, "get_models_dir", lambda: tmp_path / "models")
    monkeypatch.delenv("AUTOCLIP_WHISPER_DEVICE", raising=False)

    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")

    class _Task:
        def update_state(self, **kwargs):
            return None

    srt_path, speech_error = mod._generate_import_subtitle(_Task(), "proj-blank", str(video))

    assert srt_path is None
    assert "未识别出任何语音" in speech_error
    assert not list(tmp_path.glob("*.srt"))
    failure = mod.import_subtitle_failure(speech_error)
    assert failure.code == "transcription_empty"


def test_import_task_source_does_not_set_failure_state_by_hand():
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "state='FAILURE'" not in src
    assert 'state="FAILURE"' not in src


def test_speech_api_key_is_missing_credential_without_changing_guidance(
    memory_backend, project_service, tmp_path, monkeypatch, caplog
):
    """转写密钥没配时，Sentry 类型分开，但失败码和「设置 → 转写」提示保持原样。"""
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")
    monkeypatch.setattr(
        mod,
        "_generate_import_subtitle",
        lambda task, project_id, video_path: (None, "阿里云语音识别不可用，请配置API Key"),
    )

    with caplog.at_level("ERROR"):
        raised, meta = _run_import(
            memory_backend,
            "task-missing-key",
            "proj-key",
            str(video),
            None,
        )

    assert type(raised) is ImportMissingCredential
    assert type(meta["result"]) is ImportMissingCredential
    assert "请配置API Key" in str(raised)
    assert "设置 → 转写" in str(raised)
    assert project_service.project.project_metadata["last_error_code"] == "subtitle_setup"
    assert "设置 → 转写" in project_service.project.project_metadata["last_error"]
    assert "kind=missing-key" in caplog.text
    assert "exc=ImportMissingCredential" in caplog.text


def test_llm_not_configured_keeps_message_and_code(project_service, caplog):
    message = "没有可用的 LLM 提供商（当前选择：通义千问 · qwen），缺少 API Key 或本地服务地址。"
    with caplog.at_level("ERROR"):
        with pytest.raises(ImportMissingCredential) as caught:
            mod._fail_import(
                project_service,
                "proj-llm",
                message,
                error_code="llm_not_configured",
            )

    assert str(caught.value) == message
    assert project_service.project.status == "failed"
    assert project_service.project.project_metadata["last_error"] == message
    assert project_service.project.project_metadata["last_error_code"] == "llm_not_configured"
    assert "kind=missing-key" in caplog.text


@pytest.mark.parametrize(
    "code",
    ["whisper_not_installed", "whisper_install_failed", "transcription_empty", "subtitle_setup"],
)
def test_subtitle_codes_classify_as_subtitle(code):
    exc_cls = classify_import_failure("没有字幕可分析。到「设置 → 转写」重试。", code)
    assert exc_cls is ImportSubtitleUnavailable
    assert exc_cls.kind == "missing-subtitle"


def test_whisper_state_stays_subtitle_even_if_text_mentions_a_key():
    exc_cls = classify_import_failure("请配置API Key", "whisper_not_installed")
    assert exc_cls is ImportSubtitleUnavailable


def test_timeline_empty_stays_unexpected_import_failure():
    message = "时间线提取为空：2 个话题在对齐并按时长筛选后没有留下可用片段。"
    assert classify_import_failure(message, "timeline_empty") is ImportProcessingError


def test_unexpected_and_key_messages_do_not_share_a_type():
    assert classify_import_failure("队列已满") is ImportProcessingError
    assert classify_import_failure("broker down") is ImportProcessingError
    assert classify_import_failure("401 Unauthorized") is ImportProcessingError
    key = classify_import_failure("OpenAI API不可用，请设置OPENAI_API_KEY环境变量", "subtitle_setup")
    assert key is ImportMissingCredential
    assert key.kind == "missing-key"
