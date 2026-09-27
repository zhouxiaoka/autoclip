"""First-release typography calibration; v1–v5 remain reproducible.

Use shaped glyph masks rather than approximating weight with repeated shadows.
Comic delegates to the user-reviewed v5 geometry without changes.
"""
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageFont
from .title_art import ACCENTS, FONTS, STYLES, font_for, lines_for


def _font(text, size, weight=900):
    if all(ord(c)<0x250 for c in text):
        return ImageFont.truetype(str(FONTS/'Anton-Regular.ttf'),size)
    font=font_for(text,size)
    font.set_variation_by_axes([weight])
    return font


def _mask(text, font, shear=0, embolden=0):
    box=font.getbbox(text)
    mask=Image.new('L',(max(1,box[2]-box[0])+8,max(1,box[3]-box[1])+8))
    ImageDraw.Draw(mask).text((4-box[0],4-box[1]),text,font=font,fill=255)
    if embolden:
        mask=mask.filter(ImageFilter.MaxFilter(embolden*2+1))
    if shear:
        extra=round(mask.height*shear)
        mask=mask.transform((mask.width+extra,mask.height),Image.Transform.AFFINE,
                            (1,shear,-extra,0,1,0),Image.Resampling.BICUBIC)
    box=mask.getbbox()
    return mask.crop(box) if box else mask


def _shift(mask, x, y):
    result=Image.new('L',mask.size);result.paste(mask,(x,y));return result


def _ink(art, face, position, color, stroke=0, depth=0, light=.12):
    mask=Image.new('L',art.size);mask.paste(face,position)
    if stroke or depth:
        outline=mask.filter(ImageFilter.MaxFilter(stroke*2+1)) if stroke else mask
        ink=outline.copy()
        for offset in range(1,depth+1):
            ink=ImageChops.lighter(ink,_shift(outline,round(offset*.5),offset))
        art.paste('#080e15',(0,0,*art.size),ink)
    base=ImageColor.getrgb(color)
    gradient=Image.new('RGBA',art.size);d=ImageDraw.Draw(gradient)
    x,y=position
    for row in range(face.height):
        t=row/max(1,face.height-1)
        mix=light*(1-t)**2
        rgb=tuple(round(v+(255-v)*mix) for v in base)
        d.line((x,y+row,x+face.width,y+row),fill=(*rgb,255))
    gradient.putalpha(mask);art.alpha_composite(gradient)


def _place(art,w,h,y,angle=0,left_aligned=False,resample=Image.Resampling.BICUBIC):
    if angle:art=art.rotate(angle,resample,expand=True)
    box=art.getbbox()
    if box:art=art.crop(box)
    ratio=min(1,w*.90/art.width,h*.28/art.height)
    if ratio<1:
        art=art.resize((max(1,round(art.width*ratio)),max(1,round(art.height*ratio))),
                       Image.Resampling.NEAREST if resample==Image.Resampling.NEAREST else Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(w,h))
    left=round(w*.06) if left_aligned else (w-art.width)//2
    top=max(round(h*.04),min(round(h*(y-.05)),h-round(h*.10)-art.height))
    canvas.alpha_composite(art,(left,top));return canvas


