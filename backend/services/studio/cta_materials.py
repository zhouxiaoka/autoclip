"""Casual-game CTA treatment derived from the reviewed Royal Match reference.

No third-party logo, character, store chrome or game artwork is bundled.
"""
import io
import colorsys
import subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageColor
from backend.services.studio.title_art import font_for, lines_for
from backend.utils.ffmpeg_utils import get_ffmpeg_path


def frame(video, draft):
    scene=draft.scenes[-1]
    at=max(scene.start,scene.end-min(.2,(scene.end-scene.start)/2))
    result=subprocess.run([get_ffmpeg_path(),'-v','error','-ss',str(at),'-i',str(video),
        '-frames:v','1','-vf','scale=720:720:force_original_aspect_ratio=decrease',
        '-f','image2pipe','-vcodec','png','-'],check=True,capture_output=True,timeout=30)
    return Image.open(io.BytesIO(result.stdout)).convert('RGB')


def rounded_gradient(size, radius, stops):
    w,h=size
    image=Image.new('RGBA',size)
    d=ImageDraw.Draw(image)
    for y in range(h):
        t=y/max(1,h-1)
        for (p0,c0),(p1,c1) in zip(stops,stops[1:]):
            if p0<=t<=p1:
                f=(t-p0)/(p1-p0)
                color=tuple(round(a+(b-a)*f) for a,b in zip(c0,c1))
                d.line((0,y,w,y),fill=(*color,255));break
    mask=Image.new('L',size);ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),radius=radius,fill=255)
    image.putalpha(mask)
    return image


def fit_text(text,max_width,max_height,start):
    size=start
    while size>=max(6,start*.40):
        font=font_for(text,size)
        lines=lines_for(text,font,max_width)
        if len(lines)<=2 and len(lines)*size*1.18<=max_height:
            return font,lines,size
        size-=2
    raise ValueError('CTA 文字太长，请缩短文案')


def button(text,w,h):
    # Dark navy outer casing, thick green bevel, lime face, specular top edge.
    art=Image.new('RGBA',(w,h));d=ImageDraw.Draw(art)
    r=round(h*.21);pad=max(2,round(h*.025))
    d.rounded_rectangle((0,h*.045,w-1,h-1),radius=r,fill='#071b26')
    d.rounded_rectangle((pad,pad,w-pad-1,h-pad-1),radius=r,fill='#438dce')
    inner=rounded_gradient((w-4*pad,h-4*pad),r,[(0,(213,249,104)),(.12,(123,185,31)),(.58,(58,122,12)),(1,(24,57,4))])
    art.alpha_composite(inner,(pad*2,pad*2))
    face_pad=round(h*.09)
    face=rounded_gradient((w-face_pad*2,h-round(h*.24)),round(r*.68),[(0,(188,237,49)),(.42,(131,198,14)),(.47,(104,166,8)),(1,(83,136,6))])
    art.alpha_composite(face,(face_pad,round(h*.07)))
    sheen=Image.new('RGBA',(w,h))
    d=ImageDraw.Draw(sheen)
    d.rounded_rectangle((face_pad+pad,h*.075,w-face_pad-pad,h*.11),radius=pad,fill=(238,255,169,205))
    d.ellipse((w*.84,h*.1,w*.94,h*.17),fill=(249,255,211,130))
    art.alpha_composite(sheen)
    d=ImageDraw.Draw(art)
    font,lines,size=fit_text(text,w*.84,h*.66,round(h*.46))
    y=(h-len(lines)*size*1.18)/2-h*.025
    stroke=max(1,round(size*.055))
    for line in lines:
        x=(w-font.getlength(line))/2
        d.text((x,y+h*.025),line,font=font,anchor='lt',fill='#294807',stroke_width=stroke+1,stroke_fill='#294807')
        d.text((x,y),line,font=font,anchor='lt',fill='#fffddd',stroke_width=stroke,stroke_fill='#355506')
        y+=size*1.18
    return art



