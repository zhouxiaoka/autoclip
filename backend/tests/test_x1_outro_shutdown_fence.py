"""X1: once the desktop shell exits (begin_shutdown) branding must not start ffmpeg/ffprobe."""
import subprocess

import pytest

from backend.core import project_cancellation
from backend.services import output_branding


@pytest.fixture
def spawns(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, *a, **k):
        calls.append(cmd)
        raise AssertionError('child process started after shutdown')

    class FakePopen:
        def __init__(self, cmd, *a, **k):
            calls.append(cmd)
            raise AssertionError('child process started after shutdown')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr(subprocess, 'Popen', FakePopen)
    monkeypatch.setattr(output_branding, '_cache_dir', lambda: tmp_path)
    monkeypatch.setattr(project_cancellation, '_shutting_down', False)
    project_cancellation.begin_shutdown()
    return calls


PARAMS = {'timescale': '15360', 'fps': '30', 'sample_rate': '48000', 'channels': 2}


@pytest.mark.parametrize('bound', [False, True])
def test_designed_outro_spawns_nothing_after_shutdown(spawns, bound):
    token = project_cancellation._current.set('p1') if bound else None
    try:
        with pytest.raises(project_cancellation.ServiceRestarted):
            output_branding._designed_outro(640, 360, PARAMS)
    finally:
        if token is not None:
            project_cancellation._current.reset(token)
    assert spawns == []


def test_text_outro_and_probe_spawn_nothing_after_shutdown(spawns, tmp_path):
    with pytest.raises(project_cancellation.ServiceRestarted):
        output_branding._text_outro(tmp_path / 'o.mp4', 640, 360, PARAMS)
    with pytest.raises(project_cancellation.ServiceRestarted):
        output_branding._stream_params(tmp_path / 'c.mp4')
    assert spawns == []


def test_append_outro_after_shutdown_starts_no_child(spawns, tmp_path):
    source = tmp_path / 'c.mp4'
    source.write_bytes(b'x')
    with pytest.raises(project_cancellation.ServiceRestarted):
        output_branding.append_outro(source, tmp_path / 'out.mp4', width=640, height=360)
    assert spawns == []
