"""An encoder exit status alone must never publish a broken Studio output."""
import subprocess

import pytest

from backend.services.studio import render, store
from backend.services.studio.models import Draft, Scene


def test_successful_encoder_with_invalid_output_cannot_replace_saved_video(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=s=64x64:r=30:d=1', '-y', str(source)], check=True, capture_output=True)
    folder = store.directory('p') / 'output/studio'
    folder.mkdir(parents=True)
    output = folder / 'job.mp4'
    output.write_bytes(b'previous saved video')

    def corrupt_encode(cmd, **kwargs):
        # A successful process can still leave an empty/non-video file. Probe
        # the actual output, rather than treating returncode=0 as acceptance.
        from pathlib import Path
        Path(cmd[-1]).write_bytes(b'invalid mp4')
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(render.project_cancellation, 'run', corrupt_encode)
    draft = Draft(id='d', title='fixture', subtitles=False, original_audio=False,
                  aspect='original', scenes=[Scene(id='s', start=0, end=.5)])
    with pytest.raises(ValueError, match='渲染输出'):
        render.render_draft('p', source, draft, 'job', lambda _: None)
    assert output.read_bytes() == b'previous saved video'
    assert not list(folder.glob('*.part.mp4'))


def test_truncated_output_fails_full_decode_and_keeps_previous_video(tmp_path, monkeypatch):
    """header/probe can look fine on a truncated mp4 (faststart moov up front);
only a full decode catches it. Not published, old output kept, temp files cleaned."""
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=s=320x240:r=30:d=4',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    '-y', str(source)], check=True, capture_output=True)
    folder = store.directory('p') / 'output/studio'
    folder.mkdir(parents=True)
    output = folder / 'job.mp4'
    output.write_bytes(b'previous saved video')
    decodes = []
    real_run = render.project_cancellation.run

    def truncated_encode(cmd, **kwargs):
        from pathlib import Path
        if '-f' in cmd and cmd[cmd.index('-f') + 1] == 'null':
            decodes.append(cmd)
            return real_run(cmd, **kwargs)
        data = source.read_bytes()
        Path(cmd[-1]).write_bytes(data[:int(len(data) * 0.6)])  # cut mid-mdat
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    monkeypatch.setattr(render.project_cancellation, 'run', truncated_encode)
    monkeypatch.setattr(render, '_probe', lambda _p: {'duration': 4.0, 'width': 320, 'height': 240})
    draft = Draft(id='d', title='fixture', subtitles=False, original_audio=False,
                  aspect='original', scenes=[Scene(id='s', start=0, end=.5)])
    with pytest.raises(ValueError, match='渲染输出'):
        render.render_draft('p', source, draft, 'job', lambda _: None)
    assert decodes, 'full decode check must run before publishing'
    assert output.read_bytes() == b'previous saved video'
    assert not list(folder.glob('*.part.mp4'))
