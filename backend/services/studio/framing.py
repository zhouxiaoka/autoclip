"""Speaker-following framing for the portrait crop layout.

Every few seconds we grab two frames a quarter second apart, detect faces with OpenCV's YuNet model
(bundled ONNX, MIT licence) and pick the face whose mouth region moved most — the person talking.
Those positions become a piecewise-constant crop track per scene, so the crop window follows the
conversation instead of freezing on one side. OpenCV is not part of the base install (≈45 MB); it is
installed on demand into the data directory, the same way the Whisper runtime is.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import statistics
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from backend.services.studio.models import Draft, Scene
from backend.utils.ffmpeg_utils import get_ffmpeg_path

logger = logging.getLogger(__name__)

PACKAGES = ["opencv-python-headless>=4.10"]
MODEL = Path(__file__).resolve().parents[2] / "assets" / "models" / "face_detection_yunet_2023mar.onnx"
IMPORT_NAME = "cv2"
SAMPLE_INTERVAL = 2.5      # seconds between samples inside a scene
PAIR_GAP = 0.25            # seconds between the two frames of one sample (mouth motion)
FRAME_WIDTH = 480
MOTION_THRESHOLD = 4.0     # mean abs grey difference in the mouth box that counts as "talking"
MIN_HOLD = 2               # samples a new speaker must persist before the window moves
MIN_JUMP = 0.12            # normalised distance below which two positions are the same framing


# ---------------------------------------------------------------- runtime ---
def _data_dir() -> Path:
    from backend.services.whisper_runtime import _data_dir as data_dir
    return data_dir()


def get_install_dir() -> Path:
    d = _data_dir() / "framing-runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_on_path() -> None:
    install_dir = str(get_install_dir())
    if install_dir not in sys.path:
        sys.path.insert(0, install_dir)


def is_installed() -> bool:
    ensure_on_path()
    try:
        return importlib.util.find_spec(IMPORT_NAME) is not None and MODEL.exists()
    except (ImportError, ValueError):
        return False


_state_lock = threading.Lock()
_state: dict[str, Any] = {"status": "unknown", "progress": 0, "message": ""}


def _set_state(**kw) -> None:
    with _state_lock:
        _state.update(kw)


def get_status() -> dict[str, Any]:
    with _state_lock:
        state = dict(_state)
    if state["status"] in ("unknown", "installed", "not_installed"):
        state["status"] = "installed" if is_installed() else "not_installed"
    state["size_mb"] = 45
    return state


def _do_install(index_url: str | None) -> None:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--target", str(get_install_dir()), *PACKAGES]
    if index_url:
        cmd += ["--index-url", index_url]
    _set_state(status="installing", progress=5, message="正在下载人物识别组件…")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
        if proc.returncode == 0 and is_installed():
            _set_state(status="installed", progress=100, message="安装完成")
        else:
            _set_state(status="error", message=f"安装失败（pip 退出码 {proc.returncode}）：{proc.stdout[-300:]}")
    except (OSError, subprocess.SubprocessError) as error:
        logger.exception("安装人物识别组件异常")
        _set_state(status="error", message=f"安装异常: {error}")


def start_install(index_url: str | None = None) -> dict[str, Any]:
    with _state_lock:
        if _state["status"] == "installing":
            return {"started": False, "message": "正在安装中"}
    if is_installed():
        _set_state(status="installed", progress=100, message="已安装")
        return {"started": False, "message": "已安装"}
    threading.Thread(target=_do_install, args=(index_url or os.getenv("PIP_INDEX_URL"),), name="framing-install", daemon=True).start()
    return {"started": True, "message": "已开始安装"}


# ------------------------------------------------------------------- math ---
def window_fraction(source_w: int, source_h: int, out_w: int, out_h: int) -> float:
    """Width of the crop window as a fraction of the source width, for a cover-scaled crop."""
    scale = max(out_w / source_w, out_h / source_h)
    return min(1.0, out_w / (source_w * scale))


def crop_x_for_center(center_x: float, fraction: float) -> float:
    """crop filter uses x=(iw-ow)*crop_x; place the window so `center_x` (0..1) sits in its middle."""
    if fraction >= 1:
        return .5
    return max(0.0, min(1.0, (center_x - fraction / 2) / (1 - fraction)))


def segment_track(samples: list[tuple[float, float]], min_hold: int = MIN_HOLD, min_jump: float = MIN_JUMP) -> list[dict[str, float]]:
    """Turn (time, crop_x) samples into hold segments.

    The window only moves when a clearly different position persists for `min_hold` samples,
    so a single glance to the other person does not swing the frame back and forth.
    """
    if not samples:
        return []
    track: list[dict[str, float]] = []
    current = samples[0][1]
    track.append({"start": 0.0, "crop_x": round(current, 3)})
    pending: list[tuple[float, float]] = []
    for t, x in samples[1:]:
        if abs(x - current) < min_jump:
            pending = []
            continue
        if pending and abs(x - pending[0][1]) >= min_jump:
            pending = []
        pending.append((t, x))
        if len(pending) >= min_hold:
            current = statistics.median(v for _, v in pending)
            track.append({"start": round(pending[0][0], 2), "crop_x": round(current, 3)})
            pending = []
    return track


def crop_expression(scene: Scene, fallback: float) -> str:
    """ffmpeg expression for the crop window position within one scene (t is scene-relative)."""
    points = scene.crop_track or []
    static = scene.crop_x if scene.crop_x is not None else fallback
    if len(points) <= 1:
        return f"{points[0].crop_x if points else static}"
    # Nest from the first point outwards: each boundary tests the *next* point's start.
    expression = f"{points[0].crop_x}"
    for point in points[1:]:
        expression = f"if(lt(t,{point.start}),{expression},{point.crop_x})"
    return expression


# ------------------------------------------------------------------ frames ---
def _grab_pair(video: Path, at: float, folder: Path, key: str) -> tuple[Path, Path] | None:
    pattern = folder / f"{key}-%d.jpg"
    cmd = [get_ffmpeg_path(), "-v", "error", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "2",
           "-vf", f"fps=1/{PAIR_GAP},scale={FRAME_WIDTH}:-2", "-q:v", "4", "-y", str(pattern)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    first, second = folder / f"{key}-1.jpg", folder / f"{key}-2.jpg"
    if not first.exists():
        return None
    return first, second if second.exists() else first


def _speaker_center(pair: tuple[Path, Path]) -> float | None:
    """Normalised x-centre of the talking face; the largest face when nobody's mouth moves."""
    ensure_on_path()
    import cv2  # installed on demand

    first = cv2.imread(str(pair[0]))
    second = cv2.imread(str(pair[1]))
    if first is None:
        return None
    height, width = first.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(MODEL), "", (width, height), score_threshold=0.6, nms_threshold=0.3, top_k=50)
    _, faces = detector.detect(first)
    if faces is None or len(faces) == 0:
        return None
    grey_a = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    grey_b = cv2.cvtColor(second, cv2.COLOR_BGR2GRAY) if second is not None and second.shape == first.shape else None
    best, best_motion = None, -1.0
    for face in faces:
        w, h = face[2], face[3]
        # YuNet landmarks: right eye, left eye, nose, right mouth corner, left mouth corner.
        mx1, my1, mx2, my2 = face[10], face[11], face[12], face[13]
        if grey_b is not None:
            left, right = int(max(0, min(mx1, mx2) - w * .1)), int(min(width, max(mx1, mx2) + w * .1))
            top, bottom = int(max(0, min(my1, my2) - h * .12)), int(min(height, max(my1, my2) + h * .2))
            if right > left and bottom > top:
                motion = float(abs(grey_a[top:bottom, left:right].astype("int16") - grey_b[top:bottom, left:right].astype("int16")).mean())
            else:
                motion = 0.0
        else:
            motion = 0.0
        if motion > best_motion:
            best, best_motion = face, motion
    if best_motion < MOTION_THRESHOLD:
        best = max(faces, key=lambda f: f[2] * f[3])
    x, w = best[0], best[2]
    return float((x + w / 2) / width)


