"""PYTHON-FASTAPI-40: a broken cv2/numpy import must degrade, not 502 or report to Sentry."""
import sys

import pytest
from fastapi.testclient import TestClient

from backend.services import whisper_runtime
from backend.services.studio import framing


@pytest.fixture
def broken_cv2(monkeypatch, tmp_path):
    runtime = tmp_path / "framing-runtime"
    (runtime / "cv2").mkdir(parents=True)
    (runtime / "cv2" / "__init__.py").write_text(
        "raise ImportError('Error importing numpy: you should not try to import numpy from its source directory')\n")
    monkeypatch.setattr(framing, "get_install_dir", lambda: runtime)
    monkeypatch.setattr(framing, "MODEL", tmp_path / "model.onnx")
    (tmp_path / "model.onnx").write_bytes(b"x")
    monkeypatch.setattr(sys, "path", list(sys.path))
    for name in [n for n in sys.modules if n.split(".")[0] == "cv2"]:
        monkeypatch.delitem(sys.modules, name)
    framing.reset_cv2_cache()
    yield runtime
    framing.reset_cv2_cache()
    for name in [n for n in sys.modules if n.split(".")[0] == "cv2"]:
        sys.modules.pop(name, None)


def test_broken_cv2_is_not_installed_and_cleans_modules(broken_cv2):
    assert framing.load_cv2() is None
    assert framing.is_installed() is False
    assert "cv2" not in sys.modules
    assert "重新安装" in framing.unavailable_reason()


def test_speaker_center_falls_back_without_raising(broken_cv2, tmp_path):
    frame = tmp_path / "a.jpg"
    frame.write_bytes(b"")
    assert framing._speaker_center((frame, frame)) is None


def test_auto_frame_endpoint_returns_409_without_sentry(broken_cv2, monkeypatch):
    from backend.api.v1 import studio
    monkeypatch.setattr(studio, "project_or_404", lambda *_a, **_k: None)
    monkeypatch.setattr(studio, "capture_studio_exception", lambda *_a, **_k: pytest.fail("must not report to Sentry"))
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(studio.router)
    app.dependency_overrides[studio.get_db] = lambda: None
    body = {"id": "d", "title": "T", "scenes": [{"id": "s", "label": "S", "start": 0, "end": 5}]}
    path = next(r.path for r in studio.router.routes if r.path.endswith("/auto-frame")).replace("{project_id}", "p1")
    response = TestClient(app).post(path, json=body)
    assert response.status_code == 409
    assert "重新安装" in response.json()["detail"]


def test_framing_runtime_precedes_whisper_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "path", ["/stdlib"])
    framing_dir = tmp_path / "framing-runtime"
    whisper_dir = tmp_path / "whisper-runtime"
    monkeypatch.setattr(framing, "get_install_dir", lambda: framing_dir)
    monkeypatch.setattr(whisper_runtime, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(whisper_runtime, "get_install_dir", lambda: whisper_dir)
    monkeypatch.setattr(whisper_runtime, "get_models_dir", lambda: tmp_path / "models")
    framing.ensure_on_path()
    whisper_runtime.ensure_on_path()
    assert sys.path.index(str(framing_dir)) < sys.path.index(str(whisper_dir))
    monkeypatch.setattr(sys, "path", ["/stdlib"])
    whisper_runtime.ensure_on_path()
    framing.ensure_on_path()
    assert sys.path.index(str(framing_dir)) < sys.path.index(str(whisper_dir))
