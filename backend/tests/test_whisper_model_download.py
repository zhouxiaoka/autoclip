"""桌面端下载 Whisper 模型时，进度条写控制台失败不能打崩下载，也不能上报 Sentry。

PYTHON-FASTAPI-H / A：huggingface_hub.snapshot_download → tqdm.status_printer
在非控制台 stdout 上写 ``\\r``，抛 OSError / BrokenPipeError。
"""
import os
import sys
import types
from pathlib import Path

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
        (tmp_path / "hub").mkdir(parents=True, exist_ok=True)

    _install_fake_hub(monkeypatch, ok)
    manager = _manager(monkeypatch, tmp_path)

    manager._download_blocking("base")

    assert seen["repo_id"] == "Systran/faster-whisper-base"
    assert seen["cache_dir"] == str(tmp_path / "hub")
    with manager._lock:
        assert manager._download_state["base"]["status"] == "downloaded"


def test_ensure_on_path_disables_progress_bars(monkeypatch, tmp_path):
    monkeypatch.delenv("HF_HUB_DISABLE_PROGRESS_BARS", raising=False)
    monkeypatch.delenv("TQDM_DISABLE", raising=False)
    monkeypatch.setattr(whisper_runtime, "_data_dir", lambda: tmp_path)

    whisper_runtime.ensure_on_path()

    assert os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] == "1"
    assert os.environ["TQDM_DISABLE"] == "1"
