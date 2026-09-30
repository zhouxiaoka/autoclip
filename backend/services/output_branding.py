"""Final output branding shared by Studio and legacy exports."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from backend.services.publish_export import resolve_cjk_font
from backend.utils.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

OUTRO_SECONDS = 1.0
OUTRO_VERSION = "v1"


def _font_arg() -> str:
    font = resolve_cjk_font()
    if not font:
        return "font='Sans'"
    path = str(font).replace(':', r'\:')
    return f"fontfile='{path}'"


def _stream_params(source: Path) -> dict:
    """Video time base / fps and audio layout of the content, so the outro concatenates by copy."""
    raw = subprocess.run([
        get_ffprobe_path(), '-v', 'error', '-show_entries', 'stream=codec_type,time_base,r_frame_rate,sample_rate,channels',
        '-of', 'json', str(source),
    ], check=True, capture_output=True, text=True, timeout=30).stdout
    streams = json.loads(raw).get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), {})
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), {})
    timescale = str(video.get('time_base', '1/15360')).split('/')[-1]
    return {
        'timescale': timescale if timescale.isdigit() else '15360',
        'fps': video.get('r_frame_rate') or '30',
        'sample_rate': str(audio.get('sample_rate') or 48000),
        'channels': int(audio.get('channels') or 2),
    }


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
        params = _stream_params(source)
        layout = 'mono' if params['channels'] == 1 else 'stereo'
        drawtext = f"drawtext={_font_arg()}:text='Made with AutoClip':x=(w-text_w)/2:y=(h-text_h)/2:fontsize={max(22, round(width * .035))}:fontcolor=white"
        # Stream copy concat keeps packet timestamps in each file's own time base; the outro
        # must share the content's video timescale and frame rate or its frames collapse.
        subprocess.run([
            ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', f"color=c=0x1A1A19:s={width}x{height}:d={OUTRO_SECONDS}:r={params['fps']}",
            '-f', 'lavfi', '-i', f"anullsrc=channel_layout={layout}:sample_rate={params['sample_rate']}", '-t', str(OUTRO_SECONDS),
            '-vf', drawtext, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', params['fps'],
            '-video_track_timescale', params['timescale'],
            '-c:a', 'aac', '-b:a', '160k', '-ar', params['sample_rate'], '-ac', str(params['channels']),
            '-movflags', '+faststart', '-y', str(outro),
        ], check=True, capture_output=True, timeout=60)
        concat.write_text(f"file '{source}'\nfile '{outro}'\n", encoding='utf-8')
        subprocess.run([
            ffmpeg, '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-map', '0:v:0', '-map', '0:a:0?',
            '-c', 'copy', '-movflags', '+faststart', '-y', str(partial),
        ], check=True, capture_output=True, timeout=120)
        os.replace(partial, destination)
