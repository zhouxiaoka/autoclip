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
