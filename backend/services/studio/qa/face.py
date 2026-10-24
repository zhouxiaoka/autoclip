"""Caption or title covering a detected face, and a portrait crop that misses the speaker.

YuNet from the framing runtime is reused when it is already installed. A few
frames are sampled. The detector is a private net: it does not take
framing._detector_lock, so a check cannot stall framing. Missing the optional
detector is a skip, not a failure. Three frames and the caption box are an
estimate, not a magazine or street-cut layout.

The crop check looks at the source, not the rendered window. A turned-away head,
a window with nobody in it, or one person sliced out of a group photo fails once
that run lasts more than a second. The production crop budget (0.9 s) reads three
frames in one accurate grab: the longest span, then the longest spans framed
differently, each looked at just after its shot boundary. A grab that does not
finish or reads nothing is a skip, never a pass. The caption check still runs after
it, and the result stays a skip unless that check fails. Fit is a miss when it
covers more than 10% of the clip and a single person was there to crop. A wide group, including small low-score faces, is not.
"""
from __future__ import annotations

import threading
import time

from backend.services.studio.qa.media import ProbeError, run

_nets: dict[tuple[int, int], object] = {}
_net_lock = threading.Lock()

# Packaging caption is about two 62 px lines on a 1920 px frame.
_CAPTION_PX = 170
_TITLE_PX = 200
# A bad crop has to stay bad for longer than this before the check fails. Exactly 1 s still passes.
_PRESENCE_LIMIT = 1.0
_FACE_OVERLAP = 0.35
_MAX_GRABS = 12
_FIT_LIMIT = 0.10


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
    if longest('group') > _PRESENCE_LIMIT:
        return 'fail', 'group_crop'
    if longest('empty') > _PRESENCE_LIMIT:
        return 'fail', 'no_face'
    if longest('missing') > _PRESENCE_LIMIT:
        return 'fail', 'speaker_out'
    return 'pass', 'frontal'


def judge_fit_ratio(unjustified: float, duration: float) -> tuple[str, str]:
    """Fail when fit covers more than 10% and those shots still had a single person to crop."""
    if duration <= 0 or unjustified / duration <= _FIT_LIMIT:
        return 'pass', 'frontal'
    return 'fail', 'fit_heavy'


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


def _detect(cv2, image, score: float = 0.6):
    """Run YuNet while holding QA's lock only. Framing's detector lock stays free."""
    height, width = image.shape[:2]
    key = (width, height, round(score, 3))
    with _net_lock:
        net = _nets.get(key)
        if net is None:
            from backend.services.studio import framing
            net = cv2.FaceDetectorYN.create(
                str(framing.MODEL), '', (width, height), score_threshold=score, nms_threshold=0.3, top_k=50,
            )
            _nets[key] = net
        return net.detect(image)


def detect_faces(path, at: float, out_w: int, out_h: int, timeout: float) -> list[tuple[float, float, float, float]] | None:
    """Face boxes in output pixels, or None when YuNet is not installed."""
    from backend.services.studio import framing
    if not framing.is_installed():
        return None
    blob = _grab_jpeg(path, at, timeout, 320)
    cv2 = framing.load_cv2()
    if cv2 is None:
        return None
    import numpy as np
    image = cv2.imdecode(np.frombuffer(blob, dtype=np.uint8), cv2.IMREAD_COLOR)
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


def _presence_kind(frontals, turned, left: float, right: float, wide=None) -> str:
    from backend.services.studio import framing
    people = list(frontals) + list(turned) + list(wide or [])
    covered = [face for face in frontals if _width_overlap(face, left, right) >= _FACE_OVERLAP]
    in_window = [face for face in people if _width_overlap(face, left, right) >= _FACE_OVERLAP]
    # A family photo or a wide group cropped down to one person.
    if len(people) >= 3 and len(in_window) <= 1 and not framing._fits(people, right - left):
        return 'group'
    if covered:
        return 'frontal'
    if any(_width_overlap(face, left, right) >= _FACE_OVERLAP for face in turned):
        return 'turned'
    if people:
        return 'missing'
    return 'empty'


_PTS_SLOP = 0.5


def _grab_jpeg(path, at: float, timeout: float, width: int = 320):
    """One accurately seeked JPEG. `-ss` before `-i` stays accurate; a keyframe-only seek does not."""
    frames = _grab_frames(path, [at], timeout, width)
    blob = frames[0] if frames else None
    if not blob:
        raise ProbeError('unreadable')
    return blob


