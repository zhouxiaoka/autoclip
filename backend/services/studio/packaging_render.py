"""Render template packaging (ASS) and the interview window layout for one scene.

Each scene is encoded on its own (render.py), so every overlay is expressed on the output
timeline and clipped to the scene: the scene's ASS only carries events visible inside it,
with times relative to the scene start. Colours come from the content palette (mood), not the
product UI; the default palette matches DESIGN.md's accent.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.services.studio.models import Draft, Packaging, Scene

FONT_DIR = Path(__file__).resolve().parents[2] / 'assets' / 'fonts'
# Use the bundled variable font's actual family (name ID 1). Its preferred
# family (name ID 16) silently falls back on CoreText and older Fontconfig.
FONT = 'Noto Sans SC Thin'
W, H = 1080, 1920
WIN_Y, WIN_H = 560, 810
WHITE, SUB, INK, INK_SOFT = '&H00E6EAEC', '&H009BA2A6', '&H00191A1A', '&H26191A1A'
# Content palettes (accent, canvas). Content follows its mood, not the product UI: azure is the
# golden default; the canvas stays a near-black tinted toward the accent.
PALETTES = {
    'azure': ('5A8BFF', '1A1A19'), 'amber': ('F2B544', '1B1712'), 'coral': ('FF6F59', '1B1514'),
    'mint': ('46D3A6', '111917'), 'lemon': ('F4DC3C', '141413'), 'rose': ('FF7FA9', '1B1418'),
    'lilac': ('B69CFF', '17151C'),
}


def _ass(rgb: str) -> str:
    return f'&H00{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}'.upper()


def colours(palette: str | None) -> dict[str, str]:
    """ASS and ffmpeg colours for a palette; light accents get dark text on filled pills."""
    accent, canvas = PALETTES.get(palette or 'azure', PALETTES['azure'])
    r, g, b = (int(accent[i:i + 2], 16) for i in (0, 2, 4))
    light = 0.2126 * r + 0.7152 * g + 0.0722 * b > 150
    return {'accent': _ass(accent), 'on_accent': INK if light else WHITE, 'accent_hex': f'0x{accent}', 'bg': f'0x{canvas}'}


BG, ACCENT_HEX, ACCENT = colours(None)['bg'], colours(None)['accent_hex'], colours(None)['accent']
NAMEPLATE_SEC = 3.2


def timeline(scenes: list[Scene]) -> list[tuple[float, float, float]]:
    """(source_start, source_end, output_offset) per scene, using the renderer's frame-aligned durations."""
    from backend.services.studio.audio import scene_duration
    rows, offset = [], 0.0
    for scene in scenes:
        rows.append((scene.start, scene.end, offset))
        offset += scene_duration(scene)
    return rows


def to_output(t: float, rows) -> float | None:
    for start, end, offset in rows:
        if start <= t < end:
            return offset + t - start
    return None


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f'{int(h)}:{int(m):02d}:{s:05.2f}'


def _esc(text: str) -> str:
    return text.replace('\\', '＼').replace('{', '（').replace('}', '）').replace('\n', ' ')


def _esc_lines(text: str) -> str:
    """Escape user text but keep the layout's explicit ASS line breaks."""
    return '\\N'.join(_esc(part) for part in text.split('\\N'))


def _limit(font_size: int) -> float:
    """Line width budget (CJK characters) for a font size inside the 1080 px frame margins."""
    return 920 / font_size


def _emphasize(text: str, phrases: list[str], accent: str = ACCENT) -> str:
    """Colour phrases (already escaped) in the accent blue inside an escaped caption."""
    for phrase in sorted({p for p in phrases if p}, key=len, reverse=True):
        safe = _esc(phrase)
        if safe in text:
            text = text.replace(safe, f'{{\\c{accent}}}{safe}{{\\c{WHITE}}}', 1)
    return text


