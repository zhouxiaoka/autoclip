"""R13 #413: body validated alone before the outro (#27), full audio+video decode (#28),
and a decode timeout recorded in the isolated SQLite project index (#29)."""
import shutil
import subprocess

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.services import output_branding
from backend.services.studio import render, store
from backend.services.studio.models import Draft, Scene


def _clip(path, seconds, audio=False):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc=s=320x240:r=30:d={seconds}']
    if audio:
        cmd += ['-f', 'lavfi', '-i', f'sine=d={seconds}', '-c:a', 'aac']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-y', str(path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    folder = store.directory('p') / 'output/studio'
    folder.mkdir(parents=True)
    output = folder / 'job.mp4'
    output.write_bytes(b'previous saved video')
    return tmp_path, folder, output


def _render(monkeypatch, body, *, seconds, outro_clip=None, decode=None):
    """Real ffmpeg for decode validation; render steps copy the prepared body into place."""
    real_run = render.project_cancellation.run

    def fake(cmd, **kwargs):
        if cmd[-3:] == ['-f', 'null', '-']:
            return decode(cmd, **kwargs) if decode else real_run(cmd, **kwargs)
        shutil.copyfile(body, cmd[-1])
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    monkeypatch.setattr(render.project_cancellation, 'run', fake)
    real_probe = render._probe
    monkeypatch.setattr(render, '_probe', lambda p: {**real_probe(p), 'fps': 30})
    if outro_clip is not None:
        def append(source, destination, **_k):
            listing = source.with_name('outro-list.txt')
            listing.write_text(f"file '{source}'\nfile '{outro_clip}'\n")
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                            '-c', 'copy', '-movflags', '+faststart', '-y', str(destination)], check=True, capture_output=True)
            return True
        monkeypatch.setattr(output_branding, 'append_outro', append)
    draft = Draft(id='d', title='fixture', subtitles=False, original_audio=False,
                  aspect='original', scenes=[Scene(id='s', start=0, end=seconds)])
    source = body.with_name('source-long.mp4')
    if not source.exists():
        _clip(source, seconds + 2)
    return render.render_draft('p', source, draft, 'job', lambda _: None, brand_outro=outro_clip is not None)


def test_body_truncated_with_outro_is_rejected(env, monkeypatch):
    tmp, folder, output = env
    body = _clip(tmp / 'body.mp4', 1)          # drafted 3 s, body only 1 s
    outro = _clip(tmp / 'outro.mp4', 3)        # outro pads the total past 3 s
    with pytest.raises(ValueError, match='渲染输出'):
        _render(monkeypatch, body, seconds=3, outro_clip=outro)
    assert output.read_bytes() == b'previous saved video'


def test_full_body_with_outro_is_published(env, monkeypatch):
    tmp, folder, output = env
    body = _clip(tmp / 'body.mp4', 3)
    outro = _clip(tmp / 'outro.mp4', 1)
    result = _render(monkeypatch, body, seconds=3, outro_clip=outro)
    assert result['outro_applied'] is True
    assert output.read_bytes() != b'previous saved video'


def test_corrupt_tail_audio_is_rejected(env, monkeypatch):
    tmp, folder, output = env
    video = _clip(tmp / 'v.mp4', 3)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=d=3', '-c:a', 'aac', '-y', str(tmp / 'a.aac')], check=True)
    import random
    data = bytearray((tmp / 'a.aac').read_bytes())
    rng = random.Random(1)
    for i in range(int(len(data) * .7), len(data)):
        if data[i - 1] != 0xFF:
            data[i] = rng.randrange(256)
    (tmp / 'bad.aac').write_bytes(bytes(data))
    muxed = tmp / 'bad-audio.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-i', str(tmp / 'bad.aac'), '-map', '0:v', '-map', '1:a',
                    '-c', 'copy', '-movflags', '+faststart', '-y', str(muxed)], check=True)
    with pytest.raises(ValueError, match='渲染输出'):
        _render(monkeypatch, muxed, seconds=3)
    assert output.read_bytes() == b'previous saved video'


def test_good_audio_video_is_published(env, monkeypatch):
    tmp, folder, output = env
    clip = _clip(tmp / 'av.mp4', 3, audio=True)
    _render(monkeypatch, clip, seconds=3)
    assert output.read_bytes() == clip.read_bytes()


def test_decode_timeout_recorded_in_isolated_sqlite_auto_start_project(env, monkeypatch):
    tmp, folder, output = env
    from backend.models.base import Base
    from backend.models.project import Project, ProjectStatus
    from backend.services.studio import jobs
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr('backend.core.database.SessionLocal', sessions)
    with sessions() as session:
        session.add(Project(id='p', name='synthetic', status=ProjectStatus.PROCESSING,
                            processing_config={'smart_import': {'auto_start': True}}))
        session.commit()
    clip = _clip(tmp / 'slow.mp4', 2)

    def timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get('timeout'))

    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **kw: _render(monkeypatch, clip, seconds=2, decode=timeout))
    store.write('p', {
        'drafts': [{'id': 'd', 'scenes': []}], 'jobs': [{'job_id': 'job', 'status': 'queued', 'draft_id': 'd', 'instance': store.INSTANCE}],
        'output_variants': [{'id': 'v', 'status': 'running', 'render_job_id': 'job', 'draft_id': 'd'}],
        'generation': {'status': 'rendering', 'auto_start': True},
        'analysis': {'status': 'running', 'phase': 'rendering', 'instance': store.INSTANCE},
    })
    monkeypatch.setattr(jobs, 'source', lambda _p: clip)
    jobs._render('p', object(), 'job')
    assert store.read('p')['jobs'][0]['error_code'] == 'timeout'
    with sessions() as session:
        project = session.get(Project, 'p')
        assert project.status == ProjectStatus.FAILED
        assert project.processing_config['studio_generation_error_code'] == 'timeout'
    assert output.read_bytes() == b'previous saved video'
    engine.dispose()
