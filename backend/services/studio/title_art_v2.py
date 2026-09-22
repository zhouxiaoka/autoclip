"""Larger, layered title presets, opt-in v2. V1 artwork remains frozen."""
from PIL import Image, ImageDraw
from backend.services.studio.title_art import ACCENTS, STYLES, font_for, lines_for


def artwork(text, style, w, h, scale=1, y=.12, accent=None):
    if w < 16 or h < 16 or w*h > 16777216:
        raise ValueError('文字模板支持最大 1600 万像素画布，请使用 1080p 画幅')
    if style not in STYLES:
        raise ValueError('未知文字模板')
    canvas = Image.new('RGBA', (w, h))
    if not text.strip():
        return canvas
    latin = all(ord(c) < 0x250 for c in text)
    if latin:
        text = text.upper()
    color = accent or ACCENTS[style]
    italic = style in ('comic', 'arena')
    # Wrap before emphasis sizing: manual line breaks remain author decisions.
    size = max(14, round(min(w*.205, h*.14)*scale))
    minimum = max(10, round(min(w, h)*.045))
    while True:
        lines = lines_for(text, font_for(text, size, italic), w*.80*min(scale, 1))
        if len(lines) <= 3:
            break
        size -= 3
        if size < minimum:
            raise ValueError('开头文字太长，请缩短或减少换行（最多三行）')
    sizes = []
    for i, line in enumerate(lines):
        # Two-line headlines fill a broad block; the payoff gets the larger face.
        target = w*(.78 if i < len(lines)-1 else .82)*scale
        reference = font_for(line, size, italic)
        fit = round(size*target/max(1, reference.getlength(line)))
        sizes.append(max(minimum, min(fit, round(size*1.35))))
    fonts = [font_for(line, n, italic) for line, n in zip(lines, sizes)]
    boxes = [font.getbbox(line) for line, font in zip(lines, fonts)]
    heights = [b[3]-b[1] for b in boxes]
    widths = [round(font.getlength(line)) for line, font in zip(lines, fonts)]
    pad = max(4, round(w*.065))
    gap = max(3, round(w*(.012 if style == 'editorial' else .021)))
    cw = max(widths)+pad*2
    ch = sum(heights)+gap*(len(lines)-1)+pad*2
    art = Image.new('RGBA', (cw, ch))
    d = ImageDraw.Draw(art)
    top = pad
    for i, (line, font, box, tw, th, n) in enumerate(zip(lines, fonts, boxes, widths, heights, sizes)):
        px = pad if style == 'editorial' else (cw-tw)//2
        py = top-box[1]
        if style == 'comic':
            stroke = max(2, round(n*.040))
            depth = max(3, round(n*.075))
            for offset in range(depth, 0, -1):
                d.text((px+offset, py+offset), line, font=font, fill='#090e14', stroke_width=stroke, stroke_fill='#090e14')
            d.text((px, py), line, font=font, fill=color, stroke_width=stroke, stroke_fill='#090e14')
        elif style == 'neon':
            if i == len(lines)-1:
                margin = pad*.38
                d.rectangle((px-margin, top-gap*.40, px+tw+margin, top+th+gap*.50), fill=color)
                d.text((px, py), line, font=font, fill='#08120f')
                # Short marker stroke, separate from the slab.
                ly = top+th+gap*.86
                d.polygon([(cw*.29, ly+gap*.2),(cw*.70, ly),(cw*.70, ly+gap*.35),(cw*.29, ly+gap*.5)], fill=color)
            else:
                d.text((px+2, py+4), line, font=font, fill='#101c21', stroke_width=max(1, round(n*.014)), stroke_fill='#101c21')
                d.text((px, py), line, font=font, fill='#ffffff')
        elif style == 'arena':
            skew = pad*.40
            left, right = px-pad*.32, px+tw+pad*.32
            yt, yb = top-gap*.35, top+th+gap*.48
            if i == 0:
                d.polygon([(left+skew-pad*.29,yt),(right+skew,yt),(right-skew,yb),(left-skew-pad*.29,yb)], fill='#1db8ff')
            d.polygon([(left+skew,yt),(right+skew,yt),(right-skew,yb),(left-skew,yb)], fill='#0b1322')
            d.text((px, py), line, font=font, fill=color if i == len(lines)-1 else '#ffffff')
        else:
            if i == len(lines)-1:
                # Baseline slab behind the letters, never a whole-box card.
                d.rectangle((px-4,top+th*.83,px+tw+4,top+th+gap*.75), fill=color)
            d.text((px+3,py+5), line, font=font, fill='#090d12', stroke_width=max(1,round(n*.018)), stroke_fill='#090d12')
            d.text((px,py), line, font=font, fill='#fff9e9', stroke_width=max(1,round(n*.008)), stroke_fill='#090d12')
        top += th+gap
    if style == 'comic':
        # Small ink-edged impact marks, outside the letterforms.
        unit = max(3, round(w*.015))
        for x, yy, direction in [(pad*.40,pad+heights[0]*.9,-1),(cw-pad*.40,ch-pad*.6,1)]:
            d.polygon([(x,yy),(x+direction*unit*1.5,yy-unit*1.6),(x+direction*unit*2,yy-unit*.4)],fill=color,outline='#090e14',width=max(1,unit//4))
    angle = {'comic':6,'neon':3,'arena':5,'editorial':0}[style]
    if angle:
        art = art.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    art = art.crop(art.getbbox())
    ratio = min(1, w*.90/art.width, h*.26/art.height)
    if ratio < 1:
        art = art.resize((max(1,round(art.width*ratio)), max(1,round(art.height*ratio))), Image.Resampling.LANCZOS)
    left = round(w*.07) if style == 'editorial' else (w-art.width)//2
    upper = max(round(h*.04), min(round(h*(y-.05)), h-round(h*.10)-art.height))
    canvas.alpha_composite(art, (left, upper))
    return canvas
