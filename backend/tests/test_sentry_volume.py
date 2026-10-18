"""keep one looping machine, Proactor noise and non-production builds out of Sentry.
The end-to-end cases run the real SDK in a separate interpreter with a recording
transport (fake DSN, nothing leaves the box), so the global client never leaks
into other tests."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.core import sentry_setup

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
import json, logging, sys
import sentry_sdk
from sentry_sdk.transport import Transport
from backend.core import sentry_setup

received = []
class RecordingTransport(Transport):
    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.headers.get('type') == 'event':
                received.append(item.payload.json)

real_init = sentry_sdk.init
sentry_sdk.init = lambda **options: real_init(**options, transport=RecordingTransport)
# Packaged copies omit backend/tests. This child simulates that layout; the
# source-tree refusal is covered by a run that does not assign this.
sentry_setup._running_from_source_tree = lambda: False
assert sentry_setup.init_sentry('desktop') is True
logging.getLogger().setLevel(logging.INFO)

def functions(event):
    return [frame.get('function') for value in event['exception']['values']
            for frame in value['stacktrace']['frames']]
'''


def _child_env(tmp_path, **overrides):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('SENTRY_', 'POSTHOG', 'VITE_PUBLIC_POSTHOG', 'VITE_PUBLIC_SENTRY'))
           and key not in {'PYTEST_CURRENT_TEST', 'PYTEST_ADDOPTS'}}
    env.update(AUTOCLIP_APP_DIR=str(tmp_path), AUTOCLIP_DATA_DIR=str(tmp_path),
               AUTOCLIP_MODE='desktop', AUTOCLIP_BUILD_ENVIRONMENT='production',
               AUTOCLIP_APP_VERSION='1.5.7', SENTRY_DSN='https://public@example.invalid/1',
               AUTOCLIP_EVENT_CATALOG=str(tmp_path / 'missing-catalog.json'),
               DATABASE_URL='sqlite:///' + str(tmp_path / 'isolated.sqlite'),
               PYTHONDONTWRITEBYTECODE='1')
    env.update(overrides)
    return env


def _run(tmp_path, body, *, script=None, **overrides):
    result = subprocess.run(
        [sys.executable, '-B', '-c', script if script is not None else HARNESS + body],
        cwd=ROOT, env=_child_env(tmp_path, **overrides),
        capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_i650_same_error_100_times_sends_only_5(tmp_path):
    out = _run(tmp_path, r'''
def same_failure():
    raise RuntimeError('same failure /Users/private/video.mp4')
for _ in range(100):
    try:
        same_failure()
    except RuntimeError as error:
        sentry_setup.capture_studio_exception(error, 'production')
same = len(received)
def different_failure():
    raise KeyError('other')
try:
    different_failure()
except KeyError as error:
    sentry_sdk.capture_exception(error)
print(json.dumps({'same': same, 'total': len(received),
                  'private': any('/Users/private' in json.dumps(e) for e in received)}))
''')
    assert out['same'] == 5
    assert out['total'] == 6, 'a different fingerprint keeps its own budget'
    assert out['private'] is False


def test_i650_polling_endpoints_report_once_per_process(tmp_path):
    out = _run(tmp_path, r'''
import asyncio
from unittest.mock import Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api.v1 import projects, settings
from backend.core.error_middleware import global_exception_handler

broken = Mock()
broken.get.side_effect = RuntimeError('db locked /Users/private/project')
for _ in range(100):
    try:
        asyncio.run(projects.get_processing_status('p1', project_service=broken, processing_service=Mock()))
    except Exception:
        pass
status_events = [e for e in received if 'get_processing_status' in functions(e)]

def failing_migration():
    raise RuntimeError('legacy settings unreadable')
settings.ai_models.for_editing = failing_migration
app = FastAPI()
app.include_router(settings.router)
app.add_exception_handler(Exception, global_exception_handler)
with TestClient(app, raise_server_exceptions=False) as client:
    codes = {client.get('/settings/ai-models').status_code for _ in range(100)}
model_events = [e for e in received if 'get_ai_models' in functions(e)]
print(json.dumps({'status': len(status_events), 'models': len(model_events),
                  'codes': sorted(codes), 'total': len(received)}))
''')
    assert out['codes'] == [500]
    assert out['status'] == 1
    assert out['models'] == 1
    assert out['total'] == 2


def test_i651_proactor_reset_dropped_other_resets_reported(tmp_path):
    out = _run(tmp_path, r'''
from asyncio.proactor_events import _ProactorBasePipeTransport
from unittest.mock import Mock
sock = Mock(spec=['shutdown', 'close', 'fileno'])
sock.fileno.return_value = 42
sock.shutdown.side_effect = ConnectionResetError(10054, 'synthetic peer reset')
transport = _ProactorBasePipeTransport(Mock(), sock, Mock(), server=Mock())
try:
    _ProactorBasePipeTransport._call_connection_lost(transport, None)  # unpatched CPython path
except ConnectionResetError as error:
    proactor = error
transport._sock = None
sentry_sdk.capture_exception(proactor)
# asyncio reports callback failures through its logger ("Exception in callback ...").
logging.getLogger('asyncio').error('Exception in callback', exc_info=proactor)
proactor_sent = len(received)

def upload_reset():
    raise ConnectionResetError(104, 'provider reset')
try:
    upload_reset()
except ConnectionResetError as error:
    sentry_sdk.capture_exception(error)
other = [e for e in received if 'upload_reset' in functions(e)]
print(json.dumps({'proactor': proactor_sent, 'other': len(other),
                  'other_type': other[0]['exception']['values'][-1]['type'] if other else None}))
''')
    assert out['proactor'] == 0
    assert out['other'] == 1
    assert out['other_type'] == 'ConnectionResetError'


def _reset_volume(monkeypatch, start=1000.0):
    from collections import OrderedDict
    now = [start]
    monkeypatch.setattr(sentry_setup, '_volume_sent', OrderedDict())
    monkeypatch.setattr(sentry_setup, '_polling_reported', set())
    monkeypatch.setattr(sentry_setup, '_clock', lambda: now[0])
    return now


def _event(function, module='backend.services.studio.jobs', type_='RuntimeError'):
    return {'exception': {'values': [{'type': type_, 'stacktrace': {'frames': [
        {'module': module, 'function': function}]}}]}}


def test_i650_budget_is_per_hour_and_polling_stays_once(monkeypatch):
    now = _reset_volume(monkeypatch)
    event = _event('render')
    assert [sentry_setup._volume_allows(event) for _ in range(6)] == [True] * 5 + [False]
    now[0] += 3599
    assert sentry_setup._volume_allows(event) is False
    now[0] += 1
    assert sentry_setup._volume_allows(event) is True
    poll = _event('get_processing_status', module='backend.api.v1.projects')
    assert sentry_setup._volume_allows(poll) is True
    now[0] += 7 * 3600
    assert sentry_setup._volume_allows(poll) is False
    # Same function name outside the backend (e.g. a dependency) is not a polling endpoint.
    outside = _event('get_ai_models', module='somelib.client')
    assert [sentry_setup._volume_allows(outside) for _ in range(6)] == [True] * 5 + [False]
    # A different exception type in the same function keeps its own budget.
    assert sentry_setup._volume_allows(_event('render', type_='KeyError')) is True


def test_i650_dropped_disconnect_does_not_spend_the_budget(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    _reset_volume(monkeypatch)
    noise = {'exception': {'values': [{'type': 'ConnectionResetError', 'value': '/Users/private',
        'stacktrace': {'frames': [{'module': 'asyncio.proactor_events', 'filename': 'proactor_events.py',
                                   'function': '_call_connection_lost'}]}}]}}
    assert [sentry_setup._before_send_limited(noise) for _ in range(10)] == [None] * 10
    business = _event('render')
    assert [sentry_setup._before_send_limited(business) is not None for _ in range(6)] == [True] * 5 + [False]


def test_i651_only_proactor_disconnects_are_dropped(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))

    def event(type_, module):
        return {'exception': {'values': [{'type': type_, 'value': 'secret /Users/private/video.mp4',
            'stacktrace': {'frames': [{'module': module, 'filename': module.split('.')[-1] + '.py',
                                       'function': '_call_connection_lost'}]}}]}}

    for type_ in ('ConnectionResetError', 'ConnectionAbortedError', 'BrokenPipeError'):
        assert sentry_setup.before_send(event(type_, 'asyncio.proactor_events')) is None
        kept = sentry_setup.before_send(event(type_, 'backend.services.upload'))
        assert kept is not None and kept['exception']['values'][0]['type'] == type_
        assert 'private' not in json.dumps(kept)
        # A backend protocol failure that unwinds through the Proactor is still reported.
        mixed = event(type_, 'asyncio.proactor_events')
        mixed['exception']['values'][0]['stacktrace']['frames'].append(
            {'module': 'backend.server', 'filename': 'server.py', 'function': 'connection_lost'}
        )
        assert sentry_setup.before_send(mixed) is not None
    raw = OSError(22, 'raw disconnect')
    raw.winerror = 10054
    assert sentry_setup.before_send(
        event('OSError', 'asyncio.proactor_events'), {'exc_info': (OSError, raw, None)}
    ) is None
    kept_os = sentry_setup.before_send(
        event('OSError', 'backend.services.upload'), {'exc_info': (OSError, raw, None)}
    )
    assert kept_os is not None and 'private' not in json.dumps(kept_os)
    # A programming error inside the proactor module is not disconnect noise.
    assert sentry_setup.before_send(event('RuntimeError', 'asyncio.proactor_events')) is not None


def test_i652_source_checkout_with_a_dsn_does_not_init(tmp_path):
    out = _run(tmp_path, '', script=r'''
import json
import sentry_sdk
from sentry_sdk.transport import Transport
from backend.core import sentry_setup
received = []
class RecordingTransport(Transport):
    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.headers.get('type') == 'event':
                received.append(item.payload.json)
real_init = sentry_sdk.init
sentry_sdk.init = lambda **options: real_init(**options, transport=RecordingTransport)
assert sentry_setup._running_from_source_tree() is True
assert sentry_setup.init_sentry('desktop') is False
assert sentry_setup._initialized is False
try:
    raise RuntimeError('source run /Users/private/video.mp4')
except RuntimeError as error:
    sentry_sdk.capture_exception(error)
print(json.dumps({'initialized': sentry_setup._initialized, 'sent': len(received)}))
''')
    assert out == {'initialized': False, 'sent': 0}


def test_i652_packaged_layout_is_a_backend_directory_without_tests(monkeypatch, tmp_path):
    assert sentry_setup._running_from_source_tree() is True
    packaged = tmp_path / 'backend' / 'core'
    packaged.mkdir(parents=True)
    monkeypatch.setattr(sentry_setup, '__file__', str(packaged / 'sentry_setup.py'))
    assert sentry_setup._running_from_source_tree() is False
    (tmp_path / 'backend' / 'tests').mkdir()
    assert sentry_setup._running_from_source_tree() is True


def test_i652_pytest_never_inits_even_when_the_layout_looks_packaged(monkeypatch, tmp_path):
    import sentry_sdk
    calls = []
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('SENTRY_DSN', 'https://public@example.invalid/1')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    monkeypatch.setenv('AUTOCLIP_APP_VERSION', '1.5.7')
    monkeypatch.setattr(sentry_setup, '_running_from_source_tree', lambda: False)
    monkeypatch.setattr(sentry_setup, '_initialized', False)
    monkeypatch.setattr(sentry_sdk, 'init', lambda **options: calls.append(options))
    assert sentry_setup._under_pytest() is True
    assert sentry_setup.init_sentry('desktop') is False
    assert calls == []
    assert sentry_setup._initialized is False


@pytest.mark.parametrize('mode, build, version, expected', [
    ('web', 'production', '1.5.7', False),              # Docker / script / pip
    ('desktop', 'development', '1.5.7', False),         # launcher debug build (tauri dev)
    ('desktop', 'unknown', '1.5.7', False),             # source default when the env is unset
    ('desktop', '', '1.5.7', False),
    ('desktop', 'production', None, False),             # release unknown
    ('desktop', 'production', 'unknown', False),
    ('desktop', 'production', '1.5.7', True),           # packaged desktop production build
    ('desktop', 'validation', '1.5.7', True),           # packaged acceptance build
])
def test_i652_initializes_only_in_packaged_desktop_build(monkeypatch, tmp_path, mode, build, version, expected):
    import sentry_sdk
    calls = []
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('SENTRY_DSN', 'https://public@example.invalid/1')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', build)
    monkeypatch.delenv('SENTRY_RELEASE', raising=False)
    # The env matrix is the packaged process. pytest and the checkout are covered separately.
    monkeypatch.setattr(sentry_setup, '_under_pytest', lambda: False)
    monkeypatch.setattr(sentry_setup, '_running_from_source_tree', lambda: False)
    if version is None:
        monkeypatch.delenv('AUTOCLIP_APP_VERSION', raising=False)
    else:
        monkeypatch.setenv('AUTOCLIP_APP_VERSION', version)
    monkeypatch.setattr(sentry_setup, '_initialized', False)
    monkeypatch.setattr(sentry_setup, 'sync_anonymous_user', lambda *a, **k: None)
    monkeypatch.setattr(sentry_sdk, 'init', lambda **options: calls.append(options))
    assert sentry_setup.init_sentry(mode) is expected
    assert len(calls) == (1 if expected else 0)
    if expected:
        assert calls[0]['environment'] == 'desktop'
        assert calls[0]['release'] == 'autoclip-backend@1.5.7'
        assert calls[0]['before_send'].__name__ == '_before_send_limited'
