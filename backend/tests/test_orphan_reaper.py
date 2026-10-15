"""kill -9 of the backend leaves ffmpeg running; the next start must reap only ours."""
import os
import shutil
import subprocess
import sys
import time

import psutil
import pytest

from backend.core import orphan_reaper

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='fake ffmpeg uses /bin/sleep')


def _fake_ffmpeg(tmp_path, env_token=None):
    exe = tmp_path / 'ffmpeg'
    if not exe.exists():
        shutil.copy(shutil.which('sleep'), exe)
    env = {k: v for k, v in os.environ.items() if k != orphan_reaper.ENV}
    if env_token:
        env[orphan_reaper.ENV] = env_token
    proc = subprocess.Popen([str(exe), '60'], env=env)
    for _ in range(50):
        try:
            if psutil.Process(proc.pid).name() == 'ffmpeg':
                break
        except psutil.Error:
            pass
        time.sleep(0.05)
    return proc


def _dead_owner_token():
    owner = subprocess.Popen([sys.executable, '-c', 'pass'])
    created = psutil.Process(owner.pid).create_time()
    owner.wait()
    return f'{owner.pid}:{created:.3f}'


def test_reaps_only_orphans_of_a_dead_backend(tmp_path, monkeypatch):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan = _fake_ffmpeg(tmp_path, _dead_owner_token())
    unrelated = _fake_ffmpeg(tmp_path)  # user's own ffmpeg: no marker
    live = _fake_ffmpeg(tmp_path, orphan_reaper._owner_token(psutil.Process(os.getppid())))
    try:
        assert orphan_reaper.reap_orphans() == 1
        assert orphan.wait(timeout=5) is not None
        assert unrelated.poll() is None
        assert live.poll() is None
    finally:
        for p in (orphan, unrelated, live):
            p.kill()
            p.wait()


def test_mark_environment_is_inherited_by_children(monkeypatch):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    token = orphan_reaper.mark_environment()
    out = subprocess.check_output([sys.executable, '-c', f'import os;print(os.environ["{orphan_reaper.ENV}"])'])
    assert out.decode().strip() == token
    assert orphan_reaper.find_orphans() == []


def test_reaper_never_raises(monkeypatch):
    monkeypatch.setattr(orphan_reaper, 'find_orphans', lambda: 1 / 0)
    assert orphan_reaper.reap_orphans() == 0


def test_desktop_main_hooks_reaper_before_start():
    src = open(os.path.join(os.path.dirname(__file__), '..', 'desktop_main.py'), encoding='utf-8').read()
    assert src.index('orphan_reaper.reap_orphans()') < src.index('manager.start()')
