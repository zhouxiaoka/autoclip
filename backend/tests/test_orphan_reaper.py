"""kill -9 of the backend leaves ffmpeg running; the next start must reap only ours.

No module-level win32 skip: quality_gate treats any unexpected skip as a hard fail.
The reap logic is exercised with injected process doubles (no /bin/sleep).
"""
import os
import subprocess
import sys

import psutil
import pytest

from backend.core import orphan_reaper


class _FakeProc:
    """Minimal psutil.Process stand-in for find_orphans / reap_orphans."""

    def __init__(self, pid: int, name: str, environ: dict):
        self.pid = pid
        self.info = {'name': name}
        self._environ = dict(environ)
        self.killed = False

    def environ(self):
        return dict(self._environ)

    def kill(self):
        self.killed = True


def _dead_owner_token():
    owner = subprocess.Popen([sys.executable, '-c', 'pass'])
    created = psutil.Process(owner.pid).create_time()
    owner.wait()
    return f'{owner.pid}:{created:.3f}'


def test_reaps_only_orphans_of_a_dead_backend(monkeypatch):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    current = orphan_reaper.mark_environment()
    dead = _dead_owner_token()
    alive = orphan_reaper._owner_token(psutil.Process())

    orphan = _FakeProc(101, 'ffmpeg', {orphan_reaper.ENV: dead})
    orphan_exe = _FakeProc(102, 'ffmpeg.exe', {orphan_reaper.ENV: dead})  # Windows name
    unrelated = _FakeProc(103, 'ffmpeg', {})  # user's own: no marker
    same_backend = _FakeProc(104, 'ffmpeg', {orphan_reaper.ENV: current})
    other_live = _FakeProc(105, 'ffprobe', {orphan_reaper.ENV: alive})
    other_app = _FakeProc(106, 'chrome', {orphan_reaper.ENV: dead})

    found = orphan_reaper.find_orphans(
        [orphan, orphan_exe, unrelated, same_backend, other_live, other_app])
    assert found == [orphan, orphan_exe]

    waited = []

    def fake_wait(procs, timeout=3.0):
        waited.extend(procs)
        return (list(procs), [])

    monkeypatch.setattr(orphan_reaper, 'find_orphans', lambda: [orphan, orphan_exe])
    monkeypatch.setattr(psutil, 'wait_procs', fake_wait)
    assert orphan_reaper.reap_orphans() == 2
    assert orphan.killed and orphan_exe.killed
    assert waited == [orphan, orphan_exe]
    assert unrelated.killed is False and same_backend.killed is False


def test_mark_environment_is_inherited_by_children(monkeypatch):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    token = orphan_reaper.mark_environment()
    out = subprocess.check_output(
        [sys.executable, '-c', f'import os;print(os.environ["{orphan_reaper.ENV}"])'])
    assert out.decode().strip() == token
    assert orphan_reaper.find_orphans([]) == []


def test_reaper_never_raises(monkeypatch):
    monkeypatch.setattr(orphan_reaper, 'find_orphans', lambda: 1 / 0)
    assert orphan_reaper.reap_orphans() == 0


def test_desktop_main_hooks_reaper_before_start():
    src = open(os.path.join(os.path.dirname(__file__), '..', 'desktop_main.py'), encoding='utf-8').read()
    assert src.index('orphan_reaper.reap_orphans()') < src.index('manager.start()')


# --- R10 #393: independent live owner, PID reuse, AccessDenied ---------------------------

@pytest.fixture
def live_owner():
    """A separate, still-running process that stands in for another live AutoClip backend."""
    owner = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        yield psutil.Process(owner.pid)
    finally:
        owner.kill()
        owner.wait()


def test_ffmpeg_of_another_live_backend_is_never_reaped(monkeypatch, live_owner):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()
    token = orphan_reaper._owner_token(live_owner)
    assert token != os.environ[orphan_reaper.ENV]  # must not short-circuit on "current"
    other_live = _FakeProc(201, 'ffmpeg', {orphan_reaper.ENV: token})
    assert orphan_reaper._owner_alive(*orphan_reaper._parse(token)) is True
    assert orphan_reaper.find_orphans([other_live]) == []


def test_reused_pid_with_a_different_create_time_counts_as_dead(monkeypatch, live_owner):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()
    # The recorded owner had this PID, but the live process using it now started later.
    stale = f'{live_owner.pid}:{live_owner.create_time() - 1000:.3f}'
    orphan = _FakeProc(202, 'ffmpeg', {orphan_reaper.ENV: stale})
    assert orphan_reaper.find_orphans([orphan]) == [orphan]


def test_access_denied_owner_is_treated_as_alive(monkeypatch):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()

    def denied(pid):
        raise psutil.AccessDenied(pid)

    monkeypatch.setattr(psutil, 'Process', denied)
    proc = _FakeProc(203, 'ffmpeg', {orphan_reaper.ENV: '424242:1.000'})
    assert orphan_reaper.find_orphans([proc]) == []


def test_unreadable_environment_is_skipped(monkeypatch):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()

    class Denied(_FakeProc):
        def environ(self):
            raise psutil.AccessDenied(self.pid)

    assert orphan_reaper.find_orphans([Denied(204, 'ffmpeg.exe', {})]) == []
