import asyncio
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.api.v1 import obs
from backend.core import database
from backend.core.project_cancellation import bind
from backend.models.base import Base
from backend.models.project import Project
from backend.services.obs import billing, listener, settings, worker
from backend.services.obs.models import ObsCall, ObsCapture
from backend.services.obs.session import Capture, Outputs


def replay(steps, *, active=(False, False), armed=True):
    now = [0]
    state = Outputs(*active, clock=lambda: now[0])
    captures = []
    for step in steps.split():
        now[0] += 1
        if step == 'split':
            capture = state.event('RecordFileChanged', {}, armed=armed)
        else:
            kind, transition = step.split('.')
            data = {
                'outputState': listener.PREFIX + ('STOPPED' if transition == 'nopath' else transition.upper())
            }
            if step == 'r.stopped':
                data['outputPath'] = str(Path.cwd() / 'a.mkv')
            capture = state.event(
                'StreamStateChanged' if kind == 's' else 'RecordStateChanged', data, armed=armed
            )
        if capture:
            captures.append(capture)
    return captures, state.status


@pytest.mark.parametrize(
    'steps',
    [
        'r.started r.stopped',
        's.started s.stopped',
        's.started s.stopped r.started r.stopped',
        's.started r.started s.stopping r.stopped',
        's.started r.started s.reconnecting r.stopped',
        's.started r.started split s.stopped r.stopped',
        's.started r.started s.stopped s.started r.stopped s.stopped',
        's.started r.started r.stopped r.started r.stopped s.stopped',
        'r.started s.started s.stopped r.nopath',
    ],
)
def test_no_ambiguous_or_unfinished_import(steps):
    assert not replay(steps)[0]


@pytest.mark.parametrize(
    'steps, bounds',
    [
        ('r.started s.started s.stopped r.stopped', (1, 2, 3)),
        ('s.started r.started r.stopped s.stopped', (0, 1, 1)),
        (
            's.started r.started r.started r.paused r.resumed s.stopped s.stopped r.stopped r.stopped',
            (0, 3, 5),
        ),
        ('s.started r.started s.reconnecting s.reconnected s.stopped r.stopped', (0, 3, 4)),
    ],
)
def test_only_unique_overlap_emitted(steps, bounds):
    captures, _ = replay(steps)
    assert [(x.start, x.end, x.duration) for x in captures] == [bounds]


def test_reconnect_and_disarmed_fail_closed():
    assert not replay('s.stopped r.stopped', active=(True, True))[0]
    assert not replay('r.started s.stopped s.started r.stopped s.stopped', active=(True, False))[0]
    assert not replay('s.started r.started r.stopped s.stopped', armed=False)[0]
    assert replay('s.started r.started s.stopped')[1] == 'waiting_recording'


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(worker.store, 'get_projects_directory', lambda: tmp_path / 'projects')
    engine = database.create_database_engine('sqlite:///' + str(tmp_path / 'obs.db'))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(database, 'SessionLocal', sessionmaker(bind=engine, autoflush=False))
    recipients = [
        {
            'base': 'http://localhost/v1',
            'model': 'qwen',
            'role': 'analysis',
            'provider': 'compatible',
            'host': 'localhost',
        }
    ]
    monkeypatch.setattr(settings, 'overview', lambda: (recipients, 'digest'))
    yield recipients
    engine.dispose()


def test_status_consent_and_readonly_handshake(isolated, tmp_path, monkeypatch):
    app = FastAPI()
    monitor = listener.Monitor()
    app.state.obs = monitor
    app.include_router(obs.router, prefix='/obs')
    client = TestClient(app)
    assert client.get('/obs').json()['automatic'] is False
    assert client.put('/obs/automation', json={'enabled': True, 'digest': 'digest'}).status_code == 409
    keyring = {}

    class Vault:
        def set_password(self, service, account, password):
            keyring[(service, account)] = password

        def get_password(self, service, account):
            return keyring[(service, account)]

    monkeypatch.setattr(settings, 'keychain', Vault)
    assert client.put('/obs/connection', json={'enabled': True, 'password': 'test-only'}).status_code == 200
    cfg = settings.read()
    ws = AsyncMock()
    ws.recv.side_effect = [
        json.dumps({'op': 0, 'd': {'authentication': {'salt': 's', 'challenge': 'c'}}}),
        '{"op":2}',
    ]
    asyncio.run(listener.identify(ws, cfg))
    identify = json.loads(ws.send.await_args.args[0])
    assert identify == {
        'op': 1,
        'd': {
            'rpcVersion': 1,
            'eventSubscriptions': 64,
            'authentication': listener.digest64(listener.digest64('test-onlys') + 'c'),
        },
    }
    monitor.state, monitor.directory, monitor.supported, monitor.revision = (
        'connected',
        str(tmp_path),
        True,
        cfg['revision'],
    )
    response = client.get('/obs')
    assert 'test-only' not in response.text and 'automatic' in response.json()
    assert (
        client.put(
            '/obs/automation', json={'enabled': True, 'digest': 'wrong', 'revision': cfg['revision']}
        ).status_code
        == 409
    )
    assert (
        client.put(
            '/obs/automation', json={'enabled': True, 'digest': 'digest', 'revision': cfg['revision']}
        ).status_code
        == 200
    )
    client.put('/obs/connection', json={'enabled': False})
    assert client.get('/obs').json()['automatic']
    client.put('/obs/automation', json={'enabled': False})
    assert not settings.read()['consent']


