"""Persisted connection loss must stop startup before any provider request."""
import json

import httpx
import pytest

from backend.services import ai_model_settings as ai
from backend.services.studio import jobs, readiness, store, vision_settings
from backend.services.studio.models import ConfirmPlan


@pytest.fixture
def missing_connection(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    # A usable old provider must never rescue a broken named assignment.
    (tmp_path / 'settings.json').write_text(json.dumps({
        'llm_provider': 'openai', 'openai_base_url': 'https://old.example/v1',
        'openai_api_key': 'test-only-key', 'model_name': 'gpt-4o-mini',
    }))
    (tmp_path / 'vision-settings.json').write_text(json.dumps({
        'mode': 'custom', 'base_url': 'https://old-vision.example/v1',
        'api_key': 'test-only-key', 'model': 'gpt-4o-mini',
    }))
    raw = {
        'version': 1,
        'connections': [{'id': 'a', 'name': 'Analysis', 'provider': 'compatible',
                         'base_url': 'https://analysis.example/v1', 'api_key': 'test-only-key'}],
        'analysis': {'connection_id': 'a', 'model': 'gpt-4o-mini', 'capability': 'multimodal'},
        'vision': {'connection_id': 'a', 'model': 'gpt-4o-mini', 'capability': 'multimodal'},
    }
    calls = []

    def deny_request(*args, **kwargs):
        calls.append(True)
        raise AssertionError('Unexpected provider HTTP request')

    original_send = httpx.Client.send

    def send(client, request, *args, **kwargs):
        if request.url.host == 'testserver':
            return original_send(client, request, *args, **kwargs)
        return deny_request()

    monkeypatch.setattr(httpx.Client, 'send', send)
    monkeypatch.setattr(httpx.AsyncClient, 'send', deny_request)
    import requests
    monkeypatch.setattr(requests.Session, 'send', deny_request)
    return raw, calls


@pytest.mark.parametrize('role', ['analysis', 'vision'])
@pytest.mark.parametrize('legacy', [True, False])
def test_saved_missing_connection_blocks_pipeline_start(missing_connection, role, legacy, monkeypatch):
    raw, calls = missing_connection
    raw[role]['connection_id'] = 'removed'
    if not legacy:
        raw['acked_catalog_version'] = 1
        raw['seen_notices'] = []
    ai.path().write_text(json.dumps(raw))
    original = ai.path().read_bytes()
    store.directory('project').mkdir(parents=True)
    store.write('project', {
        'analysis': {'status': 'awaiting_confirmation'},
        'plan': {'id': 'plan', 'recommended_analysis': 'visual'},
    })
    before = store.read('project')
    dispatched = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda *a, **k: dispatched.append(True))
    with pytest.raises(ValueError, match='修复'):
        readiness.ensure_analysis_usable()
    with pytest.raises(ValueError, match='修复'):
        jobs.confirm_project('project', ConfirmPlan(plan_id='plan', goals=['highlight'], analysis_mode='visual'))
    assert store.read('project') == before
    assert ai.path().read_bytes() == original
    assert dispatched == []
    assert calls == []

    # Exercise the actual desktop API boundary, not just its readiness helper.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.api.v1.studio import router
    from backend.core.database import get_db
    from backend.models import Base, Project
    engine = create_engine('sqlite:///' + str(ai.path().parent / 'api.sqlite'),
                           connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Project(id='project', name='Test'))
        db.commit()

    def get_test_db():
        with sessions() as db:
            yield db

    app = FastAPI()
    app.include_router(router, prefix='/studio')
    app.dependency_overrides[get_db] = get_test_db
    try:
        with TestClient(app) as client:
            response = client.post('/studio/project/start', json={
                'plan_id': 'plan', 'goals': ['highlight'], 'analysis_mode': 'visual',
            })
            assert response.status_code == 422
            assert '修复' in response.json()['detail']
            response = client.post('/studio/import', data={'auto_start': 'true'},
                                   files={'video': ('test.mp4', b'test-only', 'video/mp4')})
            assert response.status_code == 422
            assert '修复' in response.json()['detail']
    finally:
        engine.dispose()
    assert store.read('project') == before
    assert dispatched == []
    assert calls == []


@pytest.mark.parametrize('role', ['analysis', 'vision'])
@pytest.mark.parametrize('legacy', [True, False])
def test_runtime_readers_never_borrow_another_connection(missing_connection, role, legacy, monkeypatch):
    raw, calls = missing_connection
    raw[role]['connection_id'] = 'removed'
    if not legacy:
        raw['acked_catalog_version'] = 1
    ai.path().write_text(json.dumps(raw))
    if legacy:
        settings = ai.load()
        with pytest.raises(ValueError, match='修复'):
            ai.vision_endpoint(settings)
    with pytest.raises(ValueError, match='修复'):
        vision_settings.effective()
    if role == 'analysis' or not legacy:
        from backend.core.llm_manager import LLMManager
        monkeypatch.setattr(LLMManager, '_sync_config_if_needed', lambda self: None)
        with pytest.raises(ValueError, match='修复'):
            LLMManager()
    assert calls == []


def test_explicit_follow_analysis_still_resolves(missing_connection):
    raw, calls = missing_connection
    raw['vision'] = None
    ai.path().write_text(json.dumps(raw))
    readiness.ensure_analysis_usable()
    assert vision_settings.effective()['base_url'] == 'https://analysis.example/v1'
    assert calls == []


def test_hot_reload_cannot_keep_using_the_previous_provider(missing_connection, monkeypatch):
    from backend.core.llm_manager import LLMManager
    raw, calls = missing_connection
    ai.path().write_text(json.dumps(raw))
    monkeypatch.setattr(LLMManager, '_sync_config_if_needed', lambda self: None)
    manager = LLMManager()
    assert manager.current_provider is not None
    raw['analysis']['connection_id'] = 'removed'
    ai.path().write_text(json.dumps(raw))
    # A failed reload must stay blocked on subsequent calls too.
    for _ in range(2):
        with pytest.raises(ValueError, match='修复'):
            manager.call('test', 'test')
        assert manager.current_provider is None
    raw['analysis']['connection_id'] = 'a'
    ai.path().write_text(json.dumps(raw))
    assert manager.openai_compatible_endpoint()['base_url'] == 'https://analysis.example/v1'
    assert manager.current_provider is not None
    assert calls == []
