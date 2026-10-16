"""Actual Windows file-sharing behaviour; executed by the Windows CI runtime job."""
import json
import os
import threading

import pytest

from backend.services.studio import store

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='actual Windows file sharing')


@pytest.fixture
def state_path(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('p1').mkdir(parents=True)
    store.write('p1', {'drafts': [], 'events': [], 'jobs': [], 'analysis': None, 'marker': 'before'})
    return store.directory('p1') / 'metadata' / 'studio.json'


def test_native_windows_external_reader_releases_and_render_state_commits(state_path, monkeypatch):
    ready, release = threading.Event(), threading.Event()
    def observe():
        with state_path.open('rb') as stream:
            assert stream.read(1)
            ready.set()
            assert release.wait(5)
    reader = threading.Thread(target=observe)
    reader.start()
    assert ready.wait(2)
    actual_replace = store.os.replace
    observed = []
    def replace(src, dst):
        try:
            return actual_replace(src, dst)
        except PermissionError as error:
            observed.append(error.winerror)
            release.set()
            raise
    monkeypatch.setattr(store.os, 'replace', replace)
    try:
        store.change('p1', lambda data: data['jobs'].append({'job_id': 'j1', 'status': 'completed'}))
    finally:
        release.set()
        reader.join(2)
    assert observed and all(code in (5, 32, 33) for code in observed)
    assert json.loads(state_path.read_text(encoding='utf-8'))['jobs'] == [{'job_id': 'j1', 'status': 'completed'}]
    assert not list(state_path.parent.glob('*.tmp'))


def test_native_windows_persistent_reader_keeps_previous_file(state_path):
    before = state_path.read_bytes()
    with state_path.open('rb'):
        with pytest.raises(PermissionError):
            store.change('p1', lambda data: data.update(marker='unsaved'))
    assert state_path.read_bytes() == before
    assert not list(state_path.parent.glob('*.tmp'))



def test_native_windows_reader_leaves_failed_worker_retryable(state_path, monkeypatch):
    from backend.services.studio import jobs
    root = state_path.parent.parent
    (root / 'raw').mkdir()
    (root / 'raw' / 'input.mp4').write_bytes(b'local protocol fixture')
    store.change('p1', lambda data: data.update(
        jobs=[{'job_id': 'j1', 'status': 'queued', 'percent': 0, 'instance': store.INSTANCE}],
        generation={'status': 'rendering'},
        output_variants=[{'id': 'v1', 'status': 'queued', 'render_job_id': 'j1'}]))
    original = state_path.read_bytes()
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: pytest.fail('Denied startup must not render'))
    with state_path.open('rb'):
        with pytest.raises(PermissionError):
            jobs._render('p1', object(), 'j1')
        live = store.read('p1')
        assert live['jobs'][0]['status'] == 'failed'
        assert live['output_variants'][0]['status'] == 'failed'
        assert live['generation']['status'] == 'failed'
        assert state_path.read_bytes() == original
    # Releasing the real native handle enables a new explicitly requested job;
    # the failed attempt is retained rather than silently repeated.
    store.change('p1', lambda data: data['jobs'].append(
        {'job_id': 'retry', 'status': 'queued', 'percent': 0, 'instance': store.INSTANCE}))
    durable = json.loads(state_path.read_text(encoding='utf-8'))
    assert durable['jobs'][0]['status'] == 'failed'
    assert durable['jobs'][1]['status'] == 'queued'
    assert not list(state_path.parent.glob('*.tmp'))
