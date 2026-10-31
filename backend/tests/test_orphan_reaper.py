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
    """psutil.Process stand-in for the real find_orphans / reap_orphans / psutil.wait_procs.

    kill_outcome: 'exits' (gone after kill), 'denied' (AccessDenied), 'gone' (NoSuchProcess on
    kill — exited in between), 'survives' (kill sent, still running after the wait).
    """

    def __init__(self, pid: int, name: str, environ: dict, kill_outcome: str = 'exits'):
        self.pid = pid
        self.info = {'name': name}
        self._environ = dict(environ)
        self.killed = False
        self.kill_outcome = kill_outcome

    def environ(self):
        return dict(self._environ)

    def kill(self):
        if self.kill_outcome == 'denied':
            raise psutil.AccessDenied(self.pid)
        if self.kill_outcome == 'gone':
            raise psutil.NoSuchProcess(self.pid)
        self.killed = True

    def wait(self, timeout=None):
        if self.kill_outcome == 'survives':
            raise psutil.TimeoutExpired(timeout, self.pid)
        return -9

    def is_running(self):
        return self.kill_outcome == 'survives'

    def __hash__(self):
        return hash(self.pid)

    def __eq__(self, other):
        return self is other


def _dead_owner_token():
    """: deterministic by construction: this test process's pid with a create time 1000 s
earlier than its real one, so that owner is dead by definition (the PID-reuse rule). A child that
just exited is not: on Windows its process object can linger (open handles), psutil then still
returns its create time and the owner reads as alive (CI jobs 117267399378, 117289886647)."""
    return f'{os.getpid()}:{psutil.Process().create_time() - 1000:.3f}'


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

    # Reaping goes through the real reap_orphans(); only the process table is mocked.
    monkeypatch.setattr(psutil, 'process_iter',
                        lambda *a, **k: iter([orphan, orphan_exe, unrelated, same_backend, other_live, other_app]))
    assert orphan_reaper.reap_orphans(timeout=0.1) == 2
    assert orphan.killed and orphan_exe.killed
    assert unrelated.killed is False and same_backend.killed is False and other_app.killed is False
    assert orphan_reaper.LAST_RESULT == {'found': 2, 'exited': 2, 'access_denied': 0, 'still_alive': 0}


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


# 393: independent live owner, PID reuse, AccessDenied

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


def test_kill_outcomes_are_counted_and_logged_separately(monkeypatch, caplog):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()
    dead = _dead_owner_token()
    procs = [
        _FakeProc(301, 'ffmpeg', {orphan_reaper.ENV: dead}, 'exits'),
        _FakeProc(302, 'ffmpeg.exe', {orphan_reaper.ENV: dead}, 'denied'),
        _FakeProc(303, 'ffprobe', {orphan_reaper.ENV: dead}, 'survives'),
        _FakeProc(304, 'ffmpeg', {orphan_reaper.ENV: dead}, 'gone'),
    ]
    monkeypatch.setattr(psutil, 'process_iter', lambda *a, **k: iter(procs))
    with caplog.at_level('WARNING', logger=orphan_reaper.logger.name):
        assert orphan_reaper.reap_orphans(timeout=0.05) == 4
    assert orphan_reaper.LAST_RESULT == {'found': 4, 'exited': 2, 'access_denied': 1, 'still_alive': 1}
    text = caplog.text
    assert 'found=4' in text and 'exited=2' in text and 'access_denied=1' in text and 'still_alive=1' in text


def test_nothing_to_reap_logs_nothing(monkeypatch, caplog):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()
    monkeypatch.setattr(psutil, 'process_iter', lambda *a, **k: iter([_FakeProc(401, 'ffmpeg', {})]))
    with caplog.at_level('WARNING', logger=orphan_reaper.logger.name):
        assert orphan_reaper.reap_orphans(timeout=0.05) == 0
    assert orphan_reaper.LAST_RESULT['found'] == 0
    assert 'Orphaned' not in caplog.text


