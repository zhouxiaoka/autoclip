"""N1: a retry run pins a freshly loaded connection and its candidate models."""
import json
import os
from pathlib import Path

import httpx
import pytest

from backend.core.llm_manager import LLMManager
from backend.core.llm_providers import LLMProviderFactory
from backend.services import ai_model_settings
from backend.tests.test_chunk_retry_budget import _response
from backend.tests.test_chunk_retry_budget import (
    http_manager as http_manager,  # noqa: PLC0414 - pytest fixture export
)


@pytest.mark.parametrize("change_during_retry", [False, True])
def test_reload_pins_connection_model_and_candidates(tmp_path, monkeypatch, http_manager, change_during_retry):
    _assert_reload_pins(tmp_path, monkeypatch, http_manager, change_during_retry)


def test_reload_false_then_true_with_coarse_write_times(tmp_path, monkeypatch, http_manager):
    """Both cases run in one process, even when writes share a filesystem tick."""
    original_write = Path.write_text

    def coarse_write(path, *args, **kwargs):
        result = original_write(path, *args, **kwargs)
        if path.name == "settings.json":
            os.utime(path, ns=(1_800_000_000_000_000_000,) * 2)
        return result

    monkeypatch.setattr(Path, "write_text", coarse_write)
    for change_during_retry in (False, True):
        case_dir = tmp_path / str(change_during_retry)
        case_dir.mkdir()
        _assert_reload_pins(case_dir, monkeypatch, http_manager, change_during_retry)


def _assert_reload_pins(tmp_path, monkeypatch, http_manager, change_during_retry):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(ai_model_settings, "load", lambda: None)
    monkeypatch.setattr(LLMManager, "_sync_config_if_needed", lambda self: None)
    hits = []
    stamp = 1_800_000_000_000_000_000

    def save(provider, model):
        nonlocal stamp
        settings_file.write_text(json.dumps({
            "llm_provider": "openai", "connection_provider": provider,
            "connection_name": "fixture", "model_source": "preset", "model_name": model,
            "openai_api_key": "test-fixture", "openai_base_url": f"https://{provider}.test/v1",
        }), encoding="utf-8")
        # Deterministic mtime changes, even on filesystems with coarse resolution.
        stamp += 1_000_000
        os.utime(settings_file, ns=(stamp, stamp))

    def factory(_provider_type, _key, model, **kwargs):
        def handler(request):
            body = json.loads(request.content)
            hits.append((request.url.host, body["model"]))
            if change_during_retry and len(hits) == 1:
                save("dashscope", "qwen-plus")
                # Another caller observes the new config while this request is in flight.
                manager.get_current_provider_info()
            if change_during_retry and len(hits) <= 2:
                return httpx.Response(429, request=request, json={"error": {
                    "code": "rate_limit_exceeded", "message": "rate",
                }})
            return _response(request, "ok")

        provider = http_manager(handler).current_provider
        provider.model_name = model
        provider.base_url = kwargs["base_url"]
        provider.client = provider.client.with_options(base_url=provider.base_url)
        return provider

    monkeypatch.setattr(LLMProviderFactory, "create_provider", factory)
    save("dashscope", "qwen-plus")
    manager = LLMManager(settings_file)
    save("openai", "gpt-5-mini")

    assert manager.call_with_retry("fixture") == "ok"
    if change_during_retry:
        assert hits == [
            ("openai.test", "gpt-5-mini"), ("openai.test", "gpt-5-mini"),
            ("openai.test", "gpt-4o-mini"),
        ]
        assert manager.settings["model_name"] == "qwen-plus"
        assert manager.call_with_retry("next run") == "ok"
        assert hits[-1] == ("dashscope.test", "qwen-plus")
    else:
        assert hits == [("openai.test", "gpt-5-mini")]
        assert manager.settings["model_name"] == "gpt-5-mini"
    assert json.loads(settings_file.read_text())["model_name"] == manager.settings["model_name"]
