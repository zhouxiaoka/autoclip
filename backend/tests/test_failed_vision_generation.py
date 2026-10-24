"""B5: saved failed vision validation blocks HTTP generation before dispatch."""
import subprocess

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.services import ai_model_settings as ai
from backend.services.studio import jobs, store
from backend.tests.test_studio import root, source, client


def test_subtitle_import_screening_ignores_failed_vision(client, source, monkeypatch):
    """import must finish its real screening worker with a failed vision binding."""
    from backend.services.studio import intelligence

    ai.save(ai.ModelSettings(
        connections=[
            ai.Connection(id='a', name='Analysis', provider='ollama', api_key='', validation_status='ok'),
            ai.Connection(id='v', name='Vision', provider='openai', api_key='', validation_status='failed'),
        ],
        analysis=ai.Assignment(connection_id='a', model='local-text', capability='text'),
        vision=ai.Assignment(connection_id='v', model='gpt-4o', capability='multimodal'),
        analysis_mode='subtitle',
    ))
    original_settings = ai.path().read_bytes()
    with pytest.raises(ValueError, match='未通过校验'):
        intelligence.ready()

    class Immediate:
        def submit(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)

    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(intelligence, 'vision_call', lambda *a, **k: pytest.fail('Unexpected vision request'))
    monkeypatch.setattr(intelligence, 'text_json', lambda *a, **k: pytest.fail('Unexpected text request'))
    video = source.with_name('subtitle-source.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=160x90:r=1:d=21',
                    '-y', str(video)], check=True)
    subtitles = b'1\n00:00:00,000 --> 00:00:10,000\nSynthetic subtitle\n'
    response = client.post('/studio/import', files={
        'video': ('fixture.mp4', video.read_bytes(), 'video/mp4'),
        'subtitle': ('fixture.srt', subtitles, 'application/x-subrip'),
    })
    assert response.status_code == 200
    pid = response.json()['project_id']
    state = client.get('/studio/' + pid).json()
    assert state['analysis']['status'] == 'awaiting_confirmation'
    assert state['generation']['status'] == 'awaiting_confirmation'
    assert state['plan']['mode'] == 'local'
    assert state['plan']['recommended_analysis'] == 'subtitle'
    assert state['plan']['local_evidence']['subtitle_status'] == 'available'
    assert (store.directory(pid) / 'raw/input.srt').read_bytes() == subtitles
    assert ai.path().read_bytes() == original_settings


@pytest.mark.parametrize('mode', ['visual'])  # S5: auto now falls back to subtitles (test_auto_vision_fallback.py)
def test_failed_vision_blocks_generation_api_and_repair_restores_start(tmp_path, monkeypatch, mode):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    from backend.api.v1.studio import router
    from backend.core.database import get_db
    from backend.models import Base, Project
    monkeypatch.setattr('backend.services.studio.readiness._transcription', lambda _: {'ok': True, 'code': 'whisper_installed', 'repair': 'none'})
    monkeypatch.setattr('backend.services.studio.readiness._ffmpeg', lambda: {'ok': True, 'code': 'available', 'repair': 'none'})
    settings = ai.ModelSettings(
        connections=[
            ai.Connection(id='a', name='Analysis', provider='openai', api_key='fixture', validation_status='ok'),
            ai.Connection(id='v', name='Vision', provider='openai', api_key='fixture', validation_status='failed'),
        ],
        analysis=ai.Assignment(connection_id='a', model='gpt-4o', capability='multimodal'),
        vision=ai.Assignment(connection_id='v', model='gpt-4o', capability='multimodal'),
        analysis_mode=mode,
    )
    ai.save(settings)
    original_settings = ai.path().read_bytes()
    store.directory('project').mkdir(parents=True)
    store.write('project', {
        'analysis': {'status': 'awaiting_confirmation'},
        'plan': {'id': 'plan', 'recommended_analysis': 'visual', 'preferences': {}},
    })
    original_project = store.read('project')
    dispatched, requests = [], []
    monkeypatch.setattr(jobs.executor, 'submit', lambda *a, **k: dispatched.append(True))
    original_send = httpx.Client.send

    def deny_request(*args, **kwargs):
        requests.append(True)
        raise AssertionError('Unexpected provider request')

    def send(client, request, *args, **kwargs):
        if request.url.host == 'testserver':
            return original_send(client, request, *args, **kwargs)
        return deny_request()

    monkeypatch.setattr(httpx.Client, 'send', send)
    monkeypatch.setattr(httpx.AsyncClient, 'send', deny_request)
    monkeypatch.setattr('requests.Session.send', deny_request)
    engine = create_engine('sqlite:///' + str(tmp_path / 'api.sqlite'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Project(id='project', name='Test'))
        db.commit()

    def test_db():
        with sessions() as db:
            yield db

    app = FastAPI()
    app.include_router(router, prefix='/studio')
    app.dependency_overrides[get_db] = test_db
    body = {'plan_id': 'plan', 'goals': ['highlight'], 'analysis_mode': 'visual'}
    try:
        with TestClient(app) as client:
            report = client.get('/studio/readiness').json()
            responses = [client.post('/studio/project/start', json=body)]
            if mode != 'subtitle':
                responses.append(client.post('/studio/import', data={'auto_start': 'true'}, files={'video': ('fixture.mp4', b'fixture', 'video/mp4')}))
            for response in responses:
                assert response.status_code == 422
                assert '未通过校验' in response.json()['detail']
                assert 'fixture' not in response.text
            assert report['ready'] is (mode == 'subtitle')
            assert report['checks']['visual'] == (
                {'ok': True, 'code': 'not_required', 'repair': 'none'} if mode == 'subtitle'
                else {'ok': False, 'code': 'validation_failed', 'repair': 'settings_vision'}
            )
            assert store.read('project') == original_project
            assert ai.path().read_bytes() == original_settings
            assert dispatched == requests == []
            with sessions() as db:
                assert db.query(Project).count() == 1

            # A successful revalidation unblocks the same saved project; no worker runs.
            repaired = ai.load()
            repaired.connections[1].validation_status = 'ok'
            ai.save(repaired)
            assert client.get('/studio/readiness').json()['ready'] is True
            response = client.post('/studio/project/start', json=body)
            assert response.status_code == 200
            assert dispatched == [True]
            assert requests == []
    finally:
        engine.dispose()
