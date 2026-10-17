"""Round-7 blockers D1–D7: each case failed on 73ff1484 before the fix."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


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

    resp = handle_http_exception(HTTPException(status_code=400, detail="请到「设置 → 模型」改密钥"), None)
    payload = json.loads(resp.body)
    assert payload["detail"] == "请到「设置 → 模型」改密钥"
    assert payload["error"]["message"] == "请到「设置 → 模型」改密钥"


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
