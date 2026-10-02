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
    assert json.loads(state_path.read_text())['jobs'] == [{'job_id': 'j1', 'status': 'completed'}]
    assert not list(state_path.parent.glob('*.tmp'))


def test_native_windows_persistent_reader_keeps_previous_file(state_path):
    before = state_path.read_bytes()
    with state_path.open('rb'):
        with pytest.raises(PermissionError):
            store.change('p1', lambda data: data.update(marker='unsaved'))
    assert state_path.read_bytes() == before
    assert not list(state_path.parent.glob('*.tmp'))
