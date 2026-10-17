"""Exercise consent activation inside a request with the real SDK and worker scope."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('environment', ['production', 'validation'])
@pytest.mark.parametrize('identity_source', ['env', 'late'])
def test_off_on_request_keeps_safe_runtime_tags_in_worker(tmp_path, environment, identity_source):
    # A separate interpreter keeps the real SDK client/global scope out of other tests.
    script = r'''
import json, os, threading
from pathlib import Path
import sentry_sdk
from sentry_sdk.transport import Transport
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api.v1.settings import router
from backend.core import sentry_setup
from backend.core.event_catalog import detect_os, detect_arch
# This child simulates the packaged tree (no backend/tests) and is not a pytest process.
sentry_setup._running_from_source_tree = lambda: False

received = []
class RecordingTransport(Transport):
    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.headers.get('type') == 'event':
                received.append(item.payload.json)

real_init = sentry_sdk.init
def init_with_local_transport(**options):
    return real_init(**options, transport=RecordingTransport)
sentry_sdk.init = init_with_local_transport
sentry_setup.write_privacy(crash_reports=False)
assert sentry_setup.init_sentry('desktop') is False
app = FastAPI()
app.include_router(router)
with sentry_sdk.isolation_scope():
    with sentry_sdk.new_scope():
        with TestClient(app) as client:
            response = client.put('/settings/privacy', json={'crash_reports': True})
            assert response.status_code == 200, (response.status_code, response.text)
            assert response.json() == {'crash_reports': True}

worker = threading.Thread(target=lambda: sentry_setup.capture_studio_exception(
    RuntimeError('synthetic-private-key /Users/private/video.mp4'), 'production'))
worker.start()
worker.join(10)
assert not worker.is_alive()
assert len(received) == 1, received
event = received[0]
expected = {'runtime': 'python', 'app_mode': 'desktop',
            'os': detect_os(), 'arch': detect_arch(),
            'build_environment': os.environ['AUTOCLIP_BUILD_ENVIRONMENT'],
            'area': 'studio', 'phase': 'production', 'error_code': 'unexpected',
            'failure_stage': 'production', 'attribution_source': 'local'}  # R26 #392: not a provider failure
if os.environ['AUTOCLIP_BUILD_ENVIRONMENT'] == 'validation':
    expected['telemetry_test'] = 'true'
assert event.get('tags') == expected, event.get('tags')
assert event['release'] == 'autoclip-backend@1.5.4'
device_id = '018f6b2a-7c3d-7b2a-8c11-111111111111'
if os.environ['IDENTITY_SOURCE'] == 'env':
    assert event['user'] == {'id': device_id}
else:
    assert 'user' not in event
    with TestClient(app) as client:
        response = client.put('/settings/analytics-identity', json={'distinct_id': device_id})
        assert response.status_code == 200
    assert sentry_sdk.get_global_scope()._user == {'id': device_id}
    worker = threading.Thread(target=lambda: sentry_setup.capture_studio_exception(RuntimeError('late identity'), 'production'))
    worker.start()
    worker.join(10)
    assert received[-1]['user'] == {'id': device_id}
    assert len(received) == 2
assert 'synthetic-private-key' not in json.dumps(event)
assert '/Users/private' not in json.dumps(event)
sentry_setup.write_privacy(crash_reports=False)
count = len(received)
worker = threading.Thread(target=lambda: sentry_setup.capture_studio_exception(
    RuntimeError('opted-out'), 'production'))
worker.start()
worker.join(10)
assert len(received) == count, 'OFF must not submit another envelope'
sentry_sdk.get_client().close()
'''
    env = {key: value for key, value in os.environ.items() if key not in {'PYTEST_CURRENT_TEST', 'PYTEST_ADDOPTS'}}
    env.update(AUTOCLIP_APP_DIR=str(tmp_path), AUTOCLIP_DATA_DIR=str(tmp_path),
               AUTOCLIP_MODE='desktop', AUTOCLIP_BUILD_ENVIRONMENT=environment,
               AUTOCLIP_APP_VERSION='1.5.4', SENTRY_DSN='https://public@example.invalid/1',
               AUTOCLIP_EVENT_CATALOG=str(tmp_path / 'missing-catalog.json'),
               DATABASE_URL='sqlite:///' + str(tmp_path / 'isolated.sqlite'),
               PYTHONDONTWRITEBYTECODE='1')
    env.update(IDENTITY_SOURCE=identity_source,
               AUTOCLIP_ANONYMOUS_DEVICE_ID='018f6b2a-7c3d-7b2a-8c11-111111111111' if identity_source == 'env' else '')
    result = subprocess.run([sys.executable, '-B', '-c', script],
                            cwd=Path(__file__).resolve().parents[2], env=env,
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
