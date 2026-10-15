"""First-party /models fetch: pagination, timeout, layered errors, preset intersection."""
import json
from pathlib import Path

import pytest

from backend.core.provider_model_fetch import (
    FETCH_LIST_FAILED,
    FETCH_LIST_NO_OVERLAP,
    FETCH_LIST_TRUNCATED,
    FETCH_LIST_UPDATED,
    MAX_MODELS,
    backfill_model_ids,
    extract_model_ids,
    fetch_provider_models,
    get_models,
    intersect_candidates,
    list_account_models,
    recommended_by_purpose,
)
from backend.core.upstream_errors import HINT_KEYS, UpstreamErrorType
from backend.services import ai_model_settings as ai
from backend.services.provider_validation import fetch_list_for_connection, validate_connection


LOCALES = Path(__file__).resolve().parents[2] / "frontend/src/i18n/locales"
SECRET = "sk-test-secret-key"
SECRET_URL = "https://user:secret@gateway.example/v1"


class _FakeResponse:
    def __init__(self, status, payload, headers=None, text=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {"content-type": "application/json"}
        if text is not None:
            self.text = text
        elif isinstance(payload, str):
            self.text = payload
        else:
            self.text = json.dumps(payload)

    def json(self):
        if isinstance(self._payload, str):
            return json.loads(self._payload)
        return self._payload


class _Recorder:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def __call__(self, url, *, headers, timeout, trust_env):
        self.calls.append({"url": url, "headers": dict(headers), "timeout": timeout, "trust_env": trust_env})
        return self.handler(url, headers)


def test_extract_skips_invalid_ids_and_strips_gemini_prefix():
    ids = extract_model_ids({
        "data": [
            {"id": "model-a"},
            {"id": "bad id"},
            {"name": "models/gemini-b"},
            {"id": "model-a"},
            "plain-c",
        ]
    })
    assert ids == ["model-a", "gemini-b", "plain-c"]


def test_intersect_keeps_candidate_order():
    live = ["qwen-plus", "qwen3.8-flash", "custom-id", "qwen3.8-max"]
    recommended = recommended_by_purpose("dashscope", live)
    assert recommended["analysis"] == ["qwen3.8-flash", "qwen3.8-max", "qwen-plus"]
    assert "qwen-vl-plus" not in recommended["analysis"]
    assert recommended["vision"] == ["qwen3.8-flash"]
    assert backfill_model_ids(live, recommended["analysis"]) == [
        "qwen3.8-flash", "qwen3.8-max", "qwen-plus", "custom-id",
    ]


def test_custom_provider_has_no_recommended_candidates():
    live = ["gpt-4o-mini", "local-custom"]
    recommended = recommended_by_purpose("compatible", live)
    assert recommended["analysis"] == []
    assert backfill_model_ids(live, recommended["analysis"]) == live
    assert intersect_candidates(live, []) == []


def test_openai_compatible_list_and_headers():
    http = _Recorder(lambda url, headers: _FakeResponse(200, {
        "data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}, {"id": "bad id"}],
    }))
    result = list_account_models(
        base_url="https://gateway.example/v1/",
        api_key=SECRET,
        provider="compatible",
        http=http,
    )
    assert result.ok is True
    assert result.models == ["gpt-4o-mini", "gpt-4o"]
    assert result.message_key == FETCH_LIST_UPDATED
    assert result.base_url_host == "gateway.example"
    assert http.calls[0]["url"] == "https://gateway.example/v1/models"
    assert http.calls[0]["headers"]["Authorization"] == "Bearer " + SECRET
    payload = json.dumps(result.as_api())
    assert SECRET not in payload
    assert "gateway.example/v1" not in payload


def test_local_auth_none_omits_authorization():
    http = _Recorder(lambda url, headers: _FakeResponse(200, {"data": [{"id": "qwen2.5:7b"}]}))
    result = list_account_models(
        base_url="http://127.0.0.1:11434/v1",
        api_key="",
        provider="ollama",
        auth="none",
        http=http,
    )
    assert result.ok is True
    assert result.models == ["qwen2.5:7b"]
    assert "Authorization" not in http.calls[0]["headers"]
    assert http.calls[0]["trust_env"] is False


def test_anthropic_pagination_and_headers():
    def handler(url, headers):
        if "after_id=claude-a" in url:
            return _FakeResponse(200, {"data": [{"id": "claude-b"}], "has_more": False})
        return _FakeResponse(200, {"data": [{"id": "claude-a", "display_name": "Claude A"}], "has_more": True, "last_id": "claude-a"})

    http = _Recorder(handler)
    result = fetch_provider_models(
        base_url="https://api.anthropic.com",
        api_key=SECRET,
        protocol="anthropic-messages",
        http=http,
    )
    assert result.models == ["claude-a", "claude-b"]
    assert result.pages == 2
    assert http.calls[0]["headers"]["x-api-key"] == SECRET
    assert http.calls[0]["headers"]["anthropic-version"] == "2023-06-01"
    assert "after_id=claude-a" in http.calls[1]["url"]
    assert SECRET not in json.dumps(result.as_api())


def test_gemini_pagination_normalizes_ids():
    def handler(url, headers):
        if "pageToken=next" in url:
            return _FakeResponse(200, {"models": [{"name": "models/gemini-b", "supportedGenerationMethods": ["generateContent"]}]})
        return _FakeResponse(200, {
            "models": [
                {"name": "models/gemini-a", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/embedding", "supportedGenerationMethods": ["embedContent"]},
            ],
            "nextPageToken": "next",
        })

    http = _Recorder(handler)
    result = fetch_provider_models(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key=SECRET,
        provider="gemini",
        http=http,
    )
    assert result.ok is True
    assert result.models == ["gemini-a", "embedding", "gemini-b"]
    assert http.calls[0]["headers"]["x-goog-api-key"] == SECRET
    assert http.calls[0]["url"].endswith("/v1beta/models?pageSize=200")
    assert "pageToken=next" in http.calls[1]["url"]
    assert "openai/models" not in http.calls[0]["url"]


def test_preflight_rejects_file_userinfo_and_unsupported_protocol():
    http = _Recorder(lambda url, headers: (_ for _ in ()).throw(AssertionError("network")))
    for base, protocol in (
        ("file:///tmp/models", "openai-completions"),
        (SECRET_URL, "openai-completions"),
        ("https://gateway.example/v1", "google-vertex"),
    ):
        result = fetch_provider_models(base_url=base, api_key=SECRET, protocol=protocol, http=http)
        assert result.ok is False
        assert result.error_type == "bad_endpoint"
        assert result.hint_key == HINT_KEYS[UpstreamErrorType.BAD_ENDPOINT]
        payload = json.dumps(result.as_api())
        assert SECRET not in payload
        assert "secret" not in payload
    assert http.calls == []


def test_missing_cloud_key_is_invalid_key_without_fetch():
    http = _Recorder(lambda url, headers: (_ for _ in ()).throw(AssertionError("network")))
    result = fetch_provider_models(base_url="https://api.openai.com/v1", api_key="", provider="openai", http=http)
    assert result.error_type == "invalid_key"
    assert http.calls == []


def test_layered_http_errors_do_not_echo_body_or_key():
    http = _Recorder(lambda url, headers: _FakeResponse(401, {"error": {"message": SECRET}}))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=http)
    assert result.error_type == "invalid_key"
    assert result.message_key == FETCH_LIST_FAILED
    dumped = json.dumps(result.as_api())
    assert SECRET not in dumped
    assert "gateway.example/v1" not in dumped


def test_empty_object_and_redirect_are_bad_endpoint():
    empty = _Recorder(lambda url, headers: _FakeResponse(200, {}))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=empty)
    assert result.ok is False
    assert result.error_type == "bad_endpoint"
    assert result.source == "empty"
    assert result.message_key == FETCH_LIST_FAILED
    assert SECRET not in json.dumps(result.as_api())

    redirect = _Recorder(lambda url, headers: _FakeResponse(
        302, {}, headers={"content-type": "application/json", "location": "https://gateway.example/login"},
    ))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=redirect)
    assert result.ok is False
    assert result.error_type == "bad_endpoint"
    assert result.source == "empty"
    dumped = json.dumps(result.as_api())
    assert SECRET not in dumped
    assert "gateway.example/v1" not in dumped
    assert "login" not in dumped


