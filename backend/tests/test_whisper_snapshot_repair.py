"""Corrupt Whisper snapshots are deleted and downloaded again. No force_download.

HuggingFace writes a snapshot path only when it is missing, and on a copy layout
(Windows without developer mode) it reuses a blob that already exists. force_download
refreshes the blob and still leaves that copy in place, so a bad file is removed
first and the next call is a normal snapshot_download.

The fake follows those rules: an existing snapshot path is never overwritten, a blob
that exists is reused at any size, and a ``.incomplete`` blob resumes with a Range
for the bytes already on disk. Passing force_download is an error.
"""
import errno
import hashlib
import os
import shutil
import sys
import types
from pathlib import Path

import pytest

from backend.services import whisper_runtime
from backend.services.whisper_model_manager import ModelStatus, WhisperModelManager

REV = "rev1"
FILES = {
    "model.bin": b"weights-full",
    "config.json": b"{}",
    "tokenizer.json": b"tok",
    "vocabulary.json": b"voc",
}
ETAG = {name: hashlib.sha256(data).hexdigest() for name, data in FILES.items()}
REPO = "Systran/faster-whisper-base"


@pytest.fixture(autouse=True)
def _clean_source_env(monkeypatch):
    for name in ("AUTOCLIP_WHISPER_MODEL_SOURCE", "HF_ENDPOINT", "HF_HUB_DISABLE_XET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("backend.services.whisper_model_manager._reachable", lambda endpoint, timeout=0: True)
    monkeypatch.setattr(
        "backend.services.whisper_model_manager.download_plan",
        lambda: [("huggingface", "https://huggingface.co")],
    )


def _manager(monkeypatch, tmp_path: Path) -> WhisperModelManager:
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: True)
    monkeypatch.setattr(whisper_runtime, "ensure_on_path", lambda: None)
    monkeypatch.setattr(whisper_runtime, "get_models_dir", lambda: tmp_path)
    return WhisperModelManager()


class HubCache:
    """huggingface_hub cache rules, both layouts. force_download is refused."""

    def __init__(self, root: Path, layout: str, *, short: bool = False):
        self.layout = layout
        self.short = short
        self.repo = root / "hub" / "models--Systran--faster-whisper-base"
        self.snap = self.repo / "snapshots" / REV
        self.blobs = self.repo / "blobs"
        self.calls = 0
        self.ranges: list[tuple[str, int]] = []

    def snapshot_download(self, **kwargs):
        if kwargs.get("force_download"):
            raise AssertionError("force_download")
        self.calls += 1
        self.snap.mkdir(parents=True, exist_ok=True)
        self.blobs.mkdir(parents=True, exist_ok=True)
        for name, data in FILES.items():
            payload = data[:1] if self.short and name == "model.bin" else data
            self._ensure(name, payload)
        ref = self.repo / "refs" / "main"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text(REV, encoding="utf-8")
        return str(self.snap)

    def _ensure(self, name: str, payload: bytes) -> None:
        etag = ETAG[name]
        blob = self.blobs / etag
        pointer = self.snap / name
        incomplete = self.blobs / f"{etag}.incomplete"
        if pointer.is_symlink() or pointer.exists():
            return
        if blob.is_file():
            self._place(blob, pointer)
            return
        have = incomplete.read_bytes() if incomplete.is_file() else b""
        self.ranges.append((name, len(have)))
        blob.write_bytes(payload)
        if incomplete.exists():
            incomplete.unlink()
        self._place(blob, pointer)

    def _place(self, blob: Path, pointer: Path) -> None:
        if pointer.is_symlink() or pointer.exists():
            return
        pointer.parent.mkdir(parents=True, exist_ok=True)
        if self.layout == "symlink":
            pointer.symlink_to(os.path.relpath(blob, start=pointer.parent))
        else:
            shutil.copyfile(blob, pointer)

    def seed_good(self, name: str) -> None:
        self.snap.mkdir(parents=True, exist_ok=True)
        self.blobs.mkdir(parents=True, exist_ok=True)
        blob = self.blobs / ETAG[name]
        blob.write_bytes(FILES[name])
        self._place(blob, self.snap / name)

    def seed_bytes(self, name: str, payload: bytes, *, blob_name: str | None = None) -> None:
        self.snap.mkdir(parents=True, exist_ok=True)
        self.blobs.mkdir(parents=True, exist_ok=True)
        blob = self.blobs / (blob_name or ETAG[name])
        blob.write_bytes(payload)
        pointer = self.snap / name
        if pointer.is_symlink() or pointer.exists():
            pointer.unlink()
        if self.layout == "symlink":
            pointer.symlink_to(os.path.relpath(blob, start=pointer.parent))
        else:
            shutil.copyfile(blob, pointer)


