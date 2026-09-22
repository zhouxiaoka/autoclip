"""Comic v4: condensed glyphs, sheared faces and hard ink extrusion.

Frozen separately from earlier presets so saved drafts remain reproducible.
"""
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageColor
from .title_art import FONTS, font_for, lines_for


def _face(line, size, width):
    font = (ImageFont.truetype(str(FONTS / 'Anton-Regular.ttf'), size)
            if all(ord(c) < 0x250 for c in line) else font_for(line, size))
    box = font.getbbox(line)
    mask = Image.new('L', (box[2]-box[0]+4, box[3]-box[1]+4))
    ImageDraw.Draw(mask).text((2-box[0], 2-box[1]), line, font=font, fill=255)
    # Shear the face itself; rotating an upright font does not create italic glyphs.
    shear = .27
    extra = round(mask.height * shear)
    mask = mask.transform((mask.width+extra, mask.height), Image.Transform.AFFINE,
                          (1, shear, -extra, 0, 1, 0), Image.Resampling.BICUBIC)
    mask = mask.filter(ImageFilter.MaxFilter(5))
    mask = mask.crop(mask.getbbox())
    factor = min(width / mask.width, 1.35)
    return mask.resize((round(mask.width*factor), round(mask.height*factor*.78)), Image.Resampling.LANCZOS)


def artwork(text, w, h, scale=1, y=.12, accent=None):
    if w < 16 or h < 16 or w*h > 16777216:
        raise ValueError('文字模板支持最大 1600 万像素画布，请使用 1080p 画幅')
    canvas = Image.new('RGBA', (w, h))
    if not text.strip():
        return canvas
    if all(ord(c) < 0x250 for c in text):
        text = text.upper()
    size = max(14, round(min(w*.20, h*.14)*scale))
    while True:
        font = (ImageFont.truetype(str(FONTS/'Anton-Regular.ttf'), size)
                if all(ord(c)<0x250 for c in text) else font_for(text, size))
        lines = lines_for(text, font, w*.77)
        if len(lines) <= 3:
            break
        size -= 3
        if size < max(12, w*.045):
            raise ValueError('开头文字太长，请缩短或减少换行（最多三行）')
    faces = [_face(line, size, w*(.76 if i<len(lines)-1 else .82)*scale)
             for i, line in enumerate(lines)]
    stroke = max(1, round(w*.009))
    depth = max(2, round(w*.018))
    gap = max(4, round(w*.019))
    pad = max(12, round(w*.08))
    cw = max(m.width for m in faces)+2*pad
    ch = sum(m.height for m in faces)+(len(faces)-1)*gap+2*pad
    art = Image.new('RGBA', (cw, ch))
    top = pad
    rgb = ImageColor.getrgb(accent or '#ffe52d')
    for face in faces:
        mask = Image.new('L', (cw, ch))
        left = (cw-face.width)//2
        mask.paste(face, (left, top))
        ink = mask.filter(ImageFilter.MaxFilter(stroke*2+1))
        extrusion = Image.new('L', ink.size)
        for offset in range(depth+1):
            shifted = Image.new('L', ink.size)
            shifted.paste(ink, (round(offset*.60), offset))
            extrusion = ImageChops.lighter(extrusion, shifted)
        art.paste('#080c10', (0, 0, cw, ch), extrusion)
        # Broad soft light, no metallic midpoint stripe. Highlight stays inside glyphs.
        fill = Image.new('RGBA', (cw, ch))
        draw = ImageDraw.Draw(fill)
        for row in range(face.height):
            t = row/max(1, face.height-1)
            mix = .62*(1-t)**2
            color = tuple(round(v+(255-v)*mix) for v in rgb)
            draw.line((0, top+row, cw, top+row), fill=(*color,255))
        art.paste(fill, (0,0), mask)
        down = Image.new('L', mask.size)
        down.paste(mask, (0,max(1,round(w*.0015))))
        edge = ImageChops.subtract(mask, down).point(lambda v: round(v*.55))
        art.paste('#fffac8', (0,0,cw,ch), edge)
        top += face.height+gap
    # Small ink-edged impact rays flank the lower line, as in the reference.
    d = ImageDraw.Draw(art)
    ray = max(3, round(w*.055))
    cy = pad + faces[0].height + gap*.4
    right_y = ch-pad-faces[-1].height*.10
    for points in [
        [(pad*.78,cy),(pad*.08,cy-ray*.40),(pad*.16,cy+ray*.10)],
        [(pad*.85,cy-ray*.20),(pad*.47,cy-ray*.85),(pad*.76,cy-ray*.62)],
        [(cw-pad*.84,right_y),(cw-pad*.08,right_y+ray*.28),(cw-pad*.35,right_y+ray*.52)],
        [(cw-pad*.92,right_y+ray*.18),(cw-pad*.65,right_y+ray*.94),(cw-pad*.25,right_y+ray*.72)],
    ]:
        d.polygon(points, fill=accent or '#ffe52d', outline='#080c10', width=max(1,stroke//2))
    art = art.rotate(7, Image.Resampling.BICUBIC, expand=True)
    box = art.getbbox()
    if box:
        art = art.crop(box)
    factor = min(1, w*.90/art.width, h*.29/art.height)
    if factor < 1:
        art = art.resize((round(art.width*factor),round(art.height*factor)),Image.Resampling.LANCZOS)
    top = max(round(h*.04), min(round(h*(y-.06)),h-round(h*.10)-art.height))
    canvas.alpha_composite(art, ((w-art.width)//2,top))
    return canvas
