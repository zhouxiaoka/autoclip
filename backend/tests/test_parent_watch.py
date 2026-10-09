"""RC156 #20: the desktop backend exits with the app, even after `kill -9` of the app.

macOS has no Job Object, so the bundled backend (and its ffmpeg/Whisper children) used to
outlive a killed or crashed app. The Tauri shell now passes AUTOCLIP_PARENT_PID; runs without
it (CLI, MCP, Docker, dev) are not watched at all.
"""
import os
import re
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from backend.core import parent_watch

ROOT = Path(__file__).resolve().parents[2]


def _gone(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True


def _wait(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


# ---------------------------------------------------------------- opt-in only

@pytest.mark.parametrize('environ', [{}, {'AUTOCLIP_PARENT_PID': ''}, {'AUTOCLIP_PARENT_PID': 'abc'},
                                     {'AUTOCLIP_PARENT_PID': '1'}, {'AUTOCLIP_PARENT_PID': '0'}])
def test_runs_without_a_desktop_parent_are_not_watched(environ):
    called = []
    environ = dict(environ)
    assert parent_watch.start(called.append, environ=environ, interval=0.01) is None
    assert 'AUTOCLIP_PARENT_PID' not in environ  # never inherited by our own children
    time.sleep(0.05)
    assert called == []


def test_own_pid_is_not_a_parent():
    assert parent_watch.parent_pid_from_env({'AUTOCLIP_PARENT_PID': str(os.getpid())}) is None


def test_variable_is_consumed_so_children_do_not_inherit_it():
    environ = {'AUTOCLIP_PARENT_PID': str(os.getppid()), 'OTHER': 'x'}
    assert parent_watch.parent_pid_from_env(environ) == os.getppid()
    assert environ == {'OTHER': 'x'}


def test_live_parent_keeps_the_backend_running_and_normal_shutdown_ends_the_watch():
    called = []
    thread = parent_watch.start(called.append, environ={'AUTOCLIP_PARENT_PID': str(os.getppid())}, interval=0.02)
    assert thread is not None
    time.sleep(0.2)
    assert called == [] and thread.is_alive()
    thread.stop.set()
    thread.join(2)
    assert not thread.is_alive() and called == []


def test_exited_parent_triggers_shutdown_once():
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    called = []
    done = threading.Event()
    thread = parent_watch.start(lambda pid: (called.append(pid), done.set()), pid=proc.pid, interval=0.05)
    time.sleep(0.2)
    assert called == []
    proc.kill()
    proc.wait()
    assert done.wait(5)
    thread.join(2)
    assert called == [proc.pid]


def test_parent_already_gone_or_pid_reused_counts_as_gone(monkeypatch):
    proc = subprocess.Popen([sys.executable, '-c', 'pass'])
    proc.wait()
    assert parent_watch.ParentProbe(proc.pid).alive() is False
    # Same PID, different start time (PID reuse): psutil.Process.is_running() says False.
    probe = parent_watch.ParentProbe(os.getppid())
    monkeypatch.setattr(probe._process, 'is_running', lambda: False)
    assert probe.alive() is False


def test_unclear_answer_never_shuts_down(monkeypatch):
    probe = parent_watch.ParentProbe(os.getppid())
    def denied():
        raise psutil.AccessDenied(os.getppid())
    monkeypatch.setattr(probe._process, 'status', denied)
    assert probe.alive() is True


def test_terminate_children_stops_the_whole_tree():
    # Run in a helper process: terminate_children() acts on the *calling* process's children.
    script = textwrap.dedent('''
        import subprocess, sys, time, psutil
        from backend.core.parent_watch import terminate_children
        child = subprocess.Popen([sys.executable, "-c",
            "import subprocess, sys, time; subprocess.Popen([sys.executable, \'-c\', \'import time; time.sleep(60)\']); time.sleep(60)"])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not psutil.Process(child.pid).children():
            time.sleep(0.05)
        grandchild = psutil.Process(child.pid).children()[0].pid
        print(child.pid, grandchild, terminate_children(timeout=3), flush=True)
        child.wait()
    ''')
    out = subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True, timeout=60,
                         env=dict(os.environ, PYTHONPATH=str(ROOT)))
    assert out.returncode == 0, out.stderr
    child, grandchild, count = map(int, out.stdout.split())
    assert count == 2
    assert _wait(lambda: _gone(child) and _gone(grandchild), 10)


# ---------------------------------------------------------------- desktop backend shutdown

def test_shutdown_for_lost_parent_stops_children_server_and_exits_zero(monkeypatch):
    from backend import desktop_main
    calls = []
    monkeypatch.setattr(parent_watch, 'terminate_children', lambda: calls.append('children') or 2)
    disposed = []
    monkeypatch.setattr('backend.core.database.engine', SimpleNamespace(dispose=lambda: disposed.append(True)))
    monkeypatch.setattr(desktop_main.logging, 'shutdown', lambda: calls.append('log-flush'))
    manager = desktop_main.DesktopServiceManager.__new__(desktop_main.DesktopServiceManager)
    manager.logger = desktop_main.logging.getLogger('test')
    manager.server = SimpleNamespace(should_exit=False)
    stopped = threading.Event()
    manager.server_thread = threading.Thread(target=lambda: stopped.wait(5))
    manager.server_thread.start()
    manager.is_running = True
    monkeypatch.setattr(manager.server, 'should_exit', False)

    def exit_(code):
        calls.append(('exit', code))
    original_join = manager.server_thread.join
    def join(timeout=None):
        assert manager.server.should_exit is True  # uvicorn told to stop before we wait for it
        stopped.set()
        original_join(timeout)
    manager.server_thread.join = join

    manager.shutdown_for_lost_parent(4242, exit=exit_, grace=1)

    assert calls == ['children', 'log-flush', ('exit', 0)]
    assert disposed == [True] and manager.is_running is False


def test_desktop_main_starts_the_watch_after_the_server():
    source = (ROOT / 'backend' / 'desktop_main.py').read_text(encoding='utf-8')
    main = source[source.index('def main():'):]
    assert main.index('manager.start()') < main.index('parent_watch.start(manager.shutdown_for_lost_parent)')


def test_tauri_shell_passes_its_own_pid_to_the_backend():
    rust = (ROOT / 'src-tauri' / 'src' / 'backend_manager.rs').read_text(encoding='utf-8')
    assert re.search(r'\.env\(\s*"AUTOCLIP_PARENT_PID",\s*std::process::id\(\)\.to_string\(\)\s*\)', rust)


# ---------------------------------------------------------------- real kill -9 of the parent

CHILD = textwrap.dedent('''
    import logging, os, subprocess, sys, time
    from pathlib import Path
    out = Path(sys.argv[1])
    from backend import desktop_main
    from backend.core import parent_watch
    manager = desktop_main.DesktopServiceManager.__new__(desktop_main.DesktopServiceManager)
    manager.logger = logging.getLogger("child")
    manager.server = None
    manager.server_thread = None
    manager.is_running = True
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])  # stands in for ffmpeg
    assert parent_watch.start(manager.shutdown_for_lost_parent, interval=0.2) is not None
    assert "AUTOCLIP_PARENT_PID" not in os.environ
    out.write_text(f"{os.getpid()} {worker.pid}")
    time.sleep(120)
''')

PARENT = textwrap.dedent('''
    import os, subprocess, sys, time
    env = dict(os.environ, AUTOCLIP_PARENT_PID=str(os.getpid()))
    subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[2]], env=env)
    time.sleep(120)
''')


@pytest.mark.skipif(os.name != 'posix', reason='kill -9 semantics; Windows is covered by the Job Object')
def test_backend_and_its_children_exit_after_kill_9_of_the_app(tmp_path):
    out = tmp_path / 'pids'
    env = dict(os.environ, AUTOCLIP_APP_DIR=str(tmp_path), AUTOCLIP_DATA_DIR=str(tmp_path),
               DATABASE_URL=f"sqlite:///{tmp_path / 'autoclip.db'}", PYTHONPATH=str(ROOT), SENTRY_DSN='')
    env.pop('AUTOCLIP_PARENT_PID', None)
    app = subprocess.Popen([sys.executable, '-c', PARENT, CHILD, str(out)], env=env, cwd=ROOT)
    try:
        assert _wait(lambda: out.exists() and out.read_text().strip(), 60), 'backend stand-in never started'
        backend, worker = map(int, out.read_text().split())
        time.sleep(0.5)
        assert not _gone(backend) and not _gone(worker)
        os.kill(app.pid, signal.SIGKILL)  # what the Mac acceptance run did to the app
        app.wait()
        assert _wait(lambda: _gone(backend), 20), 'backend survived its app'
        assert _wait(lambda: _gone(worker), 20), 'ffmpeg-like child survived'
    finally:
        if app.poll() is None:
            app.kill()
            app.wait()
        if out.exists() and out.read_text().strip():
            for pid in map(int, out.read_text().split()):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
