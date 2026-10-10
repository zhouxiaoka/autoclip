#!/usr/bin/env python3
"""Build silent 2.5s editing-style previews from packaged stills.

Each style writes three files under frontend/src/assets/editing-style/:

  <id>.poster.webp   270x480, at most 30KB
  <id>.preview.webm  VP9, 216x384, 24fps, 2.5s, no audio, at most 120KB
  <id>.preview.mp4   H.264, same picture, at most 120KB

The nine files together stay at or under 500KB, and every file stays under
300KB. Stills ship in scripts/fixtures/editing-style/. A real render can
replace a still via --video <id>=/path/to.mp4.

  python scripts/build_template_previews.py
  python scripts/build_template_previews.py --check
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STILLS = ROOT / 'scripts' / 'fixtures' / 'editing-style'
OUT = ROOT / 'frontend' / 'src' / 'assets' / 'editing-style'
STYLES = ('editorial', 'street', 'classic')
POSTER_MAX = 30 * 1024
VIDEO_MAX = 120 * 1024
FILE_MAX = 300 * 1024
TOTAL_MAX = 500 * 1024
WIDTH, HEIGHT, FPS, DURATION = 216, 384, 24, 2.5
POSTER_W, POSTER_H = 270, 480


def ffmpeg() -> str:
    found = shutil.which('ffmpeg')
    if not found:
        raise SystemExit('ffmpeg is required')
    return found


def run(cmd: list[str]) -> None:
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.stderr[-2000:] or 'ffmpeg failed')


def stills_for(style: str) -> list[Path]:
    if style == 'classic':
        portrait = STILLS / 'classic9x16.jpg'
        return [portrait if portrait.exists() else STILLS / 'classic.jpg']
    primary = STILLS / f'{style}.jpg'
    alternate = STILLS / f'{style}_b.jpg'
    frames = [primary]
    if alternate.exists():
        frames.append(alternate)
    return frames


def fit(path: Path, limit: int) -> bool:
    return path.is_file() and path.stat().st_size <= limit


def encode_pair(ff: str, frames: list[Path], dest: Path, codec: str, quality: int) -> None:
    """Crossfade two real frames, or a barely-there zoom when only one exists."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    scale = f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p'
    if len(frames) >= 2:
        graph = (
            f'[0:v]{scale},setpts=PTS-STARTPTS[a];'
            f'[1:v]{scale},setpts=PTS-STARTPTS[b];'
            f'[a][b]xfade=transition=fade:duration=0.4:offset=1.05,trim=duration={DURATION},setpts=PTS-STARTPTS[v]'
        )
        inputs = ['-loop', '1', '-t', str(DURATION), '-i', str(frames[0]), '-loop', '1', '-t', str(DURATION), '-i', str(frames[1])]
    else:
        frames_n = int(FPS * DURATION)
        graph = (
            f'[0:v]{scale},zoompan=z=\'min(1.03,1+0.0005*on)\':x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':'
            f'd={frames_n}:s={WIDTH}x{HEIGHT}:fps={FPS},format=yuv420p,trim=duration={DURATION},setpts=PTS-STARTPTS[v]'
        )
        inputs = ['-loop', '1', '-i', str(frames[0])]
    if codec == 'webm':
        encode = ['-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', str(quality), '-deadline', 'good', '-cpu-used', '1', '-row-mt', '1', '-an']
    else:
        encode = ['-c:v', 'libx264', '-preset', 'slow', '-crf', str(quality), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an']
    run([ff, '-y', *inputs, '-filter_complex', graph, '-map', '[v]', *encode, '-t', str(DURATION), str(dest)])


def encode_video(ff: str, source: Path | None, frames: list[Path], dest: Path, codec: str) -> None:
    """Prefer a real render when one is passed. Otherwise build from stills."""
    if source and source.exists():
        graph = (
            f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},'
            f'fps={FPS},format=yuv420p,trim=duration={DURATION},setpts=PTS-STARTPTS'
        )
        qualities = (36, 42, 48, 52) if codec == 'webm' else (28, 32, 36, 40)
        encode_base = ['-c:v', 'libvpx-vp9', '-b:v', '0', '-deadline', 'good', '-cpu-used', '1', '-an'] if codec == 'webm' else ['-c:v', 'libx264', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an']
        for quality in qualities:
            crf = ['-crf', str(quality)]
            run([ff, '-y', '-i', str(source), '-vf', graph, *encode_base, *crf, '-t', str(DURATION), str(dest)])
            if fit(dest, VIDEO_MAX):
                return
        raise SystemExit(f'{dest.name} is still over {VIDEO_MAX} bytes')
    for quality in ((34, 40, 46, 52) if codec == 'webm' else (26, 30, 34, 38)):
        encode_pair(ff, frames, dest, codec, quality)
        if fit(dest, VIDEO_MAX):
            return
    raise SystemExit(f'{dest.name} is still over {VIDEO_MAX} bytes')


def poster(ff: str, frame: Path, dest: Path) -> None:
    for quality in (68, 58, 48, 38, 28):
        run([ff, '-y', '-i', str(frame), '-frames:v', '1', '-vf', f'scale={POSTER_W}:{POSTER_H}:force_original_aspect_ratio=increase,crop={POSTER_W}:{POSTER_H}', '-c:v', 'libwebp', '-quality', str(quality), str(dest)])
        if fit(dest, POSTER_MAX):
            return
    raise SystemExit(f'{dest.name} is still over {POSTER_MAX} bytes')


def outputs() -> list[Path]:
    names = []
    for style in STYLES:
        names.extend([OUT / f'{style}.poster.webp', OUT / f'{style}.preview.webm', OUT / f'{style}.preview.mp4'])
    return names


def check() -> int:
    files = outputs()
    missing = [path for path in files if not path.is_file()]
    if missing:
        print('missing ' + ', '.join(str(path.relative_to(ROOT)) for path in missing), file=sys.stderr)
        return 1
    total = 0
    for path in files:
        size = path.stat().st_size
        total += size
        limit = POSTER_MAX if path.suffix == '.webp' else VIDEO_MAX
        print(f'{path.relative_to(ROOT)} {size}')
        if size > FILE_MAX or size > limit:
            print(f'{path.name} exceeds its cap', file=sys.stderr)
            return 1
    print(f'total {total}')
    if total > TOTAL_MAX:
        print(f'total {total} exceeds {TOTAL_MAX}', file=sys.stderr)
        return 1
    return 0


def build(videos: dict[str, Path]) -> None:
    ff = ffmpeg()
    OUT.mkdir(parents=True, exist_ok=True)
    for style in STYLES:
        frames = stills_for(style)
        if not frames[0].exists():
            raise SystemExit(f'missing still {frames[0]}')
        encode_video(ff, videos.get(style), frames, OUT / f'{style}.preview.webm', 'webm')
        encode_video(ff, videos.get(style), frames, OUT / f'{style}.preview.mp4', 'mp4')
        poster(ff, frames[0], OUT / f'{style}.poster.webp')
    if check() != 0:
        raise SystemExit('preview budget check failed')


def parse_videos(values: list[str]) -> dict[str, Path]:
    found = {}
    for item in values:
        if '=' not in item:
            raise SystemExit('--video expects editorial=/path.mp4')
        style, raw = item.split('=', 1)
        if style not in STYLES:
            raise SystemExit(f'unknown style {style}')
        found[style] = Path(raw)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description='Build silent editing-style preview media')
    parser.add_argument('--check', action='store_true', help='only verify the committed files')
    parser.add_argument('--video', action='append', default=[], help='style=/path/to/render.mp4')
    args = parser.parse_args()
    if args.check:
        return check()
    build(parse_videos(args.video))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
