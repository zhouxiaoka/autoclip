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
    # never probe the real network from tests; individual tests override this
    monkeypatch.setattr("backend.services.whisper_model_manager._reachable", lambda endpoint, timeout=0: True)


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
    from backend.services.whisper_model_manager import WHISPER_DOWNLOAD_USER_ERROR
    assert info.error_message == WHISPER_DOWNLOAD_USER_ERROR
    assert "10060" not in (info.error_message or "")


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
    from backend.services.whisper_model_manager import WHISPER_DOWNLOAD_USER_ERROR
    assert info.error_message == WHISPER_DOWNLOAD_USER_ERROR
    assert "huggingface.co" not in (info.error_message or "")


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
        from backend.services.whisper_model_manager import WHISPER_DOWNLOAD_USER_ERROR
        assert status["errorMessage"] == WHISPER_DOWNLOAD_USER_ERROR
        assert "10060" not in status["errorMessage"]


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
    from backend.services.whisper_model_manager import WHISPER_DOWNLOAD_USER_ERROR
    with pytest.raises(RuntimeError, match="Whisper 模型下载失败"):
        manager.ensure_downloaded("base")
    assert manager.get_model_info("base").error_message == WHISPER_DOWNLOAD_USER_ERROR


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


# --- E3: model download source setting + auto probe ---------------------------------------

def test_e3_auto_starts_with_mirror_when_official_is_unreachable(monkeypatch, tmp_path):
    from backend.services import whisper_model_manager as wmm
    monkeypatch.setattr(wmm, "_reachable", lambda endpoint, timeout=0: endpoint == wmm.MIRROR_ENDPOINT)
    calls, download = _recording(tmp_path)
    _install_fake_hub(monkeypatch, download)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    assert [call["endpoint"] for call in calls] == ["https://hf-mirror.com"]
    assert calls[0]["xet_disabled"] is True
    assert manager.get_model_info("base").source == "hf-mirror"


def test_e3_auto_keeps_official_first_when_mirror_also_unreachable(monkeypatch, tmp_path):
    from backend.services import whisper_model_manager as wmm
    monkeypatch.setattr(wmm, "_reachable", lambda endpoint, timeout=0: False)
    assert [s for s, _ in wmm.download_plan()] == ["huggingface", "hf-mirror"]


def test_e3_saved_source_is_used_and_validated(monkeypatch, tmp_path):
    from backend.services import whisper_model_manager as wmm
    monkeypatch.setattr(whisper_runtime, "get_models_dir", lambda: tmp_path)
    assert wmm.saved_model_source() == "auto"
    assert wmm.save_model_source("hf-mirror") == "hf-mirror"
    assert wmm.download_plan() == [("hf-mirror", wmm.MIRROR_ENDPOINT)]
    wmm.save_model_source("huggingface")
    assert wmm.download_plan() == [("huggingface", wmm.OFFICIAL_ENDPOINT)]
    with pytest.raises(ValueError):
        wmm.save_model_source("https://evil.example")
    monkeypatch.setenv("AUTOCLIP_WHISPER_MODEL_SOURCE", "hf-mirror")
    assert wmm.model_source() == "hf-mirror"  # env override for QA still wins


