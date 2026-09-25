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
from backend.tasks.import_processing import ImportProcessingError, process_import_task


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


def test_missing_subtitle_failure_roundtrips_with_exc_type(memory_backend, project_service, tmp_path, monkeypatch):
    _whisper_not_installed(monkeypatch)
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")

    raised, meta = _run_import(
        memory_backend,
        "task-missing-srt",
        "proj-1",
        str(video),
        str(tmp_path / "missing.srt"),
    )

    assert isinstance(raised, ImportProcessingError)
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

    assert isinstance(raised, ImportProcessingError)
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

    assert isinstance(raised, ImportProcessingError)
    assert str(raised) == "队列已满"
    assert meta["status"] == "FAILURE"
    assert str(meta["result"]) == "队列已满"
    assert project_service.project.status == "failed"
    assert project_service.project.project_metadata["last_error"] == "队列已满"


def test_unexpected_import_error_does_not_store_bare_failure_meta(memory_backend, project_service, tmp_path, monkeypatch):
    video = tmp_path / "input.mp4"
    video.write_bytes(b"not-a-real-video")
    srt = tmp_path / "input.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    def boom(**kwargs):
        raise RuntimeError("broker down")

    monkeypatch.setattr(mod, "submit_video_pipeline_task", boom)

    raised, meta = _run_import(
        memory_backend,
        "task-unexpected",
        "proj-3",
        str(video),
        str(srt),
    )

    assert isinstance(raised, ImportProcessingError)
    assert "broker down" in str(raised)
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


def test_import_task_source_does_not_set_failure_state_by_hand():
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "state='FAILURE'" not in src
    assert 'state="FAILURE"' not in src
