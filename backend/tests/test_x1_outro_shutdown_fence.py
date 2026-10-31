"""X1: once the desktop shell exits (begin_shutdown) branding must not start ffmpeg/ffprobe."""
import subprocess

import pytest

from backend.core import project_cancellation
from backend.services import output_branding


@pytest.fixture(autouse=True)
def _reset_shutdown_flag(monkeypatch):
    # begin_shutdown is process-global; never leak it into later test modules.
    monkeypatch.setattr(project_cancellation, '_shutting_down', False)
    yield


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


def test_x1r_unbound_check_and_spawn_share_lock_with_begin_shutdown(monkeypatch, tmp_path):
    """X1r: begin_shutdown between an unlocked check and subprocess.run could still start
    one child. Check+Popen must hold the same lock as begin_shutdown."""
    import threading
    import time

    spawns = []
    project_cancellation._shutting_down = False

    class FakeProc:
        def __init__(self, cmd, *a, **k):
            spawns.append(list(cmd))
            self.args = cmd
            self.returncode = 0
            self.pid = 4242
            self._released = threading.Event()
            # Hold the spawn lock open long enough for begin_shutdown to block on it.
            time.sleep(0.05)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def communicate(self, timeout=None):
            self._released.wait(1)
            return (b'', b'')

        def kill(self):
            self._released.set()

        def poll(self):
            return None if not self._released.is_set() else 0

        def wait(self, timeout=None):
            self._released.wait(timeout or 1)
            return 0

    monkeypatch.setattr(subprocess, 'Popen', FakeProc)
    monkeypatch.setattr(
        subprocess, 'run',
        lambda *a, **k: (_ for _ in ()).throw(AssertionError('unbound must not use subprocess.run')),
    )
    monkeypatch.setattr(output_branding, '_cache_dir', lambda: tmp_path)

    started = threading.Event()
    shutdown_done = threading.Event()
    raised = []

    def branding():
        started.set()
        try:
            output_branding._designed_outro(640, 360, PARAMS)
        except project_cancellation.ServiceRestarted as exc:
            raised.append(exc)
        except AssertionError as exc:
            raised.append(exc)

    def shutdown():
        started.wait(1)
        time.sleep(0.01)  # branding should be inside locked check+Popen
        project_cancellation.begin_shutdown()
        shutdown_done.set()

    t1 = threading.Thread(target=branding)
    t2 = threading.Thread(target=shutdown)
    t1.start()
    t2.start()
    t1.join(2)
    t2.join(2)
    # begin_shutdown must complete; the in-flight spawn that already held the lock may
    # finish, but a second attempt after shutdown must raise and start nothing more.
    assert shutdown_done.is_set()
    first = len(spawns)
    with pytest.raises(project_cancellation.ServiceRestarted):
        output_branding._designed_outro(640, 360, PARAMS)
    assert len(spawns) == first  # no additional child after begin_shutdown returned
    # And the unlocked subprocess.run path is gone.
    assert not any(isinstance(e, AssertionError) for e in raised)


def test_x1r_unbound_never_uses_unlocked_subprocess_run(monkeypatch):
    """X1r memory repro: unlocked shutting_down()+subprocess.run allowed begin_shutdown
    to slip in between. Unbound spawn must go through locked Popen instead."""
    runs = []
    popens = []
    project_cancellation._shutting_down = False

    def spy_run(cmd, *a, **k):
        runs.append(list(cmd))
        raise AssertionError('unbound _ffmpeg must not call subprocess.run')

    class FakeProc:
        def __init__(self, cmd, *a, **k):
            popens.append(list(cmd))
            self.args = cmd
            self.returncode = 0
            self.pid = 7

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def communicate(self, timeout=None):
            return (b'', b'')

        def kill(self):
            pass

    monkeypatch.setattr(subprocess, 'run', spy_run)
    monkeypatch.setattr(subprocess, 'Popen', FakeProc)

    output_branding._ffmpeg(['ffmpeg', '-version'], timeout=1)
    assert runs == []
    assert popens == [['ffmpeg', '-version']]

    project_cancellation.begin_shutdown()
    with pytest.raises(project_cancellation.ServiceRestarted):
        output_branding._ffmpeg(['ffmpeg', '-version'], timeout=1)
    assert runs == []
    assert popens == [['ffmpeg', '-version']]  # no second spawn
