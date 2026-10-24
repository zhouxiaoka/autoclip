"""Behavior tests for render validation and outro probing."""
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.services import output_branding
from backend.services.studio import render, store
from backend.services.studio.models import Draft, Scene
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
"""items 21/22: decoded extent must match; decode timeout keeps the timeout code."""


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
            # a real outro adds length after the (separately validated) body.
            listing = destination.with_name('outro-list.txt')
            listing.write_text(f"file '{source}'\nfile '{delivered}'\n")
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                            '-c', 'copy', '-y', str(destination)], check=True, capture_output=True)
            if report is not None:  # an applied outro always reports its proven duration
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
"""body validated alone before the outro (#27), full audio+video decode (#28),
and a decode timeout recorded in the isolated SQLite project index (#29)."""


def _clip__r13_render_validation(path, seconds, audio=False):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc=s=320x240:r=30:d={seconds}']
    if audio:
        cmd += ['-f', 'lavfi', '-i', f'sine=d={seconds}', '-c:a', 'aac']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-y', str(path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


def _render(monkeypatch, body, *, seconds, outro_clip=None, decode=None, appended=None, used_seconds=None):
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
        def append(source, destination, *, report=None, **_k):
            listing = source.with_name('outro-list.txt')
            listing.write_text(f"file '{source}'\nfile '{appended or outro_clip}'\n")
            if report is not None:
                report['outro_seconds'] = used_seconds if used_seconds is not None else _seconds(outro_clip)
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                            '-c', 'copy', '-movflags', '+faststart', '-y', str(destination)], check=True, capture_output=True)
            return True
        monkeypatch.setattr(output_branding, 'append_outro', append)
    draft = Draft(id='d', title='fixture', subtitles=False, original_audio=False,
                  aspect='original', scenes=[Scene(id='s', start=0, end=seconds)])
    source = body.with_name('source-long.mp4')
    if not source.exists():
        _clip__r13_render_validation(source, seconds + 2)
    return render.render_draft('p', source, draft, 'job', lambda _: None, brand_outro=outro_clip is not None)


def test_body_truncated_with_outro_is_rejected(env, monkeypatch):
    tmp, folder, output = env
    body = _clip__r13_render_validation(tmp / 'body.mp4', 1)          # drafted 3 s, body only 1 s
    outro = _clip__r13_render_validation(tmp / 'outro.mp4', 3)        # outro pads the total past 3 s
    with pytest.raises(ValueError, match='渲染输出'):
        _render(monkeypatch, body, seconds=3, outro_clip=outro)
    assert output.read_bytes() == b'previous saved video'


def test_full_body_with_outro_is_published(env, monkeypatch):
    tmp, folder, output = env
    body = _clip__r13_render_validation(tmp / 'body.mp4', 3)
    outro = _clip__r13_render_validation(tmp / 'outro.mp4', 1)
    result = _render(monkeypatch, body, seconds=3, outro_clip=outro)
    assert result['outro_applied'] is True
    assert output.read_bytes() != b'previous saved video'


def test_corrupt_tail_audio_is_rejected(env, monkeypatch):
    tmp, folder, output = env
    video = _clip__r13_render_validation(tmp / 'v.mp4', 3)
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
    clip = _clip__r13_render_validation(tmp / 'av.mp4', 3, audio=True)
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
    clip = _clip__r13_render_validation(tmp / 'slow.mp4', 2)

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


def _concat(listing_dir, parts, out):
    listing = listing_dir / (out.stem + '-list.txt')
    listing.write_text(''.join(f"file '{p}'\n" for p in parts))
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing),
                    '-c', 'copy', '-movflags', '+faststart', '-y', str(out)], check=True, capture_output=True)
    return out


def _seconds(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                                check=True, capture_output=True, text=True).stdout)


def test_r14_body_intact_outro_truncated_with_normal_container_is_rejected(env, monkeypatch):
    tmp, folder, output = env
    body = _clip__r13_render_validation(tmp / 'body.mp4', 3)
    outro = _clip__r13_render_validation(tmp / 'outro.mp4', 3)              # the outro actually used: 3 s
    truncated = _clip__r13_render_validation(tmp / 'outro-cut.mp4', 1)      # only 1 s of it lands in the output
    with pytest.raises(ValueError, match='渲染输出'):
        _render(monkeypatch, body, seconds=3, outro_clip=outro, appended=truncated)
    assert output.read_bytes() == b'previous saved video'


def test_r14_success_is_exactly_body_with_outro_appended(env, monkeypatch):
    tmp, folder, output = env
    body = _clip__r13_render_validation(tmp / 'body.mp4', 3)
    outro = _clip__r13_render_validation(tmp / 'outro.mp4', 1)
    expected = _concat(tmp, [body, outro], tmp / 'expected.mp4')
    result = _render(monkeypatch, body, seconds=3, outro_clip=outro)
    assert result['outro_applied'] is True
    assert output.read_bytes() == expected.read_bytes()
    assert abs(_seconds(output) - (_seconds(body) + _seconds(outro))) <= 0.1


def test_r14_real_append_outro_reports_the_outro_duration_actually_used(tmp_path, monkeypatch):
    # keep the outro cache out of the default data directory.
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr(output_branding, '_cache_dir', lambda: _tmp_cache(tmp_path))
    body = _clip__r13_render_validation(tmp_path / 'body.mp4', 2, audio=True)
    out = tmp_path / 'out.mp4'
    report = {}
    assert output_branding.append_outro(body, out, width=320, height=240, report=report) is True
    assert report['outro_seconds'] > 0
    assert abs(_seconds(out) - (2 + report['outro_seconds'])) <= 0.5
    assert list((tmp_path / 'outro-cache').glob('*.mp4')), 'designed outro was cached under tmp_path'