def receipt(tmp_path, cid='recording', status='submitted', limit=50):
    settings.arm(str(tmp_path), 'digest', limit)
    pid = billing.project_id(cid)
    with database.session_scope() as db:
        db.add(
            ObsCapture(
                id=cid,
                path='file.mkv',
                start=0,
                end=2,
                duration=2,
                epoch=settings.read()['consent_epoch'],
                project_id=pid,
                created=time.time(),
                status=status,
            )
        )
        db.commit()
    return pid


def test_billed_http_receipts_replay_and_limit(isolated, tmp_path):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"choices":[{"message":{"content":"clip"}}]}')

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = 'http://127.0.0.1:' + str(server.server_port) + '/v1'
        isolated[0]['base'] = base
        with bind(receipt(tmp_path, limit=1)):
            body = {'model': 'qwen', 'messages': [{'role': 'user', 'content': 'test'}]}
            first = billing.chat('analysis', base, body, '', 2)
            assert billing.chat('analysis', base, body, '', 2) == first
            with pytest.raises(billing.CallPaused):
                billing.chat('analysis', base, {**body, 'temperature': 0.2}, '', 2)
        server.shutdown()
    assert calls == [body]
    assert worker.latest()['status'] == 'limit'


@pytest.mark.parametrize('cause', ['timeout', 'restarted', 'changed', 'disabled', 'destination'])
def test_unsafe_paid_retries_blocked(isolated, tmp_path, monkeypatch, cause):
    pid = receipt(tmp_path)
    base = isolated[0]['base']
    sends = []

    def send():
        sends.append(True)
        if cause == 'timeout':
            raise TimeoutError()
        return {'ok': True}

    with bind(pid):
        if cause == 'timeout':
            with pytest.raises(TimeoutError):
                billing.run('analysis', base, 'qwen', 'first', send)
        elif cause == 'restarted':
            with database.session_scope() as db:
                db.add(ObsCall(project_id=pid, signature='pending', process='old-process'))
                db.commit()
        elif cause == 'disabled':
            settings.arm('', '', 50)
        elif cause == 'changed':
            monkeypatch.setattr(settings, 'overview', lambda: (isolated, 'other'))
        else:
            base += '/different'
        with pytest.raises(billing.CallPaused):
            billing.run('analysis', base, 'qwen', 'second', send)
    assert len(sends) == int(cause == 'timeout')


@pytest.mark.real_media_probe
def test_stable_file_project_and_dispatch_are_unique(isolated, tmp_path, monkeypatch):
    import uuid

    source = tmp_path / 'real.mp4'
    subprocess.run(
        [
            'ffmpeg',
            '-v',
            'error',
            '-f',
            'lavfi',
            '-i',
            'color=s=64x64:r=10:d=40',
            '-f',
            'lavfi',
            '-i',
            'anullsrc=r=16000',
            '-t',
            '40',
            '-c:v',
            'libx264',
            '-c:a',
            'aac',
            str(source),
        ],
        check=True,
    )
    settings.arm(str(tmp_path), 'digest', 50)
    epoch = settings.read()['consent_epoch']
    cid = str(uuid.uuid4())
    capture = Capture(cid, str(source), 0, 38, 40)
    worker.save(capture, epoch)
    worker.save(capture, epoch)
    calls = []
    monkeypatch.setattr(worker.jobs, 'inspect_project', lambda *args: calls.append(args))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker.process, [cid, cid]))
    assert worker.latest()['status'] == 'ready'
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker.process, [cid, cid]))
    other = str(uuid.uuid4())
    worker.save(Capture(other, str(source), 0, 38, 40), epoch)
    worker.process(other)
    with database.session_scope() as db:
        project = db.query(Project).one()
        assert project.processing_config['import_source'] == 'obs' and project.id == calls[0][0]
        assert db.get(ObsCapture, other).status == 'duplicate' and len(calls) == 1
        assert 37 <= worker.preflight.probe_material(Path(project.video_path)).duration < 38
    assert source.exists()


