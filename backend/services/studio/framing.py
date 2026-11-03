"""Shot-aware framing for the portrait crop layout.

Work in shots, not on a clock. Each scene is first split at hard cuts (ffmpeg scene-change scores)
and at dissolves, then every shot is classified from frame pairs taken about once a second.
One shot is one sequential decode, not a seek per sample.
OpenCV's YuNet model (bundled ONNX, MIT licence) finds faces. The back of a head is never the crop
centre. A side profile is, when that mouth is the one moving, or when the transcript names that
person. The window follows that face. When the transcript has no speaker labels, one person who
does the talking holds the window for the scene, and a silent listener is shown whole instead of
punched in. A run of looks that vote to show the whole frame stays a fit segment when it lasts
at least a second.

- a shot with one face that fits the window → `crop`, centred on that face (the talking profile
  when the other person is only listening, or the named speaker when a cue says who);
- a shot where several people must all stay in frame, or where the only face is a silent
  turned-away head → `fit`: the whole frame on a blurred backdrop, so nobody is sliced off;
- a shot without a usable face (quote cards, slides, screen recordings) → `fit` as well.

The window jumps on a cut and eases when the speaker changes inside a shot. OpenCV is not part of
the base install (≈45 MB); it is installed on demand into the data directory, the same way the
Whisper runtime is.
"""
from __future__ import annotations

import html
import importlib.util
import logging
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
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
LONG_SHOT = 6.0            # shots longer than this may switch speaker inside
PAIR_GAP = 0.25            # seconds between the two frames of one sample (mouth motion)
FRAME_WIDTH = 480
MOTION_THRESHOLD = 4.0     # mean abs grey difference in the mouth box that counts as "talking"
MIN_FACE = 0.035           # face width below this fraction of the frame is too small to frame on
MIN_HOLD = 2               # samples a new speaker must persist before the window moves (inside a shot)
MIN_JUMP = 0.12            # normalised distance below which two positions are the same framing
NOSE_OUTSIDE = 0.09        # a three-quarter face (nose ~0.08 outside the eyes) is still frontal
NOSE_OPEN = 0.13           # extra room only when both eyes are clearly open
OPEN_EYE = 0.30            # eye-span / face-width that earns the extra nose room
FRONTAL_EYE_MIN = 0.15     # eye-span / face-width below this is a collapsed, non-frontal landmark set
MIN_SCORE = 0.72           # close-up score below this is a false box (backs of heads land near 0.64)
TRACK_SCORE = 0.6          # single-face tracking. A box below this is not a crop centre
WIDE_SCORE = 0.45          # only for counting people when a look would otherwise be one face
PERSON_MIN = 0.02          # face width below this fraction is noise, not a person
SAMPLE_INTERVAL = 1.0      # seconds between looks inside one sequential decode of the shot
TAIL_SHOT = 0.15           # a final fragment at least this long still gets its own crop
DISSOLVE_STEP = 0.25       # seconds between frames when looking for a crossfade
DISSOLVE_WINDOW = 1.0      # a dissolve drifts across about this much time
DISSOLVE_DRIFT = 0.22      # mean pixel change (0–1) that means the picture became a different shot
MAX_FACE = 0.55            # a box wider than this fraction of the frame is not a face
EDGE_FACE = 0.22           # a box this wide that touches the frame edge is a stuck false detection
PAN_EASE = 0.45            # seconds; an interior speaker change eases instead of cutting
REVERSAL_GAP = 0.8         # seconds; a direction change closer than this is jitter and is dropped
CLUSTER_RADIUS = 0.18      # a later vote farther than this from a speaker's place does not move them
MIN_SEGMENT = 1.2          # seconds; crop/fit changes shorter than this are flicker unless the shot is a cut


# ---------------------------------------------------------------- runtime ---
def _data_dir() -> Path:
    from backend.services.whisper_runtime import _data_dir as data_dir
    return data_dir()


def get_install_dir() -> Path:
    d = _data_dir() / "framing-runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_on_path() -> None:
    """Put framing-runtime first on sys.path, ahead of whisper-runtime.

    Both runtimes ship their own numpy (opencv and faster-whisper pull different versions).
    If the whisper copy wins, cv2 loads a mixed numpy tree and fails with ImportError
    (PYTHON-FASTAPI-40), so framing always moves itself to the front.
    """
    install_dir = str(get_install_dir())
    if sys.path[:1] != [install_dir]:
        while install_dir in sys.path:
            sys.path.remove(install_dir)
        sys.path.insert(0, install_dir)


_UNSET = object()
_cv2: Any = _UNSET
_cv2_error = ""
_cv2_lock = threading.Lock()


def _purge_modules(before: set[str]) -> None:
    """Drop cv2/numpy modules that this failed attempt added, so a later attempt starts clean.

    Modules that were already loaded stay: other components (faster-whisper, PyAV) hold
    references to that numpy, and re-importing numpy in the same process corrupts it
    (sentinel identity breaks; faster-whisper then dies with RecursionError).
    """
    for name in set(sys.modules) - before:
        if name.split(".", 1)[0] in ("cv2", "numpy"):
            sys.modules.pop(name, None)


def reset_cv2_cache() -> None:
    global _cv2, _cv2_error
    with _cv2_lock:
        _cv2, _cv2_error = _UNSET, ""


def load_cv2() -> Any | None:
    """Import cv2 once; None when the on-demand component is missing or broken. Never raises."""
    global _cv2, _cv2_error
    with _cv2_lock:
        if _cv2 is not _UNSET:
            return _cv2
        ensure_on_path()
        os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")  # the DNN backend prints a harmless warning per detector
        before = set(sys.modules)
        try:
            if importlib.util.find_spec(IMPORT_NAME) is None:
                return None  # not installed yet: do not cache, an install may follow
            import cv2  # installed on demand
            import numpy  # noqa: F401  # cv2 needs a working numpy; fail here, not mid-detection
            _cv2, _cv2_error = cv2, ""
        except Exception as error:  # noqa: BLE001 - ImportError, OSError from a broken wheel, ...
            _purge_modules(before)
            _cv2, _cv2_error = None, f"{type(error).__name__}: {error}"[:300]
            logger.warning("人物识别组件无法加载: %s", _cv2_error)
        return _cv2


def unavailable_reason() -> str:
    """User-facing reason for a 409: broken install gets a reinstall hint."""
    if _cv2 is None and _cv2_error:
        return "人物识别组件加载失败，请在设置中重新安装人物识别组件"
    return "人物识别组件未安装"


def is_installed() -> bool:
    """True only when cv2 actually imports (cached) and the YuNet model is present."""
    try:
        return MODEL.exists() and load_cv2() is not None
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
    if state["status"] != "installed":
        left = cooldown_remaining()
        if left:
            state["cooldown_seconds"] = int(left)
    return state


# 自动安装失败后的冷却：这段时间里竖屏任务不再自动重装，直接用完整画面；设置页点“重新安装”不受限。
AUTO_RETRY_COOLDOWN_SECONDS = 30 * 60


def _failure_path() -> Path:
    return _data_dir() / "framing-install-failure.json"