def _tmp_cache(tmp_path):
    path = tmp_path / 'outro-cache'
    path.mkdir(parents=True, exist_ok=True)
    return path
"""an outro whose duration cannot be probed is "not added" (validated body ships,
append_outro returns False, warning shown, reason logged). #38: real media covers the
1.8 s designed outro and the 1 s text-fallback outro. #37: outro cache lives in tmp_path."""

WARNING = '品牌片尾未能添加，已保留成片'


def _clip__r15_outro_probe(path, seconds):
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc=s=320x240:r=30:d={seconds}',
                    '-f', 'lavfi', '-i', f'sine=d={seconds}', '-c:a', 'aac', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart', '-y', str(path)], check=True, capture_output=True)
    return path


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    cache = tmp_path / 'outro-cache'
    cache.mkdir()
    monkeypatch.setattr(output_branding, '_cache_dir', lambda: cache)
    return tmp_path


def _break_outro_probe(monkeypatch, mode):
    real = output_branding._ffmpeg

    def fake(cmd, timeout, **kwargs):
        if 'stream=duration:format=duration' in cmd:
            if mode == 'timeout':
                raise subprocess.TimeoutExpired(cmd, timeout)
            stdout = {'garbage': '\x00not json{{', 'empty': '{"streams": [{}], "format": {"duration": ""}}'}[mode]
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr='')
        return real(cmd, timeout, **kwargs)

    monkeypatch.setattr(output_branding, '_ffmpeg', fake)


REASONS = {'timeout': 'probe_timeout', 'garbage': 'probe_unreadable', 'empty': 'probe_empty_duration'}


@pytest.mark.parametrize('mode', sorted(REASONS))
def test_outro_probe_failure_delivers_body_and_reports_not_added(isolated, monkeypatch, caplog, mode):
    body = _clip__r15_outro_probe(isolated / 'body.mp4', 2)
    expected = body.read_bytes()
    out = isolated / 'out.mp4'
    _break_outro_probe(monkeypatch, mode)
    report = {}
    with caplog.at_level(logging.WARNING, logger=output_branding.__name__):
        assert output_branding.append_outro(body, out, width=320, height=240, report=report) is False
    assert out.read_bytes() == expected
    assert 'outro_seconds' not in report
    assert not list(isolated.glob('*.branding.part.mp4'))
    messages = [r.getMessage() for r in caplog.records]
    assert f'Outro skipped: {REASONS[mode]}' in messages
    assert not any(str(isolated) in m for m in messages)


@pytest.mark.parametrize('mode', sorted(REASONS))
def test_render_with_unprobeable_outro_ships_validated_body_with_warning(isolated, monkeypatch, mode):
    folder = store.directory('p') / 'output/studio'
    folder.mkdir(parents=True)
    output = folder / 'job.mp4'
    body = _clip__r15_outro_probe(isolated / 'body.mp4', 3)
    source = _clip__r15_outro_probe(isolated / 'source.mp4', 5)
    real_run = render.project_cancellation.run

    def fake(cmd, **kwargs):  # render steps copy the prepared body; decode/probe stay real
        if cmd[-3:] == ['-f', 'null', '-'] or 'ffprobe' in str(cmd[0]):
            return real_run(cmd, **kwargs)
        shutil.copyfile(body, cmd[-1])
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    monkeypatch.setattr(render.project_cancellation, 'run', fake)
    real_probe = render._probe
    monkeypatch.setattr(render, '_probe', lambda p: {**real_probe(p), 'fps': 30})
    _break_outro_probe(monkeypatch, mode)
    draft = Draft(id='d', title='t', subtitles=False, original_audio=False, aspect='original',
                  scenes=[Scene(id='s', start=0, end=3)])
    result = render.render_draft('p', source, draft, 'job', lambda _: None, brand_outro=True)
    assert result['outro_applied'] is False
    assert WARNING in result['warnings']
    assert output.read_bytes() == body.read_bytes()


def test_append_outro_without_valid_duration_never_returns_true(isolated, monkeypatch):
    body = _clip__r15_outro_probe(isolated / 'body.mp4', 1)
    def fake_append(source, partial, *_a):
        shutil.copyfile(source, partial)   # concat "succeeded" but no outro duration was proven
        return None

    monkeypatch.setattr(output_branding, '_append', fake_append)
    out = isolated / 'o.mp4'
    expected = body.read_bytes()
    assert output_branding.append_outro(body, out, width=320, height=240, report={}) is False
    assert out.read_bytes() == expected


@pytest.mark.parametrize('designed,expected', [(True, 1.8), (False, 1.0)])
def test_real_media_outro_duration_designed_and_text_fallback(isolated, monkeypatch, designed, expected):
    if not designed:
        empty = isolated / 'no-assets'
        empty.mkdir()
        monkeypatch.setattr(output_branding, 'OUTRO_DIR', empty)
    body = _clip__r15_outro_probe(isolated / 'body.mp4', 2)
    out = isolated / 'out.mp4'
    report = {}
    assert output_branding.append_outro(body, out, width=320, height=240, report=report) is True
    assert abs(report['outro_seconds'] - expected) <= 0.1
    assert abs(_seconds(out) - (_seconds(body) + expected)) <= 0.5
    assert bool(list((isolated / 'outro-cache').glob('*.mp4'))) is designed
