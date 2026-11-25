"""Regression tests for v1.6.2 P0 fixes (PostHog + Sentry 14d review).

Covers:
1. PYTHON-FASTAPI-1C / -81: SQLite WAL pragma runs once per engine and defers gracefully on Windows OperationalError.
2. Gemini: AQ. key prefix hint + automatic live-model fallback when preset default returns model_not_found.
3. Ollama: 45-min local clip job budget + thinking-model retry in _trial_once.
4. Telemetry: failure_stage never falls back to 'other' over a specific pipeline stage.
"""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from backend.core import database, failure_attribution, job_budget, llm_emit
from backend.core.provider_endpoint import hint_provider_for_key
from backend.core.provider_model_fetch import AccountModelList
from backend.core.upstream_errors import ClassifiedUpstreamError, UpstreamErrorType
from backend.services import ai_model_settings as ai
from backend.services import provider_validation as pv


def test_sqlite_pragmas_initializes_wal_once_and_defers_on_windows_io_error(tmp_path):
    db_file = tmp_path / "wal_once.db"
    eng = database.create_database_engine(f"sqlite:///{db_file}")
    try:
        with eng.connect() as conn:
            assert str(conn.execute(text("PRAGMA journal_mode")).fetchone()[0]).lower() == "wal"
            assert int(conn.execute(text("PRAGMA busy_timeout")).fetchone()[0]) == 30000
        # Subsequent NullPool connections still get busy_timeout=30000 without error.
        with eng.connect() as conn2:
            assert int(conn2.execute(text("PRAGMA busy_timeout")).fetchone()[0]) == 30000
    finally:
        eng.dispose()

    # Simulate transient Windows OperationalError (e.g. SQLITE_IOERR=10 or code=0) during WAL pragma.
    db_file2 = tmp_path / "wal_err.db"
    eng2 = database.create_database_engine(f"sqlite:///{db_file2}")
    listeners = list(eng2.pool.dispatch.connect)
    assert listeners

    class _FlakyCursor:
        def __init__(self):
            self.calls = []
            self.closed = False

        def execute(self, sql):
            self.calls.append(sql)
            if "journal_mode" in sql:
                err = sqlite3.OperationalError("disk I/O error")
                err.sqlite_errorcode = 10  # SQLITE_IOERR
                raise err
            return self

        def fetchone(self):
            return ("delete",)

        def close(self):
            self.closed = True

    class _FakeConn:
        def __init__(self):
            self.cur = _FlakyCursor()

        def cursor(self):
            return self.cur

    fake = _FakeConn()
    listeners[-1](fake, None)
    assert fake.cur.closed is True
    assert fake.cur.calls[-1] == "PRAGMA busy_timeout=30000"
    eng2.dispose()


def test_gemini_aq_key_hint_and_preset_default_live_fallback(monkeypatch):
    assert hint_provider_for_key("AQ.Ab8RN6exampleKey123") == "gemini"
    assert hint_provider_for_key("AIzaSyExampleKey123") == "gemini"

    live = AccountModelList(
        ok=True,
        source="live",
        models=["gemini-2.5-flash", "gemini-2.5-pro"],
        recommended={"analysis": ["gemini-2.5-flash"]},
    )
    monkeypatch.setattr(pv, "_get_models", lambda *a, **k: (live.models, None, live))
    probed = []

    def fake_probe(base, api_key, model, provider="compatible", *, options=None):
        probed.append(model)
        if model == "gemini-3.8-flash":
            return ClassifiedUpstreamError(UpstreamErrorType.MODEL_NOT_FOUND, retryable=False, hint_key="missing")
        if model == "gemini-2.5-flash":
            return None
        return ClassifiedUpstreamError(UpstreamErrorType.MODEL_NOT_FOUND, retryable=False, hint_key="missing")

    monkeypatch.setattr(pv, "_probe", fake_probe)
    conn = ai.Connection(
        id="g1", name="Gemini", provider="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="AQ.Ab8RN6test",
    )
    # Preset default missing from account's /models falls back to live recommended gemini-2.5-flash.
    res = pv._validate_resolved(conn, "gemini-3.8-flash", purpose="analysis")
    assert res.ok is True
    assert res.validated_model == "gemini-2.5-flash"
    assert res.as_api()["validated_model"] == "gemini-2.5-flash"
    assert probed == ["gemini-3.8-flash", "gemini-2.5-flash"]

    # A user-typed bogus model name must NOT silently succeed via fallback.
    probed.clear()
    bad = pv._validate_resolved(conn, "gemini-totally-bogus-999", purpose="analysis")
    assert bad.ok is False
    assert bad.error_type == "model_not_found"
    assert probed == ["gemini-totally-bogus-999"]


def test_local_ollama_job_budget_and_thinking_model_trial_retry(monkeypatch):
    assert job_budget.clip_job_budget_seconds(local=False) == 20 * 60
    assert job_budget.clip_job_budget_seconds(local=True) == 45 * 60

    ollama_settings = SimpleNamespace(
        connections=[SimpleNamespace(id="c1", provider="ollama", base_url="http://localhost:11434/v1")],
        analysis=SimpleNamespace(connection_id="c1"),
    )
    monkeypatch.setattr(ai, "load", lambda **k: ollama_settings)
    assert job_budget._is_local_analysis_provider() is True
    token = job_budget.bind_clip_job()
    try:
        remaining = job_budget._current.get().remaining()
        assert 44 * 60 < remaining <= 45 * 60
    finally:
        job_budget.unbind_clip_job(token)

    cloud_settings = SimpleNamespace(
        connections=[SimpleNamespace(id="c2", provider="deepseek", base_url="https://api.deepseek.com")],
        analysis=SimpleNamespace(connection_id="c2"),
    )
    monkeypatch.setattr(ai, "load", lambda **k: cloud_settings)
    assert job_budget._is_local_analysis_provider() is False

    # Thinking model spending 2048 tokens on reasoning_content retries with 4096 tokens and passes JSON.
    calls = []

    class _FakeResp:
        def __init__(self, payload):
            self.status_code = 200
            self.text = ""
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json=None, headers=None):
            calls.append(json)
            if len(calls) == 1:
                return _FakeResp({
                    "choices": [{
                        "finish_reason": "length",
                        "message": {"content": "", "reasoning_content": "thinking..."},
                    }]
                })
            return _FakeResp({
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"topics":[{"title":"Intro","subtopics":["A"]}]}'},
                }]
            })

    import httpx
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    out = pv._trial_once("http://localhost:11434/v1", "", "qwen3.5:9b", "prompt", provider="ollama")
    assert out["ok_http"] is True
    assert out["json_ok"] is True
    assert len(calls) == 2
    assert calls[0]["max_tokens"] == pv.TRIAL_MAX_TOKENS
    assert calls[1]["max_tokens"] == pv.TRIAL_REASONING_MAX_TOKENS


def test_failure_stage_other_never_shadows_specific_stage():
    assert llm_emit._current_stage() is None

    class _Err(failure_attribution.AttributedError):
        pass

    err = _Err("upstream failed")
    err.attribution = failure_attribution.FailureAttribution._make(
        failure_attribution.SOURCE_REQUEST,
        {"provider": "gemini", "config_source": "preset"},
        http_status=503,
        upstream_error_type="upstream_unavailable",
        failure_stage="other",
    )
    snap = failure_attribution.build_attribution(err, failure_stage="outline")
    assert snap is not None
    assert snap.failure_stage == "outline"
    assert snap.upstream_error_type == "upstream_unavailable"