def test_outside_or_broken_recording_never_creates_project(isolated, tmp_path):
    directory = tmp_path / 'obs'
    directory.mkdir()
    outside = tmp_path / 'outside.mkv'
    outside.write_bytes(b'broken')
    settings.arm(str(directory), 'digest', 50)
    epoch = settings.read()['consent_epoch']
    for name, path in [('outside', outside), ('broken', directory / 'bad.mp4')]:
        path.write_bytes(b'broken')
        worker.save(Capture(name, str(path), 0, 10, 10), epoch)
        worker.process(name)
    with database.session_scope() as db:
        assert [row.status for row in db.query(ObsCapture)] == ['file_error', 'file_error']
        assert db.query(Project).count() == db.query(ObsCall).count() == 0


def test_recovery_freezes_an_abandoned_dispatch(isolated, tmp_path):
    receipt(tmp_path, status='dispatching')
    worker.recover()
    assert worker.latest()['status'] == 'uncertain'
    assert not worker.pending()


def test_missing_transcription_reported_separately(isolated, tmp_path, monkeypatch):
    source = tmp_path / 'stream.mkv'
    source.write_bytes(b'test')
    settings.arm(str(tmp_path), 'digest', 10)
    worker.save(Capture('closed', str(source), 0, 10, 10), settings.read()['consent_epoch'])

    def missing(*args):
        raise worker.SetupRequired()

    monkeypatch.setattr(worker, 'inspect_media', missing)
    worker.process('closed')
    assert worker.latest() == {'status': 'setup_required', 'project_id': None}


def test_cloud_audio_response_is_cached(isolated, tmp_path):
    import httpx
    from backend.services import ai_model_settings as ai, cloud_transcription as asr

    connection = ai.Connection(id='audio', name='ASR', provider='compatible', base_url=isolated[0]['base'])
    isolated[0].update(model='whisper-1', role='audio')
    audio = tmp_path / 'chunk-0000.wav'
    audio.write_bytes(b'isolated audio fixture')
    requests = []

    def receive(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={'segments': [{'start': 1, 'end': 2, 'text': 'game'}]})

    with bind(receipt(tmp_path)), httpx.Client(transport=httpx.MockTransport(receive)) as client:
        first, _ = asr.request_chunk(client, connection, 'whisper-1', audio, 'auto')
        repeated, _ = asr.request_chunk(client, connection, 'whisper-1', audio, 'auto')
    assert first == repeated and requests == ['/v1/audio/transcriptions']


@pytest.mark.real_media_probe
def test_manual_replay_is_idle_until_selected_and_reopens_one_project(isolated, tmp_path, monkeypatch):
    app = FastAPI()
    app.state.obs = listener.Monitor()
    app.include_router(obs.router, prefix='/obs')
    client = TestClient(app)
    src = tmp_path / 'finished.mp4'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:r=10:d=40',
                    '-f', 'lavfi', '-i', 'anullsrc=r=16000', '-t', '40', '-c:v', 'libx264',
                    '-c:a', 'aac', str(src)], check=True)
    capture = Capture('observed', str(src), 2, 38, 40)
    worker.save_manual(capture, tmp_path)
    worker.save_manual(capture, tmp_path)
    assert worker.pending() == []
    initial = client.get('/obs/replays')
    assert str(src) not in initial.text and initial.json()['items'][0]['selectable']
    assert not settings.read()['consent']
    start = '/obs/replays/observed/generate'
    calls = []
    monkeypatch.setattr(worker.jobs, 'inspect_project', lambda *args: calls.append(args))
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: client.post(start).status_code, range(2))) == [202, 202]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker.process, ['observed', 'observed']))
        list(pool.map(worker.process, ['observed', 'observed']))
    history = client.get('/obs/replays').json()['items']
    assert len(history) == 1
    assert history[0]['status'] == 'submitted' and not history[0]['selectable']
    assert len(calls) == 1 and history[0]['project_id'] == calls[0][0]
    assert calls[0][1].replay_source == 'obs' and calls[0][1].goal == 'auto'
    assert not billing.is_obs(calls[0][0]) and worker.pending() == []
    assert client.post(start).status_code == 202 and not worker.pending()
    with database.session_scope() as db:
        project = db.query(Project).one()
        assert 34 < worker.preflight.probe_material(Path(project.video_path)).duration < 36
        assert project.processing_config['import_source'] == 'obs'