class FakeApi:
    def __init__(self, endpoint=None):
        self.endpoint = endpoint

    fail = False
    calls: list[tuple] = []

    def get_paths_info(self, repo_id, paths, revision=None):
        if type(self).fail:
            raise ConnectionError("metadata down")
        type(self).calls.append((repo_id, revision, tuple(paths)))
        found = []
        for name in paths:
            if name not in FILES:
                continue
            data = FILES[name]
            found.append(types.SimpleNamespace(
                path=name, size=len(data),
                lfs=types.SimpleNamespace(sha256=ETAG[name], size=len(data)),
            ))
        return found


def _install(monkeypatch, hub: HubCache, api_cls=FakeApi):
    module = types.ModuleType("huggingface_hub")
    module.snapshot_download = hub.snapshot_download
    module.HfApi = api_cls
    utils = types.ModuleType("huggingface_hub.utils")
    utils.disable_progress_bars = lambda: None
    constants = types.ModuleType("huggingface_hub.constants")
    constants.HF_HUB_DISABLE_XET = False
    module.constants = constants
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", utils)
    monkeypatch.setitem(sys.modules, "huggingface_hub.constants", constants)
    api_cls.fail = False
    api_cls.calls = []


def _corrupt(monkeypatch, tmp_path, layout, kind) -> tuple[WhisperModelManager, HubCache]:
    hub = HubCache(tmp_path, layout)
    for name in FILES:
        if name != "model.bin":
            hub.seed_good(name)
    if kind == "empty":
        hub.seed_bytes("model.bin", b"")
    elif kind == "truncated":
        hub.seed_bytes("model.bin", FILES["model.bin"][:1])
    elif kind == "blob":
        hub.seed_bytes("model.bin", FILES["model.bin"][:1])
    else:
        raise AssertionError(kind)
    _install(monkeypatch, hub)
    return _manager(monkeypatch, tmp_path), hub


@pytest.mark.parametrize("layout", ["symlink", "copy"])
@pytest.mark.parametrize("kind", ["empty", "truncated", "blob"])
def test_corrupt_file_is_deleted_and_redownloaded_without_force(monkeypatch, tmp_path, layout, kind):
    manager, hub = _corrupt(monkeypatch, tmp_path, layout, kind)
    manager._download_blocking("base")
    info = manager.get_model_info("base")
    assert info.status == ModelStatus.DOWNLOADED, (layout, kind, info.status, info.error_message)
    path = manager.get_local_model_path("base")
    assert path is not None and (path / "model.bin").read_bytes() == FILES["model.bin"]
    assert hub.calls == 2  # the bad snapshot is returned, then a normal download rewrites it
    assert FakeApi.calls and FakeApi.calls[0][:2] == (REPO, REV)
    assert all(start == 0 for _name, start in hub.ranges)


def test_copy_layout_keeps_a_good_blob_and_replaces_only_the_snapshot_file(monkeypatch, tmp_path):
    hub = HubCache(tmp_path, "copy")
    for name in FILES:
        if name != "model.bin":
            hub.seed_good(name)
    blob = hub.blobs / ETAG["model.bin"]
    hub.blobs.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(FILES["model.bin"])
    pointer = hub.snap / "model.bin"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_bytes(b"w")  # truncated copy; the blob itself is complete
    _install(monkeypatch, hub)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    assert manager.get_model_info("base").status == ModelStatus.DOWNLOADED
    assert pointer.read_bytes() == FILES["model.bin"]
    assert blob.read_bytes() == FILES["model.bin"]
    assert hub.ranges == []  # the good blob was copied, not downloaded again
    assert hub.calls == 2


