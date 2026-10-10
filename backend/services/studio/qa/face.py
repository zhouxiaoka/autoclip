"""Caption or title covering a detected face. Any overlap above 0 px fails.

YuNet from the framing runtime is reused when it is already installed. A few
frames are sampled. Missing the optional detector is a skip, not a failure.
"""
from __future__ import annotations

from backend.services.studio.qa.media import ProbeError, run

# Packaging caption is about two 62 px lines on a 1920 px frame.
_CAPTION_PX = 170
_TITLE_PX = 200


def overlay_rects(width: int, height: int, *, captions: bool, title: bool, packaged: bool,
                  title_y: float) -> list[tuple[float, float, float, float]]:
    """(x, y, w, h) in output pixels. Empty when nothing is drawn on the picture."""
    if width <= 0 or height <= 0:
        return []
    rects = []
    if captions:
        band = max(48, round(height * _CAPTION_PX / 1920))
        inset = max(8, round(width * 48 / 1080))
        rects.append((float(inset), float(height - band), float(width - 2 * inset), float(band)))
    if title:
        inset = max(8, round(width * 40 / 1080))
        if packaged:
            band = max(48, round(height * _TITLE_PX / 1920))
            rects.append((float(inset), 0.0, float(width - 2 * inset), float(band)))
        else:
            band = max(48, round(height * 0.12))
            y = max(0, round(float(title_y) * height - band * 0.35))
            rects.append((float(inset), float(y), float(max(1, width - 2 * inset)), float(min(band, height - y))))
    return rects


def covered_fraction(face: tuple[float, float, float, float],
                     overlays: list[tuple[float, float, float, float]]) -> float:
    """Share of the face box covered by the single overlay that covers the most of it."""
    fx, fy, fw, fh = face
    area = fw * fh
    if area <= 0:
        return 0.0
    best = 0.0
    for ox, oy, ow, oh in overlays:
        ix = max(0.0, min(fx + fw, ox + ow) - max(fx, ox))
        iy = max(0.0, min(fy + fh, oy + oh) - max(fy, oy))
        best = max(best, ix * iy)
    return best / area


def judge_cover(fraction: float) -> tuple[str, str]:
    if fraction <= 0:
        return 'pass', 'none'
    pct = fraction * 100
    if pct < 10:
        return 'fail', 'lt10'
    if pct <= 40:
        return 'fail', '10_40'
    return 'fail', 'gt40'


def _sample_times(duration: float) -> list[float]:
    if duration <= 0.3:
        return [max(0.0, duration / 2)]
    return sorted({round(max(0.1, min(t, duration - 0.1)), 3) for t in (0.4, duration / 2, duration - 0.35)})


def _duration(ctx) -> float:
    return sum(max(0.0, scene.end - scene.start) for scene in ctx.scenes)


def detect_faces(path, at: float, out_w: int, out_h: int, timeout: float) -> list[tuple[float, float, float, float]] | None:
    """Face boxes in output pixels, or None when YuNet is not installed."""
    from backend.services.studio import framing
    if not framing.is_installed():
        return None
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    proc = run([
        get_ffmpeg_path(), '-v', 'error', '-ss', f'{at:.3f}', '-i', str(path), '-frames:v', '1',
        '-vf', 'scale=320:-2', '-f', 'image2pipe', '-vcodec', 'mjpeg', 'pipe:1',
    ], timeout)
    if proc.returncode != 0 or not proc.stdout:
        raise ProbeError('unreadable')
    framing.ensure_on_path()
    import cv2
    import numpy as np
    image = cv2.imdecode(np.frombuffer(proc.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ProbeError('unreadable')
    height, width = image.shape[:2]
    with framing._detector_lock:
        _scores, faces = framing._detector(cv2, width, height).detect(image)
    if faces is None or len(faces) == 0:
        return []
    sx, sy = out_w / width, out_h / height
    return [(float(face[0]) * sx, float(face[1]) * sy, float(face[2]) * sx, float(face[3]) * sy) for face in faces]


def check(ctx, timeout: float) -> tuple[str, str]:
    rects = overlay_rects(ctx.width, ctx.height, captions=ctx.captions, title=ctx.title,
                          packaged=ctx.packaged, title_y=ctx.title_y)
    if not rects:
        return 'pass', 'none'
    if ctx.output is None or not getattr(ctx.output, 'is_file', lambda: False)():
        return 'skip', 'unreadable'
    from backend.services.studio import framing
    if not framing.is_installed():
        return 'skip', 'no_detector'
    times = _sample_times(_duration(ctx) or 1.0)
    share = timeout / max(1, len(times))
    seen = False
    worst = 0.0
    try:
        for at in times:
            boxes = detect_faces(ctx.output, at, ctx.width, ctx.height, share)
            if boxes is None:
                return 'skip', 'no_detector'
            seen = True
            for box in boxes:
                worst = max(worst, covered_fraction(box, rects))
    except ProbeError as error:
        if seen:
            return judge_cover(worst)
        return 'skip', error.reason
    if not seen:
        return 'skip', 'unreadable'
    return judge_cover(worst)
