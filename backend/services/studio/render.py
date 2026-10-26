"""Render immutable draft snapshots using the existing ffmpeg layout/subtitle code."""
from backend.core.failure_codes import UserFacingError
import logging
import os
import math
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
from backend.services.studio.templates.spec import HTML_TEMPLATE_IDS, STYLE_IDS
from backend.services import render_limits
from backend.utils.ffmpeg_utils import get_ffmpeg_path
from backend.core import project_cancellation

logger = logging.getLogger(__name__)
_SUBTITLE_TRANSLATION_PROMPT = (
    '将 title 和 cues 翻译成指定语言。cues 是带编号 n 的字幕，按编号逐条翻译，'
    '不要合并、拆分或增删条目，不添加事实。'
    '只返回 {"title":"...","cues":[{"n":1,"text":"..."}]}。'
)


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


def _cue_number(value, fallback):
    if type(value) is int:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return fallback


def _parse_translated_cues(translated, count):
    """Map cue number to text. A list of strings is numbered by position."""
    if not isinstance(translated, dict):
        return None, {}, 0
    title = translated.get('title')
    title = title if isinstance(title, str) and len(title) <= 500 else None
    raw = translated.get('cues')
    if not isinstance(raw, list):
        raw = translated.get('subtitles')
    if not isinstance(raw, list):
        return title, {}, 0
    aligned = {}
    returned = 0
    for index, item in enumerate(raw, start=1):
        if isinstance(item, str):
            number, text = index, item
        elif isinstance(item, dict):
            number = _cue_number(item.get('n', item.get('id', item.get('index'))), index)
            text = item.get('text')
        else:
            continue
        if not isinstance(text, str):
            continue
        returned += 1
        if 1 <= number <= count and number not in aligned:
            aligned[number] = text
    return title, aligned, returned


def _apply_cue_translation(hook, entries, title, aligned):
    if title is not None:
        hook = title
    for index, entry in enumerate(entries, start=1):
        text = aligned.get(index)
        if isinstance(text, str):
            entry['text'] = text
    return hook


def _translate_hook_and_cues(language, hook, entries, warnings):
    """Translate by cue number. One retry, then source text fills any gap."""
    payload = [{'n': index, 'text': entry.get('text', '')} for index, entry in enumerate(entries, start=1)]
    source_count = len(entries)
    best = None
    for _ in range(2):
        title, aligned, returned = _parse_translated_cues(text_json(
            _SUBTITLE_TRANSLATION_PROMPT, {'language': language, 'title': hook, 'cues': payload},
        ), source_count)
        if len(aligned) == source_count and returned == source_count:
            return _apply_cue_translation(hook, entries, title, aligned)
        if best is None or len(aligned) >= len(best[1]):
            best = (title, aligned, returned)
    title, aligned, returned = best
    missing = source_count - len(aligned)
    logger.warning(
        'subtitle translation mismatch source_count=%s returned_count=%s missing_count=%s',
        source_count, returned, missing,
    )
    if missing > 0:
        warnings.append('部分字幕未能翻译，已保留原文')
    return _apply_cue_translation(hook, entries, title, aligned)


def recover_empty_packaging(project_id, draft: Draft, warnings: list[str]) -> Draft:
    pack = draft.packaging
    if not (draft.subtitles and pack and pack.captions_enabled and pack.fallback and not pack.cues and not pack.burned_captions):
        return draft
    # Previously saved fallbacks have no cues. Re-rendering them must recover the source
    # track too; changing only new packaging would leave upgraded projects captionless.
    from backend.services.studio.packaging import draft_lines, source_cues
    from backend.services.studio.models import Packaging
    lines = draft_lines(_load_srt_entries(project_id), [scene.model_dump() for scene in draft.scenes])
    cues = source_cues(lines, pack.audience_language)
    warnings.append('包装未能完整生成，已使用原字幕' if cues else '包装未能完整生成，字幕暂不可用')
    return draft.model_copy(update={'packaging': Packaging.model_validate({**pack.model_dump(), 'cues': cues})})


def _output_offsets(draft: Draft) -> list[float]:
    from backend.services.studio.packaging_render import timeline
    return [row[2] for row in timeline(draft.scenes)]


def _template_report(job, encoder: str) -> dict | None:
    if job is None:
        return None
    return {
        'template': job.template,
        'requested_template': job.requested_template,
        'encoder': encoder,
        'downgraded': job.downgraded,
        'downgrade_reason': job.downgrade_reason,
        'failure_reason': job.failure_reason,
        'outcome': job.outcome,
        'duration_ms': job.duration_ms,
    }


