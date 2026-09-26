"""Bounded, model-free CTA planning and artwork shared by preview and export."""
import io
import subprocess
from backend.services.studio.audio import scene_duration
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
    return {'style': draft.cta.style, 'accent': draft.cta.accent, 'template': kind, 'reason': reason, 'start': start, 'extra_duration': extra,
            'duration': total + extra, 'scene_key': scene_key(last),
            'text': draft.cta.text.strip() or COPY[draft.cta.language].get(kind, ''),
            'brand': draft.cta.brand.strip(), 'position': draft.cta.position}


def artwork(spec, w, h, source=None):
    if w < 16 or h < 16 or w*h > 16777216:
        raise ValueError('CTA 画布尺寸无效')
    from backend.services.studio.cta_materials import artwork as render_artwork
    return render_artwork(spec, w, h, source)


def png_bytes(spec,w,h,source=None):
    stream=io.BytesIO()
    artwork(spec,w,h,source).save(stream,format='PNG')
    return stream.getvalue()


def apply(video, destination, spec, w, h, keep_audio, folder, source=None):
    layer=folder/'cta.png'
    layer.write_bytes(png_bytes(spec,w,h,source))
    extra=spec['extra_duration']
    graph=f"[0:v]tpad=stop_mode=clone:stop_duration={extra}[base];[base][1:v]overlay=0:0:enable='gte(t,{spec['start']})':shortest=1[out]"
    cmd=[get_ffmpeg_path(),'-v','error','-i',str(video),'-loop','1','-i',str(layer),'-filter_complex',graph,'-map','[out]']
    if keep_audio:
        cmd+=['-map','0:a:0','-af',f'apad=pad_dur={extra}', '-c:a','aac','-b:a','160k']
    else:
        cmd+=['-an']
    cmd+=['-t',str(spec['duration']),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r','30','-threads','2','-movflags','+faststart','-y',str(destination)]
    subprocess.run(cmd,check=True,capture_output=True,timeout=max(180,spec['duration']*20))