def _remember_failure(message: str) -> None:
    try:
        import json
        _failure_path().write_text(json.dumps({"at": time.time(), "message": message}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _clear_failure() -> None:
    try:
        _failure_path().unlink(missing_ok=True)
    except OSError:
        pass


def cooldown_remaining(now: float | None = None) -> float:
    """自动安装还要等多少秒（0 表示可以装）。记录写在数据目录，重启后仍然有效。"""
    try:
        import json
        at = float(json.loads(_failure_path().read_text(encoding="utf-8")).get("at", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0.0
    left = at + AUTO_RETRY_COOLDOWN_SECONDS - (time.time() if now is None else now)
    return max(0.0, left)


def _run(cmd: list[str], timeout: float, stall: float, label: str) -> int:
    from backend.services import pip_install
    progress = pip_install.PipProgress(label)

    def on_line(line: str, _lines: list[str]) -> None:
        step = progress.feed(line)
        if step:
            _set_state(progress=step[0], message=step[1])

    _set_state(message=f"正在连接{pip_install.SOURCE_NAMES.get(label, label)}…")
    return pip_install.stream(cmd, timeout, stall, on_line, owner="framing")[0]


def _fail(message: str) -> None:
    _remember_failure(message)
    _set_state(status="error", message=message)


def _do_install(index_url: str | None) -> None:
    """Runs on the one thread start_install() claimed; never two at once (see start_install)."""
    from backend.services import pip_install
    # Fresh target dir instead of --upgrade: pip --target leaves stale numpy files behind
    # and a mixed tree is exactly what broke cv2 in PYTHON-FASTAPI-40.
    try:
        shutil.rmtree(get_install_dir())
    except OSError as error:
        # Windows: a running process still holds cv2*.pyd. Not a code fault; say so and stop.
        logger.warning("人物识别组件旧文件清理失败，已跳过本次安装: %s", error)
        _fail(f"无法清理旧的人物识别组件，请重启后重试: {error}")
        return
    reset_cv2_cache()
    _set_state(status="installing", progress=5, message="正在准备人物识别组件…", error_code="")
    try:
        # Same sources, budgets and stall detection as the Whisper runtime (#339):
        # PyPI first, then the Tsinghua mirror; PIP_INDEX_URL pins one index.
        code, failures = pip_install.run_plan(
            pip_install.index_plan(index_url),
            lambda url: pip_install.command(PACKAGES, str(get_install_dir()), url),
            _run,
            on_switch=lambda _old, new, _why: _set_state(message=f"官方源没有响应，改用{pip_install.SOURCE_NAMES.get(new, new)}…"),
            what="人物识别组件",
        )
        reset_cv2_cache()
        if code == 0 and is_installed():
            _clear_failure()
            _set_state(status="installed", progress=100, message="安装完成")
            logger.info("人物识别组件安装完成")
            return
        if code == pip_install.CANCEL_EXIT:  # user/shutdown cancel: no cooldown
            _set_state(status="not_installed", progress=0, message="安装已取消")
            logger.info("人物识别组件安装已取消")
            return
        message = pip_install.failure_message(code, failures, "人物识别组件") if code else "安装结束，但人物识别组件仍不可用"
        _set_state(error_code=pip_install.error_code(code, failures) if code else "not_usable")
        # Network trouble is expected here: one warning with the reason, no traceback.
        logger.warning("人物识别组件安装失败（%s），竖屏成片先用完整画面；%d 分钟内不再自动重试",
                       "; ".join(failures) or message, AUTO_RETRY_COOLDOWN_SECONDS // 60)
        _fail(message)
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("人物识别组件安装没有完成: %s: %s", type(error).__name__, error)
        _fail(f"安装异常: {error}")


def start_install(index_url: str | None = None, *, manual: bool = False) -> dict[str, Any]:
    """manual=True：设置页的“安装 / 重新安装”，不看冷却。竖屏任务的自动安装用默认值。"""
    if is_installed():
        _set_state(status="installed", progress=100, message="已安装")
        return {"started": False, "message": "已安装"}
    if not manual:
        left = cooldown_remaining()
        if left > 0:
            logger.info("人物识别组件上次自动安装失败，%d 分钟内不再自动重试；本次竖屏用完整画面", int(left // 60) + 1)
            return {"started": False, "message": "上次安装失败，稍后再自动重试", "cooldown_seconds": int(left)}
    # Claim the install under the lock before the thread starts. Every vertical job calls this;
    # without the claim two threads both cleared framing-runtime while the other's pip wrote into it.
    with _state_lock:
        if _state["status"] == "installing":
            return {"started": False, "message": "正在安装中"}
        _state.update(status="installing", progress=0, message="正在准备人物识别组件…")
    if manual:
        _clear_failure()
    threading.Thread(target=_do_install, args=(index_url,), name="framing-install", daemon=True).start()
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


_EDGE_TOUCH = 0.02  # a box this close to the frame border is cut off by the source, not a full head


def crop_x_for_subject(center_x: float, width: float, fraction: float) -> float:
    """Place the window on a face box.

    A box that sits inside the frame uses the same position as `crop_x_for_center`. A box that
    touches the left or right border is a head the source already sliced. The portrait window
    then shifts inward by about one face width (capped at half the window) so the inward side
    of the head and shoulder stays inside. The sliver already on the frame border may fall
    outside. A box that touches both borders, or that is wider than the window, keeps the
    plain centre; the caller fits when the face itself cannot fit.
    """
    if fraction >= 1 or width <= 1e-6:
        return crop_x_for_center(center_x, fraction)
    left = center_x - width / 2
    right = center_x + width / 2
    touches_left = left <= _EDGE_TOUCH
    touches_right = right >= 1 - _EDGE_TOUCH
    if touches_left == touches_right:
        return crop_x_for_center(center_x, fraction)
    pad = min(width, fraction / 2)
    if touches_left:
        need_left, need_right = center_x, min(1.0, right + pad)
    else:
        need_left, need_right = max(0.0, left - pad), center_x
    if need_right - need_left > fraction + 1e-6:
        return crop_x_for_center(center_x, fraction)
    return crop_x_for_center((need_left + need_right) / 2, fraction)


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
    """ffmpeg expression for the crop window position within one scene (t is scene-relative).

    A point with ease > 0 lerps from the previous crop_x. Ease 0 keeps the step function, including
    the exact nesting `if(lt(t,17.5),if(lt(t,10.0),0.3,0.8),0.3)`.
    """
    points = scene.crop_track or []
    static = scene.crop_x if scene.crop_x is not None else fallback
    if len(points) <= 1:
        return f"{points[0].crop_x if points else static}"
    # Nest from the first point outwards: each boundary tests the *next* point's start.
    expression = f"{points[0].crop_x}"
    prev_x = points[0].crop_x
    for point in points[1:]:
        ease = float(getattr(point, "ease", 0) or 0)
        if ease > 0 and point.crop_x != prev_x:
            delta = round(point.crop_x - prev_x, 3)
            expression = (f"if(lt(t,{point.start}),{expression},"
                          f"if(lt(t,{point.start + ease}),({prev_x}+({delta})*(t-{point.start})/{ease}),{point.crop_x}))")
        else:
            expression = f"if(lt(t,{point.start}),{expression},{point.crop_x})"
        prev_x = point.crop_x
    return expression


CUT_EDGE = 0.006           # seconds; a track start rounded to 0.01 s can land up to 5 ms after its cut frame


def on_cut_frames(scene: Scene) -> Scene:
    """The scene with every later crop point starting just before its cut frame.

    Track starts are cut times rounded to 0.01 s, so a cut on a frame at 3.8667 s is stored as
    3.87 and `lt(t,3.87)` keeps the old crop on that frame. Starting 6 ms earlier lands before the
    cut frame and after the frame before it at any rate up to 60 fps. The stored track and its QA
    are untouched; only the render-time copy moves.
    """
    points = scene.crop_track or []
    if len(points) <= 1:
        return scene
    moved = [points[0]] + [point.model_copy(update={"start": max(0.0, round(point.start - CUT_EDGE, 3))})
                           if point.start > 0 else point for point in points[1:]]
    return scene.model_copy(update={"crop_track": moved})


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
def _hard_cuts(video: Path, start: float, length: float) -> list[float]:
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


def _pixel_distance(left, right) -> float:
    """Mean absolute difference of two gray frames, 0 for a match and 1 for a full invert."""
    import numpy as np
    before = np.asarray(left)
    after = np.asarray(right)
    if before.shape != after.shape or before.size == 0:
        return 0.0
    return float(np.abs(before.astype(np.int16) - after.astype(np.int16)).mean()) / 255.0


def dissolve_times(frames: list, times: list[float]) -> list[float]:
    """Ends of gradual transitions. A single hard jump is left to the scene detector.

    `times` are seconds on the same clock as `frames`. A window whose picture drifts into a
    different frame, without one step doing all of the change, is a crossfade. Histogram
    distance is not used: a flat wall sits on a bin edge and a small fade looks like a cut.
    """
    marks = []
    for index, end in enumerate(times):
        start_index = index
        while start_index > 0 and end - times[start_index - 1] <= DISSOLVE_WINDOW + 1e-6:
            start_index -= 1
        if end - times[start_index] < 0.6:
            continue
        if _pixel_distance(frames[start_index], frames[index]) < DISSOLVE_DRIFT:
            continue
        steps = [_pixel_distance(frames[i], frames[i + 1]) for i in range(start_index, index)]
        if not steps or max(steps) >= DISSOLVE_DRIFT:
            continue
        if sum(1 for step in steps if step >= 0.05) < 2:
            continue
        marks.append(end)
    kept: list[float] = []
    for mark in marks:
        if kept and mark - kept[-1] < MIN_SHOT:
            kept[-1] = mark
            continue
        kept.append(mark)
    return kept


def _dissolve_cuts(video: Path, start: float, length: float) -> list[float]:
    """Crossfades the hard-cut detector misses, as seconds relative to `start`."""
    if length < 0.8:
        return []
    width, height = 96, 54
    rate = f"{1 / DISSOLVE_STEP:.4g}"
    cmd = [get_ffmpeg_path(), "-v", "error", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(video),
           "-an", "-vf", f"fps={rate},scale={width}:{height}", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=max(30, length * 2), check=False)
    except subprocess.TimeoutExpired:
        return []
    raw = proc.stdout or b""
    size = width * height
    count = len(raw) // size
    if proc.returncode != 0 or count < 4:
        return []
    import numpy as np
    frames = []
    times = []
    for index in range(count):
        frames.append(np.frombuffer(raw, dtype=np.uint8, count=size, offset=index * size).copy())
        times.append(index * DISSOLVE_STEP)
    return dissolve_times(frames, times)


def detect_cuts(video: Path, start: float, length: float) -> list[float]:
    """Hard cuts and crossfades inside [start, start+length), seconds relative to `start`."""
    cuts = _hard_cuts(video, start, length)
    try:
        cuts.extend(_dissolve_cuts(video, start, length))
    except (OSError, ValueError):
        pass
    return sorted(set(round(cut, 2) for cut in cuts))


def split_shots(length: float, cuts: list[float], min_shot: float = MIN_SHOT, max_shots: int = MAX_SHOTS) -> list[tuple[float, float]]:
    """Turn cut times into (start, end) shots; cuts too close together collapse into one shot.

    A final fragment shorter than MIN_SHOT still stands alone when it is at least TAIL_SHOT,
    so a close-up in the last third of a second is not left on the previous crop.
    """
    bounds = [0.0]
    for cut in sorted(cuts):
        if cut - bounds[-1] < min_shot or length - cut < TAIL_SHOT:
            continue
        bounds.append(cut)
    if len(bounds) > max_shots:
        step = len(bounds) / max_shots
        bounds = [bounds[int(i * step)] for i in range(max_shots)]
    return [(bounds[i], bounds[i + 1] if i + 1 < len(bounds) else length) for i in range(len(bounds))]


def sample_offsets(start: float, end: float) -> list[float]:
    """Where to look inside one shot: every SAMPLE_INTERVAL, clear of the cut frames.

    A shot shorter than 0.8 s is one look at its middle, including a final fragment under a second.
    """
    length = end - start
    if length <= 0:
        return [start]
    if length < 0.8:
        return [start + length / 2]
    margin = min(CUT_MARGIN, (length - PAIR_GAP) / 2)
    first, last = start + margin, end - margin - PAIR_GAP
    if last <= first:
        return [(start + end) / 2]
    count = int((last - first) // SAMPLE_INTERVAL) + 1
    if count <= 1:
        return [(first + last) / 2]
    return [first + SAMPLE_INTERVAL * i for i in range(count)]


# ------------------------------------------------------------------ frames ---
def _grab_shot(video: Path, abs_start: float, abs_end: float, times: list[float], folder: Path, key: str):
    """Decode one shot once and pair frames for each sample time.

    `times` are absolute seconds. A separate seek per sample is what made framing about
    three times slower on a long source. The fps filter walks forward from a single seek.
    """
    from backend.services import render_limits
    if not times:
        return []
    length = max(PAIR_GAP, abs_end - abs_start)
    pattern = folder / f"{key}-%04d.jpg"
    rate = f"{1 / PAIR_GAP:.4g}"
    # The fps filter walks the shot on a PAIR_GAP grid. Only the two grid frames of each
    # sample (and the last few) are scaled and written; select drops the rest.
    wanted_set: set[int] = set()
    for at in times:
        first = max(0, round(max(0.0, at - abs_start) / PAIR_GAP))
        wanted_set.update((first, first + 1))
    # The last grid frames are kept too: a sample past the end of a short shot pairs with
    # whatever frame the shot really ends on, as it did when every grid frame was written.
    tail = max(0, round(length / PAIR_GAP) - 2)
    wanted = sorted(index for index in wanted_set if index < tail)
    pick = "+".join([f"eq(n\\,{index})" for index in wanted] + [f"gte(n\\,{tail})"])
    cmd = [get_ffmpeg_path(), "-v", "error", *render_limits.input_args(),
           "-ss", f"{max(0.0, abs_start):.3f}", "-t", f"{length:.3f}", "-i", str(video),
           "-an", "-vf", f"fps={rate},select={pick},scale={FRAME_WIDTH}:-2",
           "-fps_mode", "passthrough", "-q:v", "4", "-y", str(pattern)]
    cmd, priority = render_limits.low_priority(cmd)
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=max(30, length * 2), **priority)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return [(at, None) for at in times]
    frames: dict[int, Path] = {}
    for path in folder.glob(f"{key}-*.jpg"):
        try:
            written = int(path.stem.rsplit("-", 1)[-1]) - 1
        except ValueError:
            continue
        # Files are numbered in output order: the wanted grid frames, then the tail from `tail` on.
        if written < 0:
            continue
        frames[wanted[written] if written < len(wanted) else tail + written - len(wanted)] = path
    if not frames:
        return [(at, None) for at in times]
    paired = []
    for at in times:
        rel = max(0.0, at - abs_start)
        index = min(frames, key=lambda i: abs(i * PAIR_GAP - rel))
        first = frames[index]
        second = frames.get(index + 1, first)
        paired.append((at, (first, second)))
    return paired


_detectors: dict[tuple[int, int, float], Any] = {}
_detector_lock = threading.Lock()


def _detector(cv2: Any, width: int, height: int, score: float = TRACK_SCORE) -> Any:
    """One YuNet instance per frame size and score floor. Caller holds _detector_lock."""
    key = (width, height, round(float(score), 3))
    if key not in _detectors:
        _detectors[key] = cv2.FaceDetectorYN.create(
            str(MODEL), "", (width, height), score_threshold=float(score), nms_threshold=0.3, top_k=50,
        )
    return _detectors[key]


def is_frontal(face) -> bool:
    """True when YuNet's landmarks read as a face looking at the camera.

    Eye-span alone moves with scale, so a real frontal face can sit anywhere from about 0.22 to
    0.43 of the box. The stable reject is a nose outside the eye span, plus a collapsed eye span
    and a landmark order that is not eyes-then-nose-then-mouth. A turned head or the back of a
    head fails this and must not become a crop centre.
    """
    try:
        width = float(face[2])
        height = float(face[3])
        if width <= 1 or height <= 1:
            return False
        right_x, right_y = float(face[4]), float(face[5])
        left_x, left_y = float(face[6]), float(face[7])
        nose_x, nose_y = float(face[8]), float(face[9])
        mouth_y = (float(face[11]) + float(face[13])) / 2
    except (TypeError, ValueError, IndexError):
        return False
    if len(face) > 14:
        try:
            if float(face[14]) < MIN_SCORE:
                return False
        except (TypeError, ValueError):
            return False
    eye_ratio = abs(left_x - right_x) / width
    if eye_ratio < FRONTAL_EYE_MIN:
        return False
    eye_left, eye_right = (right_x, left_x) if right_x < left_x else (left_x, right_x)
    if nose_x < eye_left:
        outside = eye_left - nose_x
    elif nose_x > eye_right:
        outside = nose_x - eye_right
    else:
        outside = 0.0
    outside_ratio = outside / width
    # 0.082 is a three-quarter face. A turned head with collapsed eyes stays rejected above 0.09.
    if outside_ratio > NOSE_OPEN or (outside_ratio > NOSE_OUTSIDE and eye_ratio < OPEN_EYE):
        return False
    eye_y = (right_y + left_y) / 2
    return eye_y < nose_y < mouth_y + 0.1 * height


def _box_parts(face, frame_w: int) -> tuple[float, float, float] | None:
    try:
        x, box_w = float(face[0]), float(face[2])
        score = float(face[14]) if len(face) > 14 else 1.0
    except (TypeError, ValueError, IndexError):
        return None
    if frame_w <= 0 or box_w <= 0:
        return None
    return score, x, box_w


def _person_box(face, frame_w: int) -> bool:
    """True for anyone in the shot, including a small face a wide view would otherwise drop.

    A large box still needs MIN_SCORE, so a 0.64 back-of-head or an edge-stuck false face does
    not become a person. A small box may sit between WIDE_SCORE and MIN_SCORE.
    """
    parts = _box_parts(face, frame_w)
    if parts is None:
        return False
    score, x, box_w = parts
    norm = box_w / frame_w
    if norm < PERSON_MIN or norm > MAX_FACE:
        return False
    if norm >= 0.08 and score < MIN_SCORE:
        return False
    if score < WIDE_SCORE:
        return False
    return not (box_w >= EDGE_FACE * frame_w and (x <= 1 or x + box_w >= frame_w - 1))


def _reliable_box(face, frame_w: int) -> bool:
    """A box good enough to centre a crop on: close-up score, not huge, not stuck to the edge."""
    parts = _box_parts(face, frame_w)
    if parts is None:
        return False
    score, x, box_w = parts
    if score < MIN_SCORE:
        return False
    if box_w < MIN_FACE * frame_w or box_w > MAX_FACE * frame_w:
        return False
    return not (box_w >= EDGE_FACE * frame_w and (x <= 1 or x + box_w >= frame_w - 1))


def _mouth_motion(cv2, face, grey_a, grey_b, width: int, height: int) -> float:
    if grey_b is None:
        return 0.0
    box_w, box_h = float(face[2]), float(face[3])
    mx1, my1, mx2, my2 = face[10], face[11], face[12], face[13]
    left = int(max(0, min(mx1, mx2) - box_w * .1))
    right = int(min(width, max(mx1, mx2) + box_w * .1))
    top = int(max(0, min(my1, my2) - box_h * .12))
    bottom = int(min(height, max(my1, my2) + box_h * .2))
    if right <= left or bottom <= top:
        return 0.0
    return float(abs(grey_a[top:bottom, left:right].astype("int16") - grey_b[top:bottom, left:right].astype("int16")).mean())


def _observe_pair(pair: tuple[Path, Path]) -> dict[str, list[dict[str, float]]] | None:
    """Frontal and turned faces in one sample, each `{x, w, motion, area}` in frame fractions.

    None when the detector or the frame is missing. An empty detection is a real look with nobody
    in it, which is different from a failed read.
    """
    cv2 = load_cv2()
    if cv2 is None:
        return None  # broken/missing component: keep the default framing, no Sentry noise
    first = cv2.imread(str(pair[0]))
    second = cv2.imread(str(pair[1])) if len(pair) > 1 else None
    if first is None:
        return None
    height, width = first.shape[:2]
    # The DNN holds mutable input/output buffers. Concurrent renders must not
    # overwrite another video's input while its inference is still running.
    def _score_of(face) -> float:
        try:
            return float(face[14]) if len(face) > 14 else 1.0
        except (TypeError, ValueError):
            return 1.0

    def _item(face, motion: float) -> dict[str, float]:
        box_w = float(face[2])
        return {
            "x": float((float(face[0]) + box_w / 2) / width),
            "w": box_w / width,
            "motion": motion,
            "area": box_w * float(face[3]),
            "score": _score_of(face),
        }

    with _detector_lock:
        _, faces = _detector(cv2, width, height, TRACK_SCORE).detect(first)
        faces = faces.copy() if faces is not None else None
        other = None
        if second is not None and second.shape == first.shape:
            _, other = _detector(cv2, width, height, TRACK_SCORE).detect(second)
            other = other.copy() if other is not None else None
        tracking = [face for face in (faces if faces is not None else []) if _person_box(face, width)]
        wide_rows = None
        # The 0.45 net runs only when tracking still looks like one or two people, and its
        # boxes never become a crop centre. YuNet drops anything under its create() threshold,
        # so the tracking net stays at 0.6 and cannot see these faces itself.
        if len(tracking) < 3:
            _, wide_rows = _detector(cv2, width, height, WIDE_SCORE).detect(first)
            wide_rows = wide_rows.copy() if wide_rows is not None else None
    frontal: list[dict[str, float]] = []
    turned: list[dict[str, float]] = []
    wide: list[dict[str, float]] = []
    if (faces is None or len(faces) == 0) and (wide_rows is None or len(wide_rows) == 0):
        return {"frontal": frontal, "turned": turned, "wide": wide}
    grey_a = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    grey_b = cv2.cvtColor(second, cv2.COLOR_BGR2GRAY) if second is not None and second.shape == first.shape else None
    for face in tracking:
        motion = _mouth_motion(cv2, face, grey_a, grey_b, width, height)
        # A head that is frontal in only one frame of the pair is mid-turn. Do not crop to it.
        (frontal if _frontal_in_pair(face, other, width) else turned).append(_item(face, motion))
    if wide_rows is not None:
        for face in wide_rows:
            if _score_of(face) >= TRACK_SCORE or not _person_box(face, width):
                continue
            wide.append(_item(face, 0.0))
    return {"frontal": frontal, "turned": turned, "wide": wide}


def _frontal_in_pair(face, others, width: int) -> bool:
    if not is_frontal(face):
        return False
    if others is None:
        return True
    x = (float(face[0]) + float(face[2]) / 2) / width
    nearest, best = None, 0.12
    for other in others:
        other_x = (float(other[0]) + float(other[2]) / 2) / width
        dist = abs(other_x - x)
        if dist < best:
            nearest, best = other, dist
    return nearest is None or is_frontal(nearest)


def _speaker_center(pair: tuple[Path, Path]) -> float | None:
    """Normalised x-centre of the frontal face that is talking; the largest frontal face otherwise.

    A turned-away head is not a candidate, even when it is larger or its mouth region moves more.
    """
    observed = _observe_pair(pair)
    if not observed or not observed["frontal"]:
        return None
    talking = [face for face in observed["frontal"] if face["motion"] >= MOTION_THRESHOLD]
    if talking:
        best = max(talking, key=lambda face: face["motion"])
    else:
        best = max(observed["frontal"], key=lambda face: face["area"])
    return float(best["x"])


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


_EXPLICIT_SPEAKER = re.compile(
    r"^\s*(?:>>\s*)?(?:\[(?P<bracket>[^\[\]\n]{1,40})\]|(?P<label>[A-Za-z][A-Za-z0-9_-]{0,31})\s*[:：])"
)
# Words that start an English sentence and are followed by a colon. They are not speaker names.
_STOP_NAMES = frozenset("""
look wait note okay ok yes no oh well so and but here there now then please hey hi wow
right left one two first next this that what why how when where who if or because also
just maybe really actually basically listen watch see remember imagine consider anyway
meanwhile however therefore plus update warning important example question answer title
summary today yesterday tomorrow folks everyone somebody something nothing thanks thank
welcome hello goodbye sorry yeah yep nope fine great good bad new old big small
""".split())
_NAME = re.compile(r"^[A-Z][A-Za-z][A-Za-z0-9_-]{0,30}$")


def _as_seconds(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    from backend.pipeline.quality import to_seconds
    return to_seconds(str(value))


def _entry_bounds(entry: dict) -> tuple[float, float]:
    if "start" in entry and "end" in entry and not isinstance(entry.get("start"), str):
        return float(entry["start"]), float(entry["end"])
    start = entry["start"] if "start" in entry else entry["start_time"]
    end = entry["end"] if "end" in entry else entry["end_time"]
    return _as_seconds(start), _as_seconds(end)


def _caption_text(text: str) -> str:
    """Unescape `&gt;&gt;` and collapse a rolling line that repeats its own `>>` mark."""
    cleaned = html.unescape(str(text or "")).replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if ">>" not in cleaned:
        return cleaned
    parts = [part.strip() for part in re.split(r"\s*>>\s*", cleaned) if part.strip()]
    if not parts:
        return cleaned
    kept = parts[0]
    for part in parts[1:]:
        if _rolls(kept, part):
            kept = part if len(part) >= len(kept) else kept
        else:
            kept = part
    return ">> " + kept


def _body(text: str) -> str:
    return re.sub(r"^(?:>>\s*)+", "", text or "").strip()


def _rolls(previous: str, new: str) -> bool:
    """True when `new` is the same YouTube caption window grown by a few words."""
    old_words = _body(previous).lower().split()
    new_words = _body(new).lower().split()
    if not old_words or not new_words:
        return False
    old_text, new_text = " ".join(old_words), " ".join(new_words)
    if new_text.startswith(old_text) or old_text.startswith(new_text):
        return True
    shared = 0
    for left, right in zip(old_words, new_words):
        if left != right:
            break
        shared += 1
    shorter = min(len(old_words), len(new_words))
    return shorter >= 4 and shared >= max(4, int(shorter * 0.6))


def _explicit_name(text: str) -> tuple[str, str] | None:
    """`(kind, name)` for a bracket label or a capitalised `Name:`. `Look:` is not a name."""
    match = _EXPLICIT_SPEAKER.match(text)
    if not match:
        return None
    bracket = (match.group("bracket") or "").strip()
    if bracket:
        return ("bracket", bracket)
    label = (match.group("label") or "").strip()
    if not _NAME.match(label) or label.lower() in _STOP_NAMES:
        return None
    return ("name", label)


def _fold_rolls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Consecutive rolling captions are one cue. A new sentence that also starts with `>>` is kept."""
    folded: list[dict[str, Any]] = []
    for row in rows:
        if folded and row["text"].lstrip().startswith(">>") and _rolls(folded[-1]["text"], row["text"]):
            if len(_body(row["text"])) >= len(_body(folded[-1]["text"])):
                folded[-1]["text"] = row["text"]
            folded[-1]["end"] = max(folded[-1]["end"], row["end"])
            continue
        folded.append(dict(row))
    return folded


def cues_from_entries(entries) -> list[dict[str, Any]]:
    """Speaker cues, or plain cues when the transcript never names a speaker.

    Bracket labels always win. A capitalised `Name:` wins only when that same name labels
    at least two cues, so one `Guest:` or `Look:` does not rename the transcript.
    Every remaining `>>` is a new turn. A transcript with neither labels nor `>>` is left
    unlabelled, so framing follows the frontal talking face instead of binding one person.
    """
    parsed = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        try:
            start, end = _entry_bounds(entry)
        except (TypeError, ValueError, KeyError):
            continue
        if end <= start:
            continue
        parsed.append({"start": start, "end": end, "text": _caption_text(entry.get("text") or "")})
    parsed = _fold_rolls(parsed)
    found = [_explicit_name(row["text"]) for row in parsed]
    name_counts: dict[str, int] = {}
    for item in found:
        if item and item[0] == "name":
            name_counts[item[1]] = name_counts.get(item[1], 0) + 1
    names = []
    for item in found:
        if item is None:
            names.append(None)
        elif item[0] == "bracket" or name_counts.get(item[1], 0) >= 2:
            names.append(item[1])
        else:
            names.append(None)
    if any(names):
        current = None
        cues = []
        for row, speaker in zip(parsed, names):
            if speaker:
                current = speaker
            if current:
                cues.append({**row, "speaker": current})
            else:
                cues.append(dict(row))
        return cues
    if not any(row["text"].lstrip().startswith(">>") for row in parsed):
        return parsed
    cues = []
    turn = 0
    started = False
    labels = ("speaker_a", "speaker_b")
    for row in parsed:
        if row["text"].lstrip().startswith(">>") and started:
            turn = 1 - turn
        cues.append({**row, "speaker": labels[turn]})
        started = True
    return cues


def speaker_at(cues, t: float) -> str | None:
    """Speaker of the cue that contains `t`. A gap between cues has no speaker."""
    found = None
    for cue in cues or []:
        try:
            if float(cue["start"]) <= t < float(cue["end"]):
                found = cue.get("speaker")
        except (KeyError, TypeError, ValueError):
            continue
    return found or None


def _vote_x(frontals: list[dict[str, float]]) -> float | None:
    """One frontal face, or the single mouth that is moving, or the clearly louder of two talkers."""
    if len(frontals) == 1:
        return frontals[0]["x"]
    talking = [face for face in frontals if face["motion"] >= MOTION_THRESHOLD]
    if len(talking) == 1:
        return talking[0]["x"]
    if len(talking) >= 2:
        ordered = sorted(talking, key=lambda face: face["motion"], reverse=True)
        if ordered[0]["motion"] >= ordered[1]["motion"] * 1.5:
            return ordered[0]["x"]
    return None


def bind_speakers(samples: list[dict[str, Any]], cues) -> dict[str, float]:
    """Map each cue speaker to a stable horizontal place.

    Votes come only from frontal faces. Once a speaker has a place, a later vote farther than
    CLUSTER_RADIUS is ignored, so a louder listener cannot steal the binding.
    """
    votes: dict[str, list[float]] = {}
    ordered = sorted(samples, key=lambda sample: float(sample.get("t", 0)))
    for sample in ordered:
        speaker = speaker_at(cues, float(sample.get("t", 0)))
        if not speaker:
            continue
        chosen = _vote_x(sample.get("frontal") or [])
        if chosen is None:
            continue
        existing = votes.get(speaker)
        if existing and abs(chosen - statistics.median(existing)) > CLUSTER_RADIUS:
            continue
        votes.setdefault(speaker, []).append(chosen)
    return {speaker: float(statistics.median(xs)) for speaker, xs in votes.items()}


def _span(faces: list[dict[str, float]]) -> tuple[float, float]:
    left = min(face["x"] - face["w"] / 2 for face in faces)
    right = max(face["x"] + face["w"] / 2 for face in faces)
    return left, right


def _fits(faces: list[dict[str, float]], fraction: float) -> bool:
    if len(faces) < 2:
        return True
    left, right = _span(faces)
    return right - left <= fraction + 1e-6


def _unique_talker(faces: list[dict[str, float]], fraction: float) -> float | None:
    """The one mouth that is moving, or the clearly louder of two, when that face fits the window."""
    talking = [face for face in faces if float(face.get("motion", 0)) >= MOTION_THRESHOLD and face["w"] <= fraction]
    if len(talking) == 1:
        return talking[0]["x"]
    if len(talking) >= 2:
        ordered = sorted(talking, key=lambda face: float(face["motion"]), reverse=True)
        if ordered[0]["motion"] >= ordered[1]["motion"] * 1.5:
            return ordered[0]["x"]
    return None


def _center_for(sample: dict[str, Any], binding: dict[str, float], cues, fraction: float) -> float | None:
    """Normalised centre for one sample, or None when the shot should fit the whole frame.

    Three or more people who do not fit the window stay together (a group photo or a wide shot),
    even when a cue overlaps and even when only one of them cleared the close-up score. A small
    low-score face still counts as another person, so a wide shot is not a single-face punch-in.
    A bound speaker who has turned into profile stays the centre. They are not replaced by
    someone else. With no binding, the face whose mouth is moving wins over a silent frontal
    face, including a side profile YuNet did not call frontal. Two frontal faces with no unique
    speaker are kept when they do not fit, and centred as a pair when they do. None means show
    the whole frame: there is no face to put in the window.
    """
    frontals = list(sample.get("frontal") or [])
    turned = list(sample.get("turned") or [])
    people = frontals + turned + list(sample.get("wide") or [])
    # Three or more people who cannot share the window are a group, even when only one
    # of them cleared the close-up score. A wide shot is not a single-face punch-in.
    if len(people) >= 3 and not _fits(people, fraction):
        return None
    if len(frontals) >= 3 and not _fits(frontals, fraction):
        return None
    # Two people where the other face only cleared the wide-shot score: still not one person.
    low_score = [face for face in people if float(face.get("score", 1.0)) < MIN_SCORE]
    if len(people) >= 2 and low_score and not _fits(people, fraction):
        return None
    speaker = speaker_at(cues, float(sample.get("t", 0))) if cues else None
    bound = binding.get(speaker) if speaker else None
    if bound is not None:
        near = [face for face in frontals if abs(face["x"] - bound) <= CLUSTER_RADIUS and face["w"] <= fraction]
        if near:
            return min(near, key=lambda face: abs(face["x"] - bound))["x"]
        # The named person is in profile. Stay on that head instead of the listener facing camera.
        turned_near = [face for face in turned if abs(face["x"] - bound) <= CLUSTER_RADIUS and face["w"] <= fraction]
        if turned_near:
            return min(turned_near, key=lambda face: abs(face["x"] - bound))["x"]
        # The bound person is off screen. One remaining frontal face is who is actually there.
        if len(frontals) == 1 and frontals[0]["w"] <= fraction:
            return frontals[0]["x"]
        return None
    # A talking profile next to a silent frontal guest is the speaker. Checking the single
    # frontal face first used to crop the guest and leave the profile out of the window.
    talker = _unique_talker(frontals + turned, fraction)
    if talker is not None:
        return talker
    wide = [face for face in frontals if face["w"] > fraction]
    if len(frontals) == 1 and wide:
        return None
    if len(frontals) == 1:
        return frontals[0]["x"]
    talking = [face for face in frontals if face["motion"] >= MOTION_THRESHOLD]
    if len(frontals) == 2 and len(talking) == 1 and talking[0]["w"] <= fraction:
        return talking[0]["x"]
    if len(frontals) >= 2 and not _fits(frontals, fraction):
        return None
    if len(frontals) >= 2 and _fits(frontals, fraction):
        left, right = _span(frontals)
        return (left + right) / 2
    return None


def _cue_segments(samples: list[dict[str, Any]], cues, shot_length: float) -> list[tuple[float, float]] | None:
    """Shot-relative slices where the named speaker changes. Unlabelled cues do not slice the shot."""
    if not cues or not samples or shot_length <= 0:
        return None
    labelled = []
    for cue in cues:
        speaker = cue.get("speaker") if isinstance(cue, dict) else None
        if not speaker:
            continue
        try:
            labelled.append((float(cue["start"]), speaker))
        except (KeyError, TypeError, ValueError):
            continue
    if len(labelled) < 2:
        return None
    origin = float(samples[0]["t"]) - float(samples[0]["offset"])
    bounds = {0.0, shot_length}
    previous = None
    for start, speaker in sorted(labelled):
        if previous is not None and speaker != previous:
            rel = start - origin
            if 0.2 <= rel <= shot_length - 0.2:
                bounds.add(rel)
        previous = speaker
    ordered = sorted(bounds)
    segments = [(a, b) for a, b in zip(ordered, ordered[1:]) if b - a >= 0.2]
    return segments if len(segments) > 1 else None


def _stabilize(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One-off boxes drop. A place that is frontal in most looks stays frontal for the whole shot."""
    if len(samples) < 4:
        return samples
    clusters: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        for kind in ("frontal", "turned"):
            for face in sample.get(kind) or []:
                placed = False
                for cluster in clusters:
                    if abs(face["x"] - statistics.median(cluster["xs"])) <= CLUSTER_RADIUS:
                        cluster["xs"].append(face["x"])
                        cluster["members"].append((index, kind, face))
                        placed = True
                        break
                if not placed:
                    clusters.append({"xs": [face["x"]], "members": [(index, kind, face)]})
    rebuilt = [{
        "offset": sample["offset"], "t": sample["t"], "frontal": [], "turned": [],
        "wide": [dict(face) for face in (sample.get("wide") or [])],
    } for sample in samples]
    for cluster in clusters:
        hits = {index for index, _kind, _face in cluster["members"]}
        if len(hits) < 2:
            continue
        frontal_n = sum(1 for _index, kind, _face in cluster["members"] if kind == "frontal")
        total = len(cluster["members"])
        # Only a clear two-thirds majority renames the whole shot. A tie, or a speaker who
        # faces the camera for half a long shot, keeps each look's own label. Promoting a
        # slight majority turns a real frontal run into the back of a head.
        if frontal_n * 3 >= total * 2:
            forced = "frontal"
        elif frontal_n * 3 <= total:
            forced = "turned"
        else:
            forced = None
        for index, kind, face in cluster["members"]:
            label = forced or kind
            if any(abs(other["x"] - face["x"]) <= 0.05 for other in rebuilt[index][label]):
                continue
            rebuilt[index][label].append(face)
    return rebuilt


def _absorb_short(points: list[dict[str, Any]], shot_start: float, shot_length: float) -> list[dict[str, Any]]:
    """Drop a crop/fit change that lasts under MIN_SEGMENT. A shot that is itself that short stays."""
    if shot_length < MIN_SEGMENT or len(points) <= 1:
        return points
    shot_end = shot_start + shot_length
    points = [dict(point) for point in points]
    for _ in range(12):
        if len(points) <= 1:
            break
        short = None
        for index, point in enumerate(points):
            end = points[index + 1]["start"] if index + 1 < len(points) else shot_end
            if end - point["start"] < MIN_SEGMENT - 1e-6:
                short = index
                break
        if short is None:
            break
        if short == 0:
            adopted = dict(points[1])
            adopted["start"] = points[0]["start"]
            points = [adopted, *points[2:]]
        else:
            points = [*points[:short], *points[short + 1:]]
    return points


def fit_ratio(track: list[dict[str, Any]] | None, length: float) -> float:
    """Share of `length` rendered as fit. 0 when the track is empty or the scene has no duration."""
    if not track or length <= 0:
        return 0.0
    fit = 0.0
    for index, point in enumerate(track):
        end = track[index + 1]["start"] if index + 1 < len(track) else length
        if point.get("mode") == "fit":
            fit += max(0.0, end - point["start"])
    return fit / length


def _steady(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate framing and a reversal that lands inside the jitter window."""
    kept: list[dict[str, Any]] = []
    for point in points:
        if not kept:
            kept.append(point)
            continue
        if point["mode"] == "fit" and kept[-1]["mode"] == "fit":
            continue
        if point["mode"] == "crop" and kept[-1]["mode"] == "crop" and abs(point["crop_x"] - kept[-1]["crop_x"]) < MIN_JUMP:
            continue
        if len(kept) >= 2 and point["mode"] == "crop" and kept[-1]["mode"] == "crop" and kept[-2]["mode"] == "crop":
            before = kept[-1]["crop_x"] - kept[-2]["crop_x"]
            after = point["crop_x"] - kept[-1]["crop_x"]
            if before * after < 0 and point["start"] - kept[-1]["start"] < REVERSAL_GAP:
                continue
        kept.append(point)
    return kept


def _with_ease(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The first point of a shot is a cut. A later crop-to-crop move eases."""
    eased = []
    for point in points:
        item = {key: value for key, value in point.items() if key != "ease"}
        if eased and item["mode"] == "crop" and eased[-1]["mode"] == "crop" and abs(item["crop_x"] - eased[-1]["crop_x"]) >= MIN_JUMP:
            item["ease"] = PAN_EASE
        eased.append(item)
    return eased


def _placed_crop(subject: dict[str, float] | None, fraction: float) -> float | None:
    """crop_x for one look, or None when that look should show the whole frame."""
    if not subject or float(subject.get("w", 0)) > fraction:
        return None
    return crop_x_for_subject(float(subject["x"]), float(subject.get("w", 0)), fraction)


def _same_vote(previous: dict[str, float] | None, subject: dict[str, float] | None, fraction: float) -> bool:
    prev = _placed_crop(previous, fraction)
    nxt = _placed_crop(subject, fraction)
    if prev is None or nxt is None:
        return prev is None and nxt is None
    return abs(prev - nxt) < MIN_JUMP


def _points_from_votes(votes: list[tuple[float, dict[str, float] | None]], shot_start: float, shot_length: float,
                       fraction: float) -> list[dict[str, Any]]:
    """One point per run of agreeing looks. A fit run is kept, not dropped for lack of crop votes."""
    if not votes:
        return [{"start": round(shot_start, 2), "crop_x": .5, "mode": "fit"}]
    runs: list[list[Any]] = []
    for offset, subject in votes:
        if runs and _same_vote(runs[-1][1], subject, fraction):
            if _placed_crop(subject, fraction) is not None:
                runs[-1][2].append(subject)
            continue
        runs.append([offset, subject, [subject] if _placed_crop(subject, fraction) is not None else []])
    points = []
    for index, (offset, _subject, subjects) in enumerate(runs):
        start = shot_start if index == 0 else shot_start + offset
        if not subjects:
            points.append({"start": round(start, 2), "crop_x": .5, "mode": "fit"})
            continue
        center = float(statistics.median(float(item["x"]) for item in subjects))
        width = float(statistics.median(float(item.get("w", 0)) for item in subjects))
        if width > fraction:
            points.append({"start": round(start, 2), "crop_x": .5, "mode": "fit"})
            continue
        points.append({
            "start": round(start, 2),
            "crop_x": round(crop_x_for_subject(center, width, fraction), 3),
            "mode": "crop",
        })
    return points


def _subject_for_center(faces: list[dict[str, float]], center: float) -> dict[str, float]:
    """The face at `center`, or a zero-width marker when `center` is a pair midpoint."""
    exact = [face for face in faces if abs(float(face["x"]) - center) <= 0.02]
    if len(exact) == 1:
        return exact[0]
    return {"x": center, "w": 0.0, "motion": 0.0}


def _dominant_talker(samples: list[dict[str, Any]], fraction: float) -> float | None:
    """Horizontal place of the person who does the talking, when the votes agree.

    Needs at least three talking looks, and a cluster that holds at least half of them inside
    CLUSTER_RADIUS. Two people who split the scene (the middle of the votes sits outside that
    radius) return None, so each shot can still follow its own talker.
    """
    votes: list[float] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        faces = list(sample.get("frontal") or []) + list(sample.get("turned") or [])
        chosen = _unique_talker(faces, fraction)
        if chosen is not None:
            votes.append(chosen)
    if len(votes) < 3:
        return None
    best_n = 0
    best_x = None
    for x in votes:
        near = [vote for vote in votes if abs(vote - x) <= CLUSTER_RADIUS]
        if len(near) > best_n:
            best_n = len(near)
            best_x = float(statistics.median(near))
    if best_x is None or best_n * 2 < len(votes):
        return None
    if abs(float(statistics.median(votes)) - best_x) > CLUSTER_RADIUS:
        return None
    return best_x


def _track_face(sample: dict[str, Any], binding: dict[str, float], cues, fraction: float,
                dominant: float | None) -> dict[str, float] | None:
    """Face box to crop, or None to show the whole frame.

    Groups stay together: `_center_for` already returns None for them. When the scene has one
    unlabeled talker, a silent face far from that place is the listener and is not punched in.
    A different face that is actually talking still takes the window. Two people in frame keep
    the talker when that person is also visible, instead of cropping the listener.
    """
    center = _center_for(sample, binding, cues, fraction)
    faces = list(sample.get("frontal") or []) + list(sample.get("turned") or [])
    near = []
    if dominant is not None:
        near = [face for face in faces if abs(float(face["x"]) - dominant) <= CLUSTER_RADIUS and face["w"] <= fraction]
    # A profile close-up often has no frontal box and little mouth motion. `_center_for`
    # then has nothing to return, but the face is still the person the scene is following.
    # A group or a two-shot that already voted fit is left alone: one face only.
    if center is None:
        if len(faces) == 1 and near:
            return near[0]
        return None
    subject = _subject_for_center(faces, center)
    if dominant is None or abs(center - dominant) <= CLUSTER_RADIUS:
        return subject
    people = faces + list(sample.get("wide") or [])
    if near and len(people) <= 2:
        return min(near, key=lambda face: abs(float(face["x"]) - dominant))
    if float(subject.get("motion", 0)) < MOTION_THRESHOLD:
        return None
    return subject


def _shot_has_subject(samples: list[dict[str, Any]], dominant: float | None) -> bool:
    """True when some look has a face worth cropping, including a talking or followed profile."""
    for sample in samples:
        if sample.get("frontal"):
            return True
        for face in sample.get("turned") or []:
            if float(face.get("motion", 0)) >= MOTION_THRESHOLD:
                return True
            if dominant is not None and abs(float(face["x"]) - dominant) <= CLUSTER_RADIUS:
                return True
    return False


def frame_observed(samples: list[dict[str, Any]], shot_start: float, shot_length: float, fraction: float,
                   cues, binding: dict[str, float], dominant: float | None = None) -> list[dict[str, Any]]:
    """Track points for one shot from observed faces.

    Looks that vote fit become a fit segment when that run lasts at least MIN_SEGMENT.
    They are not discarded just because fewer than three looks voted for a crop. A shot
    with no frontal face and no talking profile is shown whole. A crop never continues
    across looks that found no face to centre on. `dominant` is the scene's unlabeled
    talker; pass None when cues already bound speakers, or when the votes do not agree.
    """
    samples = _stabilize(samples)
    if not samples or not _shot_has_subject(samples, dominant):
        return [{"start": round(shot_start, 2), "crop_x": .5, "mode": "fit"}]
    votes = [(float(sample["offset"]), _track_face(sample, binding, cues, fraction, dominant)) for sample in samples]
    points = _points_from_votes(votes, shot_start, shot_length, fraction)
    return _with_ease(_steady(_absorb_short(points, shot_start, shot_length)))


def scan_speakers(video: Path, scenes) -> list[dict[str, Any]]:
    """Shots and sampled faces per scene: the expensive part, independent of the output window.

    Each sample is `{offset, t, frontal, turned}`. A turned head still counts as a person, so a
    shot of only the back of a head is framed (as fit) instead of being treated as footage with
    nobody in it.
    """
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
                samples: list[dict[str, Any]] = []
                offsets = sample_offsets(shot_start, shot_end)
                grabbed_shot = _grab_shot(
                    video, scene.start + shot_start, scene.start + shot_end,
                    [scene.start + at for at in offsets], folder, f"{scene.id}-{index}",
                )
                for at, (_abs, pair) in zip(offsets, grabbed_shot):
                    if not pair:
                        continue
                    grabbed += 1
                    observed = _observe_pair(pair)
                    if observed is None:
                        continue
                    if observed["frontal"] or observed["turned"] or observed.get("wide"):
                        faces += 1
                    samples.append({
                        "offset": at - shot_start,
                        "t": scene.start + at,
                        "frontal": observed["frontal"],
                        "turned": observed["turned"],
                        "wide": observed.get("wide") or [],
                    })
                shots.append((shot_start, shot_end, samples))
            scans.append({"shots": shots, "faces": faces, "samples": grabbed})
    return scans


def auto_frame(video: Path, draft: Draft, source_w: int, source_h: int, *, window: tuple[int, int] | None = None,
               scans: list[dict[str, Any]] | None = None, cues=None) -> dict[str, Any]:
    """Shot-aligned crop tracks per scene.

    Scenes get a track only when somebody is visible somewhere in the draft; a clip with no
    people at all (gameplay, screen recording) keeps the layout the user chose untouched.
    `window` overrides the output size, e.g. the 4:3 window of the interview template.
    `scans` reuses a `scan_speakers` pass, so several windows cost one detection.
    `cues` are speaker-labelled transcript rows (`start`, `end`, `speaker`); without them the
    window follows the mouth that is moving, and holds that person across shots when one
    talker dominates. A group that does not fit the window is still shown whole.
    Tuple samples from an older scan keep the previous centre-only path.
    """
    if scans is None:
        scans = scan_speakers(video, draft.scenes)
    out_w, out_h = window or {"portrait": (1080, 1920), "landscape": (1920, 1080)}.get(draft.aspect, (source_w, source_h))
    fraction = window_fraction(source_w, source_h, out_w, out_h)
    observed = [sample for scan in scans for _start, _end, samples in scan["shots"] for sample in samples if isinstance(sample, dict)]
    binding = bind_speakers(observed, cues or [])
    scenes = []
    for scene, scan in zip(draft.scenes, scans):
        points: list[dict[str, Any]] = []
        # A labelled transcript already pins each speaker. An unlabelled one (the usual
        # interview export) locks the window to whoever is actually talking in this scene,
        # so a later close-up of a silent guest is not punched in under the same name card.
        scene_samples = [sample for _start, _end, samples in scan["shots"] for sample in samples if isinstance(sample, dict)]
        dominant = None if binding else _dominant_talker(scene_samples, fraction)
        for shot_start, shot_end, samples in scan["shots"]:
            if samples and isinstance(samples[0], dict):
                points += frame_observed(
                    samples, shot_start, shot_end - shot_start, fraction, cues or [], binding, dominant,
                )
            else:
                points += frame_shot(samples, shot_start, shot_end - shot_start, fraction)
        track = merge_points(points)
        scenes.append({"id": scene.id, "crop_x": track[0]["crop_x"], "crop_track": track, "faces": scan["faces"], "samples": scan["samples"],
                       "shots": len(scan["shots"]), "fit_shots": sum(p["mode"] == "fit" for p in track), "switches": len(track) - 1})
    if not any(s["faces"] for s in scenes):
        for s in scenes:
            s.update(crop_x=None, crop_track=None, fit_shots=0, switches=0)
    return {"scenes": scenes, "window_fraction": round(fraction, 3)}


def cancel_install() -> bool:
    """Stop a running install (kills pip). The install thread then records "安装已取消"."""
    from backend.services import pip_install
    return pip_install.cancel("framing") > 0
