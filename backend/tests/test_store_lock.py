"""Store lock + read-receipt tests, selected by the ``store_lock`` marker (never by file name / round):
the Windows CI job runs ``pytest backend/tests/test_store_lock.py -m store_lock`` against msvcrt.locking."""
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from backend.core import file_lock
from backend.core.sentry_setup import studio_error_code
from backend.services.studio import shutdown_marker, store
from backend.tests.test_failure_attribution import (  # noqa: F401
    _hold_lock_in_child,
    _project__r25_415 as _project,
    _records__r25_415 as _records,
    isolated__r22_415 as isolated,
)

pytestmark = [pytest.mark.store_lock, pytest.mark.usefixtures('isolated')]
ROOT = Path(__file__).resolve().parents[2]
SLACK = 0.12


def test_335_prune_waits_for_a_writer_in_another_process(tmp_path):
    root = shutdown_marker._root()
    _records(root, shutdown_marker._KEEP + 2)
    child = _hold_lock_in_child(tmp_path, 1.5)
    done = threading.Event()
    worker = threading.Thread(target=lambda: (shutdown_marker.prune(root), done.set()))
    worker.start()
    try:
        assert not done.wait(0.6), 'prune scanned/deleted while another process held the store lock'
    finally:
        child.wait(30)
        worker.join(30)
    assert done.is_set()


def test_335_release_waits_for_a_writer_in_another_process(tmp_path):
    """Closes m5 (release without store.lock survived)."""
    root = shutdown_marker._root()
    _records(root, 1)
    name = f'{0:032x}'
    shutdown_marker._consumed[(str(root), name)] = 'unacked'
    child = _hold_lock_in_child(tmp_path, 1.5)
    done = threading.Event()
    worker = threading.Thread(target=lambda: (shutdown_marker.release(name), done.set()))
    worker.start()
    try:
        assert not done.wait(0.6), 'release deleted a record while another process held the store lock'
        assert (root / name).exists()
    finally:
        child.wait(30)
        worker.join(30)
    assert done.is_set()


def test_335_lock_timeout_raises_a_coded_error(tmp_path, monkeypatch):
    from backend.core.sentry_setup import studio_error_code
    child = _hold_lock_in_child(tmp_path, 1.5)
    monkeypatch.setattr(store.lock, 'timeout', 0.2)
    try:
        with pytest.raises(OSError) as caught:
            with store.lock:
                pass
    finally:
        child.wait(30)
    assert getattr(caught.value, 'code', None) == 'store_lock_timeout'
    assert studio_error_code(caught.value) == 'store_lock_timeout'  


def test_335_release_deletes_only_while_holding_the_store_lock(monkeypatch):
    """m5: the reference scan alone being locked is not enough; the unlink must be too."""
    root = shutdown_marker._root()
    _records(root, 1)
    name = f'{0:032x}'
    shutdown_marker._consumed[(str(root), name)] = 'unacked'
    held = []
    real = Path.unlink

    def spy(self, *a, **k):
        if self.name == name:
            held.append(store.lock._is_owned())
        return real(self, *a, **k)
    monkeypatch.setattr(Path, 'unlink', spy)
    shutdown_marker.release(name)
    assert held == [True]


def test_393_non_blocking_acquire_returns_at_once_while_another_process_holds_it(tmp_path, monkeypatch):
    monkeypatch.setattr(store.lock, 'timeout', 5.0)
    child = _hold_lock_in_child(tmp_path, 3)
    try:
        started = time.monotonic()
        got = store.lock.acquire(blocking=False)
        elapsed = time.monotonic() - started
        assert got is False and elapsed < 1.0, elapsed
    finally:
        child.wait(30)

    got = []
    other = threading.Thread(target=lambda: got.append(store.lock.acquire(blocking=False) and (store.lock.release() or True)))
    other.start()
    other.join(10)
    assert got == [True], 'the failed non-blocking attempt leaked the in-process lock'


def test_393_default_acquire_bounds_the_in_process_wait_with_the_same_code(monkeypatch):

    monkeypatch.setattr(store.lock, 'timeout', 0.3)
    held, release = threading.Event(), threading.Event()

    def holder():
        with store.lock:
            held.set()
            release.wait(10)
    other = threading.Thread(target=holder)
    other.start()
    held.wait(5)
    started = time.monotonic()
    try:
        with pytest.raises(file_lock.LockTimeout) as caught:
            with store.lock:
                pass
        assert time.monotonic() - started < 3
        assert studio_error_code(caught.value) == 'store_lock_timeout'
    finally:
        release.set()
        other.join(10)


# thread lock and file lock share ONE deadline

def _hold_file_in_child(path, seconds):
    ready = path.with_suffix('.ready')
    code = textwrap.dedent(f'''
        import time, pathlib
        from backend.core import file_lock
        h = file_lock.acquire(pathlib.Path({str(path)!r}), 5)
        pathlib.Path({str(ready)!r}).write_text('1')
        time.sleep({seconds})
        file_lock.release(h)
    ''')
    child = subprocess.Popen([sys.executable, '-c', code], cwd=str(ROOT))
    deadline = time.monotonic() + 30
    while not ready.exists():
        assert time.monotonic() < deadline and child.poll() is None, 'child never took the file lock'
        time.sleep(0.02)
    return child


