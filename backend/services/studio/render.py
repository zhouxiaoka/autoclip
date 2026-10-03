"""Render immutable draft snapshots using the existing ffmpeg layout/subtitle code."""
import os
import subprocess
import tempfile
from pathlib import Path
from backend.services.publish_export import ExportRequest, _build_filter, _load_srt_entries, _probe, resolve_cjk_font, slice_srt, subtitle_line_limit
from backend.services.studio.intelligence import text_json, validate_scenes
from backend.services.studio.models import Draft
from backend.services.studio.titles import template_filters
from backend.services.studio import title_art
from backend.services.studio import audio
from backend.services.studio.store import directory
from backend.services import render_limits
from backend.utils.ffmpeg_utils import get_ffmpeg_path


def _mask_captions(graph, band):
    """Blur the burned caption band of the source before any layout uses it.

    Every layout reads the source as `[0:v]`; each use gets the masked copy instead. With no
    graph at all, returns a graph whose output label replaces the plain `0:v:0` map.
    """
    top, bottom = (min(max(float(v), 0.0), 1.0) for v in band)
    height = max(0.02, bottom - top)
    uses = graph.count('[0:v]') if graph else 0
    labels = ''.join(f'[masked{k}]' for k in range(max(1, uses)))
    prefix = (f"[0:v]split=2[maskbase][maskband];[maskband]crop=iw:ih*{height:.4f}:0:ih*{top:.4f},gblur=sigma=40:steps=2[maskblur];"
              f"[maskbase][maskblur]overlay=0:main_h*{top:.4f},split={max(1, uses)}{labels}")
    if not uses:  # no video graph (maybe audio only): the masked copy is mapped directly
        return prefix + (';' + graph if graph else ''), '[masked0]'
    parts = graph.split('[0:v]')
    rebuilt = parts[0] + ''.join(f'[masked{k}]' + part for k, part in enumerate(parts[1:]))
    return prefix + ';' + rebuilt, None


def _needs_translation(language, hook, entries):
    """Skip the model call when the hook and captions are already in the target language."""
    from backend.services.studio.packaging import CJK, foreign_for, source_language
    if language not in ('zh', 'en'):
        return True
    if entries and source_language([e.get('text', '') for e in entries]) != language:
        return True
    if hook and (foreign_for('en', hook) if language == 'en' else not CJK.search(hook)):
        return True
    return False


def recover_empty_packaging(project_id, draft: Draft, warnings: list[str]) -> Draft:
    pack = draft.packaging
    if not (draft.subtitles and pack and pack.fallback and not pack.cues and not pack.burned_captions):
        return draft
    # Previously saved fallbacks have no cues. Re-rendering them must recover the source
    # track too; changing only new packaging would leave upgraded projects captionless.
    from backend.services.studio.packaging import draft_lines, source_cues
    from backend.services.studio.models import Packaging
    lines = draft_lines(_load_srt_entries(project_id), [scene.model_dump() for scene in draft.scenes])
    cues = source_cues(lines, pack.audience_language)
    warnings.append('包装未能完整生成，已使用原字幕' if cues else '包装未能完整生成，字幕暂不可用')
    return draft.model_copy(update={'packaging': Packaging.model_validate({**pack.model_dump(), 'cues': cues})})


