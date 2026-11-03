"""422 responses must never echo credential fields (beginner self-test, 2026-10-15)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

SECRET = "sk-test-secret-should-not-echo"


def _assert_no_secret(payload) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
    assert SECRET not in text
    assert "sk-test-secret" not in text


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    from backend.app_factory import create_app
    with TestClient(create_app(mode="web"), raise_server_exceptions=False) as c:
        yield c


def _conn(**extra):
    return {
        "id": "c1", "name": "dashscope", "provider": "compatible",
        "api_key": SECRET, "base_url": "", "image_api": "auto", "image_base_url": "",
        **extra,
    }


# Model-level validators put the whole connection / body into detail[].input —
# that is the beginner-selftest leak (compatible without URL, follow mismatch, etc.).
@pytest.mark.parametrize("body", [
    {
        "version": 1,
        "connections": [_conn()],
        "analysis": {"connection_id": "c1", "model": "qwen-plus"},
        "cover_enabled": False,
    },
    {
        "version": 1,
        "connections": [_conn(), {**_conn(), "id": "c2", "name": "openai", "provider": "openai"}],
        "analysis": {"connection_id": "c1", "model": "qwen-plus"},
        "cover": {"connection_id": "c2", "model": "dall-e-3"},
        "cover_enabled": True,
        "cover_follows_analysis": True,
    },
    {
        "version": 1,
        "connections": [{"api_key": SECRET}],
        "analysis": {"connection_id": "x", "model": "m"},
        "cover_enabled": False,
    },
], ids=["compatible_needs_url", "follow_mismatch", "missing_connection_fields"])
def test_put_ai_models_422_does_not_echo_api_key(client, body):
    response = client.put("/api/v1/settings/ai-models", json=body)
    assert response.status_code == 422
    _assert_no_secret(response.text)
    stack = [response.json()]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if "api_key" in item:
                assert item["api_key"] in (None, "", "[REDACTED]")
            if "input" in item:
                _assert_no_secret(item["input"])
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            _assert_no_secret(item)


def test_settings_discover_422_does_not_echo_api_key(client):
    response = client.post("/api/v1/settings/ai-models/discover", json={
        "connection": _conn(),
        "refresh": "not-a-bool",
    })
    assert response.status_code == 422
    _assert_no_secret(response.text)