def _header(look: dict[str, str] | None = None) -> str:
    look = look or colours(None)
    ACCENT, ON_ACCENT = look['accent'], look['on_accent']  # noqa: N806 - keeps the style table readable
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{FONT},112,{WHITE},{WHITE},{INK},{INK},1,0,0,0,100,100,3,0,1,0,0,8,40,40,0,1
Style: TitleAccent,{FONT},112,{ACCENT},{ACCENT},{INK},{INK},1,0,0,0,100,100,3,0,1,0,0,8,40,40,0,1
Style: Caption,{FONT},62,{WHITE},{WHITE},&H00000000,&H80000000,1,0,0,0,100,100,1,0,1,5,1,2,48,48,0,1
Style: Original,{FONT},36,{SUB},{SUB},{INK},{INK},0,0,0,0,100,100,0,0,1,0,0,8,64,64,0,1
Style: Words,{FONT},82,{WHITE},{WHITE},&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,2,2,60,60,0,1
Style: Hook,{FONT},66,{WHITE},{WHITE},{INK},{INK},1,0,0,0,100,100,0,0,3,22,0,8,60,60,0,1
Style: Tag,{FONT},60,{ACCENT},{ACCENT},&H00000000,&H80000000,1,1,0,0,100,100,2,0,1,5,2,5,40,40,0,1
Style: PlateName,{FONT},46,{WHITE},{WHITE},{INK_SOFT},{INK_SOFT},1,0,0,0,100,100,0,0,3,14,0,7,0,0,0,1
Style: PlateRole,{FONT},32,{SUB},{SUB},{INK_SOFT},{INK_SOFT},0,0,0,0,100,100,0,0,3,12,0,7,0,0,0,1
Style: PlateBar,{FONT},10,{ACCENT},{ACCENT},{ACCENT},{ACCENT},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: CaptionBox,{FONT},58,{WHITE},{WHITE},{INK_SOFT},{INK_SOFT},1,0,0,0,100,100,1,0,3,14,0,2,48,48,0,1
Style: TagPill,{FONT},48,{ON_ACCENT},{ON_ACCENT},{ACCENT},{ACCENT},1,0,0,0,100,100,2,0,3,14,0,5,40,40,0,1
Style: Cine,{FONT},64,{WHITE},{WHITE},&H00000000,&H00000000,1,0,0,0,100,100,2,0,1,0,0,2,60,60,0,1
Style: CineGlow,{FONT},64,{ACCENT},{ACCENT},{ACCENT},&H00000000,1,0,0,0,100,100,2,0,1,3,0,2,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


class _Scene:
    """Collect events for one scene window [offset, offset + length) on the output timeline."""

    def __init__(self, offset: float, length: float):
        self.offset, self.length, self.lines = offset, length, []

    def add(self, layer: int, start: float, end: float, style: str, text: str, *, carry: bool = True) -> None:
        # Animated one-shots (nameplates, tags) must not restart in the next scene: keep them in
        # the scene where they begin. Pinned or continuous layers (title, captions) carry over.
        if not carry and not (self.offset <= start < self.offset + self.length):
            return
        s, e = max(start, self.offset), min(end, self.offset + self.length)
        if e - s < 0.04:
            return
        self.lines.append(f'Dialogue: {layer},{_ts(s - self.offset)},{_ts(e - self.offset)},{style},,0,0,0,,{text}')


def _words(cue_text: str, start: float, end: float, timed: list[dict] | None):
    """(start, end, word) on the cue's own clock; ASR word times when present, else by length."""
    if timed:
        return [(w['start'], w['end'], w['text'].strip()) for w in timed if w.get('text', '').strip()]
    tokens = cue_text.split()
    weights = [len(t) + 1 for t in tokens]
    total, cursor, out = sum(weights) or 1, start, []
    for token, weight in zip(tokens, weights):
        span = (end - start) * weight / total
        out.append((cursor, cursor + span, token))
        cursor += span
    return out