def render_draft(project_id, video, draft: Draft, job_id, progress, *, brand_outro=False):
    info = _probe(video)
    validate_scenes(draft.scenes, info.get('duration', 0))
    w, h = {'portrait': (1080, 1920), 'landscape': (1920, 1080)}.get(draft.aspect, (info.get('width'), info.get('height')))
    if not w or not h:
        raise ValueError('无法读取原视频尺寸')
    w, h = int(w) // 2 * 2, int(h) // 2 * 2
    warnings = []
    draft = recover_empty_packaging(project_id, draft, warnings)
    keep_audio = draft.original_audio and audio.has_audio(video)
    if draft.original_audio and not keep_audio:
        warnings.append('原素材没有音轨，本次导出无声')
    packaged = draft.packaging is not None
    # Template packaging carries its own captions and title; the legacy subtitle/title path stays off.
    entries = _load_srt_entries(project_id) if draft.subtitles and not packaged else []
    # Only transmit the subtitle rows used by this draft, never unrelated transcript text.
    from backend.pipeline.quality import to_seconds
    entries = [e.copy() for e in entries if any(to_seconds(e['start_time']) < s.end and to_seconds(e['end_time']) > s.start for s in draft.scenes)]
    hook = '' if packaged else draft.hook
    if draft.language != 'source' and (hook or entries) and _needs_translation(draft.language, hook, entries):
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
    if draft.subtitles and not entries and not packaged:
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
                duration = audio.scene_duration(scene)
                srt = folder / f'{i}.srt'
                body = slice_srt(entries, scene.start, scene.end, subtitle_line_limit(w, h, draft.subtitle_style))
                if body:
                    srt.write_text(body, encoding='utf-8')
                title = folder / 'title.txt'
                if hook and i == 0:
                    import textwrap
                    title.write_text('\n'.join(textwrap.wrap(hook, width=14)), encoding='utf-8')
                spec = {'layout': draft.layout, 'w': w, 'h': h}
                req = ExportRequest(project_id, draft.id, layout=draft.layout)
                if packaged:
                    from backend.services.studio import packaging_render
                    ass_path = folder / f'{i}.ass'
                    ass_path.write_text(packaging_render.scene_ass(draft.packaging, draft.scenes, i), encoding='utf-8')
                    built = packaging_render.scene_video_graph(draft, scene, i, ass_path, w, h)
                else:
                    built = _build_filter(req, spec, srt if body else None, title if hook and i == 0 and draft.title_style == 'plain' else None, font, draft.subtitle_style)
                clip_path = folder / f'{i}.mkv'
                artwork = None
                backdrop = None
                if hook and i == 0 and draft.title_style in title_art.STYLES:
                    artwork = folder / 'title-art.png'
                    artwork.write_bytes(title_art.png_bytes(hook, draft.title_style, w, h, **title_art.options_for(draft)))
                    if draft.title_style == 'frosted':
                        from backend.services.studio.title_materials import backdrop_png
                        backdrop = folder / 'backdrop.png'
                        backdrop.write_bytes(backdrop_png(hook, draft.title_style, w, h, **title_art.options_for(draft)))
                cmd = [get_ffmpeg_path(), '-v', 'error', *render_limits.input_args(), '-ss', str(scene.start), '-i', str(video)]
                if artwork:
                    cmd += ['-loop', '1', '-i', str(artwork)]
                if backdrop:
                    cmd += ['-loop', '1', '-framerate', '30', '-i', str(backdrop)]
                silence_input = 1 + int(artwork is not None) + int(backdrop is not None)
                if keep_audio:
                    cmd += ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000']
                cmd += ['-t', str(duration)]
                graph = None
                if built:
                    graph, last = built
                    graph = graph.replace(':reload=0', ':expansion=none:reload=0').replace(':fontsize=42:', f':fontsize={max(18, round(w * .06))}:').replace(f'[fg]scale={w}:-2[fg2]', f'[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fg2]')
                    if draft.layout == 'crop':
                        from backend.services.studio.framing import layout_filter
                        graph = graph.replace(f'[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[base]', layout_filter(scene, draft.crop_x, w, h))
                    if backdrop:
                        # Keep all three inputs on one clock and use RGB masks:
                        # a gray mask converted to YUV has neutral chroma (128),
                        # which otherwise blends colors outside the card.
                        from backend.services.studio.title_materials import blur_sigma
                        graph += f";[{last}]fps=30,settb=AVTB,setpts=PTS-STARTPTS,format=gbrp,split[sharp][glasssource];[glasssource]gblur=sigma={blur_sigma(w)}[blurred];[2:v]fps=30,settb=AVTB,setpts=PTS-STARTPTS,alphaextract,format=gbrp[glassmask];[sharp][blurred][glassmask]maskedmerge=enable='lt(t,4)'[glassbase]"
                        last = 'glassbase'
                    if artwork:
                        x, y = title_art.overlay_motion(draft.title_style, draft.title_motion, h)
                        graph += f";[1:v]format=rgba[titleart];[{last}][titleart]overlay=x='{x}':y='{y}':enable='lt(t,4)':shortest=1[styled]"
                        last = 'styled'
                    elif hook and i == 0 and draft.title_style != 'plain':
                        titles, last = template_filters(hook, draft.title_style, w, h, folder, font, last, scene.end-scene.start)
                        graph += ';' + ';'.join(titles)
                    cmd += ['-map', f'[{last}]']
                else:
                    cmd += ['-map', '0:v:0']
                if keep_audio:
                    graph = ';'.join(filter(None, [graph, audio.cut_filters(silence_input, duration)]))
                    cmd += ['-map', '[audioout]', '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2']
                else:
                    cmd += ['-an']
                if draft.caption_mask:
                    graph, masked_map = _mask_captions(graph, draft.caption_mask)
                    if masked_map:
                        cmd[cmd.index('0:v:0') - 1:cmd.index('0:v:0') + 1] = ['-map', masked_map]
                if graph:
                    cmd += ['-filter_complex', graph]
                from backend.services import video_encoder

                def build(name, base=cmd, clip_path=clip_path):
                    return [*base, *video_encoder.h264_args(w, h, name), '-r', '30', *render_limits.output_args(), '-y', str(clip_path)]

                def run(full, length=scene.end - scene.start):
                    full, priority = render_limits.low_priority(full)
                    return subprocess.run(full, capture_output=True, text=True, timeout=max(180, length * 20), **priority)

                proc = video_encoder.run_with_fallback(build, run)
                if proc.returncode:
                    raise RuntimeError('渲染镜头失败：' + proc.stderr[-600:])
                parts.append(clip_path)
                progress(round(10 + (i+1) / len(draft.scenes) * 80))
            concat = folder / 'parts.txt'
            durations = [audio.scene_duration(scene) for scene in draft.scenes]
            concat.write_text(''.join(f"file '{p}'\nduration {duration:.9f}\n" for p, duration in zip(parts, durations)), encoding='utf-8')
            # Encode AAC only once. Per-cut AAC packets add encoder delay and can
            # leave mismatched stream layouts when a selected interval is silent.
            cmd = [get_ffmpeg_path(), '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-map', '0:v:0', '-c:v', 'copy']
            if keep_audio:
                cmd += ['-map', '0:a:0', '-af', 'aresample=48000:async=1:first_pts=0', '-c:a', 'aac', '-b:a', '160k']
            else:
                cmd += ['-an']
            cmd += ['-t', str(sum(durations)), '-movflags', '+faststart', '-y', str(partial)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=max(180, sum(durations)*2))
            from backend.services.output_branding import append_outro
            outro_applied = append_outro(partial, output, width=w, height=h, enabled=brand_outro)
            if brand_outro and not outro_applied:
                warnings.append('品牌片尾未能添加，已保留成片')
        return {'title': draft.title, 'duration': _probe(output).get('duration'), 'width': w, 'height': h, 'warnings': warnings, 'outro_applied': outro_applied}
    finally:
        partial.unlink(missing_ok=True)
