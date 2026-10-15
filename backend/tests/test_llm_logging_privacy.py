"""Offline regressions for provider and outer-client exception log boundaries."""
import logging
from types import SimpleNamespace

import pytest

from backend.core import llm_providers as providers

pytestmark = pytest.mark.stdlib_only

# Deliberately synthetic values; no real provider or user data is used.
ENDPOINT = "https://api.example.com/private-route?key=fixture-query"
ERROR = 'request failed: {"authorization": "Bearer fixture-credential"} ' + ENDPOINT


def fail(*args, **kwargs):
    raise RuntimeError(ERROR)


@pytest.fixture(autouse=True)
def offline_observation(monkeypatch):
    from backend.core import llm_telemetry
    monkeypatch.setattr(llm_telemetry, "observe_provider_call",
                        lambda provider, impl, *args, **kwargs: impl(provider, *args, **kwargs))


def assert_safe(text):
    assert "fixture-credential" not in text
    assert "fixture-query" not in text
    assert "https://" not in text
    assert "/private-route" not in text
    assert "api.example.com" in text


def make_provider(kind):
    # Bypass constructors so SDK initialization cannot make network requests.
    cls = {
        "dashscope-native": providers.DashScopeProvider,
        "dashscope-compatible": providers.DashScopeProvider,
        "openai": providers.OpenAIProvider,
        "gemini": providers.GeminiProvider,
        "siliconflow": providers.SiliconFlowProvider,
    }[kind]
    provider = object.__new__(cls)
    provider.api_key = "sk-fixture-key"
    provider.model_name = "fixture-model"
    provider.base_url = ENDPOINT
    provider.is_custom_endpoint = True
    provider.mode = "native" if kind.endswith("-native") else "compatible"
    provider._ds_generation = SimpleNamespace(call=fail)
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fail)),
        models=SimpleNamespace(generate_content=fail),
    )
    return provider


@pytest.mark.parametrize("kind", [
    "dashscope-native", "dashscope-compatible", "openai", "gemini", "siliconflow",
])
def test_provider_call_and_connection_logs_are_sanitized(kind, monkeypatch, caplog):
    import requests
    monkeypatch.setattr(requests, "post", fail)
    # DashScope native mode temporarily sets this variable.
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fixture-original")
    provider = make_provider(kind)
    caplog.set_level(logging.DEBUG, logger=providers.__name__)
    with pytest.raises(RuntimeError) as raised:
        provider.call("fixture prompt")
    assert_safe(str(raised.value))
    assert_safe(caplog.text)
    caplog.clear()
    assert provider.test_connection() is False
    assert_safe(caplog.text)


def test_dashscope_outer_connection_error_is_sanitized(caplog):
    class InvalidKey:
        strip = staticmethod(fail)

    provider = make_provider("dashscope-native")
    provider.api_key = InvalidKey()
    assert provider.test_connection() is False
    assert_safe(caplog.text)


@pytest.mark.parametrize("kind", ["dashscope-native", "dashscope-compatible"])
def test_dashscope_constructed_api_errors_are_sanitized(kind, monkeypatch, caplog):
    import requests
    provider = make_provider(kind)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fixture-original")
    provider._ds_generation = SimpleNamespace(call=lambda **kwargs: SimpleNamespace(
        status_code=401, code="invalid_key", message=ERROR,
    ))
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: SimpleNamespace(
        status_code=401, json=lambda: {"message": ERROR},
    ))
    with pytest.raises(Exception) as raised:
        provider.call("fixture prompt")
    assert_safe(str(raised.value))
    assert_safe(caplog.text)


def test_provider_catalog_failure_is_sanitized(monkeypatch, caplog):
    monkeypatch.setattr(providers.LLMProviderFactory, "_providers", {providers.ProviderType.OPENAI: fail})
    assert providers.LLMProviderFactory.get_all_available_models() == {providers.ProviderType.OPENAI: []}
    assert_safe(caplog.text)