def test_html_and_invalid_json_are_bad_endpoint():
    html = _Recorder(lambda url, headers: _FakeResponse(
        200, "<!DOCTYPE html><html>控制台</html>",
        headers={"content-type": "text/html"},
        text="<!DOCTYPE html><html>控制台</html>",
    ))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=html)
    assert result.error_type == "bad_endpoint"

    class _BadJson(_FakeResponse):
        def json(self):
            raise ValueError("not json")

    broken = _Recorder(lambda url, headers: _BadJson(200, "not-json", text="not-json"))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=broken)
    assert result.error_type == "bad_endpoint"


def test_timeout_and_connection_are_classified():
    class _Timeout(Exception):
        pass

    _Timeout.__name__ = "TimeoutError"
    timed = _Recorder(lambda url, headers: (_ for _ in ()).throw(_Timeout()))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=timed)
    assert result.error_type == "timeout"

    class _Conn(Exception):
        pass

    _Conn.__name__ = "ConnectionError"
    offline = _Recorder(lambda url, headers: (_ for _ in ()).throw(_Conn()))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=offline)
    assert result.error_type == "connection"


def test_models_404_is_bad_endpoint():
    http = _Recorder(lambda url, headers: _FakeResponse(404, {"error": {"message": "not found"}}))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=http)
    assert result.error_type == "bad_endpoint"