def _chunks(words, max_words=3, max_chars=18):
    chunks, current = [], []
    for word in words:
        chars = sum(len(w[2]) + 1 for w in current) + len(word[2])
        if current and (len(current) >= max_words or chars > max_chars or current[-1][2][-1:] in '.?!,;:'):
            chunks.append(current)
            current = []
        current.append(word)
    return chunks + ([current] if current else [])


def _nameplate(scene: _Scene, at: float, name: str, role: str, y: int) -> None:
    end = at + NAMEPLATE_SEC
    slide = lambda row, delay: f'{{\\an7\\move(-640,{row},72,{row},{delay},{delay + 300})\\fad(0,260)}}'
    scene.add(5, at, end, 'PlateBar', f'{{\\an7\\move(-640,{y - 14},56,{y - 14},0,300)\\fad(0,260)\\p1}}m 0 0 l 8 0 8 {118 if role else 70} 0 {118 if role else 70}{{\\p0}}', carry=False)
    scene.add(5, at, end, 'PlateName', slide(y, 0) + _esc(name), carry=False)
    if role:
        scene.add(5, at, end, 'PlateRole', slide(y + 66, 80) + _esc(role), carry=False)


def scene_ass(packaging: Packaging, scenes: list[Scene], index: int, word_timing: dict | None = None) -> str:
    """ASS document for scene `index`; times are relative to that scene's start.

    Every caption screen is at most two lines (see caption_layout). Styles only change looks and
    motion, never the layout contract: title on top, captions at the window edge, plate lower-left.
    """
    from backend.services.studio.caption_layout import timed_screens, width
    rows = timeline(scenes)
    total = rows[-1][2] + (rows[-1][1] - rows[-1][0])
    offset = rows[index][2]
    length = rows[index][1] - rows[index][0]
    out = _Scene(offset, length)
    source_scene = scenes[index]
    def add_caption(layer, start, end, style, text):
        # Caption pages/words keep the cue's source clock. Edits and reordered scenes select
        # only their overlapping text instead of replaying it or dropping a boundary cue.
        start, end = max(start, source_scene.start), min(end, source_scene.end)
        if end > start:
            out.add(layer, offset + start - source_scene.start, offset + end - source_scene.start, style, text)
    interview = packaging.template == 'interview_zh'
    style = packaging.style or ('classic' if interview else 'pop')
    look = colours(packaging.palette)
    accent = look['accent']
    tag_texts = [t.text for t in packaging.tags] if packaging.tags_enabled else []

    lines = packaging.title_lines
    if interview and lines:
        entrance = {'classic': '\\fscx88\\fscy88\\t(0,200,\\fscx100\\fscy100)\\fad(180,0)',
                    'boxed': '\\fad(160,0)', 'spotlight': '\\fad(320,0)'}[style] if index == 0 else ''
        for i, line in enumerate(lines):
            y = 150 + i * 150
            title_style = 'TitleAccent' if i == packaging.title_accent_line and len(lines) > 1 else 'Title'
            move = f'\\move(540,{y + 40},540,{y},{i * 120},{i * 120 + 280})' if style == 'boxed' and index == 0 else f'\\pos(540,{y})'
            size = min(112, int(1000 / max(width(line), 1)))  # one line always fits the 1080 px frame
            out.add(3, 0, total, title_style, f'{{\\an8{move}\\fs{size}{entrance}}}{_esc(line)}')
    elif lines:
        size = min(66, int(920 / max(max(width(line) for line in lines), 1)))
        hook = '\\N'.join(_esc(line) for line in lines)
        out.add(3, 0, 2.8, 'Hook', f'{{\\an8\\fs{size}\\pos(540,250)\\move(540,300,540,250,0,260)\\fad(140,220)}}{hook}')

    for cue in packaging.cues:
        start, end = cue.start, cue.end
        if end <= source_scene.start or start >= source_scene.end:
            continue
        if interview:
            caption_style = 'CaptionBox' if style == 'boxed' else 'Caption'
            size = 58 if style == 'boxed' else 62
            # Burned captions sit at the bottom of the picture: put ours under the window instead.
            anchor, y = ('\\an8', WIN_Y + WIN_H + 30) if packaging.burned_captions else ('\\an2', WIN_Y + WIN_H - 22)
            for s, e, text, original in timed_screens(cue.text, start, end, _limit(size), cue.original, _limit(36)):
                body = _esc_lines(text)
                if style == 'spotlight':
                    body = _emphasize(body, tag_texts, accent)
                    motion = f'\\move(540,{y + 24},540,{y},0,180)\\fad(120,60)'
                else:
                    motion = f'\\pos(540,{y})\\fad(60,60)' if style == 'classic' else f'\\pos(540,{y})\\fad(90,90)'
                add_caption(2, s, e, caption_style, f'{{{anchor}{motion}}}{body}')
                if original:
                    add_caption(1, s, e, 'Original', f'{{\\an8\\pos(540,{WIN_Y + WIN_H + 34})\\fad(60,60)}}{_esc_lines(original)}')
            continue
        highlights = {h.text.lower() for h in packaging.highlights if cue.start <= h.at < cue.end}
        if style == 'boxed' or packaging.audience_language == 'zh':
            caption_style, size = {'boxed': ('CaptionBox', 58), 'cinematic': ('Cine', 64)}.get(style, ('Words', 82))
            for s, e, text, _ in timed_screens(cue.text, start, end, _limit(size) / 0.95):
                body = _esc_lines(text)
                if packaging.audience_language == 'zh':
                    body = _emphasize(body, list(highlights), accent)
                for word in highlights:
                    body = re.sub(rf'(?i)\b({re.escape(_esc(word))})\b', lambda m: f'{{\\c{accent}}}{m.group(1)}{{\\c{WHITE}}}', body, count=1)
                add_caption(2, s, e, caption_style, f'{{\\an2\\pos(540,1420)\\fad(90,90)}}{body}')
            continue
        words = _words(cue.text, start, end, None)
        if style == 'cinematic':
            # One calm line of 2–5 words at a time; single-word flashes read as jittery.
            phrases = _chunks(words, max_words=5, max_chars=26)
            for n, phrase in enumerate(phrases):
                p0 = phrase[0][0]
                p1 = phrases[n + 1][0][0] if n + 1 < len(phrases) else phrase[-1][1] + .1
                text = _esc(' '.join(token for _, _, token in phrase))
                size = min(64, int(920 / max(width(text), 1)))
                add_caption(1, p0, max(p1, p0 + .4), 'CineGlow', f'{{\\an2\\fs{size}\\pos(540,1320)\\blur8\\alpha&H70&\\fad(160,120)}}{text}')
                add_caption(2, p0, max(p1, p0 + .4), 'Cine', f'{{\\an2\\fs{size}\\pos(540,1320)\\fad(160,120)}}{text}')
            continue
        for chunk in _chunks(words):
            chunk_end = chunk[-1][1] + .05
            size = min(82, int(920 / max(width(' '.join(word[2] for word in chunk)), 1)))
            for j, (w0, _, _) in enumerate(chunk):
                parts = []
                for k, (_, _, token) in enumerate(chunk):
                    active = k == j or token.strip('.,?!;:').lower() in highlights
                    parts.append(f'{{\\c{accent}}}{_esc(token)}{{\\c{WHITE}}}' if active else _esc(token))
                stop = chunk[j + 1][0] if j + 1 < len(chunk) else chunk_end
                pop = '{\\fscx86\\fscy86\\t(0,110,\\fscx100\\fscy100)}' if j == 0 else ''
                add_caption(2, w0, stop, 'Words', f'{{\\an2\\fs{size}\\pos(540,1400)}}{pop}' + ' '.join(parts))

    plate_y = WIN_Y + WIN_H - 250 if interview else 1180
    for speaker in packaging.speakers:
        at = to_output(speaker.at, rows)
        if at is not None:
            _nameplate(out, at, speaker.name, speaker.role, plate_y)

    if interview and packaging.tags_enabled and style != 'spotlight':
        for tag in packaging.tags:
            at = to_output(tag.at, rows)
            if at is None:
                continue
            if style == 'boxed':
                out.add(4, at, at + 1.8, 'TagPill', f'{{\\an5\\pos(540,{WIN_Y + WIN_H - 130})\\fscx80\\fscy80\\t(0,160,\\fscx100\\fscy100)\\fad(120,200)}}{_esc(tag.text)}', carry=False)
                continue
            motion = '\\fscx50\\fscy50\\t(0,140,\\fscx112\\fscy112)\\t(140,260,\\fscx100\\fscy100)\\fad(0,240)'
            out.add(4, at, at + 1.8, 'Tag', f'{{\\an5\\pos(540,{WIN_Y + WIN_H - 120}){motion}}}{_esc(tag.text)}', carry=False)
    return _header(look) + '\n'.join(out.lines) + '\n'


