"""Render template packaging (ASS) and the interview window layout for one scene.

Each scene is encoded on its own (render.py), so every overlay is expressed on the output
timeline and clipped to the scene: the scene's ASS only carries events visible inside it,
with times relative to the scene start. Colours follow DESIGN.md (dark theme).
"""
from __future__ import annotations

from pathlib import Path

from backend.services.studio.models import Draft, Packaging, Scene

FONT_DIR = Path(__file__).resolve().parents[2] / 'assets' / 'fonts'
FONT = 'Noto Sans SC'  # bundled (OFL); covers CJK and Latin on every platform
W, H = 1080, 1920
WIN_Y, WIN_H = 560, 810
BG, ACCENT_HEX = '0x1A1A19', '0x5A8BFF'
ACCENT, WHITE, SUB, INK, INK_SOFT = '&H00FF8B5A', '&H00E6EAEC', '&H009BA2A6', '&H00191A1A', '&H26191A1A'
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


def _header() -> str:
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
    """ASS document for scene `index`; times are relative to that scene's start."""
    rows = timeline(scenes)
    total = rows[-1][2] + (rows[-1][1] - rows[-1][0])
    offset = rows[index][2]
    length = rows[index][1] - rows[index][0]
    out = _Scene(offset, length)
    interview = packaging.template == 'interview_zh'

    lines = packaging.title_lines
    if interview and lines:
        pop = '\\fscx88\\fscy88\\t(0,200,\\fscx100\\fscy100)\\fad(180,0)' if index == 0 else ''
        for i, line in enumerate(lines):
            style = 'TitleAccent' if i == packaging.title_accent_line and len(lines) > 1 else 'Title'
            out.add(3, 0, total, style, f'{{\\an8\\pos(540,{150 + i * 150}){pop}}}{_esc(line)}')
    elif lines:
        hook = ' '.join(lines)
        out.add(3, 0, 2.8, 'Hook', f'{{\\an8\\pos(540,250)\\move(540,300,540,250,0,260)\\fad(140,220)}}{_esc(hook)}')

    for cue in packaging.cues:
        start, end = to_output(cue.start, rows), to_output(max(cue.start, cue.end - 1e-3), rows)
        if start is None or end is None:
            continue
        end = max(end, start + .3)
        if interview:
            out.add(2, start, end, 'Caption', f'{{\\an2\\pos(540,{WIN_Y + WIN_H - 22})\\fad(60,60)}}{_esc(cue.text)}')
            if cue.original:
                out.add(1, start, end, 'Original', f'{{\\an8\\pos(540,{WIN_Y + WIN_H + 34})\\fad(60,60)}}{_esc(cue.original)}')
            continue
        highlights = {h.text.lower() for h in packaging.highlights if cue.start <= h.at < cue.end}
        for chunk in _chunks(_words(cue.text, start, end, None)):
            chunk_end = chunk[-1][1] + .05
            for j, (w0, _, _) in enumerate(chunk):
                parts = []
                for k, (_, _, token) in enumerate(chunk):
                    active = k == j or token.strip('.,?!;:').lower() in highlights
                    parts.append(f'{{\\c{ACCENT}}}{_esc(token)}{{\\c{WHITE}}}' if active else _esc(token))
                stop = chunk[j + 1][0] if j + 1 < len(chunk) else chunk_end
                pop = '{\\fscx86\\fscy86\\t(0,110,\\fscx100\\fscy100)}' if j == 0 else ''
                out.add(2, w0, stop, 'Words', f'{{\\an2\\pos(540,1400)}}{pop}' + ' '.join(parts))

    plate_y = WIN_Y + WIN_H - 250 if interview else 1180
    for speaker in packaging.speakers:
        at = to_output(speaker.at, rows)
        if at is not None:
            _nameplate(out, at, speaker.name, speaker.role, plate_y)

    if interview and packaging.tags_enabled:
        for tag in packaging.tags:
            at = to_output(tag.at, rows)
            if at is None:
                continue
            motion = '\\fscx50\\fscy50\\t(0,140,\\fscx112\\fscy112)\\t(140,260,\\fscx100\\fscy100)\\fad(0,240)'
            out.add(4, at, at + 1.8, 'Tag', f'{{\\an5\\pos(540,{WIN_Y + WIN_H - 120}){motion}}}{_esc(tag.text)}', carry=False)
    return _header() + '\n'.join(out.lines) + '\n'


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
    return f"{base};[base]{ass}[packaged]", 'packaged'
