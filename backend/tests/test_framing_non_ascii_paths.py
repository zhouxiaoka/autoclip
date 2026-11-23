"""Regression tests for PYTHON-FASTAPI-68: YuNet and frame loading on non-ASCII paths.

On Windows, OpenCV's C++ file-path APIs (`cv2.FaceDetectorYN.create(str(path), ...)` and
`cv2.imread(str(path))`) open paths with the narrow ANSI codepage instead of UTF-8, so
installing AutoClip or storing temp frames under a non-ASCII directory (such as a Chinese
Windows username) raises `cv2.error` in `framing._detector` or returns `None` from `imread`.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from backend.services.studio import framing
from backend.services.studio.qa import face as qa_face

COVER = framing.MODEL.parents[1] / "example" / "cover.jpg"


def _windows_ascii_only_cv2():
    """Proxy real cv2 while enforcing Windows-like ASCII-only C++ file-path behavior."""

    class _StrictFaceDetectorYN:
        @staticmethod
        def create(*args, **kwargs):
            # File-path overload: create(model_path: str, config: str, input_size, ...)
            # Buffer overload: create(framework: str, bufferModel: bytes/ndarray, bufferConfig, input_size, ...)
            if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], str):
                if not args[0].isascii():
                    raise cv2.error(f"Can't read ONNX file: {args[0]}")
            return cv2.FaceDetectorYN.create(*args, **kwargs)

    def _strict_imread(filename, *args, **kwargs):
        if isinstance(filename, str) and not filename.isascii():
            return None
        return cv2.imread(filename, *args, **kwargs)

    class _Proxy:
        FaceDetectorYN = _StrictFaceDetectorYN
        imread = staticmethod(_strict_imread)

        def __getattr__(self, name):
            return getattr(cv2, name)

    return _Proxy()


def _copy_model_to_unicode_dir(tmp_path: Path) -> Path:
    dest_dir = tmp_path / "用户安装目录" / "models"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / framing.MODEL.name
    shutil.copy2(framing.MODEL, dest)
    return dest


def test_detector_loads_yunet_from_non_ascii_model_path(tmp_path, monkeypatch):
    unicode_model = _copy_model_to_unicode_dir(tmp_path)
    monkeypatch.setattr(framing, "MODEL", unicode_model)
    monkeypatch.setattr(framing, "_detectors", {})

    strict_cv2 = _windows_ascii_only_cv2()
    cover = cv2.resize(cv2.imdecode(np.frombuffer(COVER.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR), (480, 270))

    with framing._detector_lock:
        detector = framing._detector(strict_cv2, 480, 270)
        ok, faces = detector.detect(cover)

    assert ok == 1
    assert faces is not None and len(faces) >= 1


def test_detector_loads_yunet_natively_from_non_ascii_path(tmp_path, monkeypatch):
    """Runs against real cv2 without proxy (catches native Windows OpenCV C++ path failures)."""
    unicode_model = _copy_model_to_unicode_dir(tmp_path)
    monkeypatch.setattr(framing, "MODEL", unicode_model)
    monkeypatch.setattr(framing, "_detectors", {})

    cover = cv2.resize(cv2.imdecode(np.frombuffer(COVER.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR), (480, 270))

    with framing._detector_lock:
        detector = framing._detector(cv2, 480, 270)
        ok, faces = detector.detect(cover)

    assert ok == 1
    assert faces is not None and len(faces) >= 1


def test_qa_face_detect_loads_yunet_from_non_ascii_model_path(tmp_path, monkeypatch):
    unicode_model = _copy_model_to_unicode_dir(tmp_path)
    monkeypatch.setattr(framing, "MODEL", unicode_model)
    monkeypatch.setattr(qa_face, "_nets", {})

    strict_cv2 = _windows_ascii_only_cv2()
    cover = cv2.resize(cv2.imdecode(np.frombuffer(COVER.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR), (320, 180))

    ok, faces = qa_face._detect(strict_cv2, cover)
    assert ok == 1
    assert faces is not None and len(faces) >= 1


def test_observe_pair_reads_non_ascii_frame_and_model_paths(tmp_path, monkeypatch):
    unicode_model = _copy_model_to_unicode_dir(tmp_path)
    frame_dir = tmp_path / "中文临时目录"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_path = frame_dir / "帧_001.jpg"
    cover = cv2.resize(cv2.imdecode(np.frombuffer(COVER.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR), (480, 270))
    ok, encoded = cv2.imencode(".jpg", cover)
    assert ok
    frame_path.write_bytes(encoded.tobytes())

    strict_cv2 = _windows_ascii_only_cv2()
    monkeypatch.setattr(framing, "MODEL", unicode_model)
    monkeypatch.setattr(framing, "_detectors", {})
    monkeypatch.setattr(framing, "load_cv2", lambda: strict_cv2)

    observed = framing._observe_pair((frame_path, frame_path))
    assert observed is not None
    assert len(observed["frontal"]) >= 1


def test_buffer_loaded_detector_matches_path_loaded_detector():
    cover = cv2.resize(cv2.imdecode(np.frombuffer(COVER.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR), (480, 270))
    path_det = cv2.FaceDetectorYN.create(
        str(framing.MODEL), "", (480, 270),
        score_threshold=framing.TRACK_SCORE, nms_threshold=0.3, top_k=50,
    )
    ok_path, faces_path = path_det.detect(cover)

    with framing._detector_lock:
        buf_det = framing._detector(cv2, 480, 270, framing.TRACK_SCORE)
        ok_buf, faces_buf = buf_det.detect(cover)

    assert ok_buf == ok_path
    assert faces_buf is not None and faces_path is not None
    np.testing.assert_allclose(faces_buf, faces_path, rtol=1e-6, atol=1e-6)


def test_create_detector_falls_back_when_cv2_lacks_buffer_overload():
    calls = []

    class _LegacyFaceDetectorYN:
        @staticmethod
        def create(model, config, input_size, *, score_threshold, nms_threshold, top_k):
            calls.append((model, config, input_size, score_threshold, nms_threshold, top_k))
            return "legacy-detector"

    legacy_cv2 = SimpleNamespace(FaceDetectorYN=_LegacyFaceDetectorYN)
    result = framing.create_detector(legacy_cv2, 480, 270, 0.6)
    assert result == "legacy-detector"
    assert calls == [(str(framing.MODEL), "", (480, 270), 0.6, 0.3, 50)]
