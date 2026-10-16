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
