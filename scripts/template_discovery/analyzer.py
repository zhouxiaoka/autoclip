"""Visual layout & style analyzer for viral video candidates.

Designed to be 100% decoupled from scrapers so Stages 3+4 can also power a future
user-facing "upload a 10s reference clip -> clone style" feature.
"""
from __future__ import annotations

import logging
import subprocess
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from scripts.template_discovery.sources import USER_AGENT, CandidateVideo

logger = logging.getLogger(__name__)

# Known template archetypes mapped to our existing catalog IDs (for novelty scoring).
ARCHETYPE_CATALOG_MAP: dict[str, tuple[str, ...]] = {
    'streamer_split': ('streamer_split', 'gta_wasted'),
    'full_bleed_pip': ('streamer_pip',),
    'interview_card': ('interview_card', 'podcast_dark'),
    'knowledge_note': ('xhs_note',),
    'headline_sandwich': (),  # NEW opportunity!
    'blur_canvas_16x9': (),   # NEW opportunity!
    'talking_head_kinetic': ('street', 'editorial'),
}


@dataclass
class StyleAnalysis:
    archetype: str
    aspect: str  # 'portrait' | 'landscape' | 'square'
    width: int = 0
    height: int = 0
    has_split_seam: bool = False
    seam_y_ratio: float | None = None
    has_top_bottom_bars: bool = False
    has_blur_canvas: bool = False
    embedded_facecam_roi: list[float] | None = None
    palette: list[str] = field(default_factory=list)
    keyframe_paths: list[str] = field(default_factory=list)
    existing_match: list[str] = field(default_factory=list)
    is_new_opportunity: bool = False
    notes: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_keyframes(video_path: Path, out_dir: Path, prefix: str, *, count: int = 3) -> list[Path]:
    """Extract evenly spaced keyframes (20%, 50%, 80%) from a local video via OpenCV or ffmpeg."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    try:
        import cv2  # type: ignore[import-not-found]
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            total = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            dur = (total / fps) if (fps > 0 and total > 0) else 5.0
            fracs = [0.2, 0.5, 0.8] if count == 3 else [0.15 + 0.7 * i / max(1, count - 1) for i in range(count)]
            for idx, frac in enumerate(fracs):
                cap.set(cv2.CAP_PROP_POS_MSEC, dur * frac * 1000.0)
                ok, frame = cap.read()
                if ok and frame is not None:
                    dest = out_dir / f'{prefix}_kf{idx}.jpg'
                    cv2.imwrite(str(dest), frame)
                    paths.append(dest)
            cap.release()
            if paths:
                return paths
    except Exception:
        pass

    # Fallback: single ffmpeg frame at 2s
    dest = out_dir / f'{prefix}_kf0.jpg'
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-v', 'error', '-ss', '2', '-i', str(video_path), '-frames:v', '1', str(dest)],
            check=True, timeout=15,
        )
        if dest.is_file():
            paths.append(dest)
    except Exception as exc:
        logger.debug('ffmpeg keyframe fallback failed for %s: %s', video_path, exc)
    return paths


def fetch_thumbnail(url: str, dest: Path) -> Path | None:
    if not url or not url.startswith(('http://', 'https://')):
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            dest.write_bytes(resp.read())
        return dest
    except Exception as exc:
        logger.debug('thumbnail fetch failed for %s: %s', url, exc)
        return None


def _extract_palette(img: Image.Image, n: int = 3) -> list[str]:
    """Extract top N representative hex colors via PIL adaptive palette quantization."""
    small = img.convert('RGB').resize((96, 96), Image.Resampling.BILINEAR)
    pal = small.quantize(colors=max(6, n * 2), method=Image.Quantize.MEDIANCUT)
    palette = pal.getpalette() or []
    counts = sorted(pal.getcolors() or [], key=lambda x: -x[0])
    out: list[str] = []
    for _cnt, idx in counts:
        r, g, b = palette[idx * 3: idx * 3 + 3]
        hx = f'#{r:02X}{g:02X}{b:02X}'
        if hx not in out:
            out.append(hx)
        if len(out) >= n:
            break
    return out


def _image_layout_signals(img: Image.Image) -> dict[str, Any]:
    """Compute lightweight structural layout signals from a single frame (pure Pillow + math)."""
    rgb = img.convert('RGB')
    w, h = rgb.size
    aspect = 'portrait' if h > w * 1.15 else ('landscape' if w > h * 1.15 else 'square')

    # Downscale to 120px wide for fast row-by-row variance & edge-seam profiling.
    sw = 120
    sh = max(60, int(round(sw * h / max(1, w))))
    gray = rgb.resize((sw, sh), Image.Resampling.BILINEAR).convert('L')
    px = list(gray.getdata())
    rows = [px[y * sw:(y + 1) * sw] for y in range(sh)]

    def row_std(row: list[int]) -> float:
        mean = sum(row) / len(row)
        return (sum((v - mean) ** 2 for v in row) / len(row)) ** 0.5

    stds = [row_std(r) for r in rows]
    # 1. Detect horizontal split-screen seam in y ∈ [26%..52%] on portrait frames.
    seam_y: float | None = None
    has_seam = False
    if aspect == 'portrait' and sh >= 100:
        y_lo, y_hi = int(sh * 0.26), int(sh * 0.52)
        diffs: list[tuple[float, int]] = []
        for y in range(y_lo, y_hi):
            diff = sum(abs(rows[y][x] - rows[y - 1][x]) for x in range(sw)) / sw
            diffs.append((diff, y))
        if diffs:
            best_diff, best_y = max(diffs, key=lambda item: item[0])
            med_diff = sorted(d for d, _ in diffs)[len(diffs) // 2]
            if best_diff >= max(24.0, med_diff * 2.4):
                has_seam = True
                seam_y = round(best_y / sh, 3)

    # 2. Detect solid top/bottom poster/card bars (low row std in top 15% and bottom 15%).
    top_band = stds[:max(1, int(sh * 0.14))]
    mid_band = stds[int(sh * 0.30):int(sh * 0.70)]
    bot_band = stds[int(sh * 0.86):]
    top_std = sum(top_band) / len(top_band)
    mid_std = sum(mid_band) / max(1, len(mid_band))
    bot_std = sum(bot_band) / len(bot_band)
    has_bars = aspect == 'portrait' and top_std < 18.0 and bot_std < 18.0 and mid_std > 28.0

    # 3. Detect blur-canvas 16:9 (soft blurred top/bottom bands vs sharp middle 16:9 band).
    has_blur = (
        aspect == 'portrait'
        and not has_bars
        and top_std < mid_std * 0.55
        and bot_std < mid_std * 0.55
        and mid_std > 30.0
    )

    return {
        'width': w,
        'height': h,
        'aspect': aspect,
        'has_split_seam': has_seam,
        'seam_y_ratio': seam_y,
        'has_top_bottom_bars': has_bars,
        'has_blur_canvas': has_blur,
        'palette': _extract_palette(rgb, 3),
    }


def classify_archetype(
    signals: dict[str, Any],
    *,
    track: str,
    embedded_roi: tuple[float, float, float, float] | None = None,
) -> tuple[str, str]:
    """Map visual layout signals + track into one of our viral template archetypes."""
    if embedded_roi is not None and signals['aspect'] == 'landscape':
        return 'streamer_split', '16:9 直播源含角落稳定摄像头，适合一键转全宽上下分屏'
    if signals['has_top_bottom_bars']:
        if track == 'interview':
            return 'interview_card', '上下留白卡片结构 + 居中主画面（访谈/播客卡片风）'
        if track == 'knowledge':
            return 'knowledge_note', '上下留白卡片结构（干货便签风）'
        return 'headline_sandwich', '上下标题/字幕留白三明治结构（适合反转/吃瓜切片）'
    if signals['has_split_seam'] or embedded_roi is not None:
        return 'streamer_split', f"检测到水平分屏中缝 (y={signals['seam_y_ratio']})"
    if signals['has_blur_canvas']:
        return 'blur_canvas_16x9', '居中完整 16:9 + 上下模糊衬底（无摄像头纯游戏/电影感兜底）'
    if track == 'gaming':
        return 'full_bleed_pip', '全屏游戏主画面（适合全屏沉浸或大号圆角反应窗）'
    return 'talking_head_kinetic', '全屏竖版口播 + 居中动态大字幕'


def analyze_candidate(
    cand: CandidateVideo,
    work_dir: Path,
    *,
    existing_catalog_ids: set[str] | None = None,
) -> StyleAnalysis:
    """Analyze a single CandidateVideo (local file or remote thumbnail) into a StyleAnalysis."""
    kf_dir = work_dir / 'keyframes'
    kf_paths: list[Path] = []
    embedded_roi: tuple[float, float, float, float] | None = None

    if cand.local_path and Path(cand.local_path).is_file():
        lp = Path(cand.local_path)
        kf_paths = extract_keyframes(lp, kf_dir, cand.id, count=3)
        try:
            from backend.services.studio import creator_pack as cp
            embedded_roi = cp.detect_embedded_facecam(lp)
        except Exception:
            embedded_roi = None
    elif cand.thumbnail_url:
        thumb = fetch_thumbnail(cand.thumbnail_url, kf_dir / f'{cand.id}_thumb.jpg')
        if thumb is not None:
            kf_paths = [thumb]

    if not kf_paths:
        return StyleAnalysis(
            archetype='talking_head_kinetic',
            aspect='portrait',
            notes='未能获取关键帧或封面，仅保留元数据',
        )

    # Use the middle keyframe (or thumbnail) as primary visual sample.
    primary = kf_paths[len(kf_paths) // 2]
    try:
        with Image.open(primary) as im:
            signals = _image_layout_signals(im)
    except Exception as exc:
        return StyleAnalysis(
            archetype='talking_head_kinetic',
            aspect='portrait',
            keyframe_paths=[str(p) for p in kf_paths],
            notes=f'图像解析失败: {exc}',
        )

    archetype, note = classify_archetype(signals, track=cand.track, embedded_roi=embedded_roi)
    mapped = list(ARCHETYPE_CATALOG_MAP.get(archetype, ()))
    if existing_catalog_ids is not None:
        matched = [tid for tid in mapped if tid in existing_catalog_ids]
    else:
        matched = mapped

    return StyleAnalysis(
        archetype=archetype,
        aspect=signals['aspect'],
        width=signals['width'],
        height=signals['height'],
        has_split_seam=signals['has_split_seam'],
        seam_y_ratio=signals['seam_y_ratio'],
        has_top_bottom_bars=signals['has_top_bottom_bars'],
        has_blur_canvas=signals['has_blur_canvas'],
        embedded_facecam_roi=list(embedded_roi) if embedded_roi is not None else None,
        palette=signals['palette'],
        keyframe_paths=[str(p) for p in kf_paths],
        existing_match=matched,
        is_new_opportunity=len(matched) == 0,
        notes=note,
    )