def scene_video_graph(draft: Draft, scene: Scene, index: int, ass_path: Path, w: int, h: int) -> tuple[str, str]:
    """(filter graph, output label) drawing the template layout plus the ASS overlay for one scene.

    `window` = warm near-black canvas with a 4:3 window that follows the speaker (whole frame
    when there is no track) and a thin progress line; other layouts reuse the existing chains.
    """
    from backend.services.publish_export import _escape_filter_path, _layout_filters
    from backend.services.studio.audio import scene_duration
    from backend.services.studio.framing import crop_expression, layout_filter
    rows = timeline(draft.scenes)
    total = rows[-1][2] + scene_duration(draft.scenes[-1])
    offset, length = rows[index][2], scene_duration(scene)
    ass = f"ass='{_escape_filter_path(ass_path)}':fontsdir='{_escape_filter_path(FONT_DIR)}'"
    look = colours(draft.packaging.palette if draft.packaging else None)
    BG, ACCENT_HEX = look['bg'], look['accent_hex']  # noqa: N806
    if draft.layout == 'window':
        if scene.crop_track or scene.crop_x is not None:
            x = crop_expression(scene, draft.crop_x)
            window = (f"[0:v]crop=w='min(iw,ih*4/3)':h='min(ih,iw*3/4)':x='(iw-ow)*({x})':y='(ih-oh)/2',"
                      f"scale={W}:{WIN_H},setsar=1[win]")
        else:
            window = (f"[0:v]scale={W}:{WIN_H}:force_original_aspect_ratio=decrease,"
                      f"pad={W}:{WIN_H}:(ow-iw)/2:(oh-ih)/2:color={BG},setsar=1[win]")
        graph = (f"{window};color=c={BG}:s={W}x{H}:r=30:d={length:.3f}[bg];[bg][win]overlay=0:{WIN_Y}:shortest=1[canvas];"
                 f"color=c={ACCENT_HEX}:s={W}x6:r=30:d={length:.3f}[bar];"
                 f"[canvas][bar]overlay=x='-w+w*(t+{offset:.3f})/{total:.3f}':y={WIN_Y + WIN_H}:shortest=1[framed];"
                 f"[framed]{ass}[packaged]")
        return graph, 'packaged'
    if draft.layout == 'crop':
        base = layout_filter(scene, draft.crop_x, w, h)
    else:
        base = ';'.join(_layout_filters(draft.layout if draft.layout in ('blur', 'fit') else 'fit', w, h))
    grade = 'eq=saturation=0.72:brightness=-0.03,vignette=PI/5,' if draft.packaging and draft.packaging.style == 'cinematic' else ''
    return f"{base};[base]{grade}{ass}[packaged]", 'packaged'
