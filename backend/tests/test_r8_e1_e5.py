"""Round-8 blockers E2–E5 (E1 lives in frontend/tests/default-model-slots.test.cjs).

Every case here fails on 6714deb5 with the fix's source reverted. All secrets are synthetic
markers; assertions never print them.
"""
from __future__ import annotations

import contextvars
import io
import logging
import threading

import pytest
from fastapi.testclient import TestClient

MARK = "plainmarker7Qx"  # synthetic, not a key shape the old regexes knew


def _no_mark(text: str) -> bool:
    return MARK not in text


# ---------------- E2: per-call, concurrency-safe retry accumulation ----------------

def _finish(llm_emit, retries, outcome="success"):
    llm_emit.request_finished(
        provider="openai", model="m", outcome=outcome, retries=retries,
        http_status=200 if outcome == "success" else 503, prompt_tokens=1, completion_tokens=1,
    )


def test_e2_interleaved_calls_in_two_contexts_count_each_retry():
    """A0 B0 A1 B1 in two worker contexts: 2 retries (6714deb5 recorded 1)."""
    from backend.core import llm_emit

    with llm_emit.track_run():
        a, b = contextvars.copy_context(), contextvars.copy_context()
        a.run(llm_emit.begin_logical_call)
        b.run(llm_emit.begin_logical_call)
        a.run(_finish, llm_emit, 0, "error")
        b.run(_finish, llm_emit, 0, "error")
        a.run(_finish, llm_emit, 1)
        b.run(_finish, llm_emit, 1)
        assert llm_emit.run_snapshot()["retry_count"] == 2


def test_e2_interleaving_does_not_inflate():
    """A0 A1 B0 A2: A retried twice, B none → 2 (6714deb5 recorded 3)."""
    from backend.core import llm_emit

    with llm_emit.track_run():
        a, b = contextvars.copy_context(), contextvars.copy_context()
        a.run(llm_emit.begin_logical_call)
        b.run(llm_emit.begin_logical_call)
        a.run(_finish, llm_emit, 0, "error")
        a.run(_finish, llm_emit, 1, "error")
        b.run(_finish, llm_emit, 0)
        a.run(_finish, llm_emit, 2)
        assert llm_emit.run_snapshot()["retry_count"] == 2


def test_e2_consecutive_vision_calls_each_count_their_retry(monkeypatch):
    """Two real vision_call()s, each with one max_completion_tokens compat retry → 2."""
    import json
    import urllib.error
    import urllib.request
    from backend.core import llm_emit
    from backend.services.studio import intelligence

    sent = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=None):
        payload = json.loads(req.data)
        sent.append(payload)
        if "max_tokens" in payload:
            body = json.dumps({"error": {"message": "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead."}}).encode()
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(body))
        out = {"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
               "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        return Resp(json.dumps(out).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("backend.core.llm_providers.token_param_kwargs",
                        lambda model, base, body: {**body, "max_tokens": 64})
    config = {"base_url": "https://vision.example.invalid/v1", "api_key": "", "model": "vision-model", "timeout": 5}
    with llm_emit.track_run():
        for _ in range(2):
            try:
                intelligence.vision_call([{"type": "text", "text": "x"}], config=config)
            except Exception:  # noqa: BLE001 - result parsing is not under test
                pass
        assert len(sent) == 4, "each call must hit the compat retry"
        assert llm_emit.run_snapshot()["retry_count"] == 2