@pytest.mark.parametrize("kind", ["dashscope-compatible", "openai"])
def test_connection_key_format_warning_does_not_log_key(kind, monkeypatch, caplog):
    provider = make_provider(kind)
    provider.api_key = "fixture-key-prefix-must-stay-private"
    provider.is_custom_endpoint = False
    monkeypatch.setattr(provider, "call", fail)
    assert provider.test_connection() is False
    assert "fixture-key" not in caplog.text
    assert_safe(caplog.text)


def test_dashscope_request_metadata_does_not_log_keys_or_content(monkeypatch, caplog):
    import requests
    monkeypatch.setattr(requests, "post", fail)
    provider = make_provider("dashscope-compatible")
    provider.api_key = "fixture-key-private"
    provider.model_name = "AIza" + "A" * 35
    caplog.set_level(logging.DEBUG, logger=providers.__name__)
    with pytest.raises(RuntimeError):
        provider.call("fixture prompt", extra_body={"content": "fixture-private-content"})
    assert_safe(caplog.text)
    for private in ("fixture-key", "fixture-private-content", provider.model_name):
        assert private not in caplog.text


@pytest.mark.parametrize("model", ["AIza" + "A" * 35, "xai-" + "a" * 48])
def test_openai_retry_and_usage_logs_sanitize_model(model, caplog):
    provider = make_provider("openai")
    provider.model_name = model
    requests = []

    def create(**payload):
        requests.append(payload)
        if len(requests) == 1:
            error = RuntimeError("use max_completion_tokens instead of max_tokens")
            error.status_code = 400
            raise error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="fixture response"), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    provider.client.chat.completions.create = create
    caplog.set_level(logging.INFO, logger=providers.__name__)
    assert provider.call("fixture prompt", max_tokens=1).content == "fixture response"
    assert len(requests) == 2
    assert "redacted" in caplog.text
    assert model not in caplog.text


@pytest.mark.parametrize("method", ["call", "call_with_retry"])
def test_outer_client_failure_is_sanitized(method, caplog):
    from backend.utils.llm_client import LLMClient
    client = object.__new__(LLMClient)
    client.llm_manager = SimpleNamespace(call=fail, call_with_retry=fail)
    with pytest.raises(RuntimeError) as raised:
        getattr(client, method)("fixture prompt")
    assert_safe(str(raised.value))
    assert_safe(caplog.text)


@pytest.mark.parametrize("stage", ["outline", "timeline"])
@pytest.mark.parametrize("status", [401, 429, 503])
def test_pipeline_failure_does_not_reintroduce_private_error(stage, status, tmp_path, monkeypatch, caplog):
    import json
    from backend.core.llm_manager import LLMManager, _CallRoute
    from backend.pipeline import concurrency, step1_outline, step2_timeline
    from backend.pipeline.failures import PipelineFailure
    from backend.utils.llm_client import LLMClient

    body = "Private English prompt subtitle and model response"
    private_path = "/fixture-private-folder/subtitle.srt"
    calls = []

    def failing_request(**payload):
        calls.append(payload)
        error = RuntimeError(ERROR + " " + body + " " + private_path)
        error.status_code = status
        error.body = {"error": {"code": "rate_limit_exceeded" if status == 429 else "server_error",
                                "message": str(error)}}
        raise error

    provider = make_provider("openai")
    provider.client.chat.completions.create = failing_request
    manager = object.__new__(LLMManager)
    settings = {"model_source": "preset", "connection_provider": "openai", "model_name": "fixture-model"}
    manager._snapshot_call_route = lambda: _CallRoute(provider, settings, {"base_url": ENDPOINT})
    monkeypatch.setattr("backend.core.llm_degrade.candidates_for_call", lambda settings: ("fixture-model", "fixture-next"))
    client = object.__new__(LLMClient)
    client.llm_manager = manager
    monkeypatch.setattr(step1_outline, "LLMClient", lambda: client)
    monkeypatch.setattr(step2_timeline, "LLMClient", lambda: client)
    monkeypatch.setattr(concurrency, "map_chunks", lambda fn, items: map(fn, items))
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    # Do not read global model settings or enable the optional disk call cache.
    monkeypatch.setattr("backend.core.llm_manager._llm_cache_path", lambda *args: None)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(body, encoding="utf-8")
    caplog.set_level(logging.DEBUG)
    if stage == "outline":
        srt = tmp_path / "input.srt"
        srt.write_text("1\n00:00:01,000 --> 00:00:12,000\n" + body + "\n", encoding="utf-8")
        extractor = step1_outline.OutlineExtractor(tmp_path, {"outline": prompt})
        with pytest.raises(PipelineFailure) as raised:
            extractor.extract_outline(srt)
        assert raised.value.http_status == status
        assert_safe(str(raised.value.__cause__))
    else:
        chunks = tmp_path / "step1_srt_chunks"
        chunks.mkdir()
        (chunks / "chunk_0.json").write_text(json.dumps([
            {"index": 1, "start_time": "00:00:01,000", "end_time": "00:00:12,000", "text": body}
        ]), encoding="utf-8")
        extractor = step2_timeline.TimelineExtractor(tmp_path, {"timeline": prompt})
        assert extractor.extract_timeline([{"title": body, "subtopics": [], "chunk_index": 0}]) == []
        report = extractor.extraction_report["chunks"][0]
        assert report["http_status"] == status
    assert len(calls) == (1 if status == 401 else 3)
    assert_safe(caplog.text)
    for private in (body, private_path, str(tmp_path)):
        assert private not in caplog.text


