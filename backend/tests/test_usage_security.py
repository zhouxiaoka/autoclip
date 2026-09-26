import subprocess
import sys
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from backend.core.api_security import APISecurity
from backend.core import usage_guard as guard


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_SECURITY_DIR', str(tmp_path / 'security'))
    monkeypatch.setenv('AUTOCLIP_AUTH_TOKEN', 'test-operator-token-' + 'x' * 32)
    monkeypatch.setenv('AUTOCLIP_ALLOWED_HOSTS', 'testserver,localhost')


def spend(directory):
    os.environ['AUTOCLIP_SECURITY_DIR'] = directory
    try:
        guard.reserve([('shared', 1, 7)])
        return True
    except guard.UsageDenied:
        return False


def test_atomic_multiprocess_persistent_limit():
    directory = str(guard.security_directory())
    def child(_):
        command = 'from backend.tests.test_usage_security import spend; import sys; sys.exit(0 if spend(sys.argv[1]) else 1)'
        return subprocess.run([sys.executable, '-c', command, directory]).returncode == 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(child, range(20))) == 7
    assert not spend(directory)


def test_failed_paid_call_consumes_allowance(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DAILY_PAID_REQUESTS', '1')
    with pytest.raises(TimeoutError):
        with guard.paid_operation(10, 10):
            raise TimeoutError()
    with pytest.raises(guard.UsageDenied):
        with guard.paid_operation(1, 1):
            pytest.fail('Must not execute')


def test_concurrent_reservations_and_release(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_CONCURRENT_PAID', '1')
    with guard.paid_operation():
        with pytest.raises(guard.UsageDenied):
            with guard.paid_operation():
                pytest.fail('Must not execute')
    with guard.paid_operation():
        pass


def test_storage_failure_denies(monkeypatch, tmp_path):
    path = tmp_path / 'not-directory'
    path.write_text('x')
    monkeypatch.setenv('AUTOCLIP_SECURITY_DIR', str(path))
    with pytest.raises(guard.UsageDenied):
        guard.reserve([('anything', 1, 5)])


def test_utc_reset_and_configuration_do_not_reset_counters(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DAILY_PAID_REQUESTS', '1')
    monkeypatch.setattr(guard.time, 'time', lambda: 100)
    with guard.paid_operation():
        pass
    monkeypatch.setenv('API_MODEL_NAME', 'different-model')
    with pytest.raises(guard.UsageDenied):
        with guard.paid_operation():
            pass
    monkeypatch.setattr(guard.time, 'time', lambda: 86500)
    with guard.paid_operation():
        pass


def test_llm_bounds_and_nonretryable_denial(monkeypatch):
    class Provider:
        def _build_full_input(self, prompt, data):
            return prompt
        @guard.guarded_llm
        def call(self, prompt, input_data=None, **kwargs):
            return kwargs
    assert Provider().call('hello', max_tokens=100000)['max_tokens'] == 8192
    with pytest.raises(guard.UsageDenied):
        Provider().call('x' * 262145)
    assert issubclass(guard.UsageDenied, ValueError)


def app_client():
    app = FastAPI()
    @app.get('/api/v1/settings/')
    def settings():
        return {'protected': True}
    @app.post('/api/v1/paid')
    async def paid(request: Request):
        await request.body()
        return {'paid': True}
    @app.get('/api/v1/projects/p/video')
    def media():
        return {'media': True}
    app.add_middleware(APISecurity)
    return TestClient(app)


def test_auth_fail_closed_and_spoofing(monkeypatch):
    client = app_client()
    assert client.get('/health').status_code == 200
    assert client.get('/api/v1/settings/', headers={'X-Forwarded-For': '127.0.0.1'}).status_code == 401
    auth = {'Authorization': 'Bearer ' + os.environ['AUTOCLIP_AUTH_TOKEN']}
    assert client.get('/api/v1/settings/', headers=auth).status_code == 200
    assert client.get('/api/v1/settings/', headers={**auth, 'Origin': 'null'}).status_code == 403
    assert client.get('/api/v1/settings/', headers={**auth, 'Host': 'evil.example'}).status_code == 400
    monkeypatch.delenv('AUTOCLIP_AUTH_TOKEN')
    assert app_client().get('/api/v1/settings/').status_code == 503


def test_cookie_login_csrf_media_ticket_scope(monkeypatch):
    client = app_client()
    headers = {'Origin': 'http://testserver'}
    response = client.post('/api/auth/login', json={'token': os.environ['AUTOCLIP_AUTH_TOKEN']}, headers=headers)
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']
    assert client.post('/api/v1/paid').status_code == 403
    assert client.post('/api/v1/paid', headers=headers).status_code == 200
    response = client.post('/api/auth/media', json={'path': '/api/v1/projects/p/video'}, headers=headers)
    ticket = response.json()['token']
    client.cookies.clear()
    assert client.get('/api/v1/projects/p/video', params={'_media': ticket}).status_code == 200
    assert client.get('/api/v1/settings/', params={'_media': ticket}).status_code == 401
    assert client.post('/api/v1/paid', params={'_media': ticket}).status_code == 401


def test_body_limit_before_handler(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_JSON_REQUEST_BYTES', '10')
    client = app_client()
    response = client.post('/api/v1/paid', content='x' * 11, headers={'Authorization': 'Bearer ' + os.environ['AUTOCLIP_AUTH_TOKEN']})
    assert response.status_code == 413


def test_global_http_limit_does_not_trust_ip(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_HTTP_PER_MINUTE', '2')
    guard.admit_http('a')
    guard.admit_http('b')
    with pytest.raises(guard.UsageDenied):
        guard.admit_http('c')


def test_media_attempts_charge_each_post(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DAILY_PAID_REQUESTS', '1')
    class Session:
        calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            raise TimeoutError()
    session = Session()
    with pytest.raises(TimeoutError):
        guard.paid_post(session, 'https://provider.test/images', json={'n': 1})
    with pytest.raises(guard.UsageDenied):
        guard.paid_post(session, 'https://provider.test/images', json={'n': 1})
    assert session.calls == 1


def test_desktop_cross_origin_auth_responses(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_ALLOWED_ORIGINS', 'tauri://localhost')
    client = app_client()
    headers = {'Origin': 'tauri://localhost', 'Authorization': 'Bearer ' + os.environ['AUTOCLIP_AUTH_TOKEN']}
    for response in [client.get('/api/auth/session', headers=headers), client.post('/api/auth/media', json={'path': '/api/v1/projects/p/video'}, headers=headers)]:
        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == 'tauri://localhost'


def test_media_path_encoding_is_canonical():
    from backend.core.api_security import media_target
    assert media_target('/api/v1/projects/p/files/片 段.mp4') == media_target('/api/v1/projects/p/files/%E7%89%87%20%E6%AE%B5.mp4')


def test_data_directory_and_multihost_fail_closed(monkeypatch):
    from backend.core.path_utils import get_data_directory
    monkeypatch.setenv('AUTOCLIP_SECURITY_DIR', str(get_data_directory() / 'security'))
    with pytest.raises(guard.UsageDenied):
        guard.reserve()
    monkeypatch.setenv('AUTOCLIP_DEPLOYMENT_HOSTS', '2')
    with pytest.raises(guard.UsageDenied):
        guard.reserve()


def test_queue_admission_before_direct_dispatch(monkeypatch):
    from backend.core.celery_app import celery_app
    monkeypatch.setenv('AUTOCLIP_OUTSTANDING_TASKS', '1')
    guard.reserve(kind='queue', capacity=1, lease_id='occupied')
    with pytest.raises(guard.UsageDenied):
        celery_app.send_task('must.never.send')


def test_audio_duration_and_bytes(monkeypatch, tmp_path):
    import wave
    from backend.utils.speech_recognizer import SpeechRecognizer
    audio = tmp_path / 'audio.wav'
    with wave.open(str(audio), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b'\0' * 32000)
    monkeypatch.setenv('AUTOCLIP_AUDIO_SECONDS', '1')
    with pytest.raises(guard.UsageDenied):
        SpeechRecognizer._check_cloud_audio(audio)


def test_preflight_emits_single_origin_header(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_ALLOWED_ORIGINS', 'tauri://localhost')
    response = app_client().options('/api/auth/session', headers={'Origin': 'tauri://localhost', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization'})
    assert response.status_code == 200
    assert response.headers.get_list('access-control-allow-origin') == ['tauri://localhost']
    assert response.headers.get_list('access-control-allow-credentials') == ['true']


def test_retry_reuses_only_current_task_lease(monkeypatch):
    from celery.app.task import Task
    from backend.core.celery_app import DesktopAwareTask, celery_app
    monkeypatch.setattr(Task, 'apply_async', lambda self, **kwargs: kwargs)
    task = DesktopAwareTask()
    task.bind(celery_app)
    first = task.apply_async(task_id='retry-id')
    assert first['task_id'] == 'retry-id'
    with pytest.raises(guard.UsageDenied):
        task.apply_async(task_id='retry-id')
    task.push_request(id='retry-id')
    try:
        result = task.apply_async(task_id='retry-id', retries=1)
        assert result['task_id'] == 'retry-id'
    finally:
        task.pop_request()
    task.after_return('SUCCESS', None, 'retry-id', [], {}, None)
    with guard.transaction() as db:
        assert db.execute("SELECT count(*) FROM leases WHERE kind='queue'").fetchone()[0] == 0


def test_media_tickets_use_read_admission_not_paid_admission(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_EXPENSIVE_PER_MINUTE', '1')
    client = app_client()
    headers = {'Authorization': 'Bearer ' + os.environ['AUTOCLIP_AUTH_TOKEN']}
    for _ in range(12):
        assert client.post('/api/auth/media', json={'path': '/api/v1/projects/p/video'}, headers=headers).status_code == 200
    assert client.post('/api/v1/paid', headers=headers).status_code == 200
    assert client.post('/api/v1/paid', headers=headers).status_code == 429


def test_async_provider_lease_retained_until_confirmed_completion(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_CONCURRENT_PAID', '1')
    class Session:
        def post(self, *args, **kwargs):
            return object()
    _, lease = guard.paid_post(Session(), 'https://provider.test/jobs', json={}, _retain_lease=True)
    with pytest.raises(guard.UsageDenied):
        guard.paid_post(Session(), 'https://provider.test/jobs', json={})
    guard.release(lease)
    guard.paid_post(Session(), 'https://provider.test/jobs', json={})
