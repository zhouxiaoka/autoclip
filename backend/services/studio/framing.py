"""Shot-aware framing for the portrait crop layout.

Work in shots, not on a clock. Each scene is first split at hard cuts (ffmpeg scene-change scores),
then every shot is classified from a few frame pairs: OpenCV's YuNet model (bundled ONNX, MIT licence)
finds faces and the face whose mouth region moved most is the person talking.

- a shot with a usable face → `crop`, window centred on the speaker (long shots may switch inside);
- a shot without one (quote cards, slides, screen recordings, empty wide shots) → `fit`: the whole
  frame on a blurred backdrop, so nothing gets sliced off.

Track points sit exactly on the cuts, so the window jumps with the edit instead of lagging behind
it. OpenCV is not part of the base install (≈45 MB); it is installed on demand into the data
directory, the same way the Whisper runtime is.
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
CUT_THRESHOLD = 0.3        # ffmpeg scene-change score that counts as a hard cut
MIN_SHOT = 0.4             # seconds; cuts closer than this are flicker/transitions, not shots
MAX_SHOTS = 120            # per scene; beyond this the footage is a montage and we sample coarsely
CUT_MARGIN = 0.3           # seconds kept clear of a cut when sampling (transition frames lie)
SAMPLE_INTERVAL = 2.5      # seconds between samples inside a long shot
LONG_SHOT = 6.0            # shots longer than this may switch speaker inside
PAIR_GAP = 0.25            # seconds between the two frames of one sample (mouth motion)
FRAME_WIDTH = 480
MOTION_THRESHOLD = 4.0     # mean abs grey difference in the mouth box that counts as "talking"
MIN_FACE = 0.035           # face width below this fraction of the frame is too small to frame on
MIN_HOLD = 2               # samples a new speaker must persist before the window moves (inside a shot)
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


def fit_spans(scene: Scene) -> list[tuple[float, float]]:
    """Scene-relative (start, end) ranges rendered as `fit` instead of the moving crop."""
    points = scene.crop_track or []
    spans: list[tuple[float, float]] = []
    length = scene.end - scene.start
    for i, point in enumerate(points):
        if point.mode != "fit":
            continue
        end = points[i + 1].start if i + 1 < len(points) else length
        if end > point.start:
            spans.append((point.start, end))
    return spans


def layout_filter(scene: Scene, fallback: float, w: int, h: int) -> str:
    """The `[0:v]…[base]` chain for a cropped scene, switching to a blurred fit on `fit` shots."""
    from backend.services.publish_export import blurred_backdrop
    cropped = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
               f"crop={w}:{h}:x='(iw-ow)*{crop_expression(scene, fallback)}':y=(ih-oh)/2,setsar=1")
    spans = fit_spans(scene)
    if not spans:
        return f"[0:v]{cropped}[base]"
    enable = "+".join(f"between(t,{start},{end})" for start, end in spans)
    return (f"[0:v]split=3[c][bg][fg];[c]{cropped}[cropped];"
            f"[bg]{blurred_backdrop(w, h)}[bg2];"
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fg2];"
            f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2[fitted];"
            f"[cropped][fitted]overlay=0:0:enable='{enable}'[base]")


# ------------------------------------------------------------------- shots ---
def detect_cuts(video: Path, start: float, length: float) -> list[float]:
    """Hard cuts inside [start, start+length) as seconds relative to `start`."""
    from backend.services import render_limits
    cmd = [get_ffmpeg_path(), "-v", "info", "-nostats", *render_limits.input_args(), "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(video),
           "-an", "-vf", f"scale=320:-2,select='gt(scene,{CUT_THRESHOLD})',showinfo", *render_limits.output_args(), "-f", "null", "-"]
    cmd, priority = render_limits.low_priority(cmd)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=max(60, length * 4), check=False, **priority)
    except subprocess.TimeoutExpired:
        return []
    cuts = []
    for line in proc.stderr.splitlines():
        if "pts_time:" not in line:
            continue
        try:
            cuts.append(float(line.split("pts_time:")[1].split()[0]))
        except (IndexError, ValueError):
            continue
    return cuts


def split_shots(length: float, cuts: list[float], min_shot: float = MIN_SHOT, max_shots: int = MAX_SHOTS) -> list[tuple[float, float]]:
    """Turn cut times into (start, end) shots; cuts too close together collapse into one shot."""
    bounds = [0.0]
    for cut in sorted(cuts):
        if cut - bounds[-1] >= min_shot and length - cut >= min_shot:
            bounds.append(cut)
    if len(bounds) > max_shots:
        step = len(bounds) / max_shots
        bounds = [bounds[int(i * step)] for i in range(max_shots)]
    return [(bounds[i], bounds[i + 1] if i + 1 < len(bounds) else length) for i in range(len(bounds))]


def sample_offsets(start: float, end: float) -> list[float]:
    """Where to look inside one shot: away from the cuts, more often in long shots."""
    length = end - start
    if length <= PAIR_GAP + .1:
        return [start]
    margin = min(CUT_MARGIN, (length - PAIR_GAP) / 2)
    first, last = start + margin, end - margin - PAIR_GAP
    if last <= first:
        return [first]
    if length <= LONG_SHOT:
        count = 1 if length < 1.5 else 3
        return [first + (last - first) * i / max(1, count - 1) for i in range(count)] if count > 1 else [(first + last) / 2]
    count = int((last - first) // SAMPLE_INTERVAL) + 1
    return [first + SAMPLE_INTERVAL * i for i in range(count)]


# ------------------------------------------------------------------ frames ---
def _grab_pair(video: Path, at: float, folder: Path, key: str) -> tuple[Path, Path] | None:
    from backend.services import render_limits
    pattern = folder / f"{key}-%d.jpg"
    cmd = [get_ffmpeg_path(), "-v", "error", *render_limits.input_args(), "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "2",
           "-vf", f"fps=1/{PAIR_GAP},scale={FRAME_WIDTH}:-2", "-q:v", "4", "-y", str(pattern)]
    cmd, priority = render_limits.low_priority(cmd)
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30, **priority)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    first, second = folder / f"{key}-1.jpg", folder / f"{key}-2.jpg"
    if not first.exists():
        return None
    return first, second if second.exists() else first


_detectors: dict[tuple[int, int], Any] = {}


def _detector(cv2: Any, width: int, height: int) -> Any:
    """One YuNet instance per frame size; every sampled frame in a run has the same size."""
    key = (width, height)
    if key not in _detectors:
        _detectors[key] = cv2.FaceDetectorYN.create(str(MODEL), "", key, score_threshold=0.6, nms_threshold=0.3, top_k=50)
    return _detectors[key]


def _speaker_center(pair: tuple[Path, Path]) -> float | None:
    """Normalised x-centre of the talking face; the largest face when nobody's mouth moves."""
    ensure_on_path()
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")  # the DNN backend prints a harmless warning per detector
    import cv2  # installed on demand

    first = cv2.imread(str(pair[0]))
    second = cv2.imread(str(pair[1]))
    if first is None:
        return None
    height, width = first.shape[:2]
    _, faces = _detector(cv2, width, height).detect(first)
    if faces is None or len(faces) == 0:
        return None
    # Audience shots and far wide shots have faces too small to frame on; treat them as none.
    faces = [face for face in faces if face[2] >= MIN_FACE * width]
    if not faces:
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