def test_repeated_cursor_and_missing_cursor_are_invalid_pages():
    repeated = _Recorder(lambda url, headers: _FakeResponse(200, {"data": [], "has_more": True, "last_id": "same"}))
    result = fetch_provider_models(
        base_url="https://gateway.example/v1", api_key=SECRET, protocol="anthropic-messages", http=repeated,
    )
    assert result.error_type == "bad_endpoint"
    assert len(repeated.calls) == 2

    missing = _Recorder(lambda url, headers: _FakeResponse(200, {"data": [], "has_more": True}))
    result = fetch_provider_models(
        base_url="https://gateway.example/v1", api_key=SECRET, protocol="anthropic-messages", http=missing,
    )
    assert result.error_type == "bad_endpoint"


def test_oversized_list_is_truncated():
    http = _Recorder(lambda url, headers: _FakeResponse(
        200, {"data": [{"id": f"model-{index}"} for index in range(MAX_MODELS + 100)]},
    ))
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=http)
    assert result.ok is True
    assert result.truncated is True
    assert len(result.models) == MAX_MODELS
    assert result.message_key == FETCH_LIST_TRUNCATED


def test_later_page_transport_error_keeps_partial_list():
    class _Timeout(Exception):
        pass

    _Timeout.__name__ = "TimeoutError"

    def handler(url, headers):
        if "after=" in url or "after_id=" in url:
            raise _Timeout()
        return _FakeResponse(200, {"data": [{"id": "model-a"}], "has_more": True, "last_id": "model-a"})

    http = _Recorder(handler)
    result = fetch_provider_models(base_url="https://gateway.example/v1", api_key=SECRET, http=http)
    assert result.ok is True
    assert result.truncated is True
    assert result.models == ["model-a"]
    assert result.message_key == FETCH_LIST_TRUNCATED
    assert result.error_type == ""


def test_dashscope_backfill_puts_candidates_first():
    http = _Recorder(lambda url, headers: _FakeResponse(200, {"data": [
        {"id": "qwen-plus"},
        {"id": "qwen3.8-flash"},
        {"id": "account-only"},
        {"id": "qwen3.8-max"},
    ]}))
    result = list_account_models(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=SECRET,
        provider="dashscope",
        http=http,
    )
    assert result.models[:3] == ["qwen3.8-flash", "qwen3.8-max", "qwen-plus"]
    assert "account-only" in result.models
    assert result.recommended["analysis"] == ["qwen3.8-flash", "qwen3.8-max", "qwen-plus"]
    assert result.message_key == FETCH_LIST_UPDATED


def test_no_overlap_uses_account_list_and_message_key():
    http = _Recorder(lambda url, headers: _FakeResponse(200, {"data": [{"id": "only-on-account"}]}))
    result = list_account_models(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=SECRET,
        provider="dashscope",
        http=http,
    )
    assert result.ok is True
    assert result.models == ["only-on-account"]
    assert result.recommended["analysis"] == []
    assert result.message_key == FETCH_LIST_NO_OVERLAP


