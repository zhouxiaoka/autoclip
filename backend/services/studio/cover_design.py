"""Local cover design for an output variant: the speaker's frame, the clip's title, its palette.

The local layout matches the video: title lines, accent line and palette follow the packaging.
Frame selection may use the configured vision service only with frame-analysis consent.
Sizes follow each platform's cover slot.
An AI cover (services/cover.py) can still replace it from the output card.
"""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Any

FONT = Path(__file__).resolve().parents[2] / 'assets' / 'fonts' / 'NotoSansSC.ttf'
SIZES = {
    'douyin': (1080, 1920), 'tiktok': (1080, 1920), 'instagram_reels': (1080, 1920), 'youtube_shorts': (1080, 1920),
    'xiaohongshu': (1080, 1440),            # 3:4 note cover
    'bilibili': (1146, 717),                # 16:10 video cover
    'youtube_long': (1280, 720),
}


def size_for(strategy_id: str, source_w: int = 1920, source_h: int = 1080) -> tuple[int, int]:
    if strategy_id in SIZES:
        return SIZES[strategy_id]
    return (1280, 720) if source_w >= source_h else (1080, 1920)


def _font(size: int, weight: str):
    from PIL import ImageFont
    font = ImageFont.truetype(str(FONT), size=size)
    try:
        font.set_variation_by_name(weight)  # the bundled file is variable and defaults to Thin
    except (OSError, ValueError, AttributeError):
        pass
    return font


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    return tuple(int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))


HOST = ('主持', 'host', 'interviewer')
TITLE_BAND = 0.2  # portrait covers: top share kept for the title


def frame_time(scene: dict[str, Any]) -> tuple[float, float | None]:
    """(source seconds, crop position) a fifth into the clip; the position is the track's value there.

    Track values are the crop window's left edge as a fraction of the free range, not the
    speaker's centre; `speaker_centre` converts them.
    """
    length = scene['end'] - scene['start']
    offset = min(max(1.5, length * 0.2), max(0.0, length - 0.5))
    crop = scene.get('crop_x')
    for point in scene.get('crop_track') or []:
        if point.get('start', 0) <= offset and point.get('mode') == 'crop':
            crop = point.get('crop_x', crop)
    return scene['start'] + offset, crop


def speaker_centre(position: float | None, layout: str, source_w: int, source_h: int) -> float | None:
    """Speaker centre (fraction of the frame width) from a track position of a 4:3 window or a 9:16 crop."""
    if position is None:
        return None
    window = min(source_w, source_h * (4 / 3 if layout == 'window' else 9 / 16))
    return (position * (source_w - window) + window / 2) / source_w


def cover_speaker(packaging: dict[str, Any]) -> tuple[str, str] | None:
    """The guest for the nameplate: the frame shows whoever speaks, and that is rarely the host."""
    for speaker in packaging.get('speakers') or []:
        if not any(word in (speaker.get('role') or '').lower() for word in HOST):
            return speaker['name'], speaker.get('role', '')
    return None


QUESTION_END = ('?', '？', '吗', '呢', '么')
CANDIDATE_SHOTS = 3


