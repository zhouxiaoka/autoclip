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