def test_replaced_manual_recording_never_spends_or_creates_project(isolated, tmp_path):
    src = tmp_path / 'stream.mkv'
    src.write_bytes(b'original')
    worker.save_manual(Capture('session', str(src), 0, 20, 20), tmp_path)
    assert worker.request_manual('session')
    src.write_bytes(b'replaced file')
    worker.process('session')
    assert worker.latest() == {'status': 'file_error', 'project_id': None}
    assert not worker.request_manual('session')
    with database.session_scope() as db:
        assert not db.query(Project).count() and not db.query(ObsCall).count()


def test_connected_listener_saves_a_selectable_replay_only_after_both_stops(isolated, tmp_path, monkeypatch):
    from contextlib import asynccontextmanager

    settings.connect(True, 4455, None)
    monitor = listener.Monitor()
    recording = tmp_path / 'session.mkv'
    recording.write_bytes(b'fixture')
    responses = {
        'GetVersion': {'obsVersion': '31', 'obsWebSocketVersion': '5.5', 'availableRequests': ['GetRecordDirectory']},
        'GetRecordDirectory': {'recordDirectory': str(tmp_path)},
        'GetStreamStatus': {'outputActive': False}, 'GetRecordStatus': {'outputActive': False},
    }
    events = iter([('StreamStateChanged', 'STARTED'), ('RecordStateChanged', 'STARTED'),
                   ('StreamStateChanged', 'STOPPED'), ('RecordStateChanged', 'STOPPED')])

    class Socket:
        async def recv(self):
            kind, state = next(events)
            if kind == 'RecordStateChanged' and state == 'STOPPED':
                assert monitor.phase == 'waiting_recording' and worker.replays() == []
                monitor.changed.set()
            return json.dumps({'op': 5, 'd': {'eventType': kind, 'eventData': {
                'outputState': listener.PREFIX + state, 'outputPath': str(recording)}}})

    @asynccontextmanager
    async def connection(*args, **kwargs):
        yield Socket()

    monkeypatch.setattr(listener, 'connect', connection)
    monkeypatch.setattr(listener, 'identify', AsyncMock())
    monkeypatch.setattr(listener, 'snapshot', AsyncMock(side_effect=lambda ws, name, *_: responses[name]))
    asyncio.run(monitor.observe(settings.read()))
    rows = worker.replays()
    assert len(rows) == 1 and rows[0]['selectable'] and rows[0]['project_id'] is None
    assert not worker.pending()


def test_obs_call_supports_official_openai_and_gemini_endpoints(isolated, tmp_path, monkeypatch):
    from backend.core import llm_providers

    called = []
    monkeypatch.setattr(
        billing,
        'chat',
        lambda role, base, body, key, timeout: (
            called.append((role, base, body['model'])),
            {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]},
        )[1],
    )
    pid = receipt(tmp_path)
    with bind(pid):
        openai_provider = llm_providers.OpenAIProvider(api_key='k', model_name='gpt-4o-mini')
        assert openai_provider.base_url == ''
        resp1 = openai_provider._obs_call('hello')
        assert resp1.content == 'ok'

        gemini = llm_providers.GeminiProvider.__new__(llm_providers.GeminiProvider)
        gemini.api_key = 'k'
        gemini.model_name = 'gemini-2.5-flash'
        gemini.kwargs = {}
        resp2 = gemini._obs_call('hello')
        assert resp2.content == 'ok'

    assert called[0][1] == llm_providers.OPENAI_OFFICIAL_BASE_URL
    assert 'generativelanguage.googleapis.com' in called[1][1]


