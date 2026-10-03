"""Local process timeouts retain typed failures and recoverable render state."""
import hashlib
import json
import subprocess
import sys

import pytest

from backend.core import sentry_setup
from backend.services.studio import jobs, store


@pytest.fixture
def process_timeout():
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        subprocess.run([sys.executable, '-c', 'import time; time.sleep(5)'],
                       capture_output=True, timeout=0.1, check=True)
    return caught.value


def test_real_process_timeout_retains_render_tag_and_scrubs_command(process_timeout, monkeypatch, tmp_path):
    assert sentry_setup.studio_error_code(process_timeout) == 'timeout'
    import sentry_sdk
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":true}')
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    captured = []
    monkeypatch.setattr(sentry_sdk, 'capture_exception', lambda error:
                        captured.append(dict(sentry_sdk.get_current_scope()._tags)))
    sentry_setup.capture_studio_exception(process_timeout, 'render')
    assert captured[0]['phase'] == 'render'
    assert captured[0]['error_code'] == 'timeout'
    clean = sentry_setup.before_send({'tags': captured[0], 'exception': {'values': [
        {'type': 'TimeoutExpired', 'value': str(process_timeout)},
    ]}})
    assert clean['tags']['phase'] == 'render'
    assert clean['tags']['error_code'] == 'timeout'
    assert clean['exception']['values'][0]['value'] == '[message omitted for privacy]'
    assert sys.executable not in json.dumps(clean)
    assert 'time.sleep' not in json.dumps(clean)


@pytest.mark.parametrize(('error', 'expected'), [
    (ValueError('timeout-shaped validation message'), 'validation'),
    (RuntimeError('TimeoutExpired in a message is not a typed timeout'), 'unexpected'),
    (OSError('timeout-shaped I/O failure'), 'unexpected'),
    (PermissionError('timeout-shaped sharing failure'), 'unexpected'),
])
def test_unrelated_errors_are_not_reclassified_by_message(error, expected):
    assert sentry_setup.studio_error_code(error) == expected


def test_render_timeout_settles_preserves_completed_output_and_recovers(process_timeout, monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false}')
    root = store.directory('process-timeout')
    (root / 'raw').mkdir(parents=True)
    source = root / 'raw' / 'input.mp4'
    source.write_bytes(b'controlled original input')
    completed = root / 'completed.mp4'
    completed.write_bytes(b'controlled previous completed output')
    old_hash = hashlib.sha256(completed.read_bytes()).hexdigest()
    input_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    store.write('process-timeout', {'drafts': [], 'events': [], 'jobs': [
        {'job_id': 'active', 'status': 'queued', 'instance': store.INSTANCE},
        {'job_id': 'ready', 'status': 'completed', 'result': {'path': 'completed.mp4'}},
    ], 'output_variants': [
        {'id': 'ready', 'status': 'completed', 'render_job_id': 'ready'},
        {'id': 'active', 'status': 'queued', 'render_job_id': 'active'},
    ], 'generation': {'status': 'rendering', 'auto_start': True},
        'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'same-flow', 'instance': store.INSTANCE}})
    captured = []
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda error, phase:
                        captured.append((error, phase)))
    # Project index synchronization has independent SQLite regressions.
    monkeypatch.setattr(jobs, 'sync_project_completion', lambda project_id: None)
    def timeout_render(*args, **kwargs):
        raise process_timeout
    monkeypatch.setattr(jobs, 'render_draft', timeout_render)
    jobs._render('process-timeout', object(), 'active')
    failed = store.read('process-timeout')
    assert failed['jobs'][0]['status'] == 'failed'
    assert failed['jobs'][0]['error_code'] == 'timeout'
    assert failed['output_variants'][1]['status'] == 'failed'
    assert failed['generation']['status'] == 'partial'
    assert failed['generation']['error_code'] == 'timeout'
    assert failed['analysis']['phase'] == 'rendering'
    assert failed['analysis']['run_id'] == 'same-flow'
    assert captured == [(process_timeout, 'render')]
    def requeue(data):
        data['jobs'].append({'job_id': 'retry', 'status': 'queued', 'instance': store.INSTANCE})
        data['output_variants'][1].update(status='queued', render_job_id='retry')
    store.change('process-timeout', requeue)
    monkeypatch.setattr(jobs, 'render_draft', lambda *args, **kwargs: {'path': 'retry.mp4'})
    monkeypatch.setattr(jobs, '_design_covers', lambda *args, **kwargs: None)
    jobs._render('process-timeout', object(), 'retry')
    recovered = store.read('process-timeout')
    assert recovered['jobs'][-1]['status'] == 'completed'
    assert recovered['output_variants'][1]['status'] == 'completed'
    assert recovered['generation']['status'] == 'completed'
    assert 'error_code' not in recovered['generation']
    assert recovered['analysis']['run_id'] == 'same-flow'
    assert recovered['jobs'][1]['result'] == {'path': 'completed.mp4'}
    assert hashlib.sha256(completed.read_bytes()).hexdigest() == old_hash
    assert hashlib.sha256(source.read_bytes()).hexdigest() == input_hash
