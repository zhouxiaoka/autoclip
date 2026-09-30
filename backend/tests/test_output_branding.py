import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'content.mp4'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=640x360:d=2:r=30',
        '-f', 'lavfi', '-i', 'sine=f=440:d=2', '-shortest', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-y', str(path),
    ], check=True)
    return path


def probe(path: Path):
    raw = subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration', '-of', 'json', str(path),
    ], text=True)
    import json
    return json.loads(raw)


def test_append_outro_preserves_video_and_audio(source, tmp_path):
    from backend.services.output_branding import append_outro

    output = tmp_path / 'branded.mp4'
    append_outro(source, output, width=640, height=360, enabled=True)
    result = probe(output)
    stream_types = {stream['codec_type'] for stream in result['streams']}
    video = next(stream for stream in result['streams'] if stream['codec_type'] == 'video')
    assert output.exists() and output.stat().st_size > 0
    assert video['width'] == 640 and video['height'] == 360
    assert stream_types == {'video', 'audio'}
    assert 2.8 <= float(result['format']['duration']) <= 3.3


def test_disabled_outro_moves_content_without_extra_second(source, tmp_path):
    from backend.services.output_branding import append_outro

    output = tmp_path / 'plain.mp4'
    append_outro(source, output, width=640, height=360, enabled=False)
    result = probe(output)
    assert 1.8 <= float(result['format']['duration']) <= 2.2
    assert output.exists() and not source.exists()
