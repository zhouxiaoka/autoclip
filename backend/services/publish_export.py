"""
发布导出：按需把一条切片渲成可直接上传的成片。

默认流水线仍出 16:9 stream-copy 素材；用户点「发布导出」才重编码。
一个 ffmpeg 调用：帧精确裁切 + 画幅预设 + 烧字幕 + 标题卡。
方案见 docs/QUALITY_AND_PUBLISH_PLAN.md 线 2。
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from backend.pipeline.quality import to_seconds, to_srt_time, load_srt_chunks
from backend.utils.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)

PRESETS: Dict[str, Dict[str, Any]] = {
    "douyin": {"label": "抖音 9:16", "w": 1080, "h": 1920, "layout": "blur", "max_sec": None},
    "xiaohongshu": {"label": "小红书 9:16", "w": 1080, "h": 1920, "layout": "blur", "max_sec": None},
    "shorts": {"label": "YouTube Shorts", "w": 1080, "h": 1920, "layout": "crop", "max_sec": 60},
    "bilibili": {"label": "B 站横屏", "w": 1920, "h": 1080, "layout": "fit", "max_sec": None},
    "original": {"label": "原画重编码", "w": None, "h": None, "layout": "none", "max_sec": None},
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
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyh.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _escape_filter_path(p: Path) -> str:
    return str(p.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def slice_srt(entries: Sequence[Dict[str, Any]], start: float, end: float) -> str:
    lines: List[str] = []
    idx = 1
    for e in entries:
        try:
            s, t = to_seconds(e["start_time"]), to_seconds(e["end_time"])
        except (KeyError, ValueError):
            continue
        if t <= start or s >= end:
            continue
        ns, nt = max(0.0, s - start), min(end, t) - start
        text = str(e.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        lines.append(f"{idx}\n{to_srt_time(ns)} --> {to_srt_time(nt)}\n{text}\n")
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
def _layout_filters(layout: str, w: Optional[int], h: Optional[int]) -> List[str]:
    if layout == "none" or not w or not h:
        return []
    if layout == "blur":
        return [
            f"[0:v]split=2[bg][fg]",
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=24[bg2]",
            f"[fg]scale={w}:-2[fg2]",
            f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2[base]",
        ]
    if layout == "crop":
        return [f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[base]"]
    if layout == "fit":
        return [f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black[base]"]
    return []


def _build_filter(req: ExportRequest, spec: Dict[str, Any], srt_path: Optional[Path],
                  title_path: Optional[Path], font: Optional[Path]) -> Optional[str]:
    layout = req.layout or spec["layout"]
    parts = _layout_filters(layout, spec.get("w"), spec.get("h"))
    last = "base" if parts else "0:v"
    if srt_path is not None:
        style = "Fontsize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=48,Alignment=2"
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
    clip = load_clip_meta(req.project_id, req.clip_id)
    video = find_source_video(req.project_id)
    start = to_seconds(clip["start_time"])
    end = to_seconds(clip["end_time"])
    duration = max(0.1, end - start)
    warnings: List[str] = []
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
    out_path = out_dir / f"{slug}.mp4"
    meta_path = out_dir / f"{slug}.json"

    if out_path.exists() and out_path.stat().st_size > 0:
        result = {"ok": True, "path": str(out_path), "cached": True, "preset": req.preset,
                  "clip_id": req.clip_id, "title": title, "duration_sec": round(duration, 2),
                  "warnings": warnings}
        return result

    font = resolve_cjk_font()
    if req.title_card and not font:
        warnings.append("没找到中文字体，已跳过标题卡")
    tmpdir = Path(tempfile.mkdtemp(prefix="ac-export-"))
    srt_file = None
    title_file = None
    try:
        if req.subtitles:
            entries = _load_srt_entries(req.project_id)
            body = slice_srt(entries, start, start + duration)
            if body:
                srt_file = tmpdir / "clip.srt"
                srt_file.write_text(body, encoding="utf-8")
            else:
                warnings.append("没有可用字幕，成片不烧字")
        if req.title_card and font:
            title_file = tmpdir / "title.txt"
            title_file.write_text(title[:40], encoding="utf-8")

        built = _build_filter(req, spec, srt_file, title_file if req.title_card else None, font)
        ffmpeg = get_ffmpeg_path()
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error",
               "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{duration:.3f}"]
        maps: List[str] = []
        if built:
            graph, last = built
            cmd += ["-filter_complex", graph, "-map", f"[{last}]"]
        else:
            cmd += ["-map", "0:v:0"]
        cmd += ["-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-y", str(out_path)]
        logger.info("发布导出: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg 失败")[-800])

        info = _probe(out_path)
        result = {
            "ok": True, "cached": False, "path": str(out_path), "preset": req.preset,
            "clip_id": req.clip_id, "project_id": req.project_id, "title": title,
            "duration_sec": info.get("duration") or round(duration, 2),
            "width": info.get("width"), "height": info.get("height"),
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
               "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)]
        raw = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
        data = json.loads(raw)
        stream = (data.get("streams") or [{}])[0]
        return {
            "width": stream.get("width"),
            "height": stream.get("height"),
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