def test_startup_marks_environment_before_starting_services(monkeypatch):
    """Behavioral: desktop_main.main() reaps, then stamps the owner token, then starts."""
    from backend import desktop_main
    from backend.services import child_guard
    events = []

    class StopStartup(BaseException):
        pass

    class Manager:
        is_running = False

        class config:
            app_version = 'test'

            class paths:
                data_dir = 'x'
            host = '127.0.0.1'

        def start(self):
            events.append(('start', os.environ.get(orphan_reaper.ENV)))
            raise StopStartup()

        def stop(self):
            pass

    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    monkeypatch.setattr(desktop_main, 'get_service_manager', lambda: Manager())
    monkeypatch.setattr(desktop_main, 'is_desktop_mode', lambda: True)
    monkeypatch.setattr(desktop_main.signal, 'signal', lambda *a, **k: None)
    monkeypatch.setattr(child_guard, 'install_hooks', lambda: None)
    monkeypatch.setattr(orphan_reaper, 'reap_orphans',
                        lambda *a, **k: events.append(('reap', os.environ.get(orphan_reaper.ENV))) or 0)
    monkeypatch.setenv('AUTOCLIP_DESKTOP_MODE', 'true')
    with pytest.raises(StopStartup):
        desktop_main.main()
    assert [name for name, _ in events] == ['reap', 'start']
    assert events[0][1] is None  # reaping happens before our own token exists
    token = events[1][1]
    assert token and token == orphan_reaper._owner_token(psutil.Process())


# 415 : one try per process; uncertain reasons reach LAST_RESULT and the log

def test_i559_dead_owner_token_is_dead_by_construction():
    pid, created = orphan_reaper._parse(_dead_owner_token())
    assert pid == os.getpid()
    assert orphan_reaper._owner_alive(pid, created) is False


def _process_raising(monkeypatch, pid_to_error):
    real = psutil.Process

    def process(pid=None):
        if pid in pid_to_error:
            raise pid_to_error[pid]
        return real() if pid is None else real(pid)
    monkeypatch.setattr(psutil, 'Process', process)


def test_i559_unclear_owner_is_kept_counted_and_logged(monkeypatch, caplog):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()
    dead = _dead_owner_token()
    _process_raising(monkeypatch, {424242: psutil.AccessDenied(424242)})
    unclear = _FakeProc(501, 'ffmpeg', {orphan_reaper.ENV: '424242:1.000'})
    orphan = _FakeProc(502, 'ffmpeg', {orphan_reaper.ENV: dead})
    monkeypatch.setattr(psutil, 'process_iter', lambda *a, **k: iter([unclear, orphan]))
    with caplog.at_level('WARNING', logger=orphan_reaper.logger.name):
        assert orphan_reaper.reap_orphans(timeout=0.05) == 1
    assert orphan.killed and not unclear.killed  # unclear is never killed
    assert orphan_reaper.LAST_RESULT.get('uncertain') == {'owner_unclear': 1}
    assert 'owner_unclear=1' in caplog.text


def test_i559_one_unreadable_process_does_not_end_the_scan(monkeypatch, caplog):
    """An environment read that raises something psutil does not wrap (OSError / SystemError) used to
    escape find_orphans: reap_orphans then returned 0 for EVERY process."""
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()
    dead = _dead_owner_token()

    class Broken(_FakeProc):
        def environ(self):
            raise OSError(22, 'invalid')

    procs = [Broken(601, 'ffmpeg.exe', {}), _FakeProc(602, 'ffmpeg', {orphan_reaper.ENV: dead})]
    monkeypatch.setattr(psutil, 'process_iter', lambda *a, **k: iter(procs))
    with caplog.at_level('WARNING', logger=orphan_reaper.logger.name):
        assert orphan_reaper.reap_orphans(timeout=0.05) == 1
    assert procs[1].killed
    assert orphan_reaper.LAST_RESULT.get('uncertain') == {'environ_error': 1}
    assert 'environ_error=1' in caplog.text


def test_i559_owner_check_raising_is_per_process(monkeypatch):
    monkeypatch.delenv(orphan_reaper.ENV, raising=False)
    orphan_reaper.mark_environment()
    dead = _dead_owner_token()
    _process_raising(monkeypatch, {434343: SystemError('psutil internal')})
    odd = _FakeProc(701, 'ffprobe', {orphan_reaper.ENV: '434343:1.000'})
    orphan = _FakeProc(702, 'ffmpeg', {orphan_reaper.ENV: dead})
    monkeypatch.setattr(psutil, 'process_iter', lambda *a, **k: iter([odd, orphan]))
    assert orphan_reaper.reap_orphans(timeout=0.05) == 1
    assert orphan.killed and not odd.killed
    assert orphan_reaper.LAST_RESULT.get('uncertain') == {'owner_error': 1}


def test_i559_scan_ending_exception_is_recorded_by_type(monkeypatch, caplog):
    monkeypatch.setattr(orphan_reaper, 'find_orphans', lambda **k: 1 / 0)
    with caplog.at_level('WARNING', logger=orphan_reaper.logger.name):
        assert orphan_reaper.reap_orphans() == 0
    assert orphan_reaper.LAST_RESULT.get('error') == 'ZeroDivisionError'
    assert 'ZeroDivisionError' in caplog.text
