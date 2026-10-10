#!/usr/bin/env python3
"""Build silent 2.5s editing-style previews.

Each style writes three files under frontend/src/assets/editing-style/:

  <id>.poster.webp   270x480, a frame from the same clip, at most 30KB
  <id>.preview.webm  VP9, 216x384, 24fps, 2.5s, no audio, at most 120KB
  <id>.preview.mp4   H.264, same picture, at most 120KB

The nine files together stay at or under 500KB, and every file stays under
300KB. Pass a real render with --video <id>=/path/to.mp4. Square footage is
centered on a darkened blur so the frame is 9:16. Without --video the script
falls back to the stills in scripts/fixtures/editing-style/.

  python scripts/build_template_previews.py --video editorial=/path.mp4
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
# Representative windows inside the supplied renders, after the title has settled.
CLIP_START = {'editorial': 1.8, 'street': 6.0, 'classic': 8.0}


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


def source_size(path: Path) -> tuple[int, int]:
    probe = shutil.which('ffprobe')
    if not probe:
        raise SystemExit('ffprobe is required')
    completed = subprocess.run(
        [probe, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0:s=x', str(path)],
        capture_output=True, text=True,
    )
    if completed.returncode != 0 or 'x' not in completed.stdout:
        raise SystemExit(completed.stderr[-500:] or f'could not read {path}')
    width, height = completed.stdout.strip().split('x', 1)
    return int(width), int(height)


def needs_portrait_pad(width: int, height: int) -> bool:
    if height <= 0:
        return False
    return abs((width / height) - (9 / 16)) > 0.04


def render_graph(pad: bool) -> str:
    """Fill 9:16, or center a non-portrait frame on a darkened blur."""
    if not pad:
        return (
            f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},'
            f'fps={FPS},format=yuv420p,setsar=1'
        )
    return (
        '[0:v]split[fg0][bg0];'
        f'[bg0]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},'
        'boxblur=16:2,eq=brightness=-0.22:saturation=0.5,setsar=1[bg];'
        f'[fg0]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,setsar=1[fg];'
        f'[bg][fg]overlay=x=(W-w)/2:y=(H-h)/2,fps={FPS},format=yuv420p,tpad=stop_mode=clone:stop_duration=0.08,trim=duration={DURATION},setpts=PTS-STARTPTS[v]'
    )


def encode_video(ff: str, source: Path | None, frames: list[Path], dest: Path, codec: str, style: str) -> None:
    """Prefer a real render when one is passed. Otherwise build from stills."""
    if source and source.exists():
        width, height = source_size(source)
        pad = needs_portrait_pad(width, height)
        graph = render_graph(pad)
        qualities = (36, 42, 48, 52) if codec == 'webm' else (28, 32, 36, 40)
        encode_base = ['-c:v', 'libvpx-vp9', '-b:v', '0', '-deadline', 'good', '-cpu-used', '2', '-row-mt', '1', '-an'] if codec == 'webm' else ['-c:v', 'libx264', '-preset', 'slow', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an']
        start = str(CLIP_START.get(style, 0))
        for quality in qualities:
            command = [ff, '-y', '-ss', start, '-t', str(DURATION), '-i', str(source)]
            if pad:
                command.extend(['-filter_complex', graph, '-map', '[v]'])
            else:
                command.extend(['-vf', graph, '-map', '0:v:0'])
            command.extend([*encode_base, '-crf', str(quality), '-an', str(dest)])
            run(command)
            if fit(dest, VIDEO_MAX):
                return
        raise SystemExit(f'{dest.name} is still over {VIDEO_MAX} bytes')
    for quality in ((34, 40, 46, 52) if codec == 'webm' else (26, 30, 34, 38)):
        encode_pair(ff, frames, dest, codec, quality)
        if fit(dest, VIDEO_MAX):
            return
    raise SystemExit(f'{dest.name} is still over {VIDEO_MAX} bytes')


def poster_from_clip(ff: str, clip: Path, dest: Path) -> None:
    """Poster is one frame of the silent clip, not a separate still."""
    for quality in (68, 58, 48, 38, 28):
        run([ff, '-y', '-ss', '0.6', '-i', str(clip), '-frames:v', '1', '-vf', f'scale={POSTER_W}:{POSTER_H}', '-c:v', 'libwebp', '-quality', str(quality), str(dest)])
        if fit(dest, POSTER_MAX):
            return
    raise SystemExit(f'{dest.name} is still over {POSTER_MAX} bytes')


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
        source = videos.get(style)
        frames = stills_for(style)
        if source is None and not frames[0].exists():
            raise SystemExit(f'missing still {frames[0]}')
        if source is not None and not source.exists():
            raise SystemExit(f'missing render {source}')
        webm = OUT / f'{style}.preview.webm'
        encode_video(ff, source, frames, webm, 'webm', style)
        encode_video(ff, source, frames, OUT / f'{style}.preview.mp4', 'mp4', style)
        if source is not None:
            poster_from_clip(ff, webm, OUT / f'{style}.poster.webp')
        else:
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
