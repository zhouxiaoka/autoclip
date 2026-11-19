"""A3-1 / A3-2: New API billing probe before paid Studio calls."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def clear_quota_cache():
    from backend.core import quota_precheck as qp
    qp.clear_cache()
    yield
    qp.clear_cache()


def _http(payload, status=200):
    body = json.dumps(payload).encode('utf-8')
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    resp.status = status
    return resp


def test_a3_1_limit_vs_usage_exhausted_and_ok(monkeypatch):
    from backend.core import quota_precheck as qp
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url if hasattr(req, 'full_url') else str(req))
        url = calls[-1]
        if 'subscription' in url:
            return _http({'hard_limit_usd': 10})
        return _http({'total_usage': 1000})  # $10.00

    monkeypatch.setattr(qp.urllib.request, 'urlopen', fake_urlopen)
    assert qp.check_quota(provider='api88', base_url='https://api.example/v1', api_key='sk-test') == 'exhausted'
    calls.clear()
    qp.clear_cache()

    def ok_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if 'subscription' in url:
            return _http({'hard_limit_usd': 10})
        return _http({'total_usage': 500})  # $5.00 remaining

    monkeypatch.setattr(qp.urllib.request, 'urlopen', ok_urlopen)
    assert qp.check_quota(provider='api88', base_url='https://api.example/v1', api_key='sk-test') == 'ok'


def test_a3_1_unavailable_fail_open(monkeypatch):
    from backend.core import quota_precheck as qp
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.HTTPError('https://x', 404, 'no', hdrs=None, fp=None)

    monkeypatch.setattr(qp.urllib.request, 'urlopen', boom)
    assert qp.check_quota(provider='api88', base_url='https://api.example/v1', api_key='sk-test') == 'unavailable'

    def timeout(req, timeout=None):
        raise TimeoutError('slow')

    qp.clear_cache()
    monkeypatch.setattr(qp.urllib.request, 'urlopen', timeout)
    assert qp.check_quota(provider='api88', base_url='https://api.example/v1', api_key='sk-test') == 'unavailable'

    def bad_json(req, timeout=None):
        resp = MagicMock()
        resp.read.return_value = b'not-json'
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    qp.clear_cache()
    monkeypatch.setattr(qp.urllib.request, 'urlopen', bad_json)
    assert qp.check_quota(provider='api88', base_url='https://api.example/v1', api_key='sk-test') == 'unavailable'


def test_a3_1_cache_and_skipped(monkeypatch):
    from backend.core import quota_precheck as qp
    calls = {'n': 0}

    def once(req, timeout=None):
        calls['n'] += 1
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if 'subscription' in url:
            return _http({'hard_limit_usd': 10})
        return _http({'total_usage': 100})

    monkeypatch.setattr(qp.urllib.request, 'urlopen', once)
    assert qp.check_quota(provider='api88', base_url='https://api.example/v1', api_key='sk-test') == 'ok'
    assert qp.check_quota(provider='api88', base_url='https://api.example/v1', api_key='sk-test') == 'ok'
    assert calls['n'] == 2  # subscription + usage once
    assert qp.check_quota(provider='openai', base_url='https://api.openai.com/v1', api_key='sk') == 'skipped'
    assert calls['n'] == 2


def test_a3_2_submit_production_exhausted_makes_no_llm_calls(tmp_path, monkeypatch):
    """Regression: before fix, exhausted keys still entered the worker; after, billable=0 at dispatch."""
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    from backend.core import quota_precheck as qp
    from backend.services.studio import jobs, store

    monkeypatch.setattr(qp, 'check_for_analysis_settings', lambda: ('exhausted', {'provider': 'api88'}))
    llm_calls = []
    def _no_submit(*a, **k):
        llm_calls.append((a, k))
        raise AssertionError('must not submit when quota exhausted')
    monkeypatch.setattr(jobs.executor, 'submit', _no_submit)

    (store.directory('p-quota') / 'metadata').mkdir(parents=True)
    store.write('p-quota', {
        'id': 'p-quota',
        'analysis': {'status': 'awaiting_confirmation', 'run_id': 'r1', 'phase': 'screening'},
        'generation': {'status': 'queued', 'auto_start': True, 'run_id': 'r1'},
    })
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    jobs._submit_production('p-quota', 'r1', {'platforms': ['original']})
    assert llm_calls == []
    state = store.read('p-quota')
    gen = state.get('generation') or {}
    assert gen.get('error_code') == 'provider_error'
    assert gen.get('upstream_error_type') == 'insufficient_quota'
    assert gen.get('quota_precheck') == 'exhausted'
    assert gen.get('billable_calls_before_failure') == 0


def test_quota_cache_separates_keys_with_the_same_prefix(monkeypatch):
    from backend.core import quota_precheck as qp

    def probe(_base, key):
        return 'exhausted' if key.endswith('empty') else 'ok'

    monkeypatch.setattr(qp, '_probe_new_api', probe)
    args = {'provider': 'api88', 'base_url': 'https://example.invalid/v1'}
    assert qp.check_quota(**args, api_key='test-credential-empty') == 'exhausted'
    assert qp.check_quota(**args, api_key='test-credential-funded') == 'ok'


def test_import_exposes_a_coded_quota_refusal(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1 import studio
    from backend.core import quota_precheck
    from backend.services import ai_model_settings as models
    from backend.tests.test_studio_readiness import document

    connection = models.Connection(id='ai', name='Test', provider='api88', api_key='fixture')
    settings = document(connections=[connection], analysis=models.Assignment(connection_id='ai', model='gpt-4o-mini'))
    monkeypatch.setattr(models, 'load', lambda: settings)
    monkeypatch.setattr(models, 'save', lambda *_: None)
    monkeypatch.setattr(quota_precheck, 'check_for_analysis_settings', lambda: ('exhausted', {}))
    app = FastAPI()
    app.include_router(studio.router, prefix='/studio')
    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.post('/studio/import', data={'url': 'https://youtu.be/example'})
    assert res.status_code == 422
    assert res.json()['detail']['code'] == 'insufficient_quota'
    assert res.json()['detail']['message']