def _decoded_extent(progress_output) -> tuple:
    """(seconds, frames) from ``ffmpeg -progress pipe:1``; end time = last pts + one frame."""
    text = progress_output.decode('utf-8', 'ignore') if isinstance(progress_output, bytes) else str(progress_output or '')
    out_us, frames = None, 0
    for line in text.splitlines():
        key, _, value = line.partition('=')
        try:
            if key == 'out_time_us' and value.strip().lstrip('-').isdigit():
                out_us = int(value)
            elif key == 'frame':
                frames = int(value)
        except ValueError:
            continue
    return (None if out_us is None else max(0, out_us) / 1_000_000), frames


def _tolerance(fps) -> float:
    return max(0.5, 2 / fps if fps and fps > 0 else 0.5)


def _decoded_video_seconds(path, fps, expected) -> float:
    """Fully decode every default stream (video AND audio, ) and return the decoded video
    duration (frames / fps), measured separately from the audio-inclusive progress clock.
    Any decoder error (including a corrupt audio tail) rejects the output. A timeout stays a
    typed TimeoutExpired (error_code=timeout)."""
    try:
        decoded = project_cancellation.run(
            [get_ffmpeg_path(), '-v', 'error', '-xerror', '-nostats', '-progress', 'pipe:1',
             '-i', str(path), '-f', 'null', '-'],
            check=True, capture_output=True, timeout=max(120, (expected or 0) * 2))
    except (subprocess.CalledProcessError, OSError):
        raise UserFacingError('渲染输出无效，请重新导出') from None
    if (decoded.stderr or b'').strip():
        raise UserFacingError('渲染输出无效，请重新导出')
    _seconds, frames = _decoded_extent(decoded.stdout)
    if frames <= 0:
        raise UserFacingError('渲染输出无效，请重新导出')
    return frames / (fps if fps and fps > 0 else 30)


