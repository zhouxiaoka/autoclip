import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def outro_cache(tmp_path, monkeypatch):
    from backend.services import output_branding
    cache = tmp_path / 'outro-cache'
    cache.mkdir()
    monkeypatch.setattr(output_branding, '_cache_dir', lambda: cache)
    return cache


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
    assert 3.6 <= float(result['format']['duration']) <= 4.1  # 2 s content + the 1.8 s designed outro


def test_disabled_outro_moves_content_without_extra_second(source, tmp_path):
    from backend.services.output_branding import append_outro

    output = tmp_path / 'plain.mp4'
    append_outro(source, output, width=640, height=360, enabled=False)
    result = probe(output)
    assert 1.8 <= float(result['format']['duration']) <= 2.2
    assert output.exists() and not source.exists()


@pytest.mark.parametrize('timescale', ['16000', '90000'])
def test_outro_frames_play_for_a_full_second_when_timescales_differ(tmp_path, timescale):
    """Real Studio output uses a 1/16000 video time base; the outro must still get real frame time."""
    from backend.services.output_branding import append_outro

    content = tmp_path / 'content.mp4'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=640x360:d=2:r=30',
        '-f', 'lavfi', '-i', 'sine=f=440:d=2:sample_rate=44100', '-shortest', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-video_track_timescale', timescale, '-y', str(content),
    ], check=True)
    output = tmp_path / 'branded.mp4'
    append_outro(content, output, width=640, height=360, enabled=True)
    raw = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'frame=pts_time', '-of', 'csv=p=0', str(output),
    ], text=True)
    pts = [float(line.split(',')[0]) for line in raw.split() if line.strip(',')]
    assert len(pts) >= 110
    assert pts[-1] - pts[-54] >= 1.6, 'outro frames must span the whole animation, not collapse onto one timestamp'
    assert all(later > earlier for earlier, later in zip(pts[-55:], pts[-54:]))


def test_the_designed_outro_is_used_and_cached_per_output_spec(source, tmp_path, outro_cache):
    from backend.services.output_branding import append_outro
    for name in ('a.mp4', 'b.mp4'):
        content = tmp_path / f'content-{name}'
        content.write_bytes(source.read_bytes())
        append_outro(content, tmp_path / name, width=640, height=360, enabled=True)
    assert len(list(outro_cache.glob('*.mp4'))) == 1  # conformed once, reused
    # The chime plays in the outro: the last second is not silent.
    level = subprocess.run(['ffmpeg', '-v', 'info', '-sseof', '-1.2', '-i', str(tmp_path / 'a.mp4'), '-af', 'volumedetect', '-f', 'null', '-'],
                           capture_output=True, text=True).stderr
    peak = float(level.split('max_volume:')[1].split('dB')[0])
    assert peak > -40
    # The animation's near-black background, not the blue content, ends the video.
    frame = subprocess.run(['ffmpeg', '-v', 'error', '-sseof', '-0.2', '-i', str(tmp_path / 'a.mp4'), '-frames:v', '1', '-vf', 'scale=1:1',
                            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    assert max(frame) < 60


def test_a_failed_outro_delivers_the_video_without_it(tmp_path, monkeypatch):
    from backend.services import output_branding

    def broken(*_args):
        raise subprocess.CalledProcessError(1, 'ffmpeg')
    monkeypatch.setattr(output_branding, '_append', broken)
    source, destination = tmp_path / 'render.mp4', tmp_path / 'final.mp4'
    source.write_bytes(b'video')
    output_branding.append_outro(source, destination, width=1080, height=1920)
    assert destination.read_bytes() == b'video'
    assert not list(tmp_path.glob('*.branding.part.mp4'))


def test_windows_font_paths_survive_the_drawtext_parser(monkeypatch):
    from backend.services import output_branding
    monkeypatch.setattr(output_branding, 'resolve_cjk_font', lambda: 'C:\\Windows\\Fonts\\msyh.ttc')
    assert output_branding._font_arg() == "fontfile='C\\:/Windows/Fonts/msyh.ttc'"