@pytest.mark.parametrize("response", [
    '```json\n[{"outline": "Private English response", invalid}]\n```',
    '[{"outline": "Private English response",}]',
    'Private English response without JSON',
])
def test_json_parser_logs_and_raised_message_hide_english_body(response, caplog):
    from backend.utils.llm_client import LLMClient
    client = object.__new__(LLMClient)
    caplog.set_level(logging.DEBUG)
    try:
        client.parse_json_response(response)
    except ValueError as error:
        assert "Private English response" not in str(error)
    assert "Private English response" not in caplog.text


def test_timeline_validation_logs_only_response_length(tmp_path, caplog):
    import json
    from backend.pipeline.step2_timeline import TimelineExtractor
    from backend.utils.llm_client import LLMClient
    extractor = object.__new__(TimelineExtractor)
    extractor.metadata_dir = tmp_path
    extractor.llm_client = object.__new__(LLMClient)
    body = "Private English title and subtitle"
    response = json.dumps([
        {"outline": body, "start_time": "00:00:01,000", "end_time": "00:00:12,000"},
        {"outline": body, "start_time": body, "end_time": "end"},
        {"outline": body},
    ])
    caplog.set_level(logging.DEBUG)
    assert len(extractor._parse_and_validate_response(response, "00:00:00,000", "00:01:00,000", 0)) == 1
    assert body not in caplog.text
    assert str(tmp_path) not in caplog.text
    for debug in (tmp_path / "debug_responses").glob("*.txt"):
        assert body not in debug.read_text(encoding="utf-8")


@pytest.mark.parametrize("error,status,payload", [
    (TimeoutError("Private English body"), None, None),
    (ConnectionError("Private English body"), None, None),
    (RuntimeError(ERROR), 403, {"error": {"code": "insufficient_user_quota"}}),
    (RuntimeError(ERROR), 404, {"error": {"code": "model_not_found"}}),
    (RuntimeError(ERROR), 429, {"error": {"code": "rate_limit_exceeded"}}),
    (RuntimeError(ERROR), 429, {"error": {"code": "insufficient_quota"}}),
    (RuntimeError("<html>Private English body</html>"), 401, None),
])
def test_safe_exception_preserves_classification_retry_after_and_degrade(error, status, payload):
    from backend.core.llm_degrade import should_degrade_to_next
    from backend.core.llm_retry import retry_after_from_error
    from backend.core.llm_telemetry import log_safe_exception
    from backend.core.upstream_errors import classify_exception
    error.status_code = status
    error.response = SimpleNamespace(headers={"Retry-After": "7"})
    if payload is not None:
        error.body = payload
    safe = log_safe_exception(error)
    assert classify_exception(safe) == classify_exception(error)
    assert retry_after_from_error(safe) == 7
    assert should_degrade_to_next(safe) == should_degrade_to_next(error)
    assert log_safe_exception(safe) is safe
    assert "Private English" not in str(safe)
    assert "fixture-credential" not in str(safe)
    assert "https://" not in str(safe)


