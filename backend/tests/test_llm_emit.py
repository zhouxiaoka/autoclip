"""1.5.8 Line A: request/run telemetry, ASR probe, reserved validation hook, privacy."""
import json

import pytest

from backend.core import llm_emit as telem
from backend.core import llm_telemetry as schema
from backend.core.llm_providers import LLMProvider, LLMResponse
from backend.core.sentry_setup import studio_failure_context
from backend.pipeline.failures import PipelineFailure


class _StatusError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class _ProbeProvider(LLMProvider):
    def __init__(self, **kwargs):
        super().__init__(api_key=kwargs.pop("api_key", "sk-secret-key"), model_name="qwen-plus", **kwargs)
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def call(self, prompt, input_data=None, **kwargs):
        if kwargs.get("fail"):
            raise _StatusError("Error code: 429 - private body sk-secret", 429)
        return LLMResponse(
            content='{"ok":true}',
            usage={"prompt_tokens": 11, "completion_tokens": 4},
            model="qwen-plus",
            finish_reason="stop",
        )

    def test_connection(self):
        return True

    def get_available_models(self):
        return []


@pytest.fixture
def capture(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_POSTHOG_KEY", "phc_test")
    monkeypatch.delenv("VITE_PUBLIC_POSTHOG_KEY", raising=False)
    (tmp_path / "privacy.json").write_text('{"analytics":true}', encoding="utf-8")
    (tmp_path / "analytics.json").write_text(
        '{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}', encoding="utf-8")
    bodies = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def urlopen(req, timeout=0):
        bodies.append(json.loads(req.data.decode()))
        return Resp()

    monkeypatch.setattr(telem.urllib.request, "urlopen", urlopen)
    return bodies


def test_hostname_and_model_never_keep_keys_or_urls():
    assert schema.hostname_of_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1") == "dashscope.aliyuncs.com"
    assert schema.hostname_of_base_url("http://127.0.0.1:11434/v1") == "local"
    assert schema.sanitize_model("qwen-plus") == "qwen-plus"
    assert schema.sanitize_model("has space") is None
    assert schema.sanitize_model("用户口播：把这段广告词发到抖音") is None
    blob = json.dumps(telem.request_finished(
        provider="openai", model="sk-abc", base_url="https://api.openai.com/v1/chat/completions?k=1",
        outcome="success", http_status=200, duration_ms=12,
    ))
    assert "sk-" not in blob.lower()
    assert "chat/completions" not in blob
    assert '"base_url"' not in blob


def test_provider_call_success_and_failure_emit_llm_request_finished(capture):
    provider = _ProbeProvider()
    with telem.track_run(), telem.bind_context(provider="dashscope", model="qwen-plus", base_url=provider.base_url):
        response = provider.call("private prompt", {"caption": "secret subtitle"})
        assert response.content == '{"ok":true}'
        with pytest.raises(_StatusError):
            provider.call("private prompt", fail=True)
        snapshot = telem.run_snapshot()
    events = [row for row in capture if row["event"] == "llm_request_finished"]
    assert len(events) == 2
    ok, failed = events
    assert ok["distinct_id"] == "018f6b2a-7c3d-7b2a-8c11-111111111111"
    assert ok["properties"]["provider"] == "dashscope"
    assert ok["properties"]["model"] == "qwen-plus"
    assert ok["properties"]["base_url_host"] == "dashscope.aliyuncs.com"
    assert ok["properties"]["http_status"] == 200
    assert ok["properties"]["outcome"] == "success"
    assert ok["properties"]["prompt_tokens"] == 11
    assert ok["properties"]["kind"] == "text"
    assert "sk-" not in json.dumps(ok)
    assert "private" not in json.dumps(ok["properties"])
    assert failed["properties"]["outcome"] == "error"
    assert failed["properties"]["upstream_error_type"] == "rate_limited"
    assert failed["properties"]["http_status"] == 429
    assert failed["properties"]["failure_stage"]
    assert snapshot["upstream_error_type"] == "rate_limited"
    assert snapshot["billable_calls_before_failure"] == 1
    assert snapshot.get("retry_count", 0) == 0


def test_opt_out_and_secret_payloads_are_not_posted(monkeypatch, tmp_path, capture):
    (tmp_path / "privacy.json").write_text('{"analytics":false}', encoding="utf-8")
    telem.request_finished(provider="openai", outcome="success", http_status=200)
    assert capture == []
    (tmp_path / "privacy.json").write_text('{"analytics":true}', encoding="utf-8")
    properties = telem.request_finished(provider="openai", model="gpt-4o-mini", outcome="success", http_status=200)
    assert properties["model"] == "gpt-4o-mini"
    leaked = dict(properties)
    leaked["authorization"] = "Bearer sk-secret"
    telem._post_event(schema.EVENT_LLM_REQUEST_FINISHED, leaked)
    assert all("sk-secret" not in json.dumps(row) for row in capture)


def test_asr_and_validation_hooks_are_allowlisted(capture):
    asr = telem.emit_asr_readiness_checked(
        provider="whisper_local", code="whisper_not_installed", has_subtitle=False, blocked=True)
    assert asr["provider"] == "whisper_local"
    assert asr["has_subtitle"] is False
    assert asr["blocked"] is True
    assert asr["code"] == "whisper_not_installed"
    validation = telem.emit_provider_validation_finished(
        provider="api88", base_url="https://88api.ai/v1/chat/completions",
        result="failed", error=_StatusError("invalid api key", 401))
    assert validation["provider"] == "api88"
    assert validation["base_url_host"] == "88api.ai"
    assert validation["result"] == "failed"
    assert validation["upstream_error_type"] == "invalid_key"
    events = {row["event"] for row in capture}
    assert events == {schema.EVENT_ASR_READINESS_CHECKED, schema.EVENT_PROVIDER_VALIDATION_FINISHED}
    assert "chat/completions" not in json.dumps(capture)


def test_failed_store_write_always_has_error_code_and_failure_stage(tmp_path, monkeypatch):
    from backend.services.studio import store
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    (tmp_path / "p1" / "metadata").mkdir(parents=True)
    store.write("p1", {
        "schema_version": 2,
        "generation": {"status": "failed"},
        "analysis": {"status": "failed", "phase": "ANALYZE"},
    })
    data = json.loads((tmp_path / "p1" / "metadata" / "studio.json").read_text(encoding="utf-8"))
    assert data["generation"]["error_code"] == "unexpected"
    assert data["generation"]["failure_stage"] in schema.FAILURE_STAGES
    assert data["analysis"]["error_code"] == "unexpected"
    assert data["analysis"]["failure_stage"] == "analyze"
    assert data["generation"]["billable_calls_before_failure"] == 0


def test_source_blocked_is_not_an_upstream_model_error():
    error = PipelineFailure("INGEST", "hint", code="source_blocked", http_status=403)
    assert studio_failure_context(error, "screening") == {"failure_stage": "ingest", "http_status": 403}


def test_sentry_tags_are_allowlisted_strings():
    with telem.track_run():
        telem.request_finished(
            provider="api88", model="gpt-4o-mini", base_url="https://88api.ai/v1",
            outcome="error", http_status=429, error=_StatusError("rate", 429),
            failure_stage="analyze", duration_ms=9,
        )
        tags = telem.sentry_tags_for_error(_StatusError("rate", 429), "analyze")
    assert tags["provider"] == "api88"
    assert tags["upstream_error_type"] == "rate_limited"
    assert tags["failure_stage"] == "analyze"
    assert tags["http_status"] == "429"
    assert "sk-" not in json.dumps(tags)
