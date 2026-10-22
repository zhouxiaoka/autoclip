"""Caption or title covering a detected face, and a portrait crop that misses the speaker.

YuNet from the framing runtime is reused when it is already installed. A few
frames are sampled. The detector is a private net: it does not take
framing._detector_lock, so a check cannot stall framing. Missing the optional
detector is a skip, not a failure. Three frames and the caption box are an
estimate, not a magazine or street-cut layout.

The crop check looks at the source, not the rendered window. A turned-away head
or a speaker left outside the 9:16 window fails once that run lasts more than
a second. A fit shot (the whole frame on a blurred fill) is not a miss.
"""
from __future__ import annotations

import threading

from backend.services.studio.qa.media import ProbeError, run

_nets: dict[tuple[int, int], object] = {}
_net_lock = threading.Lock()

# Packaging caption is about two 62 px lines on a 1920 px frame.
_CAPTION_PX = 170
_TITLE_PX = 200
# A bad crop has to stay bad for longer than this before the check fails. Exactly 1 s still passes.
_PRESENCE_LIMIT = 1.0
_FACE_OVERLAP = 0.35
_MAX_GRABS = 8


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


def judge_presence(spans: list[tuple[float, str]]) -> tuple[str, str]:
    """Fail when one bad run is longer than a second.

    `turned` is a back-of-head or turned-away face filling the window. `missing` is a frontal
    face that the window does not contain. `frontal`, `fit` and `quiet` break the run.
    """
    def longest(kind: str) -> float:
        best = current = 0.0
        for duration, label in spans:
            if label == kind:
                current += max(0.0, duration)
                best = max(best, current)
            else:
                current = 0.0
        return best

    if longest('turned') > _PRESENCE_LIMIT:
        return 'fail', 'back_of_head'
    if longest('missing') > _PRESENCE_LIMIT:
        return 'fail', 'speaker_out'
    return 'pass', 'frontal'


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


