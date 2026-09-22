"""Versioned deterministic title artwork shared by preview and FFmpeg export."""
import io
from functools import lru_cache
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

STYLES = {'comic', 'neon', 'arena', 'editorial', 'pixel', 'frosted'}
ACCENTS = {'comic':'#ffe52d', 'neon':'#ccff00', 'arena':'#dfff00', 'editorial':'#ff4826', 'pixel':'#ed327c', 'frosted':'#00e6dc'}
FONTS = Path(__file__).resolve().parents[2] / 'assets' / 'fonts'


def font_for(text, size, italic=False):
    latin = all(ord(c)<0x250 for c in text)
    name = ('BarlowCondensed-BlackItalic.ttf' if italic else 'BarlowCondensed-Black.ttf') if latin else 'NotoSansSC.ttf'
    font = ImageFont.truetype(str(FONTS / name), size)
    if not latin: font.set_variation_by_axes([900])
    return font


def lines_for(text, font, max_width):
    lines = []
    # Explicit line breaks are intentional; automatic breaks keep Latin words intact.
    for paragraph in text.splitlines():
        line = ''
        for token in re.findall(r"[a-zA-Z0-9'’]+|[^a-zA-Z0-9'’]", paragraph):
            if line and font.getlength(line+token)>max_width:
                lines.append(line.strip());line=''
            for c in token:
                if line and font.getlength(line+c)>max_width:
                    lines.append(line.strip());line=''
                line += c
        if line.strip(): lines.append(line.strip())
    return [line for line in lines if line]


def _artwork_v1(text, style, w, h, scale=1, y=.12, accent=None):
    if w<16 or h<16 or w*h>16777216:
        raise ValueError('文字模板支持最大 1600 万像素画布，请使用 1080p 画幅')
    if style not in STYLES: raise ValueError('未知文字模板')
    if not text.strip(): return Image.new('RGBA',(w,h))
    if all(ord(c)<0x250 for c in text): text=text.upper()
    color=accent or ACCENTS[style]
    size=round(min(w*.16,h*.115)*scale)
    min_size=max(14,round(min(w*.055,h*.055)))
    width=w*.72
    while True:
        font=font_for(text,size,style in ('comic','arena'))
        lines=lines_for(text,font,width)
        if len(lines)<=3: break
        size-=3
        if size<min_size: raise ValueError('开头文字太长，请缩短或减少换行（最多三行）')
    bounds=[font.getbbox(line,stroke_width=0) for line in lines]
    line_h=max(b[3]-b[1] for b in bounds)
    gap=round(size*.13)
    pad=round(w*.075)
    content_w=round(max(font.getlength(line) for line in lines))
    cw=content_w+2*pad; ch=(line_h+gap)*len(lines)+2*pad
    art=Image.new('RGBA',(cw,ch));d=ImageDraw.Draw(art)
    for i,line in enumerate(lines):
        tw=round(font.getlength(line));px=(cw-tw)//2;py=pad+i*(line_h+gap)-bounds[i][1]
        top=pad+i*(line_h+gap)
        if style=='comic':
            stroke=max(2,round(size*.035));depth=round(size*.065)
            for offset in range(depth,0,-2):
                d.text((px+offset,py+offset),line,font=font,fill='#11151e',stroke_width=stroke,stroke_fill='#11151e')
            d.text((px,py),line,font=font,fill=color,stroke_width=stroke,stroke_fill='#11151e')
        elif style=='neon':
            if i==len(lines)-1:
                d.rectangle((px-pad*.45,top-gap*.25,px+tw+pad*.45,top+line_h+gap*.45),fill=color)
            d.text((px,py),line,font=font,fill='#10151d' if i==len(lines)-1 else '#ffffff',stroke_width=0 if i==len(lines)-1 else max(1,round(size*.012)),stroke_fill='#10151d')
        else:
            skew=round(pad*.42);left=px-pad*.50;right=px+tw+pad*.50
            d.polygon([(left+skew,top-gap*.25),(right+skew,top-gap*.25),(right-skew,top+line_h+gap*.45),(left-skew,top+line_h+gap*.45)],fill='#121d30')
            if i==0:
                d.polygon([(left+skew-12,top-gap*.25),(left+skew,top-gap*.25),(left-skew,top+line_h+gap*.45),(left-skew-12,top+line_h+gap*.45)],fill='#25baff')
            d.text((px,py),line,font=font,fill=color if i==len(lines)-1 else '#ffffff')
    angle={'comic':5,'neon':2,'arena':3}[style]
    art=art.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    # Preserve an 8% horizontal safe area including shadows and slanted plates.
    if art.width>w*.9:
        ratio=w*.9/art.width;art=art.resize((round(art.width*ratio),round(art.height*ratio)),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(w,h))
    top=round(h*y)-pad
    top=max(round(h*.04),min(top,h-round(h*.10)-art.height))
    canvas.alpha_composite(art,((w-art.width)//2,top))
    return canvas


def artwork(text, style, w, h, scale=1, y=.12, accent=None, version=1):
    if version == 1 and style in ('comic', 'neon', 'arena'):
        return _artwork_v1(text, style, w, h, scale, y, accent)
    if version == 2 and style in ('comic', 'neon', 'arena', 'editorial'):
        from backend.services.studio.title_art_v2 import artwork as artwork_v2
        return artwork_v2(text, style, w, h, scale, y, accent)
    if version == 3:
        from backend.services.studio.title_art_v3 import artwork as artwork_v3
        return artwork_v3(text, style, w, h, scale, y, accent)
    raise ValueError('不支持的文字模板版本')


def png_bytes(text, style, w, h, **options):
    image=artwork(text,style,w,h,**options)
    stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()


def options_for(draft):
    return {'scale':draft.title_scale,'y':draft.title_y,'accent':draft.title_accent,'version':draft.title_template_version}


def overlay_motion(style, enabled, height):
    if not enabled or style in ('pixel', 'frosted'): return '0','0'
    # A bounded short entrance. Artwork remains visible from the very first frame.
    if style=='arena': return "-36*max(0,1-t/0.18)",'0'
    distance=round(height*.016)
    return '0',f"{distance}*max(0,1-t/0.18)"


@lru_cache(maxsize=16)
def thumbnail(style, version=1):
    image=artwork('CAN YOU\nESCAPE?',style,1080,1920,version=version)
    image=image.crop(image.getbbox())
    image.thumbnail((300,150),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(324,174))
    canvas.alpha_composite(image,((324-image.width)//2,(174-image.height)//2))
    stream=io.BytesIO();canvas.save(stream,format='PNG');return stream.getvalue()
