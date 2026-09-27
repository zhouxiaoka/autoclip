"""Portable FFmpeg title templates; no browser/Studio runtime required."""
import re
import unicodedata
from pathlib import Path
from backend.services.publish_export import _escape_filter_path


def text_width(text):
    def width(c):
        if unicodedata.east_asian_width(c) in ('W', 'F'): return 1
        if c.isspace(): return .35
        if c in 'MW@%': return 1
        return .75 if c.isupper() else .62
    return sum(width(c) for c in text)


def wrap_title(text, capacity):
    # Preserve Latin word boundaries; CJK and overlong words can wrap per character.
    tokens = re.findall(r"[a-zA-Z0-9'’]+|[^a-zA-Z0-9'’]", text)
    lines, line = [], ''
    for token in tokens:
        if line and text_width(line + token) > capacity:
            lines.append(line.strip()); line = ''
        for c in token:
            if line and text_width(line + c) > capacity:
                lines.append(line.strip()); line = ''
            line += c
    if line.strip(): lines.append(line.strip())
    return [line for line in lines if line]


def title_layout(text, style, w, h):
    text = ' '.join(text.split())
    if style == 'impact' and text.isascii(): text = text.upper()
    size = round(min(w * (.085 if style == 'impact' else .07), h * .105))
    minimum = max(12, round(min(w * .04, h * .06)))
    width = w * (.80 if style == 'impact' else .72)
    while True:
        lines = wrap_title(text, width / size)
        if len(lines) <= 3: break
        size -= 2
        if size < minimum:
            raise ValueError('开头文字太长，请缩短后再导出（标题最多三行）')
    return lines, size


def title_font(text, fallback):
    if text.isascii():
        paths = ['/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                 'C:/Windows/Fonts/arialbd.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
    else:
        paths = ['C:/Windows/Fonts/msyhbd.ttc',
                 '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
                 '/System/Library/Fonts/STHeiti Medium.ttc']
    return next((Path(p) for p in paths if Path(p).is_file()), fallback)


def template_filters(hook, style, w, h, folder, fallback, last, duration):
    lines, size = title_layout(hook, style, w, h)
    font = title_font(hook, fallback)
    end = min(4, duration)
    enable = f"between(t,0,{end})"
    parts = []
    y = round(h * .12)
    gap = round(size * 1.17)
    if style == 'card':
        pad = round(w * .04)
        height = gap * len(lines) + pad * 2
        parts.append(f"[{last}]drawbox=x=iw*0.08:y={y}:w=iw*0.84:h={height}:color=0x142231@0.9:t=fill:enable='{enable}',drawbox=x=iw*0.08:y={y}:w={max(2,round(w*.008))}:h={height}:color=0x56ecbb:t=fill:enable='{enable}'[titlecard]")
        last = 'titlecard'; y += pad
    for index, line in enumerate(lines):
        path = folder / f'title-line-{index}.txt'
        path.write_text(line, encoding='utf-8')
        output = f'title{index}'
        x = '(w-text_w)/2' if style == 'impact' else 'w*0.12'
        color = '0xffec47' if style == 'impact' else 'white'
        stroke = max(1, round(size * .055)) if style == 'impact' else 0
        shadow = max(1, round(size * .045)) if style == 'impact' else 0
        parts.append(f"[{last}]drawtext=fontfile='{_escape_filter_path(font)}':textfile='{_escape_filter_path(path)}':expansion=none:fontsize={size}:fontcolor={color}:x={x}:y={y+index*gap}:borderw={stroke}:bordercolor=0x10141c:shadowy={shadow}:shadowcolor=0x10141c:enable='{enable}'[{output}]")
        last = output
    return parts, last
