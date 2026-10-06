"""Bounded atomic state replacement under transient Windows sharing errors."""
import json
import threading

import pytest

from backend.services.studio import store


@pytest.fixture
def state_path(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('p1').mkdir(parents=True)
    store.write('p1', {'drafts': [], 'events': [], 'jobs': [], 'analysis': None, 'marker': 'before'})
    return store.directory('p1') / 'metadata' / 'studio.json'


def windows_busy(code):
    error = PermissionError('synthetic Windows file sharing conflict')
    error.winerror = code
    return error


@pytest.mark.parametrize('code', [5, 32, 33])
def test_transient_windows_reader_does_not_lose_render_state(state_path, monkeypatch, code):
    replace = store.os.replace
    calls = []
    def busy_once(src, dst):
        calls.append((src, dst))
        if len(calls) == 1:
            raise windows_busy(code)
        return replace(src, dst)
    monkeypatch.setattr(store.os, 'replace', busy_once)
    mutations = []
    def mutate(data):
        mutations.append(True)
        data['jobs'].append({'job_id': 'finished', 'status': 'completed'})
    store.change('p1', mutate)
    state = json.loads(state_path.read_text())
    assert state['jobs'] == [{'job_id': 'finished', 'status': 'completed'}]
    assert state['marker'] == 'before'
    assert mutations == [True]
    assert len(calls) == 2 and calls[0] == calls[1]
    assert not list(state_path.parent.glob('*.tmp'))


def test_persistent_windows_denial_is_bounded_and_keeps_previous_state(state_path, monkeypatch):
    original = state_path.read_bytes()
    calls = []
    def denied(src, dst):
        calls.append(True)
        raise windows_busy(5)
    monkeypatch.setattr(store.os, 'replace', denied)
    with pytest.raises(PermissionError):
        store.change('p1', lambda data: data.update(marker='must-not-be-saved'))
    assert 1 < len(calls) <= 5
    assert state_path.read_bytes() == original
    assert not list(state_path.parent.glob('*.tmp'))


def test_other_permission_error_is_not_retried_or_swallowed(state_path, monkeypatch):
    original = state_path.read_bytes()
    calls = []
    def denied(src, dst):
        calls.append(True)
        raise PermissionError('synthetic permanent denial')
    monkeypatch.setattr(store.os, 'replace', denied)
    with pytest.raises(PermissionError):
        store.change('p1', lambda data: data.update(marker='must-not-be-saved'))
    assert len(calls) == 1
    assert state_path.read_bytes() == original


def test_observer_respects_state_transaction_lock(state_path):
    started, completed = threading.Event(), threading.Event()
    def observe():
        started.set()
        store.read('p1', recover=False)
        completed.set()
    with store.lock:
        reader = threading.Thread(target=observe)
        reader.start()
        assert started.wait(1)
        blocked = not completed.wait(.1)
    reader.join(2)
    assert blocked and completed.is_set()