def styled_button(text, w, h, style='glossy', accent=None):
    if style == 'glossy':
        art = button(text, w, h)
        if accent:
            # Tint the face/bevel, preserving the blue casing and cream lettering.
            target_h, target_s, target_v = colorsys.rgb_to_hsv(*(v / 255 for v in ImageColor.getrgb(accent)))
            pixels = art.load()
            for y in range(h):
                for x in range(w):
                    red, green, blue, alpha = pixels[x, y]
                    hue, sat, val = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
                    if .16 < hue < .34 and sat > .35:
                        rgb = colorsys.hsv_to_rgb(target_h, sat * target_s, val * (.3 + .7 * target_v))
                        pixels[x, y] = (*[round(v * 255) for v in rgb], alpha)
        return art
    rgb = ImageColor.getrgb(accent or {'soft':'#68cf43','tactical':'#f1df50','type':'#ffffff'}[style])
    # Keep dark custom colors legible on the tactical plate / shadowed footage.
    if style in ('tactical', 'type') and max(rgb) < 140:
        rgb = tuple(round(v + (255-v)*.65) for v in rgb)
    art = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(art)
    pad = max(2, round(h * .04))
    if style == 'soft':
        radius = round(h * .23)
        dark = tuple(round(v * .48) for v in rgb)
        light = tuple(round(v + (255-v) * .36) for v in rgb)
        d.rounded_rectangle((pad, h*.10, w-pad-1, h-1), radius, fill=(*dark,255))
        face = rounded_gradient((w-pad*2, round(h*.86)),radius,[(0,light),(1,rgb)])
        art.alpha_composite(face,(pad,0))
        d = ImageDraw.Draw(art)
        d.rounded_rectangle((pad*2,pad,w-pad*2,h*.83),radius,outline=(*light,255),width=pad)
        fill = '#ffffff' if sum(rgb)/3 < 145 else '#14231b'
        stroke_fill = '#234c23' if fill == '#ffffff' else fill
    elif style == 'tactical':
        cut = round(h*.19)
        poly = [(cut,0),(w-cut-1,0),(w-1,cut),(w-1,h-cut-1),(w-cut-1,h-1),(cut,h-1),(0,h-cut-1),(0,cut)]
        d.polygon(poly,fill='#111713')
        d.line(poly+[poly[0]],fill=(*rgb,255),width=pad)
        d.rectangle((pad*3,h*.28,pad*4,h*.70),fill=(*rgb,255))
        d.rectangle((w-pad*4,h*.28,w-pad*3,h*.70),fill=(*rgb,255))
        fill, stroke_fill = rgb, '#111713'
    else:
        fill, stroke_fill = rgb, '#111713'
    font, lines, size = fit_text(text,w*.80,h*.67,round(h*(.48 if style=='type' else .43)))
    y=(h-len(lines)*size*1.18)/2-h*.025
    for line in lines:
        x=(w-font.getlength(line))/2
        d.text((x,y+max(2,h*.025)),line,font=font,anchor='lt',fill=stroke_fill,stroke_width=max(1,round(size*.045)),stroke_fill=stroke_fill)
        d.text((x,y),line,font=font,anchor='lt',fill=fill,stroke_width=max(1,round(size*.025)),stroke_fill=stroke_fill)
        y+=size*1.18
    return art

def artwork(spec,w,h,source=None):
    kind=spec['template']
    style=spec.get('style','glossy')
    accent=spec.get('accent')
    edge=accent or {'glossy':'#f6df77','soft':'#b7edbc','tactical':'#f1df50','type':'#ffffff'}[style]
    canvas=Image.new('RGBA',(w,h))
    if kind=='off':return canvas
    portrait=h>w
    if kind=='brand' and source is not None:
        canvas=ImageOps.fit(source,(w,h)).filter(ImageFilter.GaussianBlur(max(4,w*.02))).convert('RGBA')
        shade=Image.new('RGBA',(w,h),(4,12,21,150));canvas.alpha_composite(shade)
        # One real scene stays one scene: never repeat frames to imitate the six-grid reference.
        box=(round(w*.19),round(h*.13),round(w*.81),round(h*.66)) if portrait else (round(w*.09),round(h*.13),round(w*.55),round(h*.88))
        x0,y0,x1,y1=box;cw,ch=x1-x0,y1-y0
        d=ImageDraw.Draw(canvas)
        radius=round(min(cw,ch)*(.008 if style=='tactical' else .055))
        d.rounded_rectangle((x0-6,y0-6,x1+6,y1+10),radius=radius+6,fill='#12334a',outline=edge,width=max(2,round(w*.004)))
        tile=ImageOps.fit(source,(cw,ch)).convert('RGBA')
        mask=Image.new('L',(cw,ch));ImageDraw.Draw(mask).rounded_rectangle((0,0,cw-1,ch-1),radius=radius,fill=255)
        tile.putalpha(mask);canvas.alpha_composite(tile,(x0,y0))
    else:
        # Local contrast at the footer, not an opaque information card over the game.
        fade=Image.new('RGBA',(w,h));fd=ImageDraw.Draw(fade)
        for y in range(round(h*.58),h):
            alpha=round(150*max(0,(y/h-.58)/.42)**1.5)
            fd.line((0,y,w,y),fill=(6,16,20,alpha))
        canvas.alpha_composite(fade)
    bw=round(w*(.67 if portrait else .38))
    bh=round(bw*.29)
    x=(w-bw)//2 if portrait or kind!='brand' else round(w*.59)
    # The original model position is the top of the control; preserve overrides.
    y=round(h*(.73 if kind=='brand' and portrait else .58 if kind=='brand' else spec['position']))
    if not portrait and kind=='brand':bw=round(w*.34);bh=round(bw*.29)
    y=min(y,round(h*.89)-bh)
    art=styled_button(spec['text'],bw,bh,style,accent)
    shadow=Image.new('RGBA',(w,h))
    if style!='type':shadow.paste((0,0,0,175),(x,y+round(bh*.08),x+bw,y+bh+round(bh*.08)))
    shadow.putalpha(shadow.getchannel('A').filter(ImageFilter.GaussianBlur(max(2,w*.012))))
    canvas.alpha_composite(shadow);canvas.alpha_composite(art,(x,y))
    brand=spec['brand']
    if brand:
        width=w*.82 if portrait else w*.35
        font,lines,size=fit_text(brand,width,h*.12,round(min(w*.075,h*.09)))
        draw=ImageDraw.Draw(canvas)
        by=h*.035 if kind=='brand' and portrait else y-size*len(lines)*1.2-h*.025
        center=w*.5 if portrait or kind!='brand' else w*.76
        for line in lines:
            draw.text((center-font.getlength(line)/2,by),line,font=font,anchor='lt',fill='#fff9de',stroke_width=max(2,round(size*.065)),stroke_fill='#193e59')
            by+=size*1.2
    return canvas
