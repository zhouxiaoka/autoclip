"""X2: legacy model discovery must not expose credential-bearing HTTP errors."""

import asyncio
import json
import logging

import httpx
import pytest


@pytest.mark.parametrize("surface", ["logs", "response"])
def test_available_models_gemini_401_redacts_key_and_url(monkeypatch, caplog, surface):
    from backend.api.v1.settings import get_available_models
    from backend.core import model_catalog

    fake_key = "AIza-X2-fake-key-never-a-real-credential"
    requests = []

    class UnauthorizedClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *, headers, params):
            request = httpx.Request("GET", url, headers=headers, params=params)
            requests.append(request)
            return httpx.Response(401, request=request, json={"error": {"code": 401}})

    monkeypatch.setattr(httpx, "AsyncClient", UnauthorizedClient)
    model_catalog.clear_model_list_cache()
    try:
        with caplog.at_level(logging.INFO, logger=model_catalog.__name__):
            payload = asyncio.run(get_available_models(
                provider="gemini", api_key=fake_key, refresh=True,
            ))
    finally:
        model_catalog.clear_model_list_cache()

    assert len(requests) == 1
    assert requests[0].url.params["key"] == fake_key
    assert payload["source"] == "catalog"
    assert payload["reachable"] is False
    assert payload["models"]
    assert payload["error"]
    failure_logs = [record for record in caplog.records
                    if record.name == model_catalog.__name__ and record.levelno == logging.INFO]
    assert failure_logs, "the failed discovery must retain a safe diagnostic"

    text = caplog.text if surface == "logs" else json.dumps(payload)
    forbidden = (fake_key, str(requests[0].url), model_catalog.GEMINI_MODELS_URL,
                 "https://", "/v1beta/models", "?key=")
    assert all(value not in text for value in forbidden), "credential or full URL leaked"
    assert "invalid_key" in text
    assert "host=generativelanguage.googleapis.com" in text