def test_get_models_tuple_matches_validation_shape():
    http = _Recorder(lambda url, headers: _FakeResponse(200, {"data": [{"id": "gpt-4o-mini"}]}))
    ids, error, fetched = get_models("https://gateway.example/v1", SECRET, "compatible", http=http)
    assert error is None
    assert ids == ["gpt-4o-mini"]
    assert fetched.ok is True


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setattr(ai, "migrate_legacy", lambda: ai.ModelSettings())


def _patch_httpx(monkeypatch, handler):
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            return handler("GET", url, headers, None)

        def post(self, url, json=None, headers=None):
            return handler("POST", url, headers, json)

    monkeypatch.setattr("httpx.Client", _FakeClient)


def test_validation_backfills_recommended_order(isolated, monkeypatch):
    def handler(method, url, headers, body):
        if method == "GET":
            return _FakeResponse(200, {"data": [
                {"id": "qwen-plus"},
                {"id": "qwen3.8-flash"},
                {"id": "account-only"},
            ]})
        return _FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(
        ai.Connection(id="c", name="百炼", provider="dashscope", api_key=SECRET),
        "qwen3.8-flash",
    )
    assert result.ok is True
    assert result.model_ids[:2] == ["qwen3.8-flash", "qwen-plus"]
    assert result.recommended["analysis"][0] == "qwen3.8-flash"
    assert result.message_key == FETCH_LIST_UPDATED
    assert SECRET not in json.dumps(result.as_api())


def test_fetch_list_for_custom_provider(isolated, monkeypatch):
    def handler(method, url, headers, body):
        assert method == "GET"
        assert url.endswith("/v1/models")
        return _FakeResponse(200, {"data": [{"id": "relay-a"}, {"id": "relay-b"}]})

    _patch_httpx(monkeypatch, handler)
    result = fetch_list_for_connection(ai.Connection(
        id="c", name="custom", provider="compatible",
        base_url="https://gw.example/v1", api_key=SECRET,
    ))
    assert result.ok is True
    assert result.models == ["relay-a", "relay-b"]
    assert result.recommended["analysis"] == []
    assert result.base_url_host == "gw.example"
    dumped = json.dumps(result.as_api())
    assert SECRET not in dumped
    assert "gw.example/v1" not in dumped


def _settings_router():
    """Load the settings router without importing backend.api.v1.__init__."""
    import sys
    import types
    from pathlib import Path

    if "backend.api.v1.settings" in sys.modules:
        return sys.modules["backend.api.v1.settings"].router
    package = types.ModuleType("backend.api.v1")
    package.__path__ = [str(Path(__file__).resolve().parents[1] / "api" / "v1")]
    package.__package__ = "backend.api.v1"
    sys.modules["backend.api.v1"] = package
    from backend.api.v1.settings import router
    return router


