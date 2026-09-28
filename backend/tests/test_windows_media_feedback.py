"""Issue #224: actual JPEG output and bounded metadata probing."""
import subprocess
from pathlib import Path
from PIL import Image
import pytest
from backend.utils.thumbnail_generator import ThumbnailGenerator
from backend.utils.ffmpeg_utils import get_ffmpeg_path
from backend.services import publish_export


@pytest.mark.parametrize('duration', [0.4, 2])
def test_plain_h264_is_not_a_cover_and_thumbnail_is_real_jpeg(tmp_path, duration):
    video = tmp_path / '素材.mp4'
    subprocess.run([get_ffmpeg_path(), '-v', 'error', '-f', 'lavfi', '-i',
                    f'color=c=red:s=160x90:d={duration}', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', '-y', str(video)], check=True, capture_output=True)
    generator = ThumbnailGenerator()
    assert generator._extract_video_cover(video) is None
    thumbnail = generator.generate_thumbnail(video)
    assert thumbnail is not None
    with Image.open(thumbnail) as image:
        image.verify()


def test_probe_timeout_is_bounded_and_becomes_invalid_media(monkeypatch):
    def stalled(command, **kwargs):
        assert kwargs['timeout'] == 20
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])
    monkeypatch.setattr(publish_export.subprocess, 'check_output', stalled)
    assert publish_export._probe(Path('stalled.mp4')) == {}