def _question_times(rows: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """Source intervals of rows that end a question: in an interview, those are the host speaking."""
    return [(row['start'], row['end']) for row in rows if row['text'].rstrip(' "”」』').endswith(QUESTION_END)]


def _face_and_sharpness(frame_jpeg: bytes, geometry=None) -> tuple[float | None, float, bool]:
    """(face centre x, sharpness of the face area or frame centre, face found). Works without OpenCV."""
    from PIL import Image, ImageFilter, ImageStat
    image = Image.open(io.BytesIO(frame_jpeg)).convert('L')
    box, centre, found = None, None, False
    try:
        from backend.services.studio import framing
        cv2 = framing.load_cv2() if framing.MODEL.exists() else None
        if cv2 is not None:
            import numpy as np
            pixels = cv2.imdecode(np.frombuffer(frame_jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            height, width = pixels.shape[:2]
            with framing._detector_lock:
                _, faces = framing._detector(cv2, width, height).detect(pixels)
            faces = [f for f in (faces if faces is not None else []) if f[2] >= framing.MIN_FACE * width]
            if faces:
                x, y, w, h = (float(v) for v in max(faces, key=lambda f: f[2] * f[3])[:4])
                box, centre, found = (int(x), int(y), int(x + w), int(y + h)), (x + w / 2) / width, True
    except Exception:  # noqa: BLE001 - no detector: judge the frame centre
        box = None
    if geometry is not None and box is not None:
        geometry['face_box']=list(box)
    if box is None:
        width, height = image.size
        box = (width // 3, height // 6, width * 2 // 3, height * 2 // 3)
    edges = image.crop(box).filter(ImageFilter.FIND_EDGES)
    return centre, ImageStat.Stat(edges).var[0], found


def _signature(video, at: float) -> list[float] | None:
    """Colour profile of a frame (coarse RGB histogram): camera angles of an interview differ clearly."""
    from PIL import Image
    from backend.services.cover import extract_frame_jpeg
    try:
        image = Image.open(io.BytesIO(extract_frame_jpeg(video, at_sec=at, max_width=320))).convert('RGB').resize((64, 36))
    except Exception:  # noqa: BLE001
        return None
    histogram = image.quantize(colors=64, method=Image.Quantize.FASTOCTREE, kmeans=0).convert('RGB').histogram()
    bins = [sum(histogram[c * 256 + i * 32:c * 256 + (i + 1) * 32]) for c in range(3) for i in range(8)]
    total = sum(bins) or 1
    return [b / total for b in bins]


def _similarity(a: list[float], b: list[float]) -> float:
    return sum(min(x, y) for x, y in zip(a, b))


GUEST_SAMPLES = 24
SAME_LOOK = 0.75
_guest_looks: dict[str, list[float] | None] = {}


def guest_look(video) -> list[float] | None:
    """Colour profile of the camera the video shows most: in an interview, the guest's.

    Frames across the whole video are grouped by look; the largest group wins. Cached per file.
    """
    key = f'{video}:{Path(video).stat().st_size}'
    if key not in _guest_looks:
        from backend.services.publish_export import _probe
        duration = float(_probe(video).get('duration') or 0)
        looks = [sig for sig in (_signature(video, duration * (i + 0.5) / GUEST_SAMPLES) for i in range(GUEST_SAMPLES)) if sig]
        groups: list[list[list[float]]] = []
        for sig in looks:
            home = next((group for group in groups if _similarity(sig, group[0]) >= SAME_LOOK), None)
            (home.append(sig) if home else groups.append([sig]))
        big = max(groups, key=len) if groups else None
        # A single dominant look only: when no camera holds the screen, there is no guest look.
        _guest_looks[key] = big[0] if big and len(big) >= max(4, len(looks) * 0.35) else None
    return _guest_looks[key]


def _guest_shots(video, start: float, shots) -> tuple[list, bool]:
    """Shots that look like the guest's camera, best match first; ([], False) without a guest look."""
    look = guest_look(video)
    if look is None:
        return [], False
    scored = [(shot, _similarity(sig, look)) for shot in shots
              if (sig := _signature(video, start + (shot[0] + shot[1]) / 2)) is not None]
    matches = [shot for shot, score in sorted(scored, key=lambda item: item[1], reverse=True) if score >= SAME_LOOK]
    return matches, bool(matches)


VISION_CANDIDATES = 6
CHOOSE_PROMPT = (
    '这是一段访谈视频里的 {n} 张候选画面，编号 1–{n}。{who}'
    '请选出最适合做短视频封面的一张：必须是受访嘉宾本人（不是主持人、不是观众），正脸或清晰侧脸，'
    '不模糊、不闭眼、表情自然有感染力。如果没有一张是嘉宾本人，best 返回 0。'
    '只返回 JSON：{{"best":编号,"guest":[是嘉宾本人的编号]}}'
)


def _thumb(frame_jpeg: bytes, width: int = 384) -> str:
    import base64
    from PIL import Image
    image = Image.open(io.BytesIO(frame_jpeg)).convert('RGB')
    image.thumbnail((width, width))
    out = io.BytesIO()
    image.save(out, format='JPEG', quality=80)
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()


def _candidates(
    video, start: float, shots, limit: int, shares=(0.35, 0.65)
) -> list[tuple[bytes, float | None, float, bool, float]]:
    """Sharpest frame of each of the longest shots: (frame, face centre, sharpness, face found)."""
    from backend.services.cover import extract_frame_jpeg

    out = []
    for shot_start, shot_end in sorted(shots, key=lambda shot: shot[1] - shot[0], reverse=True)[:limit]:
        best = None
        for share in shares:
            try:
                frame = extract_frame_jpeg(
                    video, at_sec=start + shot_start + (shot_end - shot_start) * share, max_width=1920
                )
            except Exception:  # noqa: BLE001
                continue
            centre, sharpness, found = _face_and_sharpness(frame)
            if best is None or (found, sharpness) > (best[3], best[2]):
                best = (frame, centre, sharpness, found, start + shot_start + (shot_end - shot_start) * share)
        if best:
            out.append(best)
    return out


def _choose_with_vision(candidates, guest: str, host: str) -> tuple[int, bool] | None:
    """(index, is the guest) chosen by the vision model, or None when it is not set up or fails."""
    from backend.services.studio import intelligence
    if not candidates or not intelligence.source_frame_analysis_allowed():
        return None
    who = (f'受访嘉宾是 {guest}。' if guest else '') + (f'主持人是 {host}。' if host else '')
    content = [{'type': 'text', 'text': CHOOSE_PROMPT.format(n=len(candidates), who=who)}]
    for index, (frame, *_rest) in enumerate(candidates, 1):
        content += [{'type': 'text', 'text': f'画面 {index}'}, {'type': 'image_url', 'image_url': {'url': _thumb(frame)}}]
    try:
        from backend.core import llm_usage
        from backend.services.studio.vision_settings import effective
        with llm_usage.stage('cover_frame'):
            answer = intelligence.vision_call(content, {**effective(), 'quick_screening': True}) or {}
        best = int(answer.get('best') or 0)
    except Exception:  # noqa: BLE001 - fall back to the local choice
        return None
    if 1 <= best <= len(candidates):
        return best - 1, True
    return None if not answer else (max(range(len(candidates)), key=lambda i: (candidates[i][3], candidates[i][2])), False)


def _camera_frame(jpeg: bytes) -> bool:
    """A mostly white or black text slide can outscore a camera shot on edge sharpness."""
    from PIL import Image
    image = Image.open(io.BytesIO(jpeg)).convert('L').resize((48, 32))
    histogram = image.histogram()
    return sum(histogram[25:226]) > image.width * image.height * .55


def _answer_start(rows, start, end):
    """Find where a transcribed question gives way to its answer, including a single long ASR cue."""
    for row in reversed(rows):
        text = str(row.get('text') or '').strip()
        mark = max(text.rfind('?'), text.rfind('？'))
        if mark < 0:
            continue
        at = row['start'] + (row['end'] - row['start']) * (mark + 1) / len(text)
        if start <= at <= end - 1:
            return at
    return None


def pick_frame(
    video,
    scene: dict[str, Any],
    rows: list[dict[str, Any]],
    packaging: dict[str, Any] | None = None,
    guest_hint: str = "",
    *,
    local_revision: int | None = None,
    trace=None,
    context=None,
    exclude_time=None,
) -> tuple[bytes, float | None, bool]:
    """(frame, speaker centre, guest on screen) for the cover.

    A fixed point in the clip often caught a hand in motion or the host's camera, labelled with the
    guest's name. Candidates are the sharpest frame of each of the longest shots. The vision model
    (when set up) picks the guest's best frame; colour and screen-time rules cannot tell a host's
    camera from a guest's, so without it the sharpest face is used and no nameplate is drawn.
    """
    from backend.services.cover import extract_frame_jpeg
    from backend.services.studio import framing

    start, length = scene["start"], scene["end"] - scene["start"]
    shots = framing.split_shots(length, framing.detect_cuts(video, start, length))
    answer = _answer_start(rows, start, start + length)
    if context is None and answer is not None:
        # Use shots wholly inside the answer. A two-shot spanning the question can still show the host.
        response_shots = [shot for shot in shots if start + shot[0] >= answer and shot[1] - shot[0] >= 0.5]
        shots = response_shots or [(max(a, answer - start), b) for a, b in shots if start + b > answer + 0.5]
    if context and len(shots) == 1 and length > 3:
        # A stationary camera may still capture several different gestures or expressions.
        a, b = shots[0]
        step = (b - a) / 3
        shots = [(a + i * step, a + (i + 1) * step) for i in range(3)]
    if local_revision and answer is not None:
        shares = ((0.48, 0.76), (0.25, 0.52), (0.36, 0.65))[(local_revision - 1) % 3]
        candidates = _candidates(video, start, shots, VISION_CANDIDATES, shares)
    else:
        candidates = _candidates(video, start, shots, VISION_CANDIDATES)

    editorial = None
    cue = None
    if context is not None:
        from backend.services import cover_brief, cover_planner

        title = cover_brief.choose_copy(context["title"], rows, context["locked"])
        context = dict(context, title=title)
        cue = next((row for row in rows if title and title.casefold() in row["text"].casefold()
                    and row["end"] > start and row["start"] < start + length), None)
        if cue:
            a, b = max(start, cue["start"]) - start, min(start + length, cue["end"]) - start
            if b > a:
                targeted = _candidates(video, start, [(a, b)], 1, (.5,))
                candidates = targeted + candidates
        # Compare small RGB thumbnails, keeping different compositions at the same camera position.
        from PIL import Image, ImageChops, ImageStat
        unique, previews = [], []
        for candidate in candidates:
            preview = Image.open(io.BytesIO(candidate[0])).convert("RGB").resize((24, 16))
            if any(max(ImageStat.Stat(ImageChops.difference(preview, other)).mean) < 4 for other in previews):
                continue
            unique.append(candidate)
            previews.append(preview)
        candidates = unique[:VISION_CANDIDATES]
        if exclude_time is not None:
            candidates = [c for c in candidates if abs(c[4] - exclude_time) > .15] or candidates
        if candidates:
            speakers = (packaging or {}).get("speakers") or []
            hints = [dict(name=str(s.get("name") or "")[:80], role=str(s.get("role") or "")[:80])
                     for s in speakers if isinstance(s, dict) and s.get("name")][:6]
            editorial = cover_planner.inspect(candidates, context, rows, speaker_hints=hints)
            if trace is not None and hints:
                trace["speaker_hints"] = hints

    def selected(candidate, is_guest, reason):
        frame, centre, _, _, at = candidate
        if trace is not None:
            if editorial:
                trace["editorial_plan"] = dict(editorial, frame_sha256=hashlib.sha256(frame).hexdigest())
            trace.update(
                kind="video_frame",
                source_timestamp_sec=at,
                selection_reason=reason,
                clip_range=[start, start + length],
                candidates=[dict(id=i, time=c[4], sharpness=c[2], face_found=c[3], centre=c[1],
                                 frame_sha256=hashlib.sha256(c[0]).hexdigest()) for i, c in enumerate(candidates, 1)],
            )
        return frame, centre, is_guest

    if not candidates:
        at, _ = frame_time(scene)
        if trace is not None:
            trace.update(
                kind="video_frame", source_timestamp_sec=at, selection_reason="片段内备用时间点", candidates=[]
            )
        return extract_frame_jpeg(video, at_sec=at, max_width=1920), None, False
    if editorial and editorial["status"] == "planned":
        direction = editorial["direction"]
        return selected(candidates[direction["best"] - 1], False, direction["reason"])
    speakers = (packaging or {}).get("speakers") or []
    guest = (
        next((sp["name"] for sp in speakers if not any(w in (sp.get("role") or "").lower() for w in HOST)), "")
        or guest_hint
    )
    host = next((sp["name"] for sp in speakers if any(w in (sp.get("role") or "").lower() for w in HOST)), "")
    chosen = None if context is not None or local_revision is not None else _choose_with_vision(candidates, guest, host)
    if chosen is not None:
        index, is_guest = chosen
        return selected(candidates[index], is_guest, "视觉选帧：对照该片段嘉宾和主持人")
    eligible = [c for c in candidates if c[3]] or [c for c in candidates if _camera_frame(c[0])] or candidates
    if cue:
        in_cue = [c for c in eligible if cue["start"] <= c[4] < cue["end"]]
        if in_cue:
            return selected(max(in_cue, key=lambda c: c[2]), False, "批准标题对应原话时段的清晰镜头")
    if answer is not None:
        # The sustained answer shot outranks momentary listener reactions and wide cutaways.
        after = [c for c in eligible if c[4] >= answer]
        if after:
            return selected(after[(local_revision or 0) % len(after)], False, "提问后回答段中的清晰帧")
        return selected(eligible[0], False, "按片段内可用镜头选择")
    else:
        eligible.sort(key=lambda c: c[2], reverse=True)
        return selected(eligible[(local_revision or 0) % len(eligible)], False, '按真实镜头与清晰度选择')


def _crop(image, width: int, height: int, centre: float | None):
    from PIL import Image
    src_w, src_h = image.size
    aspect = width / height
    if src_w / src_h > aspect:
        crop_w = round(src_h * aspect)
        x = round(((centre if centre is not None else 0.5) * src_w) - crop_w / 2)
        left = max(0, min(src_w - crop_w, x))
        box = (left, 0, left + crop_w, src_h)
    else:
        crop_h = round(src_w / aspect)
        top = max(0, min(src_h - crop_h, round((src_h - crop_h) * 0.3)))
        box = (0, top, src_w, top + crop_h)
    from PIL import ImageFilter
    scaled = image.crop(box).resize((width, height), Image.Resampling.LANCZOS)
    upscale = width / max(1, box[2] - box[0])
    return scaled.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2)) if upscale > 1.05 else scaled


def _fit_size(draw, lines: list[str], max_width: int, start: int, weight: str) -> int:
    size = start
    while size > 28 and any(draw.textlength(line, font=_font(size, weight)) > max_width for line in lines):
        size -= 4
    return size


def _rewrap(draw, words: list[tuple[str, bool]], max_width: int, start: int, max_lines: int = 4):
    """Greedy word wrap at the largest size that fits in `max_lines` lines."""
    size = start
    while size > 28:
        font = _font(size, 'Black')
        rows, current = [], []
        for word in words:
            trial = ' '.join(w for w, _ in current + [word])
            if current and draw.textlength(trial, font=font) > max_width:
                rows.append(current)
                current = []
            current.append(word)
        rows.append(current)
        if len(rows) <= max_lines and all(draw.textlength(' '.join(w for w, _ in row), font=font) <= max_width for row in rows):
            return rows, size
        size -= 4
    return [words], size


def _shade(width: int, height: int, colour: tuple[int, int, int], *, vertical: bool, reach: float, strength: int):
    from PIL import Image, ImageDraw
    layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    span = int((height if vertical else width) * reach)
    for i in range(span):
        alpha = int(strength * (1 - i / span) ** 1.6)
        if vertical:
            draw.line([(0, i), (width, i)], fill=(*colour, alpha))
        else:
            draw.line([(i, 0), (i, height)], fill=(*colour, alpha))
    return layer


def design(frame_jpeg: bytes, *, width: int, height: int, title_lines: list[str], accent_line: int = 1,
           palette: str | None = None, speaker: tuple[str, str] | None = None, crop_centre: float | None = None) -> bytes:
    """JPEG cover bytes."""
    from PIL import Image, ImageDraw
    from backend.services.studio.packaging_render import PALETTES
    accent_hex, canvas_hex = PALETTES.get(palette or 'azure', PALETTES['azure'])
    accent, canvas, white = _rgb(accent_hex), _rgb(canvas_hex), (236, 234, 230)
    portrait = height > width
    # Landscape: the title goes on the side the speaker is not on.
    title_right = not portrait and crop_centre is not None and crop_centre < 0.45
    source = Image.open(io.BytesIO(frame_jpeg)).convert('RGB')
    lines = [line for line in title_lines if line.strip()][:2]
    # Lay out the title first: a portrait cover's photo starts below it.
    draw = ImageDraw.Draw(Image.new('RGB', (width, height)))
    margin = round(width * (0.07 if portrait else 0.06))
    max_width = width - 2 * margin if portrait else round(width * 0.52)
    start = round(width * (0.115 if portrait else 0.075))
    # Words carry their colour (the accent line keeps its accent when rewrapped).
    rows = [[(word, i == accent_line and len(lines) > 1) for word in line.split(' ')] for i, line in enumerate(lines)]
    size = _fit_size(draw, lines, max_width, start, 'Black')
    if size < start * 0.7 and all(line.isascii() for line in lines):
        # Long English titles shrink to unreadable in two lines: rewrap into up to four, larger.
        rows, size = _rewrap(draw, [word for row in rows for word in row], max_width, start)
    if portrait:
        # Faces sit in the upper third of a 16:9 frame: keep the title in its own band above them.
        title_end = round(height * 0.07) + len(rows) * round(size * 1.22) + round(size * 0.6)
        band = max(round(height * TITLE_BAND), title_end)
        image = Image.new('RGBA', (width, height), (*canvas, 255))
        image.paste(_crop(source, width, height - band, crop_centre).convert('RGBA'), (0, band))
        fade = _shade(width, height - band, canvas, vertical=True, reach=0.25, strength=255)
        image.alpha_composite(fade, (0, band))
        bottom = _shade(width, height, canvas, vertical=True, reach=0.25, strength=200).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        image = Image.alpha_composite(image, bottom)
    else:
        image = _crop(source, width, height, crop_centre).convert('RGBA')
        shade = _shade(width, height, canvas, vertical=False, reach=0.68, strength=240)
        image = Image.alpha_composite(image, shade.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if title_right else shade)
    draw = ImageDraw.Draw(image)
    font = _font(size, 'Black')
    gap = round(size * 0.22)
    block = len(rows) * size + max(0, len(rows) - 1) * gap
    y = round(height * 0.07) if portrait else round((height - block) / 2)
    bottom = y
    space = draw.textlength(' ', font=font)
    for row in rows:
        text = ' '.join(word for word, _ in row)
        x = (width - draw.textlength(text, font=font)) / 2 if portrait else (width - margin - max_width if title_right else margin)
        for word, accented in row:
            draw.text((x, y), word, font=font, fill=accent if accented else white)
            x += draw.textlength(word, font=font) + space
        bottom = draw.textbbox((0, y), text, font=font)[3]
        y += size + gap
    bar_w = round(width * (0.12 if portrait else 0.08))
    bar_x = (width - bar_w) / 2 if portrait else (width - margin - max_width if title_right else margin)
    bar_y = bottom + round(size * 0.35)
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + max(6, size // 12)], fill=accent)
    if speaker and speaker[0]:
        name_font, role_font = _font(round(width * (0.045 if portrait else 0.028)), 'Bold'), _font(round(width * (0.03 if portrait else 0.019)), 'Regular')
        base = height - round(height * (0.09 if portrait else 0.12))
        draw.rectangle([margin, base - name_font.size, margin + 8, base + (role_font.size + 10 if speaker[1] else 0)], fill=accent)
        draw.text((margin + 24, base - name_font.size), speaker[0], font=name_font, fill=white)
        if speaker[1]:
            draw.text((margin + 24, base + 6), speaker[1], font=role_font, fill=(196, 196, 196))
    out = io.BytesIO()
    image.convert('RGB').save(out, format='JPEG', quality=90)
    return out.getvalue()


def keeps_scene(reference: bytes, candidate) -> bool:
    """Reject gross studio-backdrop substitutions in the model artwork relative to the actual shot."""
    from PIL import Image
    def extremes(image):
        hist = image.convert('L').resize((64, 64)).histogram()
        return sum(hist[:25]) / 4096, sum(hist[225:]) / 4096
    original = extremes(Image.open(io.BytesIO(reference)))
    changed = extremes(candidate)
    return all(new - old < .42 for old, new in zip(original, changed))


def headline_lines(title: str) -> list[str]:
    """Prefer a complete pull quote on a small cover. Keep the publishing title intact."""
    title = ' '.join(title.split())
    if len(title) > 55:
        quotes = re.findall(r'“([^”]+)”|‘(.+?)’(?=$|[.,:;!?—\s])|"([^"]+)"|「([^」]+)」', title)
        phrases = [next(part for part in match if part) for match in quotes]
        if phrases:
            short = [q for q in phrases if len(q.split()) <= 5 and len(q) <= 28]
            title = min(short or phrases, key=len)
    if len(title) < 12:
        return [title]
    cuts = [m.start() for m in re.finditer(r'\s+', title)]
    if not cuts:
        cuts = [i for i in range(1, len(title)) if '\u3400' <= title[i] <= '\u9fff']
    if not cuts:
        return [title]
    cut = min(cuts, key=lambda i: abs(i - len(title) / 2))
    return [title[:cut].rstrip(), title[cut:].lstrip()]


def title_lines_for(draft: dict[str, Any], post_title: str, strategy_id: str) -> tuple[list[str], int]:
    """The video's own title lines when it has packaging, else the post title split in two."""
    packaging = draft.get('packaging') or {}
    if packaging.get('title_lines'):
        return list(packaging['title_lines']), int(packaging.get('title_accent_line', 1))
    return headline_lines(post_title), 1