def test_symlink_to_the_wrong_blob_name_is_replaced(monkeypatch, tmp_path):
    hub = HubCache(tmp_path, "symlink")
    for name in FILES:
        if name != "model.bin":
            hub.seed_good(name)
    hub.seed_bytes("model.bin", b"x" * len(FILES["model.bin"]), blob_name="not-the-sha")
    _install(monkeypatch, hub)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    path = manager.get_local_model_path("base")
    assert path is not None and (path / "model.bin").read_bytes() == FILES["model.bin"]
    assert (path / "model.bin").is_symlink()
    assert not (hub.blobs / "not-the-sha").exists()


@pytest.mark.parametrize("layout", ["symlink", "copy"])
def test_incomplete_blob_resumes_with_a_range_and_without_force(monkeypatch, tmp_path, layout):
    hub = HubCache(tmp_path, layout)
    for name in FILES:
        if name != "model.bin":
            hub.seed_good(name)
    partial = FILES["model.bin"][:4]
    incomplete = hub.blobs / f"{ETAG['model.bin']}.incomplete"
    incomplete.parent.mkdir(parents=True, exist_ok=True)
    incomplete.write_bytes(partial)
    _install(monkeypatch, hub)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    assert manager.get_model_info("base").status == ModelStatus.DOWNLOADED
    assert hub.calls == 1
    assert ("model.bin", len(partial)) in hub.ranges
    assert all(name != "model.bin" or start == len(partial) for name, start in hub.ranges)


def test_metadata_down_still_replaces_an_empty_file(monkeypatch, tmp_path, caplog):
    hub = HubCache(tmp_path, "copy")
    for name in FILES:
        if name != "model.bin":
            hub.seed_good(name)
    pointer = hub.snap / "model.bin"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_bytes(b"")  # no blob: metadata is down, so only the empty file can be dropped
    _install(monkeypatch, hub)
    FakeApi.fail = True
    manager = _manager(monkeypatch, tmp_path)
    with caplog.at_level("WARNING"):
        manager._download_blocking("base")
    assert manager.get_model_info("base").status == ModelStatus.DOWNLOADED
    assert pointer.read_bytes() == FILES["model.bin"]
    assert any("仓库文件信息暂时读不到" in record.message for record in caplog.records)


def test_still_corrupt_after_a_redownload_is_an_error(monkeypatch, tmp_path):
    hub = HubCache(tmp_path, "copy", short=True)
    _install(monkeypatch, hub)
    manager = _manager(monkeypatch, tmp_path)
    manager._download_blocking("base")
    info = manager.get_model_info("base")
    assert info.status == ModelStatus.ERROR
    assert info.error_code == "whisper_download_failed"
    assert hub.calls == 2


def _sentry(monkeypatch):
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
    monkeypatch.setenv("SENTRY_DSN", "https://k@o0.ingest.sentry.io/0")
    # refuses pytest and a source checkout. Stub only those two refusals so this
    # test still runs the real init, privacy filter and volume hook.
    monkeypatch.setenv("AUTOCLIP_APP_VERSION", "1.5.7")
    monkeypatch.setenv("AUTOCLIP_BUILD_ENVIRONMENT", "production")
    monkeypatch.setattr(sentry_setup, "_under_pytest", lambda: False)
    monkeypatch.setattr(sentry_setup, "_running_from_source_tree", lambda: False)
    assert sentry_setup.init_sentry("desktop") is True
    return events, real_init


def _end_sentry(real_init):
    import sentry_sdk
    from backend.core import sentry_setup
    try:
        sentry_sdk.flush(timeout=0)
        sentry_sdk.get_client().close(timeout=0)
    except Exception:
        pass
    sentry_setup._initialized = False
    real_init(dsn="")


