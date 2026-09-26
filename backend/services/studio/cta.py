"""Bounded, model-free CTA planning and artwork shared by preview and export."""
import io
import subprocess
from PIL import Image, ImageDraw
from backend.services.studio.audio import scene_duration
from backend.services.studio.title_art import font_for, lines_for
from backend.utils.ffmpeg_utils import get_ffmpeg_path

COPY = {
    'zh': {'continue': '现在开始体验', 'challenge': '轮到你挑战', 'brand': '开启你的游戏'},
    'en': {'continue': 'Start playing', 'challenge': 'Your turn to play', 'brand': 'Start your adventure'},
    'ja': {'continue': '今すぐプレイ', 'challenge': '次はあなたの番', 'brand': '冒険を始めよう'},
}


def scene_key(scene):
    return f'{scene.id}:{scene.start:g}:{scene.end:g}'


def plan(draft):
    total = sum(scene_duration(s) for s in draft.scenes)
    last = draft.scenes[-1]
    kind = draft.cta.template
    reason = '手动选择'
    if kind == 'auto':
        # Metadata can establish available time, not victory, HUD clearance or ad intent.
        kind = 'continue' if total >= 8 and scene_duration(last) >= 4 else 'brand'
        reason = '末镜头有足够续播时间' if kind == 'continue' else '短镜头使用独立落版，保留完整过程'
    if kind == 'challenge' and draft.cta.confirmed_scene != scene_key(last):
        kind, reason = 'brand', '请先确认末镜头结果完整；已使用品牌落版'
    if kind == 'continue' and (total < 8 or scene_duration(last) < 4):
        kind, reason = 'brand', '续播时间不足；已使用品牌落版'
    extra = 2.5 if kind in ('brand', 'challenge') else 0
    start = total if extra else max(total - 3, total - scene_duration(last))
    return {'template': kind, 'reason': reason, 'start': start, 'extra_duration': extra,
            'duration': total + extra, 'scene_key': scene_key(last),
            'text': draft.cta.text.strip() or COPY[draft.cta.language].get(kind, ''),
            'brand': draft.cta.brand.strip(), 'position': draft.cta.position}


def artwork(spec, w, h):
    if w < 16 or h < 16 or w*h > 16777216:
        raise ValueError('CTA 画布尺寸无效')
    kind = spec['template']
    image = Image.new('RGBA', (w, h))
    if kind == 'off':
        return image
    draw = ImageDraw.Draw(image)
    if kind == 'brand':
        # An independent branded slate avoids presenting an arbitrary last frame as evidence.
        for y in range(h):
            t = y / h
            draw.line((0,y,w,y), fill=(int(12+12*t),int(20+20*t),int(34+34*t),255))
        draw.ellipse((w*.5,-h*.15,w*1.6,h*.6),fill=(30,63,79,255))
    elif kind == 'challenge':
        draw.rectangle((0,0,w,h), fill=(7,13,23,120))
    color = '#b8ff68'
    max_width = w*.74
    size = max(12, round(min(w*.09,h*.075)))
    while True:
        font = font_for(spec['text'],size)
        lines = lines_for(spec['text'],font,max_width)
        if len(lines)<=2 and all(font.getlength(line)<=max_width for line in lines): break
        size -= 2
        if size < max(10,min(w,h)*.026):
            raise ValueError('CTA 文字太长，请缩短文案')
    line_h = size*1.3
    brand = spec['brand']
    brand_size = max(10, round(size*.55))
    brand_font = font_for(brand,brand_size)
    while brand and brand_font.getlength(brand)>max_width and brand_size>10:
        brand_size-=1
        brand_font=font_for(brand,brand_size)
    if brand and brand_font.getlength(brand)>max_width:
        raise ValueError('游戏名称太长，请缩短名称')
    pad = min(w,h)*.045
    content_h = line_h*len(lines) + (brand_size*1.8 if brand else 0)
    y = h*(.42 if kind=='brand' else spec['position'])
    y = min(y,h*.86-content_h-pad)
    if kind!='brand':
        draw.rounded_rectangle((w*.08,y-pad,w*.92,y+content_h+pad),radius=round(pad),fill=(10,19,30,238),outline=(125,160,170,210),width=max(1,round(w*.002)))
    draw.rounded_rectangle((w*.13,y-pad*.2,w*.23,y-pad*.2+max(3,h*.004)),radius=2,fill=color)
    if brand:
        draw.text((w*.13,y+pad*.25),brand,font=brand_font,fill='#c6d4df',anchor='lt')
        y+=brand_size*1.8
    for line in lines:
        draw.text((w*.13,y+pad*.25),line,font=font,fill=color if kind=='challenge' else 'white',anchor='lt')
        y+=line_h
    return image


def png_bytes(spec,w,h):
    stream=io.BytesIO()
    artwork(spec,w,h).save(stream,format='PNG')
    return stream.getvalue()


def apply(video, destination, spec, w, h, keep_audio, folder):
    layer=folder/'cta.png'
    layer.write_bytes(png_bytes(spec,w,h))
    extra=spec['extra_duration']
    graph=f"[0:v]tpad=stop_mode=clone:stop_duration={extra}[base];[base][1:v]overlay=0:0:enable='gte(t,{spec['start']})':shortest=1[out]"
    cmd=[get_ffmpeg_path(),'-v','error','-i',str(video),'-loop','1','-i',str(layer),'-filter_complex',graph,'-map','[out]']
    if keep_audio:
        cmd+=['-map','0:a:0','-af',f'apad=pad_dur={extra}', '-c:a','aac','-b:a','160k']
    else:
        cmd+=['-an']
    cmd+=['-t',str(spec['duration']),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r','30','-threads','2','-movflags','+faststart','-y',str(destination)]
    subprocess.run(cmd,check=True,capture_output=True,timeout=max(180,spec['duration']*20))