def test_e2_real_threads_share_run_without_lost_updates():
    """Many concurrent calls via run_in_context: calls and retries both exact."""
    from backend.core import llm_emit
    from backend.core.llm_usage import run_in_context

    with llm_emit.track_run():
        def worker():
            llm_emit.begin_logical_call()
            _finish(llm_emit, 0, "error")
            _finish(llm_emit, 1)

        threads = [threading.Thread(target=run_in_context(worker)) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        snap = llm_emit.run_snapshot()
        assert snap["llm_calls"] == 32
        assert snap["retry_count"] == 16


# ---------------- E3: whole Authorization value, every query value ----------------

@pytest.mark.parametrize("raw", [
    f"Authorization: Key {MARK}",
    f"Authorization: Token {MARK} extra",
    f"authorization={MARK}",
    f'{{"Authorization": "Key {MARK}"}}',
    f"Proxy-Authorization: Basic {MARK}",
    f"https://cdn.example/private/x.png?auth={MARK}",
    f"https://res.example/img?w=1&__cld_token__={MARK}&h=2",
    f"GET https://api.example/v1/models?pageSize=50&foo={MARK}",
])
def test_e3_redact_text_drops_auth_value_and_query_values(raw):
    from backend.core.log_redaction import redact_text, REDACTED

    out = redact_text(raw)
    assert _no_mark(out)
    assert REDACTED in out


def test_e3_image_provider_error_chain_is_redacted_in_logs():
    """Real _raise_for_status → ImageError → RedactingFilter: no signed URL value survives."""
    from backend.core.image_providers import ImageError, _raise_for_status
    from backend.core.log_redaction import RedactingFilter

    class Resp:
        status_code = 403
        text = f"denied https://cdn.example/obj.png?auth={MARK} Authorization: Key {MARK}"

        def json(self):
            return {"error": {"message": self.text}}

    with pytest.raises(ImageError) as caught:
        _raise_for_status(Resp())
    record = logging.LogRecord("cover", logging.WARNING, __file__, 1, "cover failed: %s", (str(caught.value),), None)
    RedactingFilter().filter(record)
    assert _no_mark(record.getMessage())


# ---------------- E4: 422 never echoes a credential field's input ----------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    from backend.app_factory import create_app
    with TestClient(create_app(mode="web"), raise_server_exceptions=False) as c:
        yield c


@pytest.mark.parametrize("value", [
    MARK + "Z" * 2100,            # string, field-level too long
    [MARK],                       # list
    {"value": MARK},              # object
    {"nested": [{"deep": MARK}]},  # nested
    int("9" * 19),                # number (marker-free; checked by input absence)
], ids=["long-string", "list", "dict", "nested", "number"])
def test_e4_422_omits_input_for_api_key_of_any_type(client, value):
    body = {
        "version": 1,
        "connections": [{"id": "c1", "name": "o", "provider": "openai", "api_key": value, "base_url": ""}],
        "analysis": {"connection_id": "c1", "model": "m"},
        "cover_enabled": False,
    }
    response = client.put("/api/v1/settings/ai-models", json=body)
    assert response.status_code == 422
    assert _no_mark(response.text)
    assert "9" * 19 not in response.text
    payload = response.json()
    entries = payload["detail"]
    secret_entries = [e for e in entries if "api_key" in [str(p) for p in e.get("loc", [])]]
    assert secret_entries, "the api_key field error must still be reported (field + message)"
    for entry in secret_entries:
        assert "input" not in entry and "ctx" not in entry
        assert entry["message"]
    assert payload["error"]["details"]["errors"] == entries


# ---------------- E5: redaction survives uvicorn.Config at both server entries ----------------

def _leaks_through_uvicorn(caplog_stream: io.StringIO) -> bool:
    logging.getLogger("uvicorn.error").error("boom ?key=%s Authorization: Bearer %s", MARK, MARK)
    for handler in logging.getLogger("uvicorn").handlers:
        handler.flush()
    return MARK in caplog_stream.getvalue()


def _capture_uvicorn_handlers(monkeypatch):
    """Point every handler uvicorn builds at an in-memory stream."""
    import logging.config
    stream = io.StringIO()
    real = logging.config.dictConfig

    def dict_config(cfg):
        cfg = {**cfg, "handlers": {name: {**h, "stream": stream} if "stream" in h else h
                                    for name, h in cfg.get("handlers", {}).items()}}
        return real(cfg)

    monkeypatch.setattr(logging.config, "dictConfig", dict_config)
    return stream


def test_e5_desktop_main_server_start_redacts_uvicorn_logs(tmp_path, monkeypatch):
    """Runs the real DesktopServiceManager._start_fastapi_server (Server.run stubbed)."""
    import uvicorn
    from backend import desktop_main

    stream = _capture_uvicorn_handlers(monkeypatch)
    monkeypatch.setattr(uvicorn.Server, "run", lambda self, sockets=None: None)
    manager = object.__new__(desktop_main.DesktopServiceManager)

    class Cfg:
        host = "127.0.0.1"
        log_level = "INFO"

        class paths:
            data_dir = tmp_path

    manager.config = Cfg
    manager.app = lambda scope, receive, send: None
    manager.logger = logging.getLogger("test.desktop")
    manager._start_fastapi_server()
    assert not _leaks_through_uvicorn(stream)


def test_e5_python_m_backend_main_redacts_uvicorn_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    import runpy
    import uvicorn

    stream = _capture_uvicorn_handlers(monkeypatch)
    monkeypatch.setattr(uvicorn.Server, "run", lambda self, sockets=None: None)
    monkeypatch.setattr("sys.argv", ["backend.main"])
    runpy.run_module("backend.main", run_name="__main__")
    assert not _leaks_through_uvicorn(stream)