def render_draft(project_id, video, draft: Draft, job_id, progress, *, brand_outro=False, html_template=None, html_fallback=None, features=None, safe_area='xiaohongshu', requested_template=None):
    info = _probe(video)
    validate_scenes(draft.scenes, info.get('duration', 0))
    w, h = {'portrait': (1080, 1920), 'landscape': (1920, 1080)}.get(draft.aspect, (info.get('width'), info.get('height')))
    if not w or not h:
        raise UserFacingError('无法读取原视频尺寸')
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
        hook = _translate_hook_and_cues(draft.language, hook, entries, warnings)
    font = resolve_cjk_font()
    if hook and draft.title_style not in title_art.STYLES and not font:
        raise UserFacingError('缺少中文字体，无法烧录开头文字，请安装 Noto Sans CJK')
    if draft.subtitles and not entries and not packaged:
        warnings.append('原素材没有可用字幕，本次未烧录字幕')
    project_cancellation.checkpoint(project_id)
    overlay_path = None
    overlay_grade = ''
    overlay_job = None
    if html_template in HTML_TEMPLATE_IDS:
        from backend.services.studio import packaging_html
        from backend.services.studio.templates.registry import TemplateRegistryError, get
        try:
            overlay_grade = get(html_template).base.grade or ''
            overlay_job = packaging_html.prepare_overlay(
                project_id, html_template, draft.packaging,
                sum(audio.scene_duration(scene) for scene in draft.scenes),
                features=features, safe_area=safe_area, scenes=draft.scenes,
            )
        except (project_cancellation.ProjectDeleted, project_cancellation.JobStopped):
            raise
        except (TemplateRegistryError, OSError) as error:
            packaging_html.report_overlay_failure(error)
            overlay_job = packaging_html.OverlayJob(None, 'classic', True, 'capture', 'capture', 'downgraded', requested_template=html_template)
        overlay_path = overlay_job.path if overlay_job else None
    elif html_fallback == 'rank':
        from backend.services.studio.packaging_html import OverlayJob
        requested = requested_template if requested_template in HTML_TEMPLATE_IDS else 'classic'
        overlay_job = OverlayJob(None, 'classic', False, 'rank', 'none', 'skipped', requested_template=requested)
    out_dir = directory(project_id) / 'output' / 'studio'
    if not directory(project_id).is_dir():
        raise project_cancellation.ProjectDeleted(project_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f'{job_id}.mp4'
    partial = out_dir / f'{job_id}.part.mp4'
    ready = out_dir / f'{job_id}.ready.part.mp4'
    try:
        with tempfile.TemporaryDirectory(prefix='ac-studio-render-') as temp:
            folder = Path(temp)
            offsets = _output_offsets(draft)
            clip_total = (offsets[-1] + audio.scene_duration(draft.scenes[-1])) if draft.scenes else 0.0
            overlay_retried = False
            from backend.services.studio.packaging_html import HtmlRetry
            while True:
                parts = []
                try:
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
                        scene_overlay = overlay_path
                        if scene_overlay:
                            from backend.services.studio import packaging_html, packaging_render
                            if html_template == 'street' and draft.layout == 'crop':
                                picture, label = packaging_render.street_picture(
                                    draft, scene, int(info.get('width') or 0), int(info.get('height') or 0), index=i,
                                )
                            else:
                                picture, label = packaging_render.picture_only(draft, scene, w, h)
                            # Street and editorial paint captions in the template safe zone.
                            # The cover owns the title; this overlay does not burn a headline.
                            tail, label = packaging_html.composite_tail(
                                label, 1, w, h, overlay_grade,
                                template=html_template or '', offset=offsets[i], total=clip_total,
                            )
                            built = (picture + ';' + tail, label)
                        elif packaged:
                            from backend.services.studio import packaging_render
                            ass_path = folder / f'{i}.ass'
                            ass_path.write_text(packaging_render.scene_ass(draft.packaging, draft.scenes, i), encoding='utf-8')
                            built = packaging_render.scene_video_graph(draft, scene, i, ass_path, w, h)
                        else:
                            built = _build_filter(req, spec, srt if body else None, title if hook and i == 0 and draft.title_style == 'plain' else None, font, draft.subtitle_style)
                        clip_path = folder / f'{i}.mkv'
                        artwork = None
                        backdrop = None
                        if scene_overlay:
                            pass
                        elif hook and i == 0 and draft.title_style in title_art.STYLES:
                            artwork = folder / 'title-art.png'
                            artwork.write_bytes(title_art.png_bytes(hook, draft.title_style, w, h, **title_art.options_for(draft)))
                            if draft.title_style == 'frosted':
                                from backend.services.studio.title_materials import backdrop_png
                                backdrop = folder / 'backdrop.png'
                                backdrop.write_bytes(backdrop_png(hook, draft.title_style, w, h, **title_art.options_for(draft)))
                        cmd = [get_ffmpeg_path(), '-v', 'error', *render_limits.input_args(), '-ss', str(scene.start), '-i', str(video)]
                        if scene_overlay:
                            # Overlay is the second input. Scene time is the output offset into that movie.
                            cmd += ['-ss', f'{max(0.0, offsets[i]):.3f}', '-i', str(scene_overlay)]
                        elif artwork:
                            cmd += ['-loop', '1', '-i', str(artwork)]
                        if backdrop:
                            cmd += ['-loop', '1', '-framerate', '30', '-i', str(backdrop)]
                        silence_input = 1 + int(scene_overlay is not None) + int(artwork is not None) + int(backdrop is not None)
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
                            elif hook and i == 0 and not scene_overlay and draft.title_style != 'plain':
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
                            return project_cancellation.run(full, capture_output=True, text=True, timeout=max(180, length * 20), **priority)

                        proc = video_encoder.run_with_fallback(build, run)
                        if proc.returncode and scene_overlay:
                            # One classic retry for the whole clip. An encoder miss must not fail the export.
                            from backend.services.studio.packaging_html import OverlayJob
                            overlay_path = None
                            overlay_job = OverlayJob(None, 'classic', True, 'encode', 'encode', 'downgraded', requested_template=html_template or 'classic')
                            raise HtmlRetry()
                        if proc.returncode:
                            raise RuntimeError('渲染镜头失败：' + proc.stderr[-600:])
                        parts.append(clip_path)
                        progress(round(10 + (i+1) / len(draft.scenes) * 80))
                    break
                except (project_cancellation.ProjectDeleted, project_cancellation.JobStopped):
                    raise
                except HtmlRetry:
                    if overlay_retried:
                        raise RuntimeError('渲染镜头失败') from None
                    overlay_retried = True
                except Exception as error:
                    # A hang, filter error or encode error on the HTML path becomes classic.
                    # The classic retry, and a deleted project, still fail the export.
                    if overlay_path is None or overlay_retried:
                        raise
                    from backend.services.studio.packaging_html import OverlayJob
                    packaging_html.report_overlay_failure(error)
                    overlay_path = None
                    overlay_job = OverlayJob(None, 'classic', True, 'capture', 'capture', 'downgraded', requested_template=html_template or 'classic')
                    overlay_retried = True
            concat = folder / 'parts.txt'
            durations = [audio.scene_duration(scene) for scene in draft.scenes]
            # One listing for classic and HTML overlay. Surrounding quotes break paths that contain '.
            from backend.services.studio.packaging_html import concat_quote
            concat.write_text(''.join(f"file {concat_quote(part)}\nduration {duration:.9f}\n" for part, duration in zip(parts, durations)), encoding='utf-8')
            # Encode AAC only once. Per-cut AAC packets add encoder delay and can
            # leave mismatched stream layouts when a selected interval is silent.
            cmd = [get_ffmpeg_path(), '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-map', '0:v:0', '-c:v', 'copy']
            if keep_audio:
                # Preview and QA both expect -14 LUFS / -1 dBTP. Classic mixes measured
                # around -22 LUFS when this pass was HTML-only. A failed measurement
                # keeps the plain resample.
                audio_filter = 'aresample=48000:async=1:first_pts=0'
                measured = audio.measure_loudnorm(['-f', 'concat', '-safe', '0', '-i', str(concat)], project_cancellation.run, max(120, sum(durations)))
                audio_filter = audio.loudnorm_filter(measured)
                cmd += ['-map', '0:a:0', '-af', audio_filter, '-c:a', 'aac', '-b:a', '160k']
            else:
                cmd += ['-an']
            cmd += ['-t', str(sum(durations)), '-movflags', '+faststart', '-y', str(partial)]
            project_cancellation.run(cmd, check=True, capture_output=True, timeout=max(180, sum(durations)*2))
            from backend.services.output_branding import append_outro
            body_seconds = None
            if brand_outro:
                # the outro must not mask a short main body; validate the body alone
                # (<= tolerance) before it is concatenated with the end card.
                body_probe = _probe(partial)
                body_fps = body_probe.get('fps') or 30
                body_seconds = _decoded_video_seconds(partial, body_fps, sum(durations))
                if body_seconds < sum(durations) - _tolerance(body_fps):
                    raise UserFacingError('渲染输出无效，请重新导出')
            outro_report = {}
            outro_applied = append_outro(partial, ready, width=w, height=h, enabled=brand_outro, report=outro_report)
            if brand_outro and not outro_applied:
                warnings.append('品牌片尾未能添加，已保留成片')
        if overlay_job is not None and overlay_job.downgraded and getattr(overlay_job, 'requested_template', None) in HTML_TEMPLATE_IDS:
            from backend.services.packaging_runtime import downgrade_warning
            hint = downgrade_warning(overlay_job.downgrade_reason)
            if hint and hint not in warnings:
                warnings.append(hint)
        validated = _probe(ready)
        duration = validated.get('duration') or 0
        if (not ready.is_file() or ready.stat().st_size == 0 or
                not math.isfinite(duration) or duration <= 0 or
                not validated.get('width') or not validated.get('height')):
            raise UserFacingError('渲染输出无效，请重新导出')
        # probe metadata survives a truncated mp4 (faststart moov up front); only a
        # full decode proves every frame is readable before the file replaces the saved video.
        # a clean cut at a packet boundary decodes without errors but short, so the
        # decoded extent must also match the container and the drafted content.
        # a decode timeout stays a typed TimeoutExpired (error_code=timeout).
        fps = validated.get('fps') or 30
        tolerance = _tolerance(fps)
        decoded_seconds = _decoded_video_seconds(ready, fps, duration)
        if (decoded_seconds < duration - tolerance
                or decoded_seconds < sum(durations) - tolerance
                or (outro_applied and body_seconds is not None and decoded_seconds <= body_seconds)):
            raise UserFacingError('渲染输出无效，请重新导出')
        # with the outro, the total must match body + the outro actually used
        # (|decoded - (body + outro)| <= 0.5 s); container metadata alone can look normal.
        # an applied outro always carries a positive duration; never skip the check.
        outro_seconds = outro_report.get('outro_seconds') if outro_applied else None
        if outro_applied and (not isinstance(outro_seconds, (int, float)) or not math.isfinite(outro_seconds) or outro_seconds <= 0):
            raise UserFacingError('渲染输出无效，请重新导出')
        if (outro_applied and body_seconds is not None
                and abs(decoded_seconds - (body_seconds + outro_seconds)) > 0.5):
            raise UserFacingError('渲染输出无效，请重新导出')
        project_cancellation.checkpoint(project_id)
        os.replace(ready, output)
        result = {'title': draft.title, 'duration': duration, 'width': w, 'height': h, 'warnings': warnings, 'outro_applied': outro_applied}
        if overlay_job is not None:
            from backend.services import video_encoder
            result['template_render'] = _template_report(overlay_job, video_encoder.encoder())
            result['template'] = overlay_job.template
            result['requested_template'] = overlay_job.requested_template
        else:
            requested = requested_template if requested_template in STYLE_IDS else 'classic'
            result['template'] = 'classic'
            result['requested_template'] = requested
        return result
    finally:
        partial.unlink(missing_ok=True)
        ready.unlink(missing_ok=True)
