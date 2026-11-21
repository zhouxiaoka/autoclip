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
    monkeypatch.setattr(listener, 'snapshot', AsyncMock(side_effect=lambda ws, name: responses[name]))
    asyncio.run(monitor.observe(settings.read()))
    rows = worker.replays()
    assert len(rows) == 1 and rows[0]['selectable'] and rows[0]['project_id'] is None
    assert not worker.pending()