def _grab_frames(path, times: list[float], timeout: float, width: int = 480) -> list[bytes | None]:
    """Accurate JPEGs for several timestamps, one ffmpeg process.

    Input seek before `-i` with accurate seek and `-copyts`, so each frame's pts can be
    checked against the request. Every output has its own named showinfo instance
    (`showinfo@g<index>`), and a pts is matched to its output by that name. The filtergraphs
    run in parallel, so the order of their log lines says nothing about which output they
    belong to. A frame more than _PTS_SLOP from its requested time is dropped.
    """
    if not times:
        return []
    import re
    import shutil
    import tempfile
    from pathlib import Path
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    folder = Path(tempfile.mkdtemp(prefix='ac-qa-'))
    cmd = [get_ffmpeg_path(), '-v', 'info', '-nostats']
    for when in times:
        cmd += ['-copyts', '-accurate_seek', '-ss', f'{max(0.0, when):.3f}', '-i', str(path)]
    for index in range(len(times)):
        cmd += [
            '-map', f'{index}:v:0', '-an', '-frames:v', '1',
            '-vf', f"scale={width}:-2,select=eq(n\\,0),showinfo@g{index}", '-q:v', '5', str(folder / f'{index}.jpg'),
        ]
    try:
        proc = run(cmd, timeout)
        stderr = proc.stderr or b''
        if isinstance(stderr, str):
            stderr = stderr.encode('utf-8', 'replace')
        pts: dict[int, float] = {}
        for label, value in re.findall(
            rb'\[showinfo@g(\d+) @[^\]]*\]\s*n:\s*0\s+pts:\s*-?\d+\s+pts_time:\s*([0-9eE.+-]+)', stderr,
        ):
            try:
                pts.setdefault(int(label), float(value))
            except ValueError:
                continue
        frames: list[bytes | None] = []
        for index, when in enumerate(times):
            jpg = folder / f'{index}.jpg'
            actual = pts.get(index)
            if not jpg.is_file() or jpg.stat().st_size == 0 or actual is None or abs(actual - when) > _PTS_SLOP:
                frames.append(None)
                continue
            frames.append(jpg.read_bytes())
        return frames
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _faces_in_jpeg(blob: bytes):
    """(width, height, frontal, turned, wide) in normalised source coordinates, or None without YuNet."""
    from backend.services.studio import framing
    cv2 = framing.load_cv2()
    if cv2 is None:
        return None
    import numpy as np
    image = cv2.imdecode(np.frombuffer(blob, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ProbeError('unreadable')
    height, width = image.shape[:2]
    _scores, found = _detect(cv2, image, framing.WIDE_SCORE)
    frontal, turned, wide = [], [], []
    if found is not None:
        for row in found:
            if not framing._person_box(row, width):
                continue
            try:
                score = float(row[14]) if len(row) > 14 else 1.0
            except (TypeError, ValueError):
                score = 1.0
            box_w = float(row[2])
            item = {'x': (float(row[0]) + box_w / 2) / width, 'w': box_w / width, 'score': score}
            if score < framing.TRACK_SCORE:
                wide.append(item)
            elif framing.is_frontal(row):
                frontal.append(item)
            else:
                turned.append(item)
    return width, height, frontal, turned, wide


def _read_faces(path, at: float, timeout: float):
    """(width, height, frontal, turned, wide) in normalised source coordinates."""
    blob = _grab_jpeg(path, at, timeout, 480)
    return _faces_in_jpeg(blob)


# Measured on the 1080p VP9 Bg2 source under load: one frame about 0.36 s, three about
# 0.5 s, eight about 1.0 s, so about 0.27 s to start plus 0.09 s per frame. Only part of the budget is planned, so a loaded
# machine still finishes inside it. A 0.9 s crop budget reads three frames.
_GRAB_BASE = 0.27
_GRAB_EACH = 0.09
_GRAB_HEADROOM = 0.6


def _grab_count(timeout: float | None) -> int:
    """How many frames one accurate grab can read inside `timeout`."""
    if timeout is None:
        return _MAX_GRABS
    usable = float(timeout) * _GRAB_HEADROOM - _GRAB_BASE
    return max(1, min(_MAX_GRABS, int(usable / _GRAB_EACH + 1e-6)))


def _framing_gap(span, others) -> float:
    """How different this span's framing is from the closest span already looked at."""
    _at, _duration, crop_x, mode = span
    gaps = []
    for _o_at, _o_duration, o_crop_x, o_mode in others:
        if mode == 'fit' and o_mode == 'fit':
            gaps.append(0.0)
        elif mode == 'fit' or o_mode == 'fit':
            gaps.append(0.5)
        else:
            gaps.append(abs(crop_x - o_crop_x))
    return min(gaps) if gaps else 1.0


def _grab_plan(spans, timeout: float | None = None):
    """(span index, absolute time), sized to the budget by _grab_count.

    The first look is on the longest span. Each next first look goes to the span with the
    largest length times framing gap: a long span framed like one already seen (same
    speaker, same crop) adds little, a long span with a different crop or mode is a new
    framing decision. A span's first look sits just after its start, next to the shot
    boundary where an inherited crop shows. Once every span has one look, second looks
    (just before the end) and third looks (middle) follow, longest span first.
    """
    limit = _grab_count(timeout)

    def fracs(duration: float) -> tuple[float, ...]:
        return (0.12, 0.88, 0.5) if duration >= 0.8 else (0.5,)

    chosen: list[tuple[int, float]] = []
    seen: list[int] = []
    remaining = list(range(len(spans)))
    while remaining and len(chosen) < limit:
        picked = [spans[index] for index in seen]
        best = max(remaining, key=lambda index: (
            spans[index][1] * _framing_gap(spans[index], picked), spans[index][1], -index,
        ))
        remaining.remove(best)
        seen.append(best)
        at, duration = spans[best][0], spans[best][1]
        chosen.append((best, at + duration * fracs(duration)[0]))
    for place in (1, 2):
        for index in sorted(range(len(spans)), key=lambda index: (-spans[index][1], index)):
            if len(chosen) >= limit:
                return chosen
            options = fracs(spans[index][1])
            if place < len(options):
                chosen.append((index, spans[index][0] + spans[index][1] * options[place]))
    return chosen


def _single_face_fit(frontal, turned, wide, fraction: float) -> bool:
    """True when this fit look still had one person who should have been cropped."""
    from backend.services.studio import framing
    people = list(frontal) + list(turned) + list(wide)
    if len(people) >= 3 or len(frontal) >= 2:
        return False
    if len(people) >= 2 and any(float(face.get('score', 1)) < framing.MIN_SCORE for face in people):
        return False
    if not frontal:
        return False
    sample = {'t': 0.0, 'offset': 0.0, 'frontal': frontal, 'turned': turned, 'wide': wide}
    return framing._center_for(sample, {}, [], fraction) is not None


def _presence_check(ctx, timeout: float) -> tuple[str, str]:
    """Portrait crops only. Landscape and a missing source stay a pass. A seek that does not finish is a skip."""
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
    plan = _grab_plan(spans, timeout)
    layout = getattr(ctx, 'layout', '') or ''
    kinds_by_span: list[list[str]] = [[] for _ in spans]
    fit_flags: list[list[bool]] = [[] for _ in spans]
    judged = False
    try:
        frames = _grab_frames(source, [when for _index, when in plan], timeout, 480)
    except ProbeError as error:
        return 'skip', error.reason
    for (index, _when), blob in zip(plan, frames):
        if not blob:
            continue
        read = _faces_in_jpeg(blob)
        if read is None:
            return 'skip', 'no_detector'
        judged = True
        width, height, frontal, turned, wide = read
        _at, _duration, crop_x, mode = spans[index]
        if layout == 'window':
            from backend.services.studio.jobs import INTERVIEW_WINDOW
            out_w, out_h = INTERVIEW_WINDOW
        else:
            out_w, out_h = ctx.width, ctx.height
        fraction = framing.window_fraction(width, height, out_w, out_h)
        if mode == 'fit':
            kinds_by_span[index].append('fit')
            fit_flags[index].append(_single_face_fit(frontal, turned, wide, fraction))
            continue
        left = crop_x * (1 - fraction)
        kinds_by_span[index].append(_presence_kind(frontal, turned, left, left + fraction, wide))
    if not judged:
        return 'skip', 'unreadable'
    kinds = []
    unjustified = 0.0
    for index, span in enumerate(spans):
        labels = kinds_by_span[index]
        if span[3] == 'fit':
            flags = fit_flags[index]
            if flags and all(flags):
                unjustified += span[1]
            kinds.append((span[1], 'fit'))
            continue
        if not labels:
            kinds.append((span[1], 'quiet'))
            continue
        # The worst look that is at least half the samples wins, so one lucky frame cannot pass.
        half = len(labels)
        if labels.count('turned') * 2 >= half:
            label = 'turned'
        elif labels.count('group') * 2 >= half:
            label = 'group'
        elif labels.count('empty') * 2 >= half:
            label = 'empty'
        elif labels.count('missing') * 2 >= half:
            label = 'missing'
        elif 'frontal' in labels:
            label = 'frontal'
        else:
            label = labels[0]
        kinds.append((span[1], label))
    presence = judge_presence(kinds)
    if presence[0] == 'fail':
        return presence
    duration = sum(max(0.0, scene.end - scene.start) for scene in ctx.scenes) or sum(span[1] for span in spans)
    return judge_fit_ratio(unjustified, duration)


def check(ctx, timeout: float) -> tuple[str, str]:
    started = time.monotonic()
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
    cover = _cover_check(ctx, rects, timeout - (time.monotonic() - started))
    # A crop check that timed out or read nothing is a skip, not a pass, unless the
    # caption check found a face under the caption.
    if cover[0] == 'fail' or presence[0] != 'skip':
        return cover
    return presence


def _cover_check(ctx, rects, remaining: float) -> tuple[str, str]:
    """Caption or title covering a face in the rendered output."""
    if ctx.output is None or not getattr(ctx.output, 'is_file', lambda: False)():
        return 'skip', 'unreadable'
    from backend.services.studio import framing
    if not framing.is_installed():
        return 'skip', 'no_detector'
    if remaining < 0.05:
        return 'skip', 'timeout'
    times = _sample_times(_duration(ctx) or 1.0)
    share = remaining / max(1, len(times))
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