def _hold_thread(lock, seconds):
    """Another thread holds only the in-process stage (the file stage belongs to the child)."""
    held = threading.Event()

    def holder():
        with lock._thread:
            held.set()
            time.sleep(seconds)
    other = threading.Thread(target=holder)
    other.start()
    held.wait(5)
    return other


def test_i414_thread_wait_and_file_wait_share_one_deadline(tmp_path):
    """Kills D1 (file wait gets a fresh/2x budget): 0.2s spent on the thread lock leaves the file lock 0.1s."""
    path = tmp_path / 'shared.lock'
    lock = file_lock.ProcessLock(lambda: path, timeout=0.35)
    child = _hold_file_in_child(path, 3)
    holder = _hold_thread(lock, 0.2)
    try:
        started = time.monotonic()
        with pytest.raises(file_lock.LockTimeout):
            lock.acquire()
        elapsed = time.monotonic() - started
        assert elapsed < 0.35 + SLACK, f'waited {elapsed:.2f}s for a 0.35s budget'
    finally:
        holder.join(10)
        child.wait(30)
    assert not lock._is_owned()


def test_i414_explicit_timeout_bounds_the_file_lock_and_returns_false(tmp_path):
    """Kills D3 (explicit timeout ignored by the file stage): returns False within the explicit 0.2s."""
    path = tmp_path / 'explicit.lock'
    lock = file_lock.ProcessLock(lambda: path, timeout=5.0)
    child = _hold_file_in_child(path, 3)
    try:
        started = time.monotonic()
        got = lock.acquire(timeout=0.2)
        elapsed = time.monotonic() - started
        assert got is False and elapsed < 0.2 + SLACK, (got, elapsed)
    finally:
        child.wait(30)
    got = []
    t = threading.Thread(target=lambda: got.append(lock.acquire(timeout=5) and (lock.release() or True)))
    t.start()
    t.join(10)
    assert got == [True], 'the failed explicit attempt leaked the in-process lock'


def test_i414_explicit_timeout_on_the_thread_stage_also_returns_false(tmp_path):
    lock = file_lock.ProcessLock(lambda: tmp_path / 'thread.lock', timeout=5.0)
    holder = _hold_thread(lock, 0.6)
    try:
        started = time.monotonic()
        assert lock.acquire(timeout=0.2) is False
        assert time.monotonic() - started < 0.2 + SLACK
    finally:
        holder.join(10)


# read and clear receipts under _receipt_mutex; only handled receipts go

def test_i419_receipt_appended_during_a_read_survives_its_clear(monkeypatch):
    _project('p419', {'status': 'running', 'phase': 'production', 'run_id': 'r1'})
    path = store.directory('p419') / 'metadata' / 'studio.json'
    late = {'identity': ('analysis', 'r1', 'production'), 'pending': {},
            'message': file_lock.LOCK_TIMEOUT_MESSAGE, 'error_code': file_lock.LOCK_TIMEOUT_CODE}
    real = store._apply_read_receipts
    injected = []

    def interleave(p, data, *args, **kwargs):
        changed = real(p, data, *args, **kwargs)
        if not injected:  # a worker's lock-timeout receipt lands between apply and clear
            injected.append(True)
            store._append_receipt(p, late) if hasattr(store, '_append_receipt') else store._read_failures.setdefault(p, []).append(late)
        return changed
    monkeypatch.setattr(store, '_apply_read_receipts', interleave)
    store.recover('p419')
    assert injected
    assert any(r is late for r in store._read_failures.get(path, [])), 'the late receipt was popped with the bucket'
    monkeypatch.setattr(store, '_apply_read_receipts', real)
    analysis = store.recover('p419')['analysis']
    assert analysis['status'] == 'failed' and analysis['error_code'] == 'store_lock_timeout'
    assert not store._read_failures.get(path)


def test_i419_every_receipt_access_holds_the_mutex():
    """Static guard: no direct _read_failures access outside the three mutex helpers."""
    import re
    src = (ROOT / 'backend/services/studio/store.py').read_text(encoding='utf-8')
    body = re.sub(r'def _(append_receipt|receipts|drop_receipts)\(.*?(?=\ndef |\n@)', '', src, flags=re.S)
    uses = [ln for ln in body.splitlines() if '_read_failures' in ln and not ln.startswith('_read_failures = ')]
    assert uses == [], uses


def test_i419_receipt_carries_no_unread_lock_timeout_flag():
    src = (ROOT / 'backend/services/studio/store.py').read_text(encoding='utf-8')
    assert "'lock_timeout'" not in src


def test_r27_phase_frozen_is_gone():
    """write-only ``phase_frozen`` removed (phase_identity being non-empty is the freeze)."""
    from backend.core import llm_emit
    assert 'phase_frozen' not in (ROOT / 'backend/core/llm_emit.py').read_text(encoding='utf-8')
    assert not hasattr(llm_emit._RunAcc(), 'phase_frozen')


def test_i419_helpers_take_the_mutex(monkeypatch, tmp_path):
    entered = []

    class Spy:
        def __enter__(self):
            entered.append(True)

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(store, '_receipt_mutex', Spy())
    path = tmp_path / 'studio.json'
    receipt = {'identity': ('render', 'j'), 'pending': {}}
    store._append_receipt(path, receipt)
    assert entered == [True]
    assert store._receipts(path) == [receipt] and len(entered) == 2
    store._drop_receipts(path, [receipt])
    assert len(entered) == 3 and path not in store._read_failures