def frame_shot(samples: list[tuple[float, float | None]], shot_start: float, shot_length: float, fraction: float) -> list[dict[str, Any]]:
    """Track points for one shot from (offset-in-shot, speaker centre | None) samples.

    Most samples without a usable face → the shot is a card/slide/empty frame: show it whole (`fit`).
    Otherwise centre on the speaker; long shots may switch speaker inside via segment_track.
    """
    seen = [(t, crop_x_for_center(c, fraction)) for t, c in samples if c is not None]
    if not samples or len(seen) * 2 < len(samples):
        return [{"start": round(shot_start, 2), "crop_x": .5, "mode": "fit"}]
    if shot_length <= LONG_SHOT or len(seen) < 3:
        return [{"start": round(shot_start, 2), "crop_x": round(statistics.median(x for _, x in seen), 3), "mode": "crop"}]
    return [{"start": round(shot_start + p["start"], 2), "crop_x": p["crop_x"], "mode": "crop"} for p in segment_track(seen)]


def merge_points(points: list[dict[str, Any]], min_jump: float = MIN_JUMP) -> list[dict[str, Any]]:
    """Drop points that do not change anything visible (same mode, near-identical position)."""
    merged: list[dict[str, Any]] = []
    for point in points:
        last = merged[-1] if merged else None
        if last and last["mode"] == point["mode"] and (point["mode"] == "fit" or abs(last["crop_x"] - point["crop_x"]) < min_jump):
            continue
        merged.append(point)
    return merged


