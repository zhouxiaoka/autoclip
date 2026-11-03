"""RL: inspect every enabled logger, including SDK/HTTP and exception output."""
import asyncio
import logging
import re

import httpx
import openai
import pytest


@pytest.mark.parametrize("operation", ["llm", "models"])
def test_failed_requests_do_not_log_private_data(operation, monkeypatch, tmp_path, caplog):
    from backend.core import model_catalog
    from backend.core.llm_providers import OpenAIProvider
    from backend.services.local_runner import setup_logging

    # Use the application's logging policy; do not filter or sanitize captured output.
    root = logging.getLogger()
    capture_handlers = root.handlers[:]
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", root.level)
    for name in ("httpx", "httpcore", "openai"):
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, "level", logger.level)
    setup_logging(verbose=True)
    application_handlers = root.handlers[:]
    root.handlers.extend(capture_handlers)
    caplog.clear()

    # All values are synthetic. Assert with category labels, never echo a leaked value.
    key = "sk-redline-synthetic-credential"
    user_text = "RL_PRIVATE_SUBTITLE_AND_PROMPT_口播"
    endpoint = "https://redline.example.invalid/fixture-private-route"
    paths = ("/fixture-private-folder/source.srt", r"C:\fixture-private-folder\source.srt")
    body = " ".join((key, user_text, endpoint, *paths))
    requests = []

    def reject(request):
        requests.append(request)
        return httpx.Response(401, json={"error": {"message": body}})

    try:
        if operation == "llm":
            with openai.OpenAI(api_key=key, base_url=endpoint, max_retries=0,
                               http_client=httpx.Client(transport=httpx.MockTransport(reject))) as sdk:
                provider = object.__new__(OpenAIProvider)
                provider.api_key, provider.base_url, provider.model_name = key, endpoint, "gpt-4o-mini"
                provider.client = sdk
                with pytest.raises(Exception):
                    provider.call(user_text)
            assert len(requests) == 1, "failure must reach the actual SDK transport"
            assert user_text.encode() in requests[0].content
            assert requests[0].headers["authorization"] == "Bearer " + key
        else:
            real_client = httpx.AsyncClient
            monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(
                **kwargs, transport=httpx.MockTransport(reject)))
            model_catalog.clear_model_list_cache()
            try:
                result = asyncio.run(model_catalog.list_available_models("gemini", api_key=key, refresh=True))
            finally:
                model_catalog.clear_model_list_cache()
            assert len(requests) == 1, "failure must reach the model-list HTTP transport"
            assert requests[0].url.params["key"] == key
            assert not result.reachable and result.source == "catalog" and result.error

        assert caplog.records, "the failure must retain a diagnostic"
        for handler in application_handlers:
            handler.flush()
        output = caplog.text + (tmp_path / "redline.log").read_text(encoding="utf-8")
        forbidden = {
            "credential": re.escape(key),
            "key pattern": r"(?i)(?:sk-[a-z0-9-]{8,}|AIza[a-z0-9_-]{20,}|Bearer\s+\S+)",
            "full URL": r"(?i)https?://",
            "user text": re.escape(user_text),
            "POSIX path": re.escape(paths[0]),
            "Windows path": re.escape(paths[1]),
            "endpoint path": r"/fixture-private-route",
        }
        for category, pattern in forbidden.items():
            assert re.search(pattern, output) is None, "private data in logger output: " + category
    finally:
        root.handlers = capture_handlers
        for handler in application_handlers:
            handler.close()
