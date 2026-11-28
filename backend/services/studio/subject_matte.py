"""Local ONNX portrait segmentation matte generator for 3-layer depth compositing.

Runs OpenCV Zoo's PP-HumanSeg ONNX model (~5.9 MB, Apache-2.0) directly via
``cv2.dnn`` — zero extra Python packages beyond ``opencv-python-headless``
(already used by ``framing.py``). Decodes the exact framed scene picture via
FFmpeg at a compact working resolution (270x480), applies temporal EMA smoothing
and gentle spatial feathering to prevent edge flicker, and encodes a grayscale
alpha matte movie that FFmpeg merges via ``alphamerge`` so giant typography can
pass cleanly behind the speaker's head and shoulders.
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from backend.utils.ffmpeg_utils import get_ffmpeg_path

logger = logging.getLogger(__name__)

MODEL = Path(__file__).resolve().parents[2] / 'assets' / 'models' / 'human_segmentation_pphumanseg_2023mar.onnx'
_NET_LOCK = threading.Lock()
_NET_CACHE = None


def _load_cv2(*, auto_install: bool = False, wait_sec: float = 90.0) -> Any | None:
    """Load cv2 via ``framing.load_cv2()`` so packaged ``framing-runtime`` is on sys.path.

    When ``auto_install`` is True and the runtime is not yet installed, starts the
    on-demand framing runtime install (outside clip job request budget) and waits up
    to ``wait_sec`` seconds for it to finish.
    """
    from backend.services.studio import framing

    cv2 = framing.load_cv2()
    if cv2 is not None or not auto_install:
        return cv2
    try:
        from backend.core.job_budget import pause_clip_job_budget
    except Exception:
        pause_clip_job_budget = None

    def _install_and_wait():
        try:
            framing.start_install()
        except Exception as exc:  # noqa: BLE001 - optional enhancement
            logger.warning('Framing runtime install for subject matte could not start: %s', exc)
            return None
        deadline = time.monotonic() + max(0.0, wait_sec)
        while time.monotonic() < deadline:
            loaded = framing.load_cv2()
            if loaded is not None:
                return loaded
            if framing.get_status().get('status') != 'installing':
                break
            time.sleep(2.0)
        return framing.load_cv2()

    if pause_clip_job_budget is not None:
        with pause_clip_job_budget():
            return _install_and_wait()
    return _install_and_wait()


def available() -> bool:
    """Return True when the bundled PP-HumanSeg ONNX model and cv2/numpy are ready."""
    if not MODEL.is_file():
        return False
    return _load_cv2(auto_install=False) is not None


def ensure_ready(*, wait_sec: float = 90.0) -> bool:
    """Ensure the bundled ONNX model and framing-runtime cv2/numpy are ready."""
    if not MODEL.is_file():
        return False
    return _load_cv2(auto_install=True, wait_sec=wait_sec) is not None


def _load_net():
    global _NET_CACHE
    with _NET_LOCK:
        if _NET_CACHE is None:
            cv2 = _load_cv2(auto_install=False)
            if cv2 is None:
                raise RuntimeError('cv2 unavailable for subject matte')
            _NET_CACHE = cv2.dnn.readNetFromONNX(str(MODEL))
        return _NET_CACHE


def generate_scene_matte(
    video: Path,
    *,
    start: float,
    duration: float,
    picture_filter: str,
    picture_label: str,
    fps: int = 30,
    dest: Path,
    work_w: int = 270,
    work_h: int = 480,
) -> Path | None:
    """Generate a temporally smoothed grayscale matte video aligned to ``picture_filter``.

    Returns ``dest`` on success, or ``None`` if segmentation is unavailable or fails
    so the caller can degrade gracefully to standard 2-layer compositing.
    """
    if duration <= 0 or not MODEL.is_file():
        return None
    cv2 = _load_cv2(auto_install=True)
    if cv2 is None:
        return None
    try:
        import numpy as np
    except Exception:
        return None

    ffmpeg = get_ffmpeg_path()
    # Decode the exact framed scene picture scaled to work_w x work_h RGB24 at target fps.
    dec_graph = f'{picture_filter};[{picture_label}]fps={fps},scale={work_w}:{work_h}:flags=bilinear,format=rgb24[m_in]'
    dec_cmd = [
        ffmpeg, '-v', 'error', '-ss', str(max(0.0, start)), '-i', str(video),
        '-t', str(duration), '-filter_complex', dec_graph, '-map', '[m_in]',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1',
    ]
    enc_cmd = [
        ffmpeg, '-y', '-v', 'error',
        '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{work_w}x{work_h}', '-r', str(fps), '-i', 'pipe:0',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '16', '-pix_fmt', 'yuv420p',
        str(dest),
    ]

    frame_bytes = work_w * work_h * 3
    dec = None
    enc = None
    try:
        net = _load_net()
        dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert dec.stdout is not None and enc.stdin is not None

        ema: np.ndarray | None = None
        written = 0
        while True:
            buf = dec.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            rgb = np.frombuffer(buf, dtype=np.uint8).reshape((work_h, work_w, 3))
            small = cv2.resize(rgb, (192, 192), interpolation=cv2.INTER_LINEAR)
            inp = (small.astype(np.float32) / 255.0 - 0.5) / 0.5
            blob = np.transpose(inp, (2, 0, 1))[None, ...]
            with _NET_LOCK:
                net.setInput(blob)
                out = net.forward()
            # PP-HumanSeg ONNX outputs post-softmax probabilities in [0, 1] at channel 1 (person).
            prob = out[0, 1]
            if ema is None:
                ema = prob.copy()
            else:
                ema = 0.68 * prob + 0.32 * ema
            refined = np.clip((ema - 0.28) / 0.50, 0.0, 1.0)
            mask = cv2.resize((refined * 255.0).astype(np.uint8), (work_w, work_h), interpolation=cv2.INTER_CUBIC)
            mask = cv2.GaussianBlur(mask, (7, 7), 0)
            enc.stdin.write(mask.tobytes())
            written += 1

        enc.stdin.close()
        dec.wait(timeout=30)
        enc.wait(timeout=30)
        if written == 0 or enc.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            return None
        return dest
    except Exception as exc:  # noqa: BLE001 - graceful downgrade to 2-layer compositing
        logger.warning('Subject matte generation failed; falling back to 2-layer composite: %s', exc)
        dest.unlink(missing_ok=True)
        return None
    finally:
        for proc in (dec, enc):
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