def scan_speakers(video: Path, scenes) -> list[dict[str, Any]]:
    """Shots and sampled speaker centres per scene: the expensive part, independent of the output window."""
    if not is_installed():
        raise RuntimeError("人物识别组件未安装")
    scans = []
    with tempfile.TemporaryDirectory(prefix="ac-framing-") as temp:
        folder = Path(temp)
        for scene in scenes:
            length = scene.end - scene.start
            shots = []
            faces = grabbed = 0
            for index, (shot_start, shot_end) in enumerate(split_shots(length, detect_cuts(video, scene.start, length))):
                samples: list[tuple[float, float | None]] = []
                for j, at in enumerate(sample_offsets(shot_start, shot_end)):
                    pair = _grab_pair(video, scene.start + at, folder, f"{scene.id}-{index}-{j}")
                    if not pair:
                        continue
                    grabbed += 1
                    center = _speaker_center(pair)
                    faces += center is not None
                    samples.append((at - shot_start, center))
                shots.append((shot_start, shot_end, samples))
            scans.append({"shots": shots, "faces": faces, "samples": grabbed})
    return scans


def auto_frame(video: Path, draft: Draft, source_w: int, source_h: int, *, window: tuple[int, int] | None = None,
               scans: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Shot-aligned crop tracks per scene.

    Scenes get a track only when somebody is visible somewhere in the draft; a clip with no
    people at all (gameplay, screen recording) keeps the layout the user chose untouched.
    `window` overrides the output size, e.g. the 4:3 window of the interview template.
    `scans` reuses a `scan_speakers` pass, so several windows cost one detection.
    """
    if scans is None:
        scans = scan_speakers(video, draft.scenes)
    out_w, out_h = window or {"portrait": (1080, 1920), "landscape": (1920, 1080)}.get(draft.aspect, (source_w, source_h))
    fraction = window_fraction(source_w, source_h, out_w, out_h)
    scenes = []
    for scene, scan in zip(draft.scenes, scans):
        points: list[dict[str, Any]] = []
        for shot_start, shot_end, samples in scan["shots"]:
            points += frame_shot(samples, shot_start, shot_end - shot_start, fraction)
        track = merge_points(points)
        scenes.append({"id": scene.id, "crop_x": track[0]["crop_x"], "crop_track": track, "faces": scan["faces"], "samples": scan["samples"],
                       "shots": len(scan["shots"]), "fit_shots": sum(p["mode"] == "fit" for p in track), "switches": len(track) - 1})
    if not any(s["faces"] for s in scenes):
        for s in scenes:
            s.update(crop_x=None, crop_track=None, fit_shots=0, switches=0)
    return {"scenes": scenes, "window_fraction": round(fraction, 3)}