def test_compatible_models_runs_fetch_in_threadpool(isolated, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.core.provider_model_fetch import AccountModelList

    seen = []

    def fake_list(**kwargs):
        seen.append(("list", kwargs.get("base_url"), kwargs.get("provider")))
        return AccountModelList(ok=True, models=["local-a"], source="live", base_url_host="127.0.0.1")

    async def fake_pool(func, *args, **kwargs):
        seen.append(("threadpool", func))
        return func(*args, **kwargs)

    monkeypatch.setattr("backend.core.provider_model_fetch.list_account_models", fake_list)
    monkeypatch.setattr("starlette.concurrency.run_in_threadpool", fake_pool)
    app = FastAPI()
    app.include_router(_settings_router())
    with TestClient(app) as client:
        response = client.get("/settings/compatible-models", params={
            "base_url": "http://127.0.0.1:11434/v1",
            "provider": "ollama",
        })
    assert response.status_code == 200
    assert seen[0] == ("threadpool", fake_list)
    assert seen[1][0] == "list"
    assert seen[1][2] == "ollama"
    assert response.json()["models"] == ["local-a"]
    assert response.json()["reachable"] is True
    assert SECRET not in response.text


def test_fetch_list_http_endpoint(isolated, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    def handler(method, url, headers, body):
        return _FakeResponse(200, {"data": [{"id": "relay-a"}]})

    _patch_httpx(monkeypatch, handler)
    app = FastAPI()
    app.include_router(_settings_router())
    with TestClient(app) as client:
        response = client.post("/settings/ai-models/fetch-list", json={
            "connection": {
                "id": "c1", "name": "custom", "provider": "compatible",
                "base_url": "https://gw.example/v1", "api_key": SECRET,
            }
        })
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["models"] == ["relay-a"]
    assert body["base_url_host"] == "gw.example"
    assert SECRET not in response.text
    assert "https://gw.example" not in response.text
    assert "normalized_base_url" not in body


@pytest.mark.stdlib_only
def test_fetch_list_copy_exists_in_all_locales():
    langs = ("zh", "en", "ja", "ko", "es", "pt", "ru", "fr")
    keys = (
        FETCH_LIST_FAILED, FETCH_LIST_UPDATED, FETCH_LIST_NO_OVERLAP,
        FETCH_LIST_TRUNCATED, "settings.providers.fetch_list",
    )
    catalogs = {lang: json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8")) for lang in langs}
    for key in keys:
        for lang, catalog in catalogs.items():
            assert key in catalog, f"{lang} missing {key}"
            assert str(catalog[key]).strip()
            if lang != "zh":
                assert catalog[key] != key


@pytest.mark.parametrize('status,payload', [(401, {'error': 'sk-test-secret-key https://gw.example/v1'}),
    (503, {'error': 'sk-test-secret-key https://gw.example/v1'}), (200, {}), (302, {})])
def test_fetch_failure_never_uses_discover_cache_or_catalog(isolated, monkeypatch, status, payload):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.core import model_registry

    async def forbidden(*args, **kwargs):
        pytest.fail('fetch-list must not use discover or its fallback catalogs')

    monkeypatch.setattr(model_registry, 'discover', forbidden)
    _patch_httpx(monkeypatch, lambda *args: _FakeResponse(status, payload))
    app = FastAPI()
    app.include_router(_settings_router())
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/fetch-list', json={'connection': {
            'id': 'gw', 'name': 'gateway', 'provider': 'compatible',
            'base_url': 'https://gw.example/v1', 'api_key': SECRET,
            'custom_models': [{'id': 'local-fallback', 'types': ['language']}],
        }})
    assert response.status_code == 200
    body = response.json()
    assert body['ok'] is body['success'] is False
    assert body['models'] == []
    assert body['source'] == 'empty'
    assert SECRET not in response.text
    assert 'https://gw.example/v1' not in response.text


@pytest.mark.parametrize('connection', [
    {'id': 'gw', 'name': 'gateway', 'provider': 'compatible', 'base_url': SECRET_URL, 'api_key': SECRET},
    {'id': 'gw', 'name': 'gateway', 'provider': 'compatible', 'base_url': 'https://gw.example/v1?key='+SECRET, 'api_key': SECRET},
    {'id': 'gw', 'name': 'gateway', 'provider': 'compatible', 'base_url': 'https://platform.openai.com/api-keys', 'api_key': SECRET},
    SECRET_URL + SECRET,
])
def test_fetch_request_validation_does_not_echo_url_or_key(isolated, connection):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(_settings_router())
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/fetch-list', json={'connection': connection})
    assert response.status_code == 422
    assert response.json() == {'detail': 'Invalid provider connection'}
    assert SECRET not in response.text
    assert 'https://' not in response.text


@pytest.mark.parametrize('error', [ValueError, RuntimeError])
def test_fetch_exceptions_are_sanitized(isolated, monkeypatch, error):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.services import provider_validation
    def fail(*args, **kwargs):
        raise error(SECRET_URL + SECRET)
    monkeypatch.setattr(provider_validation, 'fetch_list_for_connection', fail)
    app = FastAPI()
    app.include_router(_settings_router())
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/fetch-list', json={'connection': {
            'id': 'gw', 'name': 'gateway', 'provider': 'compatible',
            'base_url': 'https://gw.example/v1', 'api_key': SECRET,
        }})
    assert response.status_code in (200, 422)
    assert SECRET not in response.text
    assert 'https://' not in response.text