def test_call_paused_is_not_swallowed_by_planning_and_formats_user_error(tmp_path, monkeypatch):
    from backend.core.failure_codes import user_visible_error
    from backend.core.sentry_setup import studio_error_code
    from backend.services.studio import intelligence, planning
    from backend.services.studio.models import ImportOptions
    from backend.tests.test_auto_vision_fallback import configure

    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    video = tmp_path / 'sample.mp4'
    video.write_bytes(b'x')
    configure(monkeypatch, 'available', mode='auto')
    monkeypatch.setattr(intelligence, '_probe', lambda _: {'duration': 120.0, 'width': 1280, 'height': 720})
    monkeypatch.setattr(planning, '_subtitle_blockers', lambda *a, **kw: (False, False))
    monkeypatch.setattr(planning, '_require_local_transcription', lambda *a, **kw: None)
    monkeypatch.setattr(intelligence, 'sample', lambda *a, **kw: [])
    err = billing.CallPaused('OBS model call limit reached', code='rate_limited', user_message='已达到本场 OBS 自动出片的模型请求次数上限')
    monkeypatch.setattr(intelligence, 'vision_call', lambda *a, **kw: (_ for _ in ()).throw(err))

    with pytest.raises(billing.CallPaused):
        planning.recommend(video, ImportOptions(auto_start=True))
    assert studio_error_code(err) == 'rate_limited'
    assert '上限' in user_visible_error(err)


def test_automation_update_keeps_active_obs_connection_and_snapshot_buffers_events(isolated, tmp_path, monkeypatch):
    app = FastAPI()
    monitor = listener.Monitor()
    app.state.obs = monitor
    app.include_router(obs.router, prefix='/obs')
    client = TestClient(app)

    vault = {}

    class Vault:
        def set_password(self, s, a, p):
            vault[(s, a)] = p

        def get_password(self, s, a):
            return vault.get((s, a))

        def delete_password(self, s, a):
            vault.pop((s, a), None)

    monkeypatch.setattr(settings, 'keychain', Vault)
    assert client.put('/obs/connection', json={'enabled': True, 'password': 'secret'}).status_code == 200
    assert client.get('/obs').json()['has_password'] is True
    cfg = settings.read()
    monitor.state, monitor.directory, monitor.supported, monitor.revision = 'connected', str(tmp_path), True, cfg['revision']
    monitor.changed.clear()
    assert client.put('/obs/automation', json={'enabled': True, 'digest': 'digest', 'revision': cfg['revision']}).status_code == 200
    assert not monitor.changed.is_set()
    assert client.get('/obs').json()['connected'] is True
    # Clearing password via empty string removes it from the vault.
    assert client.put('/obs/connection', json={'enabled': False, 'password': ''}).status_code == 200
    assert client.get('/obs').json()['has_password'] is False and not vault

    # snapshot() buffers racing op=5 events instead of failing handshake.
    ws = AsyncMock()
    ws.recv.side_effect = [
        json.dumps({'op': 5, 'd': {'eventType': 'StreamStateChanged', 'eventData': {'outputState': listener.PREFIX + 'STARTED'}}}),
        json.dumps({'op': 7, 'd': {'requestId': 'GetVersion', 'requestStatus': {'result': True}, 'responseData': {'obsVersion': '31'}}}),
    ]
    queued = []
    data = asyncio.run(listener.snapshot(ws, 'GetVersion', queued))
    assert data == {'obsVersion': '31'} and len(queued) == 1


def test_manual_obs_transient_io_uses_request_time_not_capture_created(isolated, tmp_path, monkeypatch):
    src = tmp_path / 'old.mkv'
    src.write_bytes(b'data')
    worker.save_manual(Capture('old-session', str(src), 0, 20, 20), tmp_path)
    with database.session_scope() as db:
        row = db.get(ObsCapture, 'old-session')
        row.created = time.time() - 3600  # Recorded 1 hour ago
        db.commit()
    assert worker.request_manual('old-session')
    monkeypatch.setattr(worker, 'copy_recording', lambda *a, **kw: (_ for _ in ()).throw(OSError('busy')))
    worker.process('old-session')
    # Should stay retryable (manual_waiting) instead of immediately flipping to file_error.
    with database.session_scope() as db:
        assert db.get(ObsCapture, 'old-session').status == 'manual_waiting'


