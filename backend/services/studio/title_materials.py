"""Deterministic ink materials, grid typography, and shared glass masks."""
import io
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageFont
from backend.services.studio.title_art import FONTS, font_for, lines_for


def _mix(color, target, amount):
    return tuple(round(a+(b-a)*amount) for a,b in zip(color,target))


def _gradient(size, box, color, strength=1):
    base = ImageColor.getrgb(color)
    x0,y0,x1,y1 = box
    layer = Image.new('RGBA', size)
    draw = ImageDraw.Draw(layer)
    # Top rim, broad light face, crisp reflection boundary, shaded lower face.
    stops = [(0,.66),(.18,.20),(.40,.06),(.46,.44),(.51,-.08),(1,-.24)]
    for yy in range(max(0,y0), min(size[1],y1)):
        t=(yy-y0)/max(1,y1-y0-1)
        for (a,va),(b,vb) in zip(stops,stops[1:]):
            if a<=t<=b:
                light=(va+(vb-va)*(t-a)/(b-a))*strength
                rgb=_mix(base,(255,255,255) if light>=0 else (0,0,0),abs(light))
                draw.line((x0,yy,x1,yy),fill=(*rgb,255))
                break
    return layer


def _shift(mask, x, y):
    result=Image.new('L',mask.size)
    result.paste(mask,(x,y))
    return result


def gloss_text(art, position, text, font, color, strength=1):
    mask=Image.new('L',art.size)
    ImageDraw.Draw(mask).text(position,text,font=font,fill=255)
    box=mask.getbbox()
    if not box:return
    layer=_gradient(art.size,box,color,strength)
    layer.putalpha(mask)
    art.alpha_composite(layer)
    # Interior bevel: light on top/left, darker lower/right edge, no outer glow.
    edge=max(1,round((box[3]-box[1])*.018))
    light=ImageChops.subtract(mask,_shift(mask,edge,edge)).point(lambda p:round(p*.55*strength))
    dark=ImageChops.subtract(mask,_shift(mask,-edge,-edge)).point(lambda p:round(p*.25*strength))
    rim=Image.new('RGBA',art.size,'white');rim.putalpha(light);art.alpha_composite(rim)
    rim=Image.new('RGBA',art.size,'#09101b');rim.putalpha(dark);art.alpha_composite(rim)


def gradient_shape(art, points, color, strength):
    mask=Image.new('L',art.size);ImageDraw.Draw(mask).polygon(points,fill=255)
    box=mask.getbbox()
    if box:
        layer=_gradient(art.size,box,color,strength);layer.putalpha(mask);art.alpha_composite(layer)


