"""Saved provider, key, base URL and model survive a reload. No sponsor migration."""
from __future__ import annotations

import copy

from backend.services.ai_model_settings import ModelSettings


def _document(provider: str, base_url: str, model: str) -> dict:
    return {
        "version": 1,
        "connections": [{
            "id": "kept",
            "name": provider,
            "provider": provider,
            "base_url": base_url,
            "api_key": "fixture-key",
            "image_api": "auto",
            "image_base_url": "",
            "base_url_source": "user" if provider == "compatible" else "preset",
        }],
        "analysis": {
            "connection_id": "kept",
            "model": model,
            "capability": "auto",
            "model_source": "user",
        },
        "cover_enabled": False,
        "cover_follows_analysis": False,
        "analysis_mode": "auto",
    }


PROFILES = (
    ("api88", "https://api.88api.ai/v1", "qwen3.8-flash"),
    ("infistar", "https://infistar.cc/v1", "doubao-seed-2-1-turbo-260628"),
    ("apimart", "https://api.apimart.ai/v1", "qwen3.8-flash"),
    ("compatible", "https://gw.example.com/v1", "my-model"),
)


def test_saved_profiles_keep_provider_key_base_url_and_model():
    for provider, base_url, model in PROFILES:
        raw = _document(provider, base_url, model)
        before = copy.deepcopy(raw)
        loaded = ModelSettings.model_validate(raw)
        connection = loaded.connections[0]
        assert connection.provider == provider
        assert connection.api_key == "fixture-key"
        assert connection.base_url == base_url
        assert loaded.analysis is not None
        assert loaded.analysis.model == model
        assert loaded.analysis.model_source == "user"
        assert raw == before
        assert loaded._migration_warnings == []


def test_blank_document_has_no_provider():
    loaded = ModelSettings.model_validate({"version": 1, "connections": []})
    assert loaded.connections == []
    assert loaded.analysis is None


def test_save_and_load_keep_legacy_profiles_on_real_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    from backend.services import ai_model_settings as ai

    cases = (
        ("api88", "https://api.88api.ai/v1", "qwen3.8-flash", "user"),
        ("infistar", "https://custom.example/v1", "account-only-model", "preset"),
        ("apimart", "https://api.apimart.ai/v1", "deepseek-v4-flash", "user"),
        ("compatible", "https://gw.example.com/v1", "my-model", "user"),
    )
    for provider, base_url, model, source in cases:
        raw = _document(provider, base_url, model)
        raw["analysis"]["model_source"] = source
        if provider == "api88":
            raw["connections"][0]["api_key"] = ""
        saved = ai.save(ModelSettings.model_validate(raw))
        assert saved["connections"][0]["provider"] == provider
        assert saved["analysis"]["model"] == model
        loaded = ai.load()
        assert loaded is not None
        assert loaded.connections[0].provider == provider
        assert loaded.connections[0].base_url == base_url
        assert loaded.connections[0].api_key == ("" if provider == "api88" else "fixture-key")
        assert loaded.analysis.model == model
        assert loaded.analysis.model_source == source
        (tmp_path / "ai-model-settings.json").unlink()


def test_blank_model_is_rejected_and_catalog_classes_are_local():
    from pydantic import ValidationError

    from backend.core.model_catalog import is_chat_model, is_image_model, is_non_chat_family, supports_vision

    raw = _document("apimart", "https://api.apimart.ai/v1", "deepseek-v4-flash")
    raw["analysis"]["model"] = "   "
    try:
        ModelSettings.model_validate(raw)
    except ValidationError:
        pass
    else:
        raise AssertionError("an empty model must not be stored as a selected model")
    assert supports_vision("gemini-3.8-flash")
    assert not supports_vision("deepseek-v4-flash")
    assert is_chat_model("deepseek-v4-flash", "apimart", official=False)
    assert is_image_model("gpt-image-1")
    assert is_non_chat_family("gpt-4o-realtime-preview")
    assert not is_chat_model("wan2.6", "apimart", official=False)