def _detect(cv2, image):
    """Run YuNet while holding QA's lock only. Framing's detector lock stays free."""
    height, width = image.shape[:2]
    key = (width, height)
    with _net_lock:
        net = _nets.get(key)
        if net is None:
            from backend.services.studio import framing
            net = cv2.FaceDetectorYN.create(
                str(framing.MODEL), '', key, score_threshold=0.6, nms_threshold=0.3, top_k=50,
            )
            _nets[key] = net
        return net.detect(image)


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
    cv2 = framing.load_cv2()
    if cv2 is None:
        return None
    import numpy as np
    image = cv2.imdecode(np.frombuffer(proc.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ProbeError('unreadable')
    height, width = image.shape[:2]
    _scores, faces = _detect(cv2, image)
    if faces is None or len(faces) == 0:
        return []
    sx, sy = out_w / width, out_h / height
    return [(float(face[0]) * sx, float(face[1]) * sy, float(face[2]) * sx, float(face[3]) * sy) for face in faces]


def _crop_spans(ctx) -> list[tuple[float, float, float, str]]:
    """(absolute time, duration, crop_x, mode) for every crop-track point."""
    spans = []
    for scene in ctx.scenes:
        points = list(scene.points or [])
        modes = list(scene.modes or [])
        length = max(0.0, scene.end - scene.start)
        for index, (start, crop_x) in enumerate(points):
            end = points[index + 1][0] if index + 1 < len(points) else length
            duration = end - start
            if duration <= 0:
                continue
            mode = modes[index] if index < len(modes) else 'crop'
            if mode not in ('crop', 'fit'):
                mode = 'crop'
            spans.append((scene.start + start, duration, crop_x, mode))
    return spans


def _width_overlap(face: dict, left: float, right: float) -> float:
    face_left = face['x'] - face['w'] / 2
    face_right = face['x'] + face['w'] / 2
    overlap = max(0.0, min(face_right, right) - max(face_left, left))
    return overlap / face['w'] if face['w'] else 0.0


def _presence_kind(frontals, turned, left: float, right: float) -> str:
    if any(_width_overlap(face, left, right) >= _FACE_OVERLAP for face in frontals):
        return 'frontal'
    if any(_width_overlap(face, left, right) >= _FACE_OVERLAP for face in turned):
        return 'turned'
    if frontals:
        return 'missing'
    return 'quiet'


def _read_faces(path, at: float, timeout: float):
    """(width, height, frontal faces, turned faces) in normalised source coordinates."""
    from backend.services.studio import framing
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    proc = run([
        get_ffmpeg_path(), '-v', 'error', '-ss', f'{at:.3f}', '-i', str(path), '-frames:v', '1',
        '-vf', 'scale=480:-2', '-f', 'image2pipe', '-vcodec', 'mjpeg', 'pipe:1',
    ], timeout)
    if proc.returncode != 0 or not proc.stdout:
        raise ProbeError('unreadable')
    cv2 = framing.load_cv2()
    if cv2 is None:
        return None
    import numpy as np
    image = cv2.imdecode(np.frombuffer(proc.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ProbeError('unreadable')
    height, width = image.shape[:2]
    _scores, found = _detect(cv2, image)
    frontal, turned = [], []
    if found is not None:
        for row in found:
            box_w = float(row[2])
            if box_w <= 1:
                continue
            item = {'x': (float(row[0]) + box_w / 2) / width, 'w': box_w / width}
            (frontal if framing.is_frontal(row) else turned).append(item)
    return width, height, frontal, turned


def _presence_check(ctx, timeout: float) -> tuple[str, str]:
    """Portrait crops only. Landscape, a missing source, and an unreadable frame stay a pass."""
    if ctx.height <= ctx.width:
        return 'pass', 'none'
    spans = _crop_spans(ctx)
    if not spans:
        return 'pass', 'none'
    from backend.services.studio import framing
    if not framing.is_installed():
        return 'skip', 'no_detector'
    source = getattr(ctx, 'source', None)
    if source is None or not getattr(source, 'is_file', lambda: False)():
        return 'pass', 'none'
    ranked = sorted(range(len(spans)), key=lambda index: spans[index][1], reverse=True)[:_MAX_GRABS]
    chosen = set(ranked)
    share = timeout / max(1, len(chosen))
    layout = getattr(ctx, 'layout', '') or ''
    judged: list[tuple[float, str] | None] = [None] * len(spans)
    try:
        for index in ranked:
            at, duration, crop_x, mode = spans[index]
            if mode == 'fit':
                judged[index] = (duration, 'fit')
                continue
            read = _read_faces(source, at + duration / 2, share)
            if read is None:
                return 'skip', 'no_detector'
            width, height, frontal, turned = read
            if layout == 'window':
                from backend.services.studio.jobs import INTERVIEW_WINDOW
                out_w, out_h = INTERVIEW_WINDOW
            else:
                out_w, out_h = ctx.width, ctx.height
            fraction = framing.window_fraction(width, height, out_w, out_h)
            left = crop_x * (1 - fraction)
            judged[index] = (duration, _presence_kind(frontal, turned, left, left + fraction))
    except ProbeError:
        return 'pass', 'none'
    kinds = []
    for index, span in enumerate(spans):
        item = judged[index]
        kinds.append(item if item is not None else (span[1], 'quiet'))
    return judge_presence(kinds)


def check(ctx, timeout: float) -> tuple[str, str]:
    rects = overlay_rects(ctx.width, ctx.height, captions=ctx.captions, title=ctx.title,
                          packaged=ctx.packaged, title_y=ctx.title_y)
    presence_limit = timeout if not rects else max(0.05, timeout * 0.45)
    presence = _presence_check(ctx, presence_limit)
    if presence[0] == 'fail':
        return presence
    if not rects:
        if presence[0] == 'skip':
            return presence
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