@pytest.mark.real_media_probe
def test_obs_small_jitter_skips_reencode_and_larger_trim_uses_stream_copy(isolated, tmp_path, monkeypatch):
    src = tmp_path / 'gop1s.mp4'
    subprocess.run(
        [
            'ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:r=10:d=30',
            '-f', 'lavfi', '-i', 'anullsrc=r=16000', '-t', '30',
            '-c:v', 'libx264', '-g', '10', '-keyint_min', '10', '-c:a', 'aac', str(src),
        ],
        check=True,
    )
    monkeypatch.setattr(worker.readiness, 'ensure_analysis_usable', lambda: None)
    monkeypatch.setattr(worker.preflight, 'check', lambda *a, **kw: None)
    # <= 1s start/end jitter skips trimming entirely.
    monkeypatch.setattr(worker, '_trim_recording', lambda *a, **kw: pytest.fail('small jitter should not trim'))
    out_small = worker.inspect_media(src, Capture('j1', str(src), 0.4, 29.6, 30.0))
    assert out_small == src

    # Larger privacy boundary uses -c copy instead of libx264 when keyframes are dense.
    monkeypatch.undo()
    monkeypatch.setattr(worker.readiness, 'ensure_analysis_usable', lambda: None)
    monkeypatch.setattr(worker.preflight, 'check', lambda *a, **kw: None)
    cmds = []
    real_run = worker._run_ffmpeg_tracked

    def spy_run(cmd, stopping, timeout=7200):
        cmds.append(cmd)
        return real_run(cmd, stopping, timeout=timeout)

    monkeypatch.setattr(worker, '_run_ffmpeg_tracked', spy_run)
    out_trimmed = worker.inspect_media(src, Capture('j2', str(src), 4.0, 26.0, 30.0))
    assert out_trimmed != src
    assert cmds and '-c' in cmds[0] and 'copy' in cmds[0] and 'libx264' not in cmds[0]


@pytest.mark.real_media_probe
def test_manual_obs_import_via_studio_uses_user_platforms(isolated, tmp_path, monkeypatch):
    from backend.services.studio.models import ImportOptions

    src = tmp_path / 'stream.mp4'
    subprocess.run(
        [
            'ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:r=10:d=25',
            '-f', 'lavfi', '-i', 'anullsrc=r=16000', '-t', '25',
            '-c:v', 'libx264', '-g', '10', '-c:a', 'aac', str(src),
        ],
        check=True,
    )
    monkeypatch.setattr(worker.readiness, 'ensure_analysis_usable', lambda: None)
    monkeypatch.setattr(worker.preflight, 'check', lambda *a, **kw: None)
    worker.save_manual(Capture('home-pick', str(src), 0.0, 25.0, 25.0), tmp_path)
    dispatched = []
    monkeypatch.setattr(worker.jobs, 'inspect_project', lambda pid, opts, *a, **kw: (dispatched.append((pid, opts)), 'run-1')[1])
    prefs = ImportOptions(goal='auto', replay_source='obs', platforms=['tiktok', 'youtube_shorts'], auto_start=True)
    pid, run_id = worker.import_manual_with_options('home-pick', prefs, 'OBS · Night Stream')
    assert run_id == 'run-1' and len(dispatched) == 1
    assert dispatched[0][1].platforms == ['tiktok', 'youtube_shorts']
    # Re-importing the same capture returns the existing project idempotently.
    pid2, run_id2 = worker.import_manual_with_options('home-pick', prefs, 'OBS · Night Stream')
    assert pid2 == pid and run_id2 is None and len(dispatched) == 1


@pytest.mark.real_media_probe
def test_async_manual_obs_home_claim_and_prepare_recording(isolated, tmp_path, monkeypatch):
    from backend.services.studio.models import ImportOptions

    src = tmp_path / 'async_stream.mp4'
    subprocess.run(
        [
            'ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:r=10:d=25',
            '-f', 'lavfi', '-i', 'anullsrc=r=16000', '-t', '25',
            '-c:v', 'libx264', '-g', '10', '-c:a', 'aac', str(src),
        ],
        check=True,
    )
    monkeypatch.setattr(worker.readiness, 'ensure_analysis_usable', lambda: None)
    monkeypatch.setattr(worker.preflight, 'check', lambda *a, **kw: None)
    worker.save_manual(Capture('async-pick', str(src), 0.0, 25.0, 25.0), tmp_path)
    prefs = ImportOptions(goal='auto', replay_source='obs', platforms=['douyin'], auto_start=True)
    pid, created = worker.claim_manual_for_home('async-pick', prefs, 'OBS · Async')
    assert created is True
    pid2, created2 = worker.claim_manual_for_home('async-pick', prefs, 'OBS · Async')
    assert pid2 == pid and created2 is False
    with database.session_scope() as db:
        project = db.get(Project, pid)
        assert project.video_path is None
        replay_cfg = project.processing_config['obs_manual_replay']
    landed = worker.prepare_manual_recording(pid, replay_cfg)
    assert landed.is_file()
    with database.session_scope() as db:
        assert db.get(Project, pid).video_path == str(landed)
        assert db.get(ObsCapture, 'async-pick').status == 'submitted'
