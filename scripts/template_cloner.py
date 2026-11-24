#!/usr/bin/env python3
"""Reference video/screenshot analyzer and local hot-installer for AutoClip templates.

Turns any viral clip video or screenshot set into a structured visual brief
(keyframes + contact sheet + probe metadata) that an AI Agent can reverse-engineer
into a compliant AutoClip TemplateSpec v2 package, then hot-install directly into
AutoClip's user template directory.

Usage:
  python scripts/template_cloner.py extract-ref /path/to/viral_clip.mp4 --out ./ref_work
  python scripts/template_cloner.py extract-ref /path/to/shot1.png /path/to/shot2.png --out ./ref_work
  python scripts/template_cloner.py install-local ./my_templates/xhs_tech_card
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.studio.templates import catalog
from scripts import template_factory

VIDEO_EXTS = {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi'}
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp'}


def _require_bin(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise SystemExit(f'{name} is required in PATH')
    return found


def _probe_video(ffprobe: str, path: Path) -> dict:
    completed = subprocess.run(
        [
            ffprobe, '-v', 'error',
            '-show_entries', 'format=duration:stream=width,height,r_frame_rate,codec_type',
            '-of', 'json', str(path),
        ],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        raise SystemExit(f'ffprobe failed for {path}: {completed.stderr[-500:]}')
    data = json.loads(completed.stdout)
    width = height = 0
    fps = 30.0
    for stream in data.get('streams') or []:
        if stream.get('codec_type') == 'video':
            width = int(stream.get('width') or 0)
            height = int(stream.get('height') or 0)
            rate = str(stream.get('r_frame_rate') or '30/1')
            if '/' in rate:
                num, den = rate.split('/', 1)
                try:
                    fps = round(float(num) / max(1.0, float(den)), 2)
                except ValueError:
                    fps = 30.0
            break
    duration = float((data.get('format') or {}).get('duration') or 0.0)
    aspect = 'portrait' if height > width else ('square' if width == height and width > 0 else 'landscape')
    return {
        'kind': 'video',
        'source': str(path.resolve()),
        'width': width,
        'height': height,
        'aspect': aspect,
        'fps': fps,
        'duration_sec': round(duration, 2),
    }


def _build_contact_sheet(ffmpeg: str, frames: list[Path], dest: Path) -> Path | None:
    if not frames:
        return None
    cols = min(3, len(frames))
    rows = (len(frames) + cols - 1) // cols
    inputs: list[str] = []
    for frame in frames:
        inputs.extend(['-i', str(frame)])
    scale_parts = [f'[{i}:v]scale=360:-2[s{i}]' for i in range(len(frames))]
    stack_inputs = ''.join(f'[s{i}]' for i in range(len(frames)))
    # Pad with black if grid has empty cells
    if len(frames) == 1:
        filter_complex = '[0:v]scale=540:-2[out]'
    else:
        filter_complex = ';'.join(scale_parts) + f';{stack_inputs}xstack=inputs={len(frames)}:layout='
        # Simple tile via concat when all frames have identical size
        filter_complex = f'{";".join(scale_parts)};{stack_inputs}concat=n={len(frames)}:v=1:a=0,tile={cols}x{rows}[out]'
    completed = subprocess.run(
        [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', *inputs, '-filter_complex', filter_complex, '-map', '[out]', '-frames:v', '1', str(dest)],
        capture_output=True, text=True, check=False,
    )
    return dest if completed.returncode == 0 and dest.is_file() else None


def cmd_extract_ref(args: argparse.Namespace) -> int:
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = [Path(p).expanduser().resolve() for p in args.inputs]
    for src in sources:
        if not src.is_file():
            raise SystemExit(f'Reference file not found: {src}')

    frames: list[Path] = []
    meta: dict = {}

    if len(sources) == 1 and sources[0].suffix.lower() in VIDEO_EXTS:
        video = sources[0]
        ffmpeg = _require_bin('ffmpeg')
        ffprobe = _require_bin('ffprobe')
        meta = _probe_video(ffprobe, video)
        count = max(1, min(12, int(args.frames)))
        dur = max(0.2, float(meta['duration_sec']))
        # Sample across [8%, 92%] to capture intro hook, mid captions, and closing frame.
        stamps = [round(dur * (0.08 + 0.84 * (i / max(1, count - 1))), 2) for i in range(count)] if count > 1 else [round(dur * 0.5, 2)]
        for idx, ts in enumerate(stamps, start=1):
            frame_path = out_dir / f'frame_{idx:02d}_{ts:.2f}s.jpg'
            completed = subprocess.run(
                [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(ts), '-i', str(video), '-frames:v', '1', '-q:v', '3', str(frame_path)],
                capture_output=True, text=True, check=False,
            )
            if completed.returncode == 0 and frame_path.is_file():
                frames.append(frame_path)
        meta['timestamps_sec'] = stamps
        sheet = _build_contact_sheet(ffmpeg, frames, out_dir / 'contact_sheet.jpg')
        meta['contact_sheet'] = str(sheet) if sheet else None
    else:
        for idx, src in enumerate(sources, start=1):
            if src.suffix.lower() not in IMAGE_EXTS:
                raise SystemExit(f'Unsupported reference file type: {src.suffix}')
            dest = out_dir / f'ref_{idx:02d}{src.suffix.lower()}'
            shutil.copy2(src, dest)
            frames.append(dest)
        meta = {
            'kind': 'images',
            'sources': [str(s) for s in sources],
            'count': len(frames),
            'contact_sheet': None,
        }

    meta['frames'] = [str(f) for f in frames]
    brief_path = out_dir / 'reference_brief.json'
    brief_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'brief': str(brief_path), 'frames': len(frames), 'contact_sheet': meta.get('contact_sheet')}, ensure_ascii=False))
    return 0


def cmd_install_local(args: argparse.Namespace) -> int:
    folder = Path(args.folder).resolve()
    spec, _info = template_factory.verify_folder(folder)

    buf = io.BytesIO()
    files = sorted(
        p for p in folder.rglob('*')
        if p.is_file() and not any(part.startswith('.') or part == '__MACOSX' for part in p.relative_to(folder).parts)
    )
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            arcname = f'{folder.name}/{path.relative_to(folder).as_posix()}'
            zi = zipfile.ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, path.read_bytes())

    loaded = catalog.install_from_archive(
        buf.getvalue(),
        expected_id=spec.id,
        source_url=f'local-clone:{folder}',
    )
    print(f'INSTALLED {loaded.spec.id} v{loaded.spec.effective_meta().package_version} -> {loaded.root}')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Clone reference videos/screenshots into AutoClip templates')
    sub = parser.add_subparsers(dest='command', required=True)

    ext = sub.add_parser('extract-ref', help='Extract keyframes and metadata from a reference video or screenshots')
    ext.add_argument('inputs', nargs='+', help='One reference video (.mp4/.mov) or one/more screenshots (.png/.jpg/.webp)')
    ext.add_argument('--out', required=True, help='Working directory for extracted frames and reference_brief.json')
    ext.add_argument('--frames', type=int, default=6, help='Number of evenly spaced keyframes for video input (default 6)')
    ext.set_defaults(func=cmd_extract_ref)

    inst = sub.add_parser('install-local', help='Verify, pack, and hot-install a template folder into AutoClip')
    inst.add_argument('folder', help='Path to the template directory')
    inst.set_defaults(func=cmd_install_local)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
