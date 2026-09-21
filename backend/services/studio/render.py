"""Render immutable draft snapshots using the existing ffmpeg layout/subtitle code."""
import os
import subprocess
import tempfile
from pathlib import Path
from backend.services.publish_export import ExportRequest, _build_filter, _load_srt_entries, _probe, resolve_cjk_font, slice_srt
from backend.services.studio.intelligence import text_json, validate_scenes
from backend.services.studio.models import Draft
from backend.services.studio.titles import template_filters
from backend.services.studio import title_art
from backend.services.studio.store import directory
from backend.utils.ffmpeg_utils import get_ffmpeg_path


def render_draft(project_id, video, draft: Draft, job_id, progress):
    info = _probe(video)
    validate_scenes(draft.scenes, info.get('duration', 0))
    w, h = {'portrait': (1080, 1920), 'landscape': (1920, 1080)}.get(draft.aspect, (info.get('width'), info.get('height')))
    if not w or not h:
        raise ValueError('无法读取原视频尺寸')
    w, h = int(w) // 2 * 2, int(h) // 2 * 2
    warnings = []
    entries = _load_srt_entries(project_id) if draft.subtitles else []
    # Only transmit the subtitle rows used by this draft, never unrelated transcript text.
    from backend.pipeline.quality import to_seconds
    entries = [e.copy() for e in entries if any(to_seconds(e['start_time']) < s.end and to_seconds(e['end_time']) > s.start for s in draft.scenes)]
    hook = draft.hook
    if draft.language != 'source' and (hook or entries):
        translated = text_json('将 title 和 subtitles 翻译成指定语言；保持 subtitles 的数量与顺序，不添加事实。返回 {"title":"...","subtitles":["..."]}。', {'language': draft.language, 'title': hook, 'subtitles': [e.get('text', '') for e in entries]})
        rows = translated.get('subtitles', [])
        if len(rows) != len(entries) or not all(isinstance(t, str) for t in rows) or not isinstance(translated.get('title'), str):
            raise ValueError('字幕翻译格式不完整，请重试')
        hook = translated['title']
        if len(hook) > 500:
            raise ValueError('翻译后的开头文字过长')
        for e, t in zip(entries, rows):
            e['text'] = t
    font = resolve_cjk_font()
    if hook and draft.title_style not in title_art.STYLES and not font:
        raise ValueError('缺少中文字体，无法烧录开头文字，请安装 Noto Sans CJK')
    if draft.subtitles and not entries:
        warnings.append('原素材没有可用字幕，本次未烧录字幕')
    out_dir = directory(project_id) / 'output' / 'studio'
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f'{job_id}.mp4'
    partial = out_dir / f'{job_id}.part.mp4'
    try:
        with tempfile.TemporaryDirectory(prefix='ac-studio-render-') as temp:
            folder = Path(temp)
            parts = []
            for i, scene in enumerate(draft.scenes):
                srt = folder / f'{i}.srt'
                body = slice_srt(entries, scene.start, scene.end)
                if body:
                    srt.write_text(body, encoding='utf-8')
                title = folder / 'title.txt'
                if hook and i == 0:
                    import textwrap
                    title.write_text('\n'.join(textwrap.wrap(hook, width=14)), encoding='utf-8')
                spec = {'layout': draft.layout, 'w': w, 'h': h}
                req = ExportRequest(project_id, draft.id, layout=draft.layout)
                built = _build_filter(req, spec, srt if body else None, title if hook and i == 0 and draft.title_style == 'plain' else None, font)
                clip_path = folder / f'{i}.mp4'
                artwork = None
                if hook and i == 0 and draft.title_style in title_art.STYLES:
                    artwork = folder / 'title-art.png'
                    artwork.write_bytes(title_art.png_bytes(hook, draft.title_style, w, h, **title_art.options_for(draft)))
                cmd = [get_ffmpeg_path(), '-v', 'error', '-ss', str(scene.start), '-i', str(video)]
                if artwork:
                    cmd += ['-loop', '1', '-i', str(artwork)]
                cmd += ['-t', str(scene.end-scene.start)]
                if built:
                    graph, last = built
                    graph = graph.replace(':reload=0', ':expansion=none:reload=0').replace(':fontsize=42:', f':fontsize={max(18, round(w * .06))}:').replace(f'[fg]scale={w}:-2[fg2]', f'[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fg2]')
                    if draft.layout == 'crop':
                        graph = graph.replace(f'crop={w}:{h}[base]', f'crop={w}:{h}:x=(iw-ow)*{draft.crop_x}:y=(ih-oh)/2,setsar=1[base]')
                    if artwork:
                        x, y = title_art.overlay_motion(draft.title_style, draft.title_motion, h)
                        graph += f";[1:v]format=rgba[titleart];[{last}][titleart]overlay=x='{x}':y='{y}':enable='lt(t,4)':shortest=1[styled]"
                        last = 'styled'
                    elif hook and i == 0 and draft.title_style != 'plain':
                        titles, last = template_filters(hook, draft.title_style, w, h, folder, font, last, scene.end-scene.start)
                        graph += ';' + ';'.join(titles)
                    cmd += ['-filter_complex', graph, '-map', f'[{last}]']
                else:
                    cmd += ['-map', '0:v:0']
                cmd += ['-map', '0:a:0?', '-c:a', 'aac', '-b:a', '160k'] if draft.original_audio else ['-an']
                cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30', '-threads', '2', '-y', str(clip_path)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=max(180, (scene.end-scene.start)*20))
                if proc.returncode:
                    raise RuntimeError('渲染镜头失败：' + proc.stderr[-600:])
                parts.append(clip_path)
                progress(round(10 + (i+1) / len(draft.scenes) * 80))
            concat = folder / 'parts.txt'
            concat.write_text(''.join(f"file '{p}'\n" for p in parts), encoding='utf-8')
            subprocess.run([get_ffmpeg_path(), '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-c', 'copy', '-movflags', '+faststart', '-y', str(partial)], check=True, capture_output=True, timeout=180)
            os.replace(partial, output)
        return {'title': draft.title, 'duration': _probe(output).get('duration'), 'width': w, 'height': h, 'warnings': warnings}
    finally:
        partial.unlink(missing_ok=True)
