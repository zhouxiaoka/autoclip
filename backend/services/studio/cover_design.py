"""Local cover design for an output variant: the speaker's frame, the clip's title, its palette.

No image model, no cost, under a second, and it matches the video it belongs to: the same title
lines, accent line and palette as the packaging. Sizes follow each platform's cover slot.
An AI cover (services/cover.py) can still replace it from the output card.
"""
from __future__ import annotations

import io
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


def _face_and_sharpness(frame_jpeg: bytes) -> tuple[float | None, float, bool]:
    """(face centre x, sharpness of the face area or frame centre, face found). Works without OpenCV."""
    from PIL import Image, ImageFilter, ImageStat
    image = Image.open(io.BytesIO(frame_jpeg)).convert('L')
    box, centre, found = None, None, False
    try:
        from backend.services.studio import framing
        if framing.is_installed():
            framing.ensure_on_path()
            import cv2
            import numpy as np
            pixels = cv2.imdecode(np.frombuffer(frame_jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            height, width = pixels.shape[:2]
            _, faces = framing._detector(cv2, width, height).detect(pixels)
            faces = [f for f in (faces if faces is not None else []) if f[2] >= framing.MIN_FACE * width]
            if faces:
                x, y, w, h = (float(v) for v in max(faces, key=lambda f: f[2] * f[3])[:4])
                box, centre, found = (int(x), int(y), int(x + w), int(y + h)), (x + w / 2) / width, True
    except Exception:  # noqa: BLE001 - no detector: judge the frame centre
        box = None
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


def _candidates(video, start: float, shots, limit: int) -> list[tuple[bytes, float | None, float, bool]]:
    """Sharpest frame of each of the longest shots: (frame, face centre, sharpness, face found)."""
    from backend.services.cover import extract_frame_jpeg
    out = []
    for shot_start, shot_end in sorted(shots, key=lambda shot: shot[1] - shot[0], reverse=True)[:limit]:
        best = None
        for share in (0.35, 0.65):
            try:
                frame = extract_frame_jpeg(video, at_sec=start + shot_start + (shot_end - shot_start) * share, max_width=1920)
            except Exception:  # noqa: BLE001
                continue
            centre, sharpness, found = _face_and_sharpness(frame)
            if best is None or (found, sharpness) > (best[3], best[2]):
                best = (frame, centre, sharpness, found)
        if best:
            out.append(best)
    return out


def _choose_with_vision(candidates, guest: str, host: str) -> tuple[int, bool] | None:
    """(index, is the guest) chosen by the vision model, or None when it is not set up or fails."""
    from backend.services.studio import intelligence
    if not intelligence.ready() or not candidates:
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


def pick_frame(video, scene: dict[str, Any], rows: list[dict[str, Any]], packaging: dict[str, Any] | None = None,
               guest_hint: str = '') -> tuple[bytes, float | None, bool]:
    """(frame, speaker centre, guest on screen) for the cover.

    A fixed point in the clip often caught a hand in motion or the host's camera, labelled with the
    guest's name. Candidates are the sharpest frame of each of the longest shots. The vision model
    (when set up) picks the guest's best frame; colour and screen-time rules cannot tell a host's
    camera from a guest's, so without it the sharpest face is used and no nameplate is drawn.
    """
    from backend.services.cover import extract_frame_jpeg
    from backend.services.studio import framing
    start, length = scene['start'], scene['end'] - scene['start']
    shots = framing.split_shots(length, framing.detect_cuts(video, start, length))
    candidates = _candidates(video, start, shots, VISION_CANDIDATES)
    if not candidates:
        at, _ = frame_time(scene)
        return extract_frame_jpeg(video, at_sec=at, max_width=1920), None, False
    speakers = (packaging or {}).get('speakers') or []
    guest = next((sp['name'] for sp in speakers if not any(w in (sp.get('role') or '').lower() for w in HOST)), '') or guest_hint
    host = next((sp['name'] for sp in speakers if any(w in (sp.get('role') or '').lower() for w in HOST)), '')
    chosen = _choose_with_vision(candidates, guest, host)
    if chosen is not None:
        index, is_guest = chosen
        frame, centre, _, _ = candidates[index]
        return frame, centre, is_guest
    questions = _question_times(rows)
    frame, centre, _, _ = max(candidates, key=lambda c: (c[3], c[2]))
    return frame, centre, False


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


def nameplate(image, name: str, role: str = '', palette: str | None = None):
    """Our own, always-correct nameplate on an AI cover (image models invent names)."""
    from PIL import ImageDraw
    from backend.services.studio.packaging_render import PALETTES
    accent = _rgb(PALETTES.get(palette or 'azure', PALETTES['azure'])[0])
    image = image.convert('RGB')
    draw = ImageDraw.Draw(image)
    width, height = image.size
    portrait = height > width
    margin = round(width * (0.07 if portrait else 0.05))
    name_font = _font(round(width * (0.042 if portrait else 0.026)), 'Bold')
    role_font = _font(round(width * (0.028 if portrait else 0.017)), 'Regular')
    base = height - round(height * (0.08 if portrait else 0.1))
    text_w = max(draw.textlength(name, font=name_font), draw.textlength(role, font=role_font) if role else 0)
    pad = round(name_font.size * 0.45)
    top = base - name_font.size - pad
    bottom = base + (role_font.size + 12 if role else 0) + pad
    draw.rectangle([margin, top, margin + 8 + pad * 2 + text_w + 16, bottom], fill=(18, 18, 18))
    draw.rectangle([margin, top, margin + 8, bottom], fill=accent)
    draw.text((margin + 8 + pad + 8, base - name_font.size), name, font=name_font, fill=(236, 234, 230))
    if role:
        draw.text((margin + 8 + pad + 8, base + 6), role, font=role_font, fill=(190, 190, 190))
    return image


def title_lines_for(draft: dict[str, Any], post_title: str, strategy_id: str) -> tuple[list[str], int]:
    """The video's own title lines when it has packaging, else the post title split in two."""
    packaging = draft.get('packaging') or {}
    if packaging.get('title_lines'):
        return list(packaging['title_lines'])[:2], int(packaging.get('title_accent_line', 1))
    from backend.services.studio.caption_layout import lines_for
    zh = not post_title.isascii()
    lines = lines_for(post_title, 11 if zh else 22 * 0.55) or [post_title]
    return lines[:2], 1
