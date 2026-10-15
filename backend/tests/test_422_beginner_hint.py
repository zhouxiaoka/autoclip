"""422 field hints are beginner-readable Chinese, without pydantic prefixes or the input."""
from __future__ import annotations

import re
import secrets

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    from backend.app_factory import create_app
    with TestClient(create_app(mode="web"), raise_server_exceptions=False) as c:
        yield c


def _cfg(key="sk-" + "a" * 20, **extra):
    base = {
        "version": 1,
        "connections": [{"id": "c1", "name": "88API", "provider": "api88", "api_key": key, "base_url": ""}],
        "analysis": {"connection_id": "c1", "model": "m"},
        "cover_enabled": False,
    }
    base.update(extra)
    return base


def _messages(response):
    assert response.status_code == 422
    return [entry["message"] for entry in response.json()["detail"]]


def test_overlong_key_says_key_too_long_in_chinese(client):
    key = "sk-" + secrets.token_hex(1600)
    response = client.put("/api/v1/settings/ai-models", json=_cfg(key))
    assert _messages(response) == ["密钥太长，请检查是否粘贴错了"]
    assert key[3:20] not in response.text


def test_object_level_error_drops_value_error_prefix(client):
    response = client.put("/api/v1/settings/ai-models", json=_cfg(cover_enabled=True, cover=None))
    messages = _messages(response)
    assert messages == ["请选择封面生图模型"]
    assert "Value error" not in response.text.split('"input"')[0]


def test_english_pydantic_message_becomes_chinese(client):
    response = client.put("/api/v1/settings/ai-models", json=_cfg(analysis_mode="nonsense"))
    for message in _messages(response):
        assert re.search(r"[\u4e00-\u9fff]", message), message
        assert "Input should" not in message