def test_malformed_url_in_error_cannot_break_sanitization():
    from backend.core.llm_telemetry import sanitize_exception_text
    assert sanitize_exception_text(RuntimeError("Private English https://[broken/path")) == "unknown"


def test_missing_configuration_keeps_settings_recovery_after_redaction(tmp_path, monkeypatch):
    from backend.pipeline import step1_outline
    from backend.pipeline.failures import PipelineFailure, CODE_LLM_NOT_CONFIGURED
    from backend.utils.llm_client import LLMClient

    def missing(*args, **kwargs):
        raise ValueError("未配置LLM提供商，请在设置页面配置API密钥")

    client = object.__new__(LLMClient)
    client.llm_manager = SimpleNamespace(call_with_retry=missing)
    monkeypatch.setattr(step1_outline, "LLMClient", lambda: client)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Private English prompt", encoding="utf-8")
    srt = tmp_path / "input.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:12,000\nPrivate English subtitle\n", encoding="utf-8")
    extractor = step1_outline.OutlineExtractor(tmp_path, {"outline": prompt})
    with pytest.raises(PipelineFailure) as raised:
        extractor.extract_outline(srt)
    assert raised.value.code == CODE_LLM_NOT_CONFIGURED
    assert str(raised.value.__cause__) == "unknown"


def test_sanitizer_keeps_known_type_only_diagnostics():
    from backend.core.llm_telemetry import sanitize_exception_text
    assert sanitize_exception_text("RuntimeError") == "RuntimeError"
    assert sanitize_exception_text("PrivateEnglishSubtitleError") == "unknown"


@pytest.mark.parametrize("body_shape", ["dict", "json", "text"])
@pytest.mark.parametrize("code,message,expected", [
    ("context_length_exceeded", "Request rejected", "context_length_exceeded"),
    ("invalid_request_error", "Maximum context length exceeded", "context_length_exceeded"),
    ("content_filter", "Request rejected", "content_filter"),
    ("content_policy_violation", "Request rejected", "content_filter"),
    ("invalid_request_error", "Request blocked by content filter", "content_filter"),
    ("fixture-private-arbitrary-code", "Request rejected", "unknown"),
])
def test_provider_and_client_logs_keep_safe_diagnostic_code(
    body_shape, code, message, expected, caplog,
):
    import json
    from backend.core.llm_telemetry import sanitize_exception_text
    from backend.utils.llm_client import LLMClient

    private_body = "fixture-private-prompt-subtitle-response"
    private_path = "/fixture-private-folder/input.srt"
    body = {"error": {"code": code, "message": f"{message} {ERROR} {private_body} {private_path}"}}
    if body_shape == "json":
        body = json.dumps(body)
    elif body_shape == "text":
        body = f"{code}: {message} {ERROR} {private_body} {private_path}"

    def rejected_request(**kwargs):
        error = RuntimeError(ERROR)
        error.status_code = 400
        error.body = body
        raise error

    provider = make_provider("openai")
    provider.client.chat.completions.create = rejected_request
    client = object.__new__(LLMClient)
    client.llm_manager = SimpleNamespace(call=lambda *args: provider.call(*args))
    with pytest.raises(RuntimeError) as raised:
        client.call("fixture prompt")

    diagnostic = expected + " host=api.example.com"
    assert str(raised.value) == diagnostic
    assert sanitize_exception_text(raised.value) == diagnostic
    for name in (providers.__name__, "backend.utils.llm_client"):
        messages = [record.getMessage() for record in caplog.records if record.name == name]
        assert len(messages) == 1
        assert messages[0].endswith(diagnostic)
    assert_safe(caplog.text)
    for private in (private_body, private_path, "fixture-private-arbitrary-code"):
        assert private not in caplog.text
