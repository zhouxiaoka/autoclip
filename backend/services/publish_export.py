"""
发布导出：按需把一条切片渲成可直接上传的成片。

默认流水线仍出 16:9 stream-copy 素材；用户点「发布导出」才重编码。
一个 ffmpeg 调用：帧精确裁切 + 画幅预设 + 烧字幕 + 标题卡。
方案见 docs/QUALITY_AND_PUBLISH_PLAN.md 线 2。
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from backend.pipeline.quality import to_seconds, to_srt_time, load_srt_chunks
from backend.services.platform_strategy import legacy_export_presets
from backend.utils.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)

# Kept for API/CLI callers. Platform semantics live in platform_strategy.py; 1080p60 is a
# delivery format (frame rate), not a platform, so it stays an export-only preset.
PRESETS: Dict[str, Dict[str, Any]] = {
    **legacy_export_presets(),
    "1080p60": {"label": "1080p60", "w": 1920, "h": 1080, "layout": "fit", "fps": 60, "max_sec": None},
}

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


@dataclass
class ExportRequest:
    project_id: str
    clip_id: str
    preset: str = "douyin"
    subtitles: bool = True
    title_card: bool = True
    layout: Optional[str] = None  # 覆盖预设：blur / crop / fit / none
    brand_outro: bool = False


# ---------------------------------------------------------------- resolve ---
def list_presets() -> List[Dict[str, Any]]:
    return [{"key": k, **v} for k, v in PRESETS.items()]


def find_source_video(project_id: str) -> Path:
    from backend.core.path_utils import get_project_directory
    raw = get_project_directory(project_id) / "raw"
    for p in [raw / "input.mp4", raw / "input.mov", raw / "input.mkv", raw / "input.webm"]:
        if p.exists():
            return p
    vids = sorted(raw.glob("input.*"))
    if vids:
        return vids[0]
    raise FileNotFoundError(f"项目 {project_id} 没有源视频（raw/input.*）")


def find_source_srt(project_id: str) -> Optional[Path]:
    from backend.core.path_utils import get_project_directory
    project_dir = get_project_directory(project_id)
    for p in (project_dir / "raw" / "input.srt", project_dir / "metadata" / "input.srt"):
        if p.exists():
            return p
    found = list((project_dir / "metadata").glob("*.srt"))
    return found[0] if found else None


def load_clip_meta(project_id: str, clip_id: str) -> Dict[str, Any]:
    if clip_id.startswith('studio-'):
        from backend.services.studio.publishing import export_meta
        return export_meta(project_id, clip_id)
    from backend.core.path_utils import get_project_directory
    path = get_project_directory(project_id) / "metadata" / "clips_metadata.json"
    if path.exists():
        clips = json.loads(path.read_text(encoding="utf-8"))
        for c in clips:
            if str(c.get("id")) == str(clip_id):
                return c
    raise FileNotFoundError(f"项目 {project_id} 没有切片 {clip_id}")


def resolve_cjk_font() -> Optional[Path]:
    candidates = [
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyh.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _escape_filter_path(p: Path) -> str:
    return str(p.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def slice_srt(entries: Sequence[Dict[str, Any]], start: float, end: float, line_limit: Optional[float] = None) -> str:
    """SRT for [start, end); with `line_limit`, long rows become consecutive screens of ≤ 2 lines."""
    lines: List[str] = []
    idx = 1
    for e in entries:
        try:
            s, t = to_seconds(e["start_time"]), to_seconds(e["end_time"])
        except (KeyError, ValueError):
            continue
        if t <= start or s >= end:
            continue
        if t <= s:
            continue
        text = str(e.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        if line_limit:
            from backend.services.studio.caption_layout import timed_screens
            # Paginate on the source clock BEFORE clipping. A scene starting halfway through
            # a paragraph must not replay all of its earlier words in the remaining time.
            screens = [(a, b, screen.replace('\\N', '\n')) for a, b, screen, _ in timed_screens(text, s, t, line_limit)]
        else:
            screens = [(s, t, text)]
        for a, b, screen in screens:
            a, b = max(a, start) - start, min(b, end) - start
            if b <= a or round(b * 1000) <= round(a * 1000):
                continue
            lines.append(f"{idx}\n{to_srt_time(a)} --> {to_srt_time(b)}\n{screen}\n")
            idx += 1
    return "\n".join(lines)


def _load_srt_entries(project_id: str) -> List[Dict[str, Any]]:
    from backend.core.path_utils import get_project_directory
    from backend.utils.text_processor import TextProcessor
    project_dir = get_project_directory(project_id)
    chunks = load_srt_chunks(project_dir / "metadata")
    if chunks:
        return chunks
    srt = find_source_srt(project_id)
    if srt:
        return TextProcessor.parse_srt(srt)
    return []


# ---------------------------------------------------------------- ffmpeg ---
def blurred_backdrop(w: int, h: int) -> str:
    """Filter chain (no labels) turning the source into a dim, heavily blurred full-canvas backdrop.

    Blurring at 1/8 size is far cheaper than a full-resolution gblur and blurs harder; dimming to
    ~35% keeps text in the source (burned captions, lower thirds) from reading as a ghost copy.
    """
    sw, sh = max(2, w // 8 // 2 * 2), max(2, h // 8 // 2 * 2)
    return (f"scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},gblur=sigma=6,"
            f"colorlevels=romax=0.35:gomax=0.35:bomax=0.35,scale={w}:{h}")


def _layout_filters(layout: str, w: Optional[int], h: Optional[int]) -> List[str]:
    if layout == "none" or not w or not h:
        return []
    if layout == "blur":
        return [
            f"[0:v]split=2[bg][fg]",
            f"[bg]{blurred_backdrop(w, h)}[bg2]",
            f"[fg]scale={w}:-2[fg2]",
            f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2[base]",
        ]
    if layout == "crop":
        return [f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[base]"]
    if layout == "fit":
        return [f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black[base]"]
    return []


# Whole-clip subtitle looks, expressed as libass force_style (colours are &HAABBGGRR).
SUBTITLE_STYLES: Dict[str, str] = {
    # White with a thin dark outline: reads on any footage.
    "clean": "Fontsize=16,Bold=0,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=48,Alignment=2",
    # Large bold white with a heavy outline for phone screens.
    "bold": "Fontsize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,MarginV=56,Alignment=2",
    # White on a translucent dark card.
    "box": "Fontsize=17,Bold=0,PrimaryColour=&H00FFFFFF,BackColour=&H88000000,OutlineColour=&H88000000,BorderStyle=3,Outline=6,Shadow=0,MarginV=52,Alignment=2",
    # Bold yellow with a dark outline, the classic short-video caption.
    "accent": "Fontsize=20,Bold=1,PrimaryColour=&H0000E5FF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,MarginV=56,Alignment=2",
}


def subtitle_line_limit(w: int, h: int, subtitle_style: str = 'clean') -> int:
    """Two-line captions with a width budget for the selected frame and font size.

    SRT uses a 288 px-high libass canvas. Leave horizontal padding and cap density even on
    wide footage; Latin width is measured as 0.55 CJK units by caption_layout.
    """
    style = SUBTITLE_STYLES.get(subtitle_style, SUBTITLE_STYLES['clean'])
    size = float(re.search(r'Fontsize=([0-9.]+)', style).group(1))
    if h > w:
        size = round(size * 0.47, 1)
    return max(1, min(15 if h >= w else 24, int(w / h * 288 * 0.86 / size)))


def portrait_subtitle_style(style: str, factor: float = 0.47) -> str:
    """Scale a force_style for 9:16 output.

    libass lays SRT out on a 288 px-high virtual canvas, so the same Fontsize is ~1.8× larger on
    a 1920 px-high portrait frame than on 1080 px landscape (Fontsize 20 ≈ 133 px, five lines per
    sentence). Scale size, outline, shadow and margin so portrait captions match landscape.
    """
    def scale(match):
        return f"{match.group(1)}={float(match.group(2)) * factor:.1f}"
    return re.sub(r'\b(Fontsize|Outline|Shadow|MarginV)=([0-9.]+)', scale, style)


def _build_filter(req: ExportRequest, spec: Dict[str, Any], srt_path: Optional[Path],
                  title_path: Optional[Path], font: Optional[Path], subtitle_style: str = "clean") -> Optional[str]:
    layout = req.layout or spec["layout"]
    parts = _layout_filters(layout, spec.get("w"), spec.get("h"))
    last = "base" if parts else "0:v"
    if srt_path is not None:
        style = SUBTITLE_STYLES.get(subtitle_style, SUBTITLE_STYLES["clean"])
        if spec.get("w") and spec.get("h") and spec["h"] > spec["w"]:
            style = portrait_subtitle_style(style)
        if font:
            # FontName 给 libass；mac 上 PingFang SC 通常能解析
            style = "FontName=PingFang SC," + style
        nxt = "sub"
        parts.append(f"[{last}]subtitles='{_escape_filter_path(srt_path)}':force_style='{style}'[{nxt}]")
        last = nxt
    if title_path is not None and font is not None:
        nxt = "out"
        parts.append(
            f"[{last}]drawtext=fontfile='{_escape_filter_path(font)}':textfile='{_escape_filter_path(title_path)}'"
            f":reload=0:x=(w-text_w)/2:y=h*0.08:fontsize=42:fontcolor=white:borderw=3:bordercolor=black"
            f":box=1:boxcolor=black@0.45:boxborderw=18:enable='lt(t\\,4)'[{nxt}]"
        )
        last = nxt
    if not parts:
        return None
    # 最后一条没有输出标签时 ffmpeg 也能用，但我们都打了标签：把最后标签接到默认输出
    # filter_complex 最后一个 [tag] 需要 map
    return ";".join(parts), last


def export_clip(req: ExportRequest) -> Dict[str, Any]:
    """同步导出一条切片。幂等：同参数已存在直接返回。"""
    if req.preset not in PRESETS:
        raise ValueError(f"未知预设: {req.preset}（可选 {', '.join(PRESETS)}）")
    spec = PRESETS[req.preset]
    if req.preset == '1080p60' and req.layout not in (None, 'fit'):
        raise ValueError("1080p60 使用固定横屏等比适配，不支持覆盖画幅")
    clip = load_clip_meta(req.project_id, req.clip_id)
    studio = clip.get('source_type') == 'studio'
    if studio and req.preset != '1080p60':
        duration = float(clip['duration_sec'])
        if spec.get('max_sec') and duration > spec['max_sec']:
            raise ValueError(f"成片超过 {req.preset} 的 {spec['max_sec']} 秒限制，请回编辑器调整后重新导出")
        return {'ok': True, 'path': clip['video_path'], 'cached': True, 'preset': 'studio',
                'clip_id': req.clip_id, 'title': clip['title'], 'duration_sec': duration,
                'studio_job_id': clip['studio_job_id'], 'revision': clip['revision'],
                'width': clip['width'], 'height': clip['height'],
                'warnings': [*clip['warnings'], '使用已导出的成片，保留原有画幅、文字和声音，不重复渲染']}
    video = Path(clip['video_path']) if studio else find_source_video(req.project_id)
    start = 0 if studio else to_seconds(clip["start_time"])
    end = float(clip['duration_sec']) if studio else to_seconds(clip["end_time"])
    duration = max(0.1, end - start)
    warnings: List[str] = []
    if studio:
        warnings.append("Studio 成片按 1080p60 重编码，保留已渲染的文字与声音，不重复烧录字幕和标题卡")
    if spec.get("max_sec") and duration > spec["max_sec"]:
        duration = float(spec["max_sec"])
        warnings.append(f"按时长上限截到 {spec['max_sec']}s（{req.preset}）")

    title = str(clip.get("generated_title") or clip.get("title") or clip.get("outline") or f"切片{req.clip_id}")
    from backend.core.path_utils import get_project_directory
    out_dir = get_project_directory(req.project_id) / "output" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{req.clip_id}_{req.preset}"
    if not req.subtitles:
        slug += "_nosub"
    if not req.title_card:
        slug += "_notitle"
    if req.layout:
        slug += f"_{req.layout}"
    if req.subtitles and not studio:
        slug += '_captions-v2'
    if req.brand_outro:
        slug += "_autoclip-outro-v1"
    out_path = out_dir / f"{slug}.mp4"
    meta_path = out_dir / f"{slug}.json"

    if out_path.exists() and out_path.stat().st_size > 0:
        info = _probe(out_path)
        result = {"ok": True, "path": str(out_path), "cached": True, "preset": req.preset,
                  "clip_id": req.clip_id, "title": title, "duration_sec": info.get('duration') or round(duration, 2),
                  "width": info.get('width'), "height": info.get('height'),
                  "fps": info.get('fps'), "video_codec": info.get('video_codec'), "warnings": warnings}
        return result

    font = resolve_cjk_font()
    if req.title_card and not studio and not font:
        warnings.append("没找到中文字体，已跳过标题卡")
    tmpdir = Path(tempfile.mkdtemp(prefix="ac-export-"))
    srt_file = None
    title_file = None
    try:
        if req.subtitles and not studio:
            entries = _load_srt_entries(req.project_id)
            source_info = _probe(video) if not spec.get('w') or not spec.get('h') else spec
            width = source_info.get('w') or source_info.get('width') or 1920
            height = source_info.get('h') or source_info.get('height') or 1080
            body = slice_srt(entries, start, start + duration, subtitle_line_limit(width, height))
            if body:
                srt_file = tmpdir / "clip.srt"
                srt_file.write_text(body, encoding="utf-8")
            else:
                warnings.append("没有可用字幕，成片不烧字")
        if req.title_card and not studio and font:
            title_file = tmpdir / "title.txt"
            title_file.write_text(title[:40], encoding="utf-8")

        built = _build_filter(req, spec, srt_file, title_file if req.title_card else None, font)
        ffmpeg = get_ffmpeg_path()
        temp_output = tmpdir / 'content.mp4'
        from backend.services import render_limits
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", *render_limits.input_args(),
               "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{duration:.3f}"]
        maps: List[str] = []
        if built:
            graph, last = built
            cmd += ["-filter_complex", graph, "-map", f"[{last}]"]
        else:
            cmd += ["-map", "0:v:0"]
        if spec.get('fps'):
            cmd += ["-r", str(spec['fps']), "-fps_mode", "cfr"]
        cmd += ["-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", *render_limits.output_args(),
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-y", str(temp_output)]
        logger.info("发布导出: %s", " ".join(cmd))
        cmd, priority = render_limits.low_priority(cmd)
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", **priority)
        if proc.returncode != 0 or not temp_output.exists() or temp_output.stat().st_size == 0:
            raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg 失败")[-800:])
        from backend.services.output_branding import append_outro
        info = _probe(temp_output)
        append_outro(temp_output, out_path, width=int(info.get('width') or 0), height=int(info.get('height') or 0), enabled=req.brand_outro)
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError('最终成片文件为空')

        info = _probe(out_path)
        result = {
            "ok": True, "cached": False, "path": str(out_path), "preset": req.preset,
            "clip_id": req.clip_id, "project_id": req.project_id, "title": title,
            "duration_sec": info.get("duration") or round(duration, 2),
            "width": info.get("width"), "height": info.get("height"),
            "fps": info.get("fps"), "video_codec": info.get("video_codec"),
            "font": str(font) if font else None, "warnings": warnings,
        }
        meta_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def _probe(path: Path) -> Dict[str, Any]:
    try:
        cmd = [get_ffprobe_path(), "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,avg_frame_rate,codec_name:format=duration", "-of", "json", str(path)]
        raw = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore", timeout=20)
        data = json.loads(raw)
        stream = (data.get("streams") or [{}])[0]
        rate = str(stream.get('avg_frame_rate') or '0/1').split('/')
        fps = float(rate[0]) / float(rate[1]) if len(rate) == 2 and float(rate[1]) else 0
        return {
            "width": stream.get("width"),
            "height": stream.get("height"),
            "fps": round(fps, 3), "video_codec": stream.get("codec_name"),
            "duration": round(float((data.get("format") or {}).get("duration") or 0), 2),
        }
    except Exception as e:  # noqa: BLE001
        logger.debug(f"ffprobe 失败: {e}")
        return {}


# ---------------------------------------------------------------- jobs ---
def start_export(req: ExportRequest) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"job_id": job_id, "status": "queued", "percent": 0, "project_id": req.project_id, "clip_id": req.clip_id}
    t = threading.Thread(target=_run_job, args=(job_id, req), daemon=True, name=f"export-{job_id[:8]}")
    t.start()
    return {"ok": True, "job_id": job_id, "status": "queued"}


def _run_job(job_id: str, req: ExportRequest) -> None:
    with _jobs_lock:
        _jobs[job_id].update(status="running", percent=10)
    try:
        result = export_clip(req)
        with _jobs_lock:
            _jobs[job_id].update(status="completed", percent=100, result=result)
    except Exception as e:  # noqa: BLE001
        logger.exception("发布导出失败")
        with _jobs_lock:
            _jobs[job_id].update(status="failed", percent=100, error=str(e)[:500])


def get_export_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def export_many(project_id: str, clip_ids: Sequence[str], preset: str,
                subtitles: bool = True, title_card: bool = True) -> List[Dict[str, Any]]:
    out = []
    for cid in clip_ids:
        try:
            out.append(export_clip(ExportRequest(project_id, cid, preset, subtitles, title_card)))
        except Exception as e:  # noqa: BLE001
            out.append({"ok": False, "clip_id": cid, "error": str(e)[:400]})
    return out