def test_three_sources_that_fail_the_network_report_once(monkeypatch, tmp_path):
    events, real_init = _sentry(monkeypatch)

    def drop(**kwargs):
        raise ConnectionError("reset https://huggingface.co/Systran/x?token=secret")

    module = types.ModuleType("huggingface_hub")
    module.snapshot_download = drop
    utils = types.ModuleType("huggingface_hub.utils")
    utils.disable_progress_bars = lambda: None
    constants = types.ModuleType("huggingface_hub.constants")
    constants.HF_HUB_DISABLE_XET = False
    module.constants = constants
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", utils)
    monkeypatch.setitem(sys.modules, "huggingface_hub.constants", constants)
    monkeypatch.setattr("backend.services.whisper_model_manager.download_plan", lambda: [
        ("huggingface", "https://huggingface.co"),
        ("hf-mirror", "https://hf-mirror.com"),
        ("custom", "https://example.invalid"),
    ])
    manager = _manager(monkeypatch, tmp_path)
    import sentry_sdk
    try:
        manager._download_blocking("base")
        sentry_sdk.flush()
        assert manager.get_model_info("base").status == ModelStatus.ERROR
        assert len(events) == 1, f"one final report, got {len(events)}"
        tags = events[0].get("tags", {})
        assert tags.get("phase") == "model_download" and tags.get("error_code") == "network", tags
        text = str(events[0])
        for leaked in ("huggingface.co", "secret", "token", str(tmp_path)):
            assert leaked not in text, leaked
    finally:
        _end_sentry(real_init)


def test_a_disk_full_download_reports_disk_once(monkeypatch, tmp_path):
    events, real_init = _sentry(monkeypatch)

    def full(**kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    module = types.ModuleType("huggingface_hub")
    module.snapshot_download = full
    utils = types.ModuleType("huggingface_hub.utils")
    utils.disable_progress_bars = lambda: None
    constants = types.ModuleType("huggingface_hub.constants")
    constants.HF_HUB_DISABLE_XET = False
    module.constants = constants
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", utils)
    monkeypatch.setitem(sys.modules, "huggingface_hub.constants", constants)
    manager = _manager(monkeypatch, tmp_path)
    import sentry_sdk
    try:
        manager._download_blocking("base")
        sentry_sdk.flush()
        assert len(events) == 1
        assert events[0].get("tags", {}).get("error_code") == "disk"
        assert "No space" not in str(events[0])
    finally:
        _end_sentry(real_init)


def test_download_failure_code_walks_the_cause_and_ignores_http_status():
    from backend.services.whisper_model_manager import ModelDownloadFailed, download_failure_code
    import requests
    assert download_failure_code(ConnectionError("reset")) == "network"
    assert download_failure_code(TimeoutError()) == "network"
    assert download_failure_code(requests.Timeout("slow")) == "network"
    assert download_failure_code(requests.ConnectionError("reset")) == "network"
    assert download_failure_code(requests.HTTPError("404")) == "unexpected"
    assert download_failure_code(OSError(errno.ENOSPC, "full")) == "disk"
    assert download_failure_code(OSError(errno.EACCES, "denied")) == "disk"
    assert download_failure_code(OSError(errno.EROFS, "ro")) == "disk"
    assert download_failure_code(OSError(22, "invalid")) == "unexpected"
    assert download_failure_code(ModelDownloadFailed("corrupt")) == "corrupt"
    assert download_failure_code(ModelDownloadFailed("nope")) == "unexpected"

    class ConnectTimeout(Exception):
        pass
    ConnectTimeout.__module__ = "httpx"
    assert download_failure_code(ConnectTimeout()) == "network"

    try:
        raise ConnectionError("reset")
    except ConnectionError as cause:
        try:
            raise RuntimeError("huggingface_hub wrapped it") from cause
        except RuntimeError as wrapped:
            assert download_failure_code(wrapped) == "network"


@pytest.mark.real_hf
def test_real_hub_copy_layout_does_not_replace_an_existing_file(tmp_path, monkeypatch):
    """The fake's 'never overwrite a snapshot path' rule, checked against the installed library."""
    pytest.importorskip("huggingface_hub")
    file_download = pytest.importorskip("huggingface_hub.file_download")
    create = getattr(file_download, "_create_symlink", None)
    if create is None or not hasattr(file_download, "are_symlinks_supported"):
        pytest.skip("this huggingface_hub has no copy-layout hook to compare")
    monkeypatch.setattr(file_download, "are_symlinks_supported", lambda *args, **kwargs: False)
    blob = tmp_path / "blobs" / "etag"
    blob.parent.mkdir()
    blob.write_bytes(b"fresh-bytes-from-the-hub")
    pointer = tmp_path / "snapshots" / "rev" / "model.bin"
    pointer.parent.mkdir(parents=True)
    pointer.write_bytes(b"truncated")
    create(str(blob), str(pointer), True)
    assert pointer.read_bytes() == b"truncated"
    assert not pointer.is_symlink()