def _headline(text,style,w,h,scale,y,accent):
    if all(ord(c)<0x250 for c in text):text=text.upper()
    size=max(14,round(min(w*.20,h*.14)*scale))
    minimum=max(10,round(min(w,h)*.045))
    while True:
        font=_font(text,size)
        lines=lines_for(text,font,w*.78*min(scale,1))
        if len(lines)<=3:break
        size-=3
        if size<minimum:raise ValueError('开头文字太长，请缩短或减少换行（最多三行）')
    faces=[]
    for i,line in enumerate(lines):
        face=_mask(line,_font(line,size),.25 if style=='arena' else 0,2 if style=='arena' else 0)
        target=w*(.76 if i<len(lines)-1 else .80)*scale
        factor=min(target/face.width,1.35)
        height_factor={'neon':.82,'arena':.78,'editorial':1.02}[style]
        face=face.resize((max(1,round(face.width*factor)),max(1,round(face.height*factor*height_factor))),Image.Resampling.LANCZOS)
        faces.append(face)
    pad=max(10,round(w*.09));gap=max(3,round(w*({'neon':.032,'arena':.030,'editorial':.017}[style])))
    cw=max(f.width for f in faces)+pad*2
    ch=sum(f.height for f in faces)+gap*(len(faces)-1)+pad*2
    art=Image.new('RGBA',(cw,ch));d=ImageDraw.Draw(art)
    top=pad
    color=accent or ACCENTS[style]
    for i,face in enumerate(faces):
        left=pad if style=='editorial' else (cw-face.width)//2
        last=i==len(faces)-1
        if style=='neon':
            if last:
                margin=round(w*.023);yt=top-round(gap*.40);yb=top+face.height+round(gap*.44)
                d.polygon([(left-margin+3,yt+5),(left+face.width+margin+3,yt+5),
                           (left+face.width+margin+3,yb+9),(left-margin+3,yb+9)],fill='#08140c')
                # Saturated marker slab, with a narrow lit edge rather than a metal band.
                d.rectangle((left-margin,yt,left+face.width+margin,yb),fill=color)
                d.line((left-margin,yt,left+face.width+margin,yt),fill='#e7ff9f',width=max(1,round(w*.002)))
                _ink(art,face,(left,top),'#070d06',light=0)
                line_y=yb+round(w*.018)
                d.polygon([(cw*.28,line_y+6),(cw*.70,line_y),(cw*.69,line_y+8),(cw*.27,line_y+12)],fill=color)
            else:
                _ink(art,face,(left,top),'#ffffff',stroke=max(1,round(w*.003)),depth=max(2,round(w*.005)),light=0)
        elif style=='arena':
            margin=round(w*.026);skew=round(w*.033)
            yt=top-round(gap*.44);yb=top+face.height+round(gap*.54)
            x0=left-margin;x1=left+face.width+margin
            if i==0:
                d.polygon([(x0+skew-w*.04,yt+6),(x1+skew,yt+6),(x1-skew,yb+7),(x0-skew-w*.04,yb+7)],fill='#13a9ff')
            d.polygon([(x0+skew,yt),(x1+skew,yt),(x1-skew,yb),(x0-skew,yb)],fill='#080e1c')
            if last:
                d.polygon([(x0,yb+2),(x1-skew,yb+2),(x1-skew-w*.013,yb+w*.009),(x0-w*.013,yb+w*.009)],fill='#168cdd')
            _ink(art,face,(left,top),color if last else '#ffffff',light=.10 if last else 0)
        else:
            stroke=max(1,round(w*.003));depth=max(2,round(w*.009))
            if last:
                yt=top+round(face.height*.79);yb=top+face.height+round(w*.032)
                d.rectangle((left-12+5,yt+8,left+face.width+12+5,yb+8),fill='#090f16')
                d.rectangle((left-12,yt,left+face.width+12,yb),fill=color)
                d.line((left-12,yt,left+face.width+12,yt),fill='#ff9476',width=max(1,round(w*.003)))
            _ink(art,face,(left,top),'#fff7df',stroke=stroke,depth=depth,light=.18)
        top+=face.height+gap
    return _place(art,w,h,y,angle={'neon':4,'arena':9,'editorial':0}[style],left_aligned=style=='editorial')


def _pixel(text,w,h,scale,y,accent):
    latin=all(ord(c)<0x250 for c in text)
    if latin:text=text.upper()
    font=ImageFont.truetype(str(FONTS/'PressStart2P-Regular.ttf'),8) if latin else font_for(text,20)
    lines=lines_for(text,font,96 if latin else 120)
    if len(lines)>3:raise ValueError('开头文字太长，请缩短或减少换行（最多三行）')
    faces=[]
    for i,line in enumerate(lines):
        if latin:
            # Compact word spaces and tracking keep the raster letters as one headline.
            face=Image.new('L',(len(line)*8+4,16));d=ImageDraw.Draw(face);x=2
            for c in line:
                d.text((x,0),c,font=font,fill=255);x+=4 if c==' ' else 8
            face=face.crop(face.getbbox())
        else:face=_mask(line,font)
        face=face.point(lambda p:255 if p>=110 else 0)
        factor=(1.30 if i<len(lines)-1 else 1.55) if latin else 1.05
        face=face.resize((face.width,max(1,round(face.height*factor))),Image.Resampling.NEAREST)
        faces.append(face)
    pad=5;gap=3;cw=max(f.width for f in faces)+pad*2;ch=sum(f.height for f in faces)+gap*(len(faces)-1)+pad*2
    art=Image.new('RGBA',(cw,ch),(7,10,19,226));d=ImageDraw.Draw(art)
    color=accent or ACCENTS['pixel']
    d.rectangle((0,0,cw-1,ch-1),outline=(*ImageColor.getrgb(color),125),width=1)
    top=pad
    for face in faces:
        left=(cw-face.width)//2;mask=Image.new('L',art.size);mask.paste(face,(left,top))
        edge=mask.filter(ImageFilter.MaxFilter(3))
        art.paste('#160b22',(0,0,cw,ch),_shift(edge,2,2))
        art.paste(color,(0,0,cw,ch),edge)
        art.paste('#fff2c9',(0,0,cw,ch),mask)
        top+=face.height+gap
    for x,yy,sx,sy in [(1,1,1,1),(cw-2,1,-1,1),(1,ch-2,1,-1),(cw-2,ch-2,-1,-1)]:
        d.line((x,yy,x+sx*3,yy),fill=color,width=1)
        d.line((x,yy,x,yy+sy*3),fill=color,width=1)
        d.point((x,yy),fill='#fff2c9')
        d.point((x+sx,yy),fill='#fff2c9')
    factor=max(1,int(min(w*.85/cw,h*.255/ch)*min(scale,1.15)))
    art=art.resize((cw*factor,ch*factor),Image.Resampling.NEAREST)
    return _place(art,w,h,y,angle=3,resample=Image.Resampling.NEAREST)


