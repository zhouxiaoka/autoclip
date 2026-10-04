"""桌面端下载 Whisper 模型时，进度条写控制台失败不能打崩下载，也不能上报 Sentry。

PYTHON-FASTAPI-H / A：huggingface_hub.snapshot_download → tqdm.status_printer
在非控制台 stdout 上写 ``\\r``，抛 OSError / BrokenPipeError。
"""
import os
import sys
import types
from pathlib import Path

import pytest

from backend.services import whisper_runtime
from backend.services.whisper_model_manager import (
    ModelStatus,
    WhisperModelManager,
    _silence_download_progress,
)


def _install_fake_hub(monkeypatch, snapshot_download):
    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = snapshot_download
    utils = types.ModuleType("huggingface_hub.utils")
    utils.disable_progress_bars = lambda: None
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", utils)


def _manager(monkeypatch, tmp_path: Path) -> WhisperModelManager:
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: True)
    monkeypatch.setattr(whisper_runtime, "ensure_on_path", lambda: None)
    monkeypatch.setattr(whisper_runtime, "get_models_dir", lambda: tmp_path)
    return WhisperModelManager()


def test_silence_progress_sets_env_even_without_hub(monkeypatch):
    monkeypatch.delenv("HF_HUB_DISABLE_PROGRESS_BARS", raising=False)
    monkeypatch.delenv("TQDM_DISABLE", raising=False)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", types.ModuleType("missing"))

    _silence_download_progress()

    assert os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] == "1"
    assert os.environ["TQDM_DISABLE"] == "1"


def test_silence_progress_calls_hub_helper(monkeypatch):
    called = []
    utils = types.ModuleType("huggingface_hub.utils")
    utils.disable_progress_bars = lambda: called.append(True)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", utils)

    _silence_download_progress()

    assert called == [True]


def test_download_oserror_records_error_without_traceback(monkeypatch, tmp_path, caplog):
    silenced = []

    def boom(**kwargs):
        raise OSError(22, "Invalid argument")

    _install_fake_hub(monkeypatch, boom)
    monkeypatch.setattr(
        "backend.services.whisper_model_manager._silence_download_progress",
        lambda: silenced.append(True),
    )
    manager = _manager(monkeypatch, tmp_path)

    with caplog.at_level("WARNING"):
        manager._download_blocking("tiny")

    info = manager.get_model_info("tiny")
    assert silenced == [True]
    assert info is not None
    assert info.status == ModelStatus.ERROR
    assert info.error_message
    assert all(record.exc_info in (None, (None, None, None)) for record in caplog.records)
    assert not any(record.levelno >= 40 for record in caplog.records)


def test_download_success_marks_downloaded(monkeypatch, tmp_path):
    seen = {}

    def ok(**kwargs):
        seen.update(kwargs)
        return str(_snapshot(tmp_path))

    _install_fake_hub(monkeypatch, ok)
    manager = _manager(monkeypatch, tmp_path)

    manager._download_blocking("base")

    assert seen["repo_id"] == "Systran/faster-whisper-base"
    assert seen["cache_dir"] == str(tmp_path / "hub")
    with manager._lock:
        assert manager._download_state["base"]["status"] == "downloaded"


def _snapshot(root, revision="complete"):
    snapshot = root / "hub/models--Systran--faster-whisper-base/snapshots" / revision
    snapshot.mkdir(parents=True, exist_ok=True)
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.json"):
        (snapshot / name).write_bytes(b"data")
    return snapshot


@pytest.mark.parametrize("missing", ["model.bin", "config.json", "tokenizer.json", "vocabulary.json"])
def test_partial_snapshot_is_not_downloaded(monkeypatch, tmp_path, missing):
    manager = _manager(monkeypatch, tmp_path)
    snapshot = _snapshot(tmp_path)
    (snapshot / missing).unlink()
    assert manager.get_model_info("base").status == ModelStatus.AVAILABLE
    assert manager.get_download_progress("base") is None


def test_empty_weights_and_broken_symlinks_are_not_downloaded(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    snapshot = _snapshot(tmp_path)
    (snapshot / "model.bin").write_bytes(b"")
    assert not manager._is_downloaded("base")
    (snapshot / "model.bin").unlink()
    (snapshot / "model.bin").symlink_to(tmp_path / "missing-blob")
    assert not manager._is_downloaded("base")


def test_download_does_not_report_success_for_incomplete_snapshot(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    snapshot = _snapshot(tmp_path)
    (snapshot / "model.bin").unlink()
    _install_fake_hub(monkeypatch, lambda **kwargs: str(snapshot))
    manager._download_blocking("base")
    assert manager.get_model_info("base").status == ModelStatus.ERROR
    assert manager.get_download_progress("base") != 100


def test_complete_cached_model_can_be_resolved_without_hub(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    snapshot = _snapshot(tmp_path)
    assert manager.get_local_model_path("base") == snapshot
    assert manager.get_model_info("base").status == ModelStatus.DOWNLOADED


def test_retry_clears_failed_download_when_complete_snapshot_now_exists(monkeypatch, tmp_path):
    import asyncio
    manager = _manager(monkeypatch, tmp_path)
    manager._download_state["base"] = {"status": "error", "progress": 0, "error": "connect timeout"}
    _snapshot(tmp_path)
    assert manager.get_model_info("base").status == ModelStatus.ERROR

    assert asyncio.run(manager.download_model("base"))

    info = manager.get_model_info("base")
    assert info.status == ModelStatus.DOWNLOADED
    assert info.error_message is None
    assert manager.get_download_progress("base") == 100


def test_cached_main_revision_is_preferred_and_large_alias_is_supported(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    main = _snapshot(tmp_path, "main-revision")
    _snapshot(tmp_path, "other-revision")
    ref = main.parent.parent / "refs/main"
    ref.parent.mkdir()
    ref.write_text("main-revision", encoding="utf-8")
    assert manager.get_local_model_path("base") == main
    large = tmp_path / "hub/models--Systran--faster-whisper-large-v3"
    main.parent.parent.rename(large)
    assert manager.get_local_model_path("large") == large / "snapshots/main-revision"


def test_incomplete_cache_can_be_downloaded_again(monkeypatch, tmp_path):
    import asyncio
    manager = _manager(monkeypatch, tmp_path)
    snapshot = _snapshot(tmp_path)
    (snapshot / "model.bin").unlink()
    calls = []

    def complete(**kwargs):
        calls.append(kwargs)
        (snapshot / "model.bin").write_bytes(b"weights")
        return str(snapshot)

    class ImmediateThread:
        def __init__(self, target, args, **kwargs):
            self.run = lambda: target(*args)

        def start(self):
            self.run()

    _install_fake_hub(monkeypatch, complete)
    monkeypatch.setattr("backend.services.whisper_model_manager.threading.Thread", ImmediateThread)
    assert asyncio.run(manager.download_model("base"))
    assert len(calls) == 1
    assert manager.get_model_info("base").status == ModelStatus.DOWNLOADED
    assert manager.get_download_progress("base") == 100
    (snapshot / "model.bin").unlink()
    assert manager.get_download_progress("base") is None


def test_ensure_on_path_disables_progress_bars(monkeypatch, tmp_path):
    monkeypatch.delenv("HF_HUB_DISABLE_PROGRESS_BARS", raising=False)
    monkeypatch.delenv("TQDM_DISABLE", raising=False)
    monkeypatch.setattr(whisper_runtime, "_data_dir", lambda: tmp_path)

    whisper_runtime.ensure_on_path()

    assert os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] == "1"
    assert os.environ["TQDM_DISABLE"] == "1"
