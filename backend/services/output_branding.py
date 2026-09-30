"""Final output branding shared by Studio and legacy exports."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from backend.services.publish_export import resolve_cjk_font
from backend.utils.ffmpeg_utils import get_ffmpeg_path

OUTRO_SECONDS = 1.0
OUTRO_VERSION = "v1"


def _font_arg() -> str:
    font = resolve_cjk_font()
    if not font:
        return "font='Sans'"
    path = str(font).replace(':', r'\:')
    return f"fontfile='{path}'"


def append_outro(source: Path, destination: Path, *, width: int, height: int, enabled: bool = True) -> None:
    """Append one branded second atomically, preserving the original on failure."""
    partial = destination.with_name(f'{destination.stem}.branding.part.mp4')
    partial.unlink(missing_ok=True)
    if not enabled:
        os.replace(source, destination)
        return
    with tempfile.TemporaryDirectory(prefix='ac-outro-') as tmp:
        outro = Path(tmp) / 'outro.mp4'
        concat = Path(tmp) / 'concat.txt'
        ffmpeg = get_ffmpeg_path()
        drawtext = f"drawtext={_font_arg()}:text='Made with AutoClip':x=(w-text_w)/2:y=(h-text_h)/2:fontsize={max(22, round(width * .035))}:fontcolor=white"
        subprocess.run([
            ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', f'color=c=0x1A1A19:s={width}x{height}:d={OUTRO_SECONDS}:r=30',
            '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000', '-t', str(OUTRO_SECONDS),
            '-vf', drawtext, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-y', str(outro),
        ], check=True, capture_output=True, timeout=60)
        concat.write_text(f"file '{source}'\nfile '{outro}'\n", encoding='utf-8')
        subprocess.run([
            ffmpeg, '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-map', '0:v:0', '-map', '0:a:0?',
            '-c', 'copy', '-movflags', '+faststart', '-y', str(partial),
        ], check=True, capture_output=True, timeout=120)
        os.replace(partial, destination)
