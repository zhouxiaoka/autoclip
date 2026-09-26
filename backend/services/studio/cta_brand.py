"""Brand endcard with bounded inline assets, shared by preview and export.

Assets are supplied by the user, never fetched by the renderer. Inline storage
keeps saved revisions self-contained; no arbitrary filesystem or network URLs.
"""
import base64
import io
import re
from PIL import Image, ImageDraw, ImageFilter, ImageOps


def decode_asset(value):
    if len(value)>700000 or not re.match(r'^data:image/(png|jpeg|webp);base64,',value):
        raise ValueError('品牌图片需为 PNG、JPEG 或 WebP，且不超过 512 KB')
    try:
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
        if len(raw)>512*1024: raise ValueError('asset too large')
        image=Image.open(io.BytesIO(raw))
        if image.format not in ('PNG','JPEG','WEBP') or image.width*image.height>4_000_000 or getattr(image,'n_frames',1)!=1:
            raise ValueError('unsupported image')
        image.load()
        return image.convert('RGBA')
    except Exception as exc:
        raise ValueError('品牌图片无效，请使用不超过 400 万像素的静态图片') from exc


def place_asset(canvas, value, box, rounded=False):
    x,y,w,h=map(round,box)
    image=ImageOps.contain(decode_asset(value),(max(1,w),max(1,h)))
    if rounded:
        mask=Image.new('L',image.size)
        ImageDraw.Draw(mask).rounded_rectangle((0,0,image.width-1,image.height-1),radius=min(image.size)*.2,fill=255)
        from PIL import ImageChops
        image.putalpha(ImageChops.multiply(image.getchannel('A'),mask))
    canvas.alpha_composite(image,(x+(w-image.width)//2,y+(h-image.height)//2))


def brand_letters(canvas,text,box,accent):
    """Designed game-name lettering, never represented as an official logo."""
    from backend.services.studio.cta_materials import fit_text
    x,y,w,h=box
    font,lines,size=fit_text(text,w*.88,h*.72,round(h*.47))
    draw=ImageDraw.Draw(canvas)
    top=y+(h-len(lines)*size*1.18)/2
    stroke=max(1,round(size*.07))
    for line in lines:
        left=x+(w-font.getlength(line))/2
        draw.text((left,top+size*.09),line,font=font,anchor='lt',fill='#072638',stroke_width=stroke*2,stroke_fill='#072638')
        draw.text((left,top),line,font=font,anchor='lt',fill=accent,stroke_width=stroke,stroke_fill='#fff3c4')
        top+=size*1.18


def poster(spec,w,h,source):
    from backend.services.studio.cta_materials import fit_text,styled_button
    portrait=h>w
    canvas=Image.new('RGBA',(w,h),'#103441') if source is None else ImageOps.fit(source,(w,h)).convert('RGBA').filter(ImageFilter.GaussianBlur(max(3,w*.014)))
    # A quieter brand header and footer while preserving the gameplay palette.
    shade=Image.new('RGBA',(w,h));d=ImageDraw.Draw(shade)
    for y in range(h):
        alpha=round(95+85*abs(y/h-.48))
        d.line((0,y,w,y),fill=(5,18,37,alpha))
    canvas.alpha_composite(shade)
    accent=spec.get('accent') or '#ffce36'
    if portrait:
        brand_box=(w*.08,h*.045,w*.84,h*.18)
        hero_box=(w*.12,h*.25,w*.76,h*.43)
        icon_box=(w*.09,h*.695,w*.14,w*.14)
        slogan_box=(w*(.27 if spec.get('icon') else .09),h*.69,w*(.64 if spec.get('icon') else .82),h*.09)
        button_box=(w*.19,h*.805,w*.62,w*.62*.29)
    else:
        brand_box=(w*.53,h*.08,w*.42,h*.25)
        hero_box=(w*.045,h*.08,w*.44,h*.82)
        icon_box=(w*.54,h*.40,h*.17,h*.17)
        slogan_box=(w*(.66 if spec.get('icon') else .54),h*.39,w*(.28 if spec.get('icon') else .40),h*.18)
        button_box=(w*.57,h*.68,w*.34,w*.34*.29)
    # Hero is an actual source frame, not a synthetic character or fake app icon.
    if source is not None:
        x,y,hw,hh=map(round,hero_box)
        radius=round(min(hw,hh)*.04)
        d=ImageDraw.Draw(canvas)
        d.rounded_rectangle((x-4,y-4,x+hw+4,y+hh+8),radius+4,fill='#062735',outline=accent,width=max(2,round(w*.003)))
        hero=ImageOps.fit(source,(hw,hh)).convert('RGBA')
        mask=Image.new('L',(hw,hh));ImageDraw.Draw(mask).rounded_rectangle((0,0,hw-1,hh-1),radius,fill=255)
        hero.putalpha(mask);canvas.alpha_composite(hero,(x,y))
    if spec.get('logo'):
        place_asset(canvas,spec['logo'],brand_box)
    elif spec.get('brand'):
        brand_letters(canvas,spec['brand'],brand_box,accent)
    if spec.get('icon'):
        place_asset(canvas,spec['icon'],icon_box,rounded=True)
    if spec.get('slogan'):
        x,y,sw,sh=slogan_box
        font,lines,size=fit_text(spec['slogan'],sw,sh,round(min(w,h)*.043))
        d=ImageDraw.Draw(canvas)
        for line in lines:
            d.text((x,y),line,font=font,anchor='lt',fill='#ffffff',stroke_width=max(1,round(size*.035)),stroke_fill='#173044')
            y+=size*1.18
    x,y,bw,bh=map(round,button_box)
    canvas.alpha_composite(styled_button(spec['text'],bw,bh,spec.get('style','glossy'),spec.get('accent')),(x,y))
    return canvas