def auto_frame(video: Path, draft: Draft, source_w: int, source_h: int) -> dict[str, Any]:
    """Speaker-following crop tracks per scene; scenes without a face keep the draft framing."""
    if not is_installed():
        raise RuntimeError("人物识别组件未安装")
    out_w, out_h = {"portrait": (1080, 1920), "landscape": (1920, 1080)}.get(draft.aspect, (source_w, source_h))
    fraction = window_fraction(source_w, source_h, out_w, out_h)
    scenes = []
    with tempfile.TemporaryDirectory(prefix="ac-framing-") as temp:
        folder = Path(temp)
        for scene in draft.scenes:
            length = scene.end - scene.start
            count = max(1, int(length // SAMPLE_INTERVAL) + 1)
            samples: list[tuple[float, float]] = []
            grabbed = 0
            for i in range(count):
                rel = min(length - PAIR_GAP - .05, SAMPLE_INTERVAL * i + .5) if length > 1 else length / 2
                rel = max(0.0, rel)
                pair = _grab_pair(video, scene.start + rel, folder, f"{scene.id}-{i}")
                if not pair:
                    continue
                grabbed += 1
                center = _speaker_center(pair)
                if center is not None:
                    samples.append((rel, crop_x_for_center(center, fraction)))
            if samples:
                track = segment_track(samples)
                scenes.append({"id": scene.id, "crop_x": track[0]["crop_x"], "crop_track": track,
                               "faces": len(samples), "samples": grabbed, "switches": len(track) - 1})
            else:
                scenes.append({"id": scene.id, "crop_x": None, "crop_track": None, "faces": 0, "samples": grabbed, "switches": 0})
    return {"scenes": scenes, "window_fraction": round(fraction, 3)}