def frosted_layers(text,w,h,scale=1,y=.12,accent=None):
    canvas=Image.new('RGBA',(w,h));mask=Image.new('L',(w,h))
    if not text.strip():return canvas,mask
    if all(ord(c)<0x250 for c in text):text=text.upper()
    size=max(12,round(min(w*.138,h*.12)*scale));minimum=max(9,round(min(w,h)*.04))
    pad=max(4,round(min(w*.055,h*.04)));bar=max(3,round(w*.021));gap=max(3,round(w*.018))
    while True:
        font=ImageFont.truetype(str(FONTS/'NotoSansSC.ttf'),size);font.set_variation_by_axes([900])
        lines=lines_for(text,font,w*.68)
        faces=[_mask(line,font) for line in lines]
        if len(lines)<=3 and sum(f.height for f in faces)+gap*(len(lines)-1)+pad*2<=h*.28:break
        size-=3
        if size<minimum:raise ValueError('开头文字太长，请缩短或减少换行（最多三行）')
    cw=round(w*.84);ch=sum(f.height for f in faces)+gap*(len(faces)-1)+pad*2
    left=(w-cw)//2;top=max(round(h*.04),min(round(h*(y-.05)),h-round(h*.10)-ch))
    radius=max(4,round(w*.048));box=(left,top,left+cw,top+ch)
    ImageDraw.Draw(mask).rounded_rectangle(box,radius=radius,fill=255)
    panel=Image.new('RGBA',(w,h));d=ImageDraw.Draw(panel)
    for row in range(ch+1):
        t=row/max(1,ch)
        color=tuple(round(a+(b-a)*t) for a,b in zip((53,70,76),(16,28,35)))
        d.line((left,top+row,left+cw,top+row),fill=(*color,round(156+12*t)))
    panel.putalpha(ImageChops.multiply(panel.getchannel('A'),mask));canvas.alpha_composite(panel)
    d=ImageDraw.Draw(canvas)
    d.rounded_rectangle(box,radius=radius,outline=(217,248,255,82),width=max(1,round(w*.003)))
    # Broad edge sheen lives on the card rim, not as a stripe across the letters.
    d.line((left+radius,top+2,left+cw-radius,top+2),fill=(244,255,255,115),width=max(1,round(w*.002)))
    d.rounded_rectangle((left+pad*.65,top+pad,left+pad*.65+bar,top+ch-pad),radius=max(1,bar//5),fill=accent or ACCENTS['frosted'])
    yy=top+pad
    for face in faces:
        _ink(canvas,face,(left+round(pad*1.35),yy),'#f8fcff',light=0)
        yy+=face.height+gap
    return canvas,mask


def artwork(text,style,w,h,scale=1,y=.12,accent=None):
    if w<16 or h<16 or w*h>16777216:raise ValueError('文字模板支持最大 1600 万像素画布，请使用 1080p 画幅')
    if style not in STYLES:raise ValueError('未知文字模板')
    if not text.strip():return Image.new('RGBA',(w,h))
    if style=='comic':
        from .comic_art import artwork as comic
        return comic(text,w,h,scale,y,accent,punch=True)
    if style=='pixel':return _pixel(text,w,h,scale,y,accent)
    if style=='frosted':return frosted_layers(text,w,h,scale,y,accent)[0]
    return _headline(text,style,w,h,scale,y,accent)
