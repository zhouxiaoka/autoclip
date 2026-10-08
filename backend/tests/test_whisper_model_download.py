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


@pytest.fixture(autouse=True)
def _clean_source_env(monkeypatch):
    for name in ("AUTOCLIP_WHISPER_MODEL_SOURCE", "HF_ENDPOINT", "HF_HUB_DISABLE_XET"):
        monkeypatch.delenv(name, raising=False)


def _install_fake_hub(monkeypatch, snapshot_download):
    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = snapshot_download
    utils = types.ModuleType("huggingface_hub.utils")
    utils.disable_progress_bars = lambda: None
    constants = types.ModuleType("huggingface_hub.constants")
    constants.HF_HUB_DISABLE_XET = False
    hub.constants = constants
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", utils)
    monkeypatch.setitem(sys.modules, "huggingface_hub.constants", constants)
    return hub


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

    assert asyncio.run(manager.download_model("base")) == "installed"

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
    # "downloading" even though this fake thread already finished: the call only starts it.
    assert asyncio.run(manager.download_model("base")) == "downloading"
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


# ---- RC156 Win QA #6: download source and mirror fallback ----

class ConnectTimeout(OSError):
    pass


def _recording(tmp_path, fail_endpoints=()):
    calls = []

    def download(**kwargs):
        import huggingface_hub
        calls.append({**kwargs, "xet_disabled": huggingface_hub.constants.HF_HUB_DISABLE_XET,
                      "xet_env": os.environ.get("HF_HUB_DISABLE_XET")})
        if kwargs.get("endpoint") in fail_endpoints:
            raise ConnectTimeout("[WinError 10060] connect timed out")
        return str(_snapshot(tmp_path))

    return calls, download


def test_auto_falls_back_to_hf_mirror_without_xet(monkeypatch, tmp_path):
    calls, download = _recording(tmp_path, fail_endpoints=("https://huggingface.co",))
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    assert [call["endpoint"] for call in calls] == ["https://huggingface.co", "https://hf-mirror.com"]
    assert calls[0]["xet_disabled"] is False
    assert calls[1]["xet_disabled"] is True and calls[1]["xet_env"] == "1"
    info = manager.get_model_info("base")
    assert info.status == ModelStatus.DOWNLOADED
    assert info.source == "hf-mirror"


def test_auto_uses_official_source_when_reachable(monkeypatch, tmp_path):
    calls, download = _recording(tmp_path)
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    assert [call["endpoint"] for call in calls] == ["https://huggingface.co"]
    assert manager.get_model_info("base").source == "huggingface"


def test_hf_mirror_source_goes_straight_to_the_mirror(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_WHISPER_MODEL_SOURCE", "hf-mirror")
    calls, download = _recording(tmp_path)
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    assert [(call["endpoint"], call["xet_disabled"]) for call in calls] == [("https://hf-mirror.com", True)]


def test_huggingface_source_never_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_WHISPER_MODEL_SOURCE", "huggingface")
    calls, download = _recording(tmp_path, fail_endpoints=("https://huggingface.co",))
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    assert [call["endpoint"] for call in calls] == ["https://huggingface.co"]
    info = manager.get_model_info("base")
    assert info.status == ModelStatus.ERROR
    assert "10060" in info.error_message


def test_user_hf_endpoint_is_respected_without_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_ENDPOINT", "https://mirror.example/")
    calls, download = _recording(tmp_path, fail_endpoints=("https://mirror.example",))
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    assert [(call["endpoint"], call["xet_disabled"]) for call in calls] == [("https://mirror.example", True)]
    assert manager.get_model_info("base").status == ModelStatus.ERROR


def test_both_sources_failing_reports_both(monkeypatch, tmp_path):
    calls, download = _recording(tmp_path, fail_endpoints=("https://huggingface.co", "https://hf-mirror.com"))
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    info = manager.get_model_info("base")
    assert info.status == ModelStatus.ERROR
    assert "huggingface" in info.error_message and "hf-mirror" in info.error_message


# ---- RC156 Win QA #5: the download endpoint must not claim completion ----

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.speech_recognition import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_download_api_says_started_and_background_failure_is_visible(monkeypatch, tmp_path):
    import threading
    release = threading.Event()

    def slow_failure(**kwargs):
        release.wait(5)
        raise ConnectTimeout("[WinError 10060] connect timed out")

    _install_fake_hub(monkeypatch, slow_failure)
    manager = _manager(monkeypatch, tmp_path)
    monkeypatch.setattr("backend.api.v1.speech_recognition.get_model_manager", lambda: manager)
    with _client() as client:
        response = client.post("/whisper-models/download", json={"model": "base"})
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "downloading" and body["model"] == "base"
        assert "完成" not in body["message"]
        again = client.post("/whisper-models/download", json={"model": "base"})
        assert again.status_code == 202 and again.json()["status"] == "downloading"
        assert client.get("/whisper-models/base/status").json()["status"] == "downloading"
        release.set()
        for thread in threading.enumerate():
            if thread.name == "whisper-dl-base":
                thread.join(5)
        status = client.get("/whisper-models/base/status").json()
        assert status["status"] == "error"
        assert "10060" in status["errorMessage"]


def test_download_api_reports_an_installed_model(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    _snapshot(tmp_path)
    monkeypatch.setattr("backend.api.v1.speech_recognition.get_model_manager", lambda: manager)
    with _client() as client:
        response = client.post("/whisper-models/download", json={"model": "base"})
    assert response.status_code == 200
    assert response.json()["status"] == "installed"


def test_ensure_downloaded_blocks_until_the_snapshot_exists(monkeypatch, tmp_path):
    calls, download = _recording(tmp_path, fail_endpoints=("https://huggingface.co",))
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    assert manager.ensure_downloaded("base") == tmp_path / "hub/models--Systran--faster-whisper-base/snapshots/complete"
    assert manager.get_model_info("base").source == "hf-mirror"
    assert len(calls) == 2
    assert manager.ensure_downloaded("base") and len(calls) == 2  # cached: no second download


def test_ensure_downloaded_raises_the_recorded_error(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_WHISPER_MODEL_SOURCE", "huggingface")
    _, download = _recording(tmp_path, fail_endpoints=("https://huggingface.co",))
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="10060"):
        manager.ensure_downloaded("base")


def test_ensure_downloaded_waits_for_a_running_download(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    manager._download_state["base"] = {"status": "downloading", "progress": 0, "error": None}
    ticks = []

    def finish(_seconds):
        ticks.append(True)
        _snapshot(tmp_path)
        manager._download_state["base"] = {"status": "downloaded", "progress": 100, "error": None, "source": "hf-mirror"}

    monkeypatch.setattr("backend.services.whisper_model_manager.time.sleep", finish)
    assert manager.ensure_downloaded("base").name == "complete"
    assert ticks == [True]
