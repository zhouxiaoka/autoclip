"""R12 #413 items 21/22: decoded extent must match; decode timeout keeps the timeout code."""
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.services import output_branding
from backend.services.studio import render, store
from backend.services.studio.models import Draft, Scene


def _clip(path, seconds):
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc=s=320x240:r=30:d={seconds}',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-y', str(path)],
                   check=True, capture_output=True)
    return path


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    folder = store.directory('p') / 'output/studio'
    folder.mkdir(parents=True)
    output = folder / 'job.mp4'
    output.write_bytes(b'previous saved video')
    return tmp_path, folder, output


def _run(monkeypatch, delivered, claimed, *, outro=False, decode=None):
    real_run = render.project_cancellation.run

    def fake(cmd, **kwargs):
        if '-f' in cmd and cmd[cmd.index('-f') + 1] == 'null':
            return decode(cmd, **kwargs) if decode else real_run(cmd, **kwargs)
        shutil.copyfile(delivered, cmd[-1])
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    monkeypatch.setattr(render.project_cancellation, 'run', fake)
    monkeypatch.setattr(render, '_probe', lambda _p: {'duration': claimed, 'width': 320, 'height': 240, 'fps': 30})
    if outro:
        def append(source, destination, *, report=None, **_k):
            # R13 #27: a real outro adds length after the (separately validated) body.
            listing = destination.with_name('outro-list.txt')
            listing.write_text(f"file '{source}'\nfile '{delivered}'\n")
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                            '-c', 'copy', '-y', str(destination)], check=True, capture_output=True)
            if report is not None:  # R15 #36: an applied outro always reports its proven duration
                report['outro_seconds'] = float(subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(delivered)],
                    check=True, capture_output=True, text=True).stdout)
            return True
        monkeypatch.setattr(output_branding, 'append_outro', append)
    draft = Draft(id='d', title='fixture', subtitles=False, original_audio=False,
                  aspect='original', scenes=[Scene(id='s', start=0, end=.5)])
    return render.render_draft('p', delivered, draft, 'job', lambda _: None, brand_outro=outro)


def test_packet_boundary_truncation_decodes_clean_but_short_is_rejected(env, monkeypatch):
    tmp, folder, output = env
    full = _clip(tmp / 'full.mp4', 4)
    short = tmp / 'short.mp4'
    # Clean remux cut at a packet boundary: no decode errors, only 2 s of the claimed 4 s.
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(full), '-t', '2', '-c', 'copy', '-y', str(short)], check=True)
    with pytest.raises(ValueError, match='渲染输出'):
        _run(monkeypatch, short, claimed=4.0)
    assert output.read_bytes() == b'previous saved video'
    assert not list(folder.glob('*.part.mp4'))


def test_outro_full_length_is_published(env, monkeypatch):
    tmp, folder, output = env
    clip = _clip(tmp / 'with-outro.mp4', 3)
    result = _run(monkeypatch, clip, claimed=3.0, outro=True)
    assert result['outro_applied'] is True
    assert output.read_bytes() != b'previous saved video'


def test_outro_truncated_is_rejected(env, monkeypatch):
    tmp, folder, output = env
    clip = _clip(tmp / 'cut-outro.mp4', 1)
    with pytest.raises(ValueError, match='渲染输出'):
        _run(monkeypatch, clip, claimed=3.0, outro=True)
    assert output.read_bytes() == b'previous saved video'


def test_within_tolerance_is_published(env, monkeypatch):
    tmp, folder, output = env
    clip = _clip(tmp / 'ok.mp4', 4)
    _run(monkeypatch, clip, claimed=4.3)
    assert output.read_bytes() == clip.read_bytes()


def test_decode_timeout_keeps_timeout_code_through_the_render_task(env, monkeypatch):
    tmp, folder, output = env
    from backend.services.studio import jobs
    clip = _clip(tmp / 'slow.mp4', 2)

    def timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get('timeout'))

    real_render = render.render_draft
    monkeypatch.setattr(jobs, 'render_draft', lambda project_id, video, draft, job_id, progress, **kw:
                        _run(monkeypatch, clip, claimed=2.0, decode=timeout))
    store.write('p', {
        'drafts': [], 'jobs': [{'job_id': 'job', 'status': 'queued', 'draft_id': 'd'}],
        'output_variants': [{'id': 'v', 'status': 'running', 'render_job_id': 'job'}],
        'generation': {'status': 'rendering'}, 'analysis': {'status': 'running', 'instance': store.INSTANCE},
    })
    monkeypatch.setattr(jobs, 'source', lambda _p: clip)
    jobs._render('p', object(), 'job')
    job = store.read('p')['jobs'][0]
    assert job['status'] == 'failed'
    assert job['error_code'] == 'timeout'
    assert output.read_bytes() == b'previous saved video'
    assert real_render is render.render_draft