def test_e3_model_source_api_round_trip(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1 import speech_recognition
    monkeypatch.setattr(whisper_runtime, "get_models_dir", lambda: tmp_path)
    app = FastAPI()
    app.include_router(speech_recognition.router)
    client = TestClient(app)
    assert client.get("/whisper/model-source").json()["source"] == "auto"
    assert client.put("/whisper/model-source", json={"source": "hf-mirror"}).json() == {"source": "hf-mirror"}
    assert client.get("/whisper/model-source").json()["source"] == "hf-mirror"
    assert client.put("/whisper/model-source", json={"source": "nope"}).status_code == 422


def test_r2_status_api_never_echoes_raw_download_exception(monkeypatch, tmp_path):
    """exception text with URL/query must not reach GET status errorMessage."""
    secret = "tok_leaked_credential_r2"
    url = f"https://huggingface.co/models/x?token={secret}"

    def boom(**_kwargs):
        raise ConnectionError(f"Failed to download {url} Authorization: Bearer {secret}")

    _install_fake_hub(monkeypatch, boom)
    manager = _manager(monkeypatch, tmp_path)
    monkeypatch.setattr("backend.api.v1.speech_recognition.get_model_manager", lambda: manager)
    manager._download_blocking("base")
    info = manager.get_model_info("base")
    from backend.services.whisper_model_manager import WHISPER_DOWNLOAD_USER_ERROR
    assert info.error_message == WHISPER_DOWNLOAD_USER_ERROR
    assert secret not in (info.error_message or "")
    assert "huggingface.co" not in (info.error_message or "")
    with _client() as client:
        status = client.get("/whisper-models/base/status").json()
    assert status["status"] == "error"
    assert status["errorMessage"] == WHISPER_DOWNLOAD_USER_ERROR
    assert secret not in status["errorMessage"]
    assert url not in status["errorMessage"]



def test_r28_i520_background_download_failure_is_reported_once_without_text_url_or_path(monkeypatch, tmp_path):
    """A failure in the background download thread reaches Sentry exactly once through capture_studio_exception
    (phase=model_download, an error_code), with no exception text, URL or path in the event."""
    import sentry_sdk
    from backend.core import sentry_setup

    events = []

    class Transport(sentry_sdk.transport.Transport):
        def capture_envelope(self, envelope):
            events.extend(item.payload.json for item in envelope.items if item.type == "event")

    real_init = sentry_sdk.init
    monkeypatch.setattr(sentry_sdk, "init", lambda *a, **k: real_init(*a, transport=Transport(), **k))
    monkeypatch.setattr(sentry_setup, "_initialized", False)
    monkeypatch.setattr(sentry_setup, "crash_reports_enabled", lambda: True)
    monkeypatch.setattr(sentry_setup, "sync_anonymous_user", lambda *a, **k: None)
    monkeypatch.setenv("SENTRY_DSN", "https://k@o0.ingest.sentry.io/0")  # memory transport: nothing leaves the box
    # refuses pytest and a source checkout. Stub only those two refusals.
    monkeypatch.setenv("AUTOCLIP_APP_VERSION", "1.5.7")
    monkeypatch.setenv("AUTOCLIP_BUILD_ENVIRONMENT", "production")
    monkeypatch.setattr(sentry_setup, "_under_pytest", lambda: False)
    monkeypatch.setattr(sentry_setup, "_running_from_source_tree", lambda: False)

    def drop(**kwargs):
        raise ConnectionError("Connection reset fetching https://huggingface.co/Systran/x/model.bin into /Users/someone/whisper-models/hub/blobs/abc.incomplete")

    _install_fake_hub(monkeypatch, drop)
    monkeypatch.setattr("backend.services.whisper_model_manager.download_plan", lambda: [("official", "https://huggingface.co")])
    manager = _manager(monkeypatch, tmp_path)
    try:
        assert sentry_setup.init_sentry("desktop") is True
        manager._download_blocking("base")
        sentry_sdk.flush()
        assert manager.get_model_info("base").status == ModelStatus.ERROR
        assert len(events) == 1, f"background download failure reported exactly once, got {len(events)}"
        tags = events[0].get("tags", {})
        assert tags.get("phase") == "model_download" and tags.get("area") == "studio", tags
        assert tags.get("error_code") == "network", tags
        assert "http_status" not in tags
        text = str(events[0])
        for leaked in ("Connection reset", "huggingface.co", "/Users/", "model.bin", ".incomplete", str(tmp_path)):
            assert leaked not in text, leaked
    finally:
        sentry_sdk.flush(timeout=0)
        sentry_sdk.get_client().close(timeout=0)
        sentry_setup._initialized = False
        real_init(dsn="")
