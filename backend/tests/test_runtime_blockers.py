"""Behavior tests for runtime privacy and entry-point blockers."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import contextvars
import io
import threading
"""Round-7 blockers D1–D7: each case failed on 73ff1484 before the fix."""


# ---------- D2: retry accumulation inside one track_run ----------

def test_d2_retry_count_survives_later_zero_retry_call():
    """Fail→retry ok→normal call must keep retry_count=1, not wipe to 0."""
    from backend.core import llm_emit

    with llm_emit.track_run():
        llm_emit.request_finished(provider="openai", model="m", outcome="error", retries=0, http_status=500)
        assert llm_emit.run_snapshot().get("retry_count", 0) == 0
        llm_emit.request_finished(
            provider="openai", model="m", outcome="success", retries=1, http_status=200,
            prompt_tokens=1, completion_tokens=1,
        )
        assert llm_emit.run_snapshot()["retry_count"] == 1
        llm_emit.request_finished(
            provider="openai", model="m", outcome="success", retries=0, http_status=200,
            prompt_tokens=1, completion_tokens=1,
        )
        snap = llm_emit.run_snapshot()
        assert snap["llm_calls"] == 3
        assert snap["retry_count"] == 1, "later retry_count=0 must not erase earlier retries"


def test_d2_retry_peaks_accumulate_across_logical_calls_not_raw_indices():
    """(0,1,2) within one call counts as 2 retries, not 0+1+2=3."""
    from backend.core import llm_emit

    with llm_emit.track_run():
        for r, outcome in ((0, "error"), (1, "error"), (2, "success")):
            llm_emit.request_finished(
                provider="openai", model="m", outcome=outcome, retries=r,
                http_status=500 if outcome == "error" else 200,
                prompt_tokens=1, completion_tokens=1,
            )
        assert llm_emit.run_snapshot()["retry_count"] == 2
        # Second logical call retries once more
        llm_emit.request_finished(provider="openai", model="m", outcome="error", retries=0, http_status=500)
        llm_emit.request_finished(
            provider="openai", model="m", outcome="success", retries=1, http_status=200,
            prompt_tokens=1, completion_tokens=1,
        )
        assert llm_emit.run_snapshot()["retry_count"] == 3


# ---------- D3: signed URL + userinfo ----------

@pytest.mark.parametrize("raw,forbidden", [
    (
        "GET https://bucket.s3.amazonaws.com/o?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA/20260101&X-Amz-Signature=abcdef0123456789deadbeef",
        ["abcdef0123456789deadbeef", "AKIA/20260101"],
    ),
    (
        "upstream https://user:super-secret-pass@api.example.com/v1/images",
        ["super-secret-pass", "user:super"],
    ),
])
def test_d3_redact_signed_url_and_userinfo(raw, forbidden):
    from backend.core.log_redaction import redact_text, REDACTED

    out = redact_text(raw)
    for secret in forbidden:
        assert secret not in out, (secret, out)
    assert REDACTED in out


def test_d3_filter_redacts_signed_url_in_log_record():
    from backend.core.log_redaction import RedactingFilter, REDACTED

    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, 
        "cover fetch failed: https://cdn.example/?X-Amz-Signature=%s", ("sig-SHOULD-HIDE-999",), None,
    )
    assert RedactingFilter().filter(record) is True
    assert "sig-SHOULD-HIDE-999" not in record.getMessage()
    assert REDACTED in record.getMessage()


# ---------- D4: covered by test_r8_e1_e5.py::test_e5_* (real desktop_main / backend.main entries) ----------


# ---------- D5: loc-based api_key wipe + userinfo ----------

PLAIN_SECRET = "plain-secret-" + ("Z" * 48)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    from backend.app_factory import create_app
    with TestClient(create_app(mode="web"), raise_server_exceptions=False) as c:
        yield c


def test_d5_422_wipes_non_sk_api_key_string_input(client):
    body = {
        "version": 1,
        "connections": [{
            "id": "c1", "name": "x", "provider": "openai",
            # F3: field-level error (string_too_long on api_key itself), not an object-level one
            "api_key": PLAIN_SECRET + "Z" * 2000, "base_url": "",
        }],
        "analysis": {"connection_id": "c1", "model": "m"},
        "cover_enabled": False,
    }
    response = client.put("/api/v1/settings/ai-models", json=body)
    assert response.status_code == 422
    assert PLAIN_SECRET not in response.text
    assert "plain-secret-" not in response.text


def test_d5_422_redacts_base_url_userinfo_in_validation_input():
    from backend.core.error_middleware import handle_validation_error
    from fastapi.exceptions import RequestValidationError

    class Fake(RequestValidationError):
        def __init__(self):
            Exception.__init__(self, "x")

        def errors(self):
            return [{
                "loc": ("body", "connections", 0, "base_url"),
                "msg": "invalid url",
                "type": "value_error.url",
                "input": "https://user:password99@evil.example/v1",
            }]

    resp = handle_validation_error(Fake(), None)
    text = resp.body.decode()
    assert "password99" not in text
    assert "user:password" not in text
    assert "[REDACTED]" in text


def test_d5_validation_handler_wipes_secret_loc_string():
    from backend.core.error_middleware import handle_validation_error
    from fastapi.exceptions import RequestValidationError

    class Fake(RequestValidationError):
        def __init__(self):
            Exception.__init__(self, "x")

        def errors(self):
            return [{
                "loc": ("body", "connections", 0, "api_key"),
                "msg": "ensure this value has at most 10 characters",
                "type": "value_error.any_str.max_length",
                "input": PLAIN_SECRET,
            }]

    resp = handle_validation_error(Fake(), None)
    payload = json.loads(resp.body)
    assert PLAIN_SECRET not in json.dumps(payload)
    errors = payload["error"]["details"]["errors"]
    assert "input" not in errors[0]  # E4: credential fields omit input entirely


# ---------- D6: detail contract ----------

def test_d6_http_exception_keeps_top_level_detail():
    from backend.core.error_middleware import handle_http_exception

    resp = handle_http_exception(HTTPException(status_code=400, detail="请到「设置 → 服务商与模型」改密钥"), None)
    payload = json.loads(resp.body)
    assert payload["detail"] == "请到「设置 → 服务商与模型」改密钥"
    assert payload["error"]["message"] == "请到「设置 → 服务商与模型」改密钥"


def test_d6_error_text_reads_detail_and_envelope():
    """Mirror frontend errorText resolution against the new response shape."""
    detail_shape = {"response": {"data": {"detail": "具体指引", "error": {"message": "具体指引"}}}}
    envelope_only = {"response": {"data": {"error": {"message": "信封文案"}}}}
    # Inline the same priority as frontend/src/features/studio/api.ts errorText
    def error_text(error):
        data = error.get("response", {}).get("data") or {}
        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
        envelope = (data.get("error") or {}).get("message")
        if isinstance(envelope, str) and envelope.strip():
            return envelope
        return "请求失败，请重试"

    assert error_text(detail_shape) == "具体指引"
    assert error_text(envelope_only) == "信封文案"


# ---------- D7: auto + text readiness ----------

def test_d7_auto_text_readiness_is_optional_not_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    binary = tmp_path / "ffmpeg"
    binary.write_bytes(b"ffmpeg")
    monkeypatch.setattr("backend.utils.ffmpeg_utils.get_ffmpeg_path", lambda: str(binary))
    monkeypatch.setattr("backend.services.whisper_runtime.get_status", lambda: {"status": "installed"})
    from backend.services.whisper_model_manager import WhisperModelManager
    import backend.services.whisper_model_manager as wmm
    monkeypatch.setattr(wmm, "_model_manager", WhisperModelManager())
    monkeypatch.setattr("backend.services.whisper_runtime.get_models_dir", lambda: tmp_path / "whisper-models")
    snap = tmp_path / "whisper-models" / "hub" / "models--Systran--faster-whisper-base" / "snapshots" / "complete"
    snap.mkdir(parents=True)
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.json"):
        (snap / name).write_bytes(b"x")

    from backend.services import ai_model_settings as ai
    from backend.services.studio import readiness

    settings = ai.ModelSettings(
        connections=[ai.Connection(id="ai", name="OpenAI", provider="openai", api_key="sk-test-key")],
        analysis=ai.Assignment(connection_id="ai", model="gpt-4o", capability="text"),
        analysis_mode="auto",
    )
    assert ai.vision_follow_lacks_capability(settings) is False
    monkeypatch.setattr(ai, "for_editing", lambda: settings)
    report = readiness.report()
    assert report["checks"]["visual"] == {"ok": True, "code": "optional", "repair": "none"}
    assert report["ready"] is True
    readiness.ensure_analysis_usable()

    visual = settings.model_copy(update={"analysis_mode": "visual"})
    assert ai.vision_follow_lacks_capability(visual) is True
    monkeypatch.setattr(ai, "for_editing", lambda: visual)
    assert readiness.report()["checks"]["visual"]["code"] == "vision_unsupported"
"""Round-8 blockers E2–E5 (E1 lives in frontend/tests/default-model-slots.test.cjs).

Every case here fails on 6714deb5 with the fix's source reverted. All secrets are synthetic
markers; assertions never print them.
"""

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