def _place(art,w,h,y):
    canvas=Image.new('RGBA',(w,h))
    top=max(round(h*.04),min(round(h*(y-.05)),h-round(h*.10)-art.height))
    canvas.alpha_composite(art,((w-art.width)//2,top))
    return canvas


def pixel_artwork(text,w,h,scale=1,y=.12,accent=None):
    if not text.strip():return Image.new('RGBA',(w,h))
    latin=all(ord(c)<0x250 for c in text)
    if latin:text=text.upper()
    # Latin uses a designed 8px bitmap face. CJK retains full character coverage
    # via a 20px thresholded Noto grid; this is explicitly a raster fallback.
    font=ImageFont.truetype(str(FONTS/'PressStart2P-Regular.ttf'),8) if latin else font_for(text,20)
    lines=lines_for(text,font,96 if latin else 120)
    if len(lines)>3:raise ValueError('开头文字太长，请缩短或减少换行（最多三行）')
    masks=[]
    for line in lines:
        b=font.getbbox(line)
        m=Image.new('L',(max(1,b[2]-b[0])+2,max(1,b[3]-b[1])+2))
        ImageDraw.Draw(m).text((1-b[0],1-b[1]),line,font=font,fill=255)
        masks.append(m.point(lambda p:255 if p>=110 else 0))
    pad=5;gap=3;cw=max(m.width for m in masks)+pad*2;ch=sum(m.height for m in masks)+gap*(len(masks)-1)+pad*2
    art=Image.new('RGBA',(cw,ch),(9,16,26,206));d=ImageDraw.Draw(art)
    accent=accent or '#ed327c'
    d.rectangle((0,0,cw-1,ch-1),outline=(*ImageColor.getrgb(accent),95),width=1)
    yy=pad
    for m in masks:
        x=(cw-m.width)//2
        mask=Image.new('L',art.size);mask.paste(m,(x,yy))
        outline=mask.filter(ImageFilter.MaxFilter(3))
        art.paste('#180d24',(0,0,cw,ch),_shift(outline,2,2))
        art.paste(accent,(0,0,cw,ch),_shift(outline,1,1))
        face=_gradient(art.size,mask.getbbox(),'#fff1c4',.48);face.putalpha(mask);art.alpha_composite(face)
        yy+=m.height+gap
    # Corner brackets stay on the same whole-pixel grid as the type.
    for x,yy,sx,sy in [(1,1,1,1),(cw-2,1,-1,1),(1,ch-2,1,-1),(cw-2,ch-2,-1,-1)]:
        d.line((x,yy,x+sx*3,yy),fill='#fff3d1',width=1)
        d.line((x,yy,x,yy+sy*3),fill=accent,width=1)
    factor=max(1,int(min(w*.88/cw,h*.26/ch)*min(scale,1.15)))
    factor=min(factor,max(1,int(min(w*.92/cw,h*.30/ch))))
    art=art.resize((cw*factor,ch*factor),Image.Resampling.NEAREST)
    return _place(art,w,h,y)


def _glass_font(size):
    font=ImageFont.truetype(str(FONTS/'NotoSansSC.ttf'),size)
    font.set_variation_by_axes([700])
    return font


def frosted_layers(text,w,h,scale=1,y=.12,accent=None):
    art=Image.new('RGBA',(w,h));mask=Image.new('L',(w,h))
    if not text.strip():return art,mask
    size=max(12,round(min(w*.125,h*.12)*scale))
    minimum=max(9,round(min(w,h)*.04))
    pad=max(4,round(w*.046));bar=max(3,round(w*.018));gap=max(3,round(w*.016))
    while True:
        font=_glass_font(size);lines=lines_for(text,font,w*.70)
        heights=[font.getbbox(line)[3]-font.getbbox(line)[1] for line in lines]
        if len(lines)<=3 and sum(heights)+gap*(len(lines)-1)+pad*2<=h*.28:break
        size-=3
        if size<minimum:raise ValueError('开头文字太长，请缩短或减少换行（最多三行）')
    cw=round(w*.84);ch=sum(heights)+gap*(len(lines)-1)+pad*2
    left=(w-cw)//2;top=max(round(h*.04),min(round(h*(y-.05)),h-round(h*.10)-ch));radius=max(4,round(w*.047))
    box=(left,top,left+cw,top+ch)
    ImageDraw.Draw(mask).rounded_rectangle(box,radius=radius,fill=255)
    # Transparent charcoal material; actual moving background blur is separate.
    panel=Image.new('RGBA',(w,h));pd=ImageDraw.Draw(panel)
    for yy in range(top,top+ch+1):
        t=(yy-top)/max(1,ch)
        rgb=_mix((49,67,77),(12,23,31),t)
        pd.line((left,yy,left+cw,yy),fill=(*rgb,round(155+20*t)))
    panel.putalpha(ImageChops.multiply(panel.getchannel('A'),mask));art.alpha_composite(panel)
    d=ImageDraw.Draw(art)
    d.rounded_rectangle(box,radius=radius,outline=(221,248,255,92),width=max(1,round(w*.002)))
    d.line((left+radius,top+2,left+cw-radius,top+2),fill=(244,255,255,120),width=max(1,round(w*.002)))
    d.rounded_rectangle((left+pad*.65,top+pad,left+pad*.65+bar,top+ch-pad),radius=max(1,bar//4),fill=accent or '#00e6dc')
    yy=top+pad
    for line,lh in zip(lines,heights):
        b=font.getbbox(line)
        gloss_text(art,(left+pad*1.4,yy-b[1]),line,font,'#f5faff',strength=.3)
        yy+=lh+gap
    return art,mask


def backdrop_png(text,style,w,h,scale=1,y=.12,accent=None,version=3):
    if style!='frosted' or version not in (3,6):raise ValueError('仅磨砂字幕卡支持背景遮罩')
    if w<16 or h<16 or w*h>16777216:raise ValueError('文字模板支持最大 1600 万像素画布')
    if version == 6:
        from .title_art_v6 import frosted_layers as layers
    else:
        layers = frosted_layers
    mask=layers(text,w,h,scale,y,accent)[1]
    # RGBA with alpha supports CSS mask-image as well as FFmpeg alphaextract.
    image=Image.new('RGBA',(w,h),'white');image.putalpha(mask)
    stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()


def blur_sigma(width):
    return max(1,round(width*.016,2))
