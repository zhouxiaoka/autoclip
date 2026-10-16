"""R15 #36: an outro whose duration cannot be probed is "not added" (validated body ships,
append_outro returns False, warning shown, reason logged). R15 #38: real media covers the
1.8 s designed outro and the 1 s text-fallback outro. R15 #37: outro cache lives in tmp_path."""
import logging
import shutil
import subprocess

import pytest

from backend.services import output_branding
from backend.services.studio import render, store
from backend.services.studio.models import Draft, Scene

WARNING = '品牌片尾未能添加，已保留成片'


def _clip(path, seconds):
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc=s=320x240:r=30:d={seconds}',
                    '-f', 'lavfi', '-i', f'sine=d={seconds}', '-c:a', 'aac', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart', '-y', str(path)], check=True, capture_output=True)
    return path


def _seconds(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                                check=True, capture_output=True, text=True).stdout)


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
    body = _clip(isolated / 'body.mp4', 2)
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
    body = _clip(isolated / 'body.mp4', 3)
    source = _clip(isolated / 'source.mp4', 5)
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
    body = _clip(isolated / 'body.mp4', 1)
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
    body = _clip(isolated / 'body.mp4', 2)
    out = isolated / 'out.mp4'
    report = {}
    assert output_branding.append_outro(body, out, width=320, height=240, report=report) is True
    assert abs(report['outro_seconds'] - expected) <= 0.1
    assert abs(_seconds(out) - (_seconds(body) + expected)) <= 0.5
    assert bool(list((isolated / 'outro-cache').glob('*.mp4'))) is designed
