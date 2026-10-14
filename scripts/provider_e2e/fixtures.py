"""Generate small, redistributable lavfi + SRT fixtures for the e2e matrix."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def srt_text(lines: tuple[str, ...] | list[str], duration_sec: float) -> str:
    if not lines:
        raise ValueError('fixture needs at least one subtitle line')
    span = duration_sec / len(lines)
    blocks = []
    for index, line in enumerate(lines):
        start = index * span
        end = duration_sec if index == len(lines) - 1 else (index + 1) * span
        blocks.append(f'{index + 1}\n{_stamp(start)} --> {_stamp(end)}\n{line}\n')
    return '\n'.join(blocks) + '\n'


def _stamp(seconds: float) -> str:
    total_ms = int(round(max(0.0, float(seconds)) * 1000))
    hours, rest = divmod(total_ms, 3600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def generate(spec: dict[str, Any], dest: Path) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('ffmpeg is required to generate provider-e2e fixtures')
    video = dest / f"{spec['id']}.mp4"
    duration = float(spec['duration_sec'])
    width, height = int(spec['width']), int(spec['height'])
    command = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error']
    pattern = spec.get('pattern')
    if pattern == 'testsrc':
        command += ['-f', 'lavfi', '-i', f'testsrc=size={width}x{height}:rate=8:duration={duration}']
    elif pattern == 'smptebars':
        command += ['-f', 'lavfi', '-i', f'smptebars=size={width}x{height}:rate=8:duration={duration}']
    else:
        color = spec.get('color') or '0x334455'
        command += ['-f', 'lavfi', '-i', f'color=c={color}:s={width}x{height}:d={duration}:r=8']
    tone = spec.get('tone_hz')
    if tone:
        command += ['-f', 'lavfi', '-i', f'sine=frequency={int(tone)}:sample_rate=16000:duration={duration}']
        command += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'ultrafast', '-crf', '32',
                    '-c:a', 'aac', '-b:a', '32k', '-ac', '1', '-shortest', str(video)]
    else:
        command += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'ultrafast', '-crf', '32',
                    '-an', str(video)]
    subprocess.run(command, check=True, timeout=90)
    if not video.is_file() or video.stat().st_size == 0:
        raise RuntimeError(f'fixture video was not written: {video}')
    record = {
        'id': spec['id'],
        'label': spec['label'],
        'expect': spec['expect'],
        'video': str(video),
        'sha256': sha256_file(video),
        'bytes': video.stat().st_size,
        'duration_sec': duration,
        'width': width,
        'height': height,
        'license': 'generated-test-fixture',
    }
    if spec.get('attach_srt', spec['expect'] == 'succeed'):
        subtitle = dest / f"{spec['id']}.srt"
        subtitle.write_text(srt_text(spec['lines'], duration), encoding='utf-8')
        record['srt'] = str(subtitle)
        record['srt_sha256'] = sha256_file(subtitle)
    else:
        record['srt'] = None
    if spec.get('block_code'):
        record['block_code'] = spec['block_code']
    (dest / f"{spec['id']}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    return record


def generate_all(specs: list[dict[str, Any]], dest: Path) -> list[dict[str, Any]]:
    return [generate(spec, dest) for spec in specs]
