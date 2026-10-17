"""#418 R26: the QA 500 switch for the model download request is off by default and only exact "1" enables it."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1 import speech_recognition as sr


@pytest.fixture
def client(monkeypatch):
    calls = []

    class Manager:
        async def download_model(self, model):
            calls.append(model)
            return 'downloading'
    monkeypatch.setattr(sr, 'get_model_manager', lambda: Manager())
    app = FastAPI()
    app.include_router(sr.router, prefix='/api/v1')
    return TestClient(app), calls


def test_off_by_default(client, monkeypatch):
    monkeypatch.delenv(sr.QA_FAIL_MODEL_DOWNLOAD_ENV, raising=False)
    http, calls = client
    assert sr.qa_fail_model_download() is False
    res = http.post('/api/v1/whisper-models/download', json={'model': 'base'})
    assert res.status_code == 202 and calls == ['base']


@pytest.mark.parametrize('value', ['0', 'true', 'yes', '', ' 1'])
def test_only_exact_one_enables(client, monkeypatch, value):
    monkeypatch.setenv(sr.QA_FAIL_MODEL_DOWNLOAD_ENV, value)
    assert sr.qa_fail_model_download() is False


def test_switch_answers_500_without_starting_a_download(client, monkeypatch):
    monkeypatch.setenv(sr.QA_FAIL_MODEL_DOWNLOAD_ENV, '1')
    http, calls = client
    res = http.post('/api/v1/whisper-models/download', json={'model': 'base'})
    assert res.status_code == 500 and calls == []


def test_no_shipped_config_sets_the_switch():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    for rel in ('src-tauri', '.github', 'env.example', 'docker-compose.yml', 'Dockerfile'):
        target = root / rel
        files = [target] if target.is_file() else [p for p in target.rglob('*') if p.is_file() and p.stat().st_size < 2_000_000] if target.exists() else []
        for f in files:
            assert sr.QA_FAIL_MODEL_DOWNLOAD_ENV not in f.read_text(encoding='utf-8', errors='ignore'), f


def test_switch_log_says_qa_simulation(client, monkeypatch, caplog):
    """#405: the local log is still written and names it a QA simulation."""
    import logging
    monkeypatch.setenv(sr.QA_FAIL_MODEL_DOWNLOAD_ENV, '1')
    http, _ = client
    with caplog.at_level(logging.WARNING, logger=sr.logger.name):
        res = http.post('/api/v1/whisper-models/download', json={'model': 'base'})
    assert res.status_code == 500 and res.json()['detail'] == sr.QA_MOCK_DOWNLOAD_DETAIL
    lines = [r.getMessage() for r in caplog.records if sr.QA_FAIL_MODEL_DOWNLOAD_ENV in r.getMessage()]
    assert lines and all('QA 模拟' in line for line in lines), lines


def test_endpoint_docstring_is_kept():
    """#405: the switch check sits after the docstring, so the endpoint keeps its docs."""
    assert sr.download_whisper_model.__doc__ and 'Whisper' in sr.download_whisper_model.__doc__


def test_switch_sends_no_telemetry_and_nothing_to_sentry(client, monkeypatch):
    """#406 + R27b I427: with the production Sentry init (init_sentry, production before_send, no Starlette
    integration added) the QA simulated 500 sends 0 Sentry events and 0 success-rate events, and a real model
    download 500 is reported exactly once, carrying only the error code and status (no message, no path)."""
    import sentry_sdk
    from backend.core import llm_emit, sentry_setup

    telemetry = []
    monkeypatch.setattr(llm_emit, '_post_event', lambda event, props: telemetry.append(event))
    events = []

    class Transport(sentry_sdk.transport.Transport):
        def capture_envelope(self, envelope):
            events.extend(item.payload.json for item in envelope.items if item.type == 'event')

    real_init = sentry_sdk.init
    seen = {}

    def init_with_memory_transport(*args, **kwargs):
        seen.update(kwargs)
        return real_init(*args, transport=Transport(), **kwargs)
    monkeypatch.setattr(sentry_sdk, 'init', init_with_memory_transport)
    monkeypatch.setattr(sentry_setup, '_initialized', False)
    monkeypatch.setattr(sentry_setup, 'crash_reports_enabled', lambda: True)
    monkeypatch.setattr(sentry_setup, 'sync_anonymous_user', lambda *a, **k: None)
    monkeypatch.setenv('SENTRY_DSN', 'https://k@o0.ingest.sentry.io/0')
    try:
        assert sentry_setup.init_sentry('desktop') is True
        names = {type(i).__name__ for i in seen['integrations']}
        assert 'StarletteIntegration' not in names and seen['auto_enabling_integrations'] is False
        assert seen['before_send'] is sentry_setup.before_send

        monkeypatch.setenv(sr.QA_FAIL_MODEL_DOWNLOAD_ENV, '1')
        http, calls = client
        res = http.post('/api/v1/whisper-models/download', json={'model': 'base'})
        sentry_sdk.flush()
        assert res.status_code == 500 and calls == []
        assert telemetry == [], telemetry
        assert events == [], 'QA simulated 500 reported to Sentry'

        monkeypatch.delenv(sr.QA_FAIL_MODEL_DOWNLOAD_ENV)

        class Broken:
            async def download_model(self, model):
                raise RuntimeError('disk full at /Users/someone/models/base.pt')
        monkeypatch.setattr(sr, 'get_model_manager', lambda: Broken())
        assert http.post('/api/v1/whisper-models/download', json={'model': 'base'}).status_code == 500
        sentry_sdk.flush()
        assert len(events) == 1, f'a real download 500 is reported exactly once, got {len(events)}'
        event = events[0]
        text = str(event)
        assert 'disk full' not in text and '/Users/' not in text and 'base.pt' not in text
        assert set(event.get('tags', {})) <= {'error_code', 'http_status', 'runtime', 'app_mode', 'os', 'arch', 'build_environment'}
        assert event['tags']['http_status'] == '500' and event['tags']['error_code']
        assert 'request' not in event and 'extra' not in event
    finally:
        real_init(dsn=None)


def test_switch_affects_only_the_model_download(monkeypatch):
    """Group decision: the switch acts on the model download request only; other routes answer as usual."""
    class Manager:
        def get_model_info(self, name):
            return None
    monkeypatch.setattr(sr, 'get_model_manager', lambda: Manager())
    app = FastAPI()
    app.include_router(sr.router, prefix='/api/v1')
    http = TestClient(app)
    monkeypatch.setenv(sr.QA_FAIL_MODEL_DOWNLOAD_ENV, '1')
    res = http.delete('/api/v1/whisper-models/base')
    assert res.status_code == 404, res.text
    assert sr.QA_MOCK_DOWNLOAD_DETAIL not in res.text
