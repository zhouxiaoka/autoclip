"""count SDK HTTP sends across the whole outline chunk lifecycle."""
import json
from collections import Counter
from types import SimpleNamespace

import httpx
import openai
import pytest

from backend.core.llm_degrade import CHUNK_CALL_CAP
from backend.core.llm_manager import LLMManager
from backend.core.llm_providers import LLM_SDK_MAX_RETRIES, OpenAIProvider
from backend.pipeline import concurrency, step1_outline, step2_timeline
from backend.pipeline.failures import PipelineFailure


@pytest.fixture
def http_manager(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setenv("AUTOCLIP_LLM_CONCURRENCY", "2")
    monkeypatch.delenv("AUTOCLIP_LLM_CACHE_DIR", raising=False)
    concurrency.reset_limiter()
    clients = []

    def make(handler):
        client = openai.OpenAI(
            api_key="test-fixture", base_url="https://llm.test/v1",
            max_retries=LLM_SDK_MAX_RETRIES,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        clients.append(client)
        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider.api_key = "test-fixture"
        provider.model_name = "qwen-plus"
        provider.kwargs = {}
        provider.base_url = "https://llm.test/v1"
        provider.is_custom_endpoint = True
        provider.client = client
        manager = LLMManager.__new__(LLMManager)
        manager.settings = {
            "model_source": "preset", "model_name": "qwen-plus",
            "connection_provider": "dashscope", "llm_provider": "openai",
            "openai_base_url": provider.base_url,
        }
        manager.current_provider = provider
        manager._reload_if_settings_changed = lambda: None
        manager.get_current_provider_info = lambda: {
            "provider": "dashscope", "model": "qwen-plus", "base_url": provider.base_url,
        }
        return manager

    yield make
    for client in clients:
        client.close()
    concurrency.reset_limiter()


def _response(request, content):
    return httpx.Response(200, request=request, json={
        "id": "fixture", "object": "chat.completion", "created": 0,
        "model": "fixture", "choices": [{"index": 0,
            "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
    })


def _outline(tmp_path, monkeypatch, manager):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("outline", encoding="utf-8")
    monkeypatch.setattr(step1_outline, "LLMClient", lambda: SimpleNamespace(
        call_with_retry=manager.call_with_retry,
    ))
    extractor = step1_outline.OutlineExtractor(tmp_path / "meta", {"outline": prompt})
    srt = tmp_path / "input.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:10,000\nfixture\n", encoding="utf-8")
    monkeypatch.setattr(extractor.text_processor, "chunk_srt_data", lambda *a, **k: [
        {"chunk_index": i, "text": name, "srt_entries": []}
        for i, name in enumerate(("chunk-a", "chunk-b"))
    ])
    monkeypatch.setattr(extractor.text_processor, "limit_srt_chunk_size", lambda chunks, *a: chunks)
    return extractor, srt


def test_outline_outer_repair_rounds_share_http_budget(tmp_path, monkeypatch, http_manager):
    hits = Counter()

    def handler(request):
        body = json.loads(request.content)
        chunk = json.loads(body["messages"][0]["content"].split("输入内容：\n", 1)[1])["text"]
        hits[chunk] += 1
        # Every outer round: SDK retries a 500, then the manager gets invalid JSON.
        if hits[chunk] % 3:
            return httpx.Response(500, request=request, json={"error": {"message": "unavailable"}})
        return _response(request, "[]")

    extractor, srt = _outline(tmp_path, monkeypatch, http_manager(handler))
    with pytest.raises(PipelineFailure):
        extractor.extract_outline(srt)
    assert set(hits) == {"chunk-a", "chunk-b"}
    assert all(0 < count <= CHUNK_CALL_CAP for count in hits.values()), hits


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.parametrize("success_round", [2, 3])
def test_timeline_can_recover_within_budget_and_new_run_resets_it(
    tmp_path, monkeypatch, http_manager, workers, success_round,
):
    from backend.tests.test_recent_feedback import cue

    monkeypatch.setenv("AUTOCLIP_LLM_CONCURRENCY", str(workers))
    hits = Counter()

    def handler(request):
        body = json.loads(request.content)
        data = json.loads(body["messages"][0]["content"].split("输入内容：\n", 1)[1])
        chunk = data["outline"][0]["title"]
        hits[chunk] += 1
        offset = 0 if chunk == "chunk-a" else 90
        start, end = (0, 5) if hits[chunk] < success_round else (25, 55)
        return _response(request, json.dumps([{
            "outline": chunk, "start_time": offset + start, "end_time": offset + end,
        }]))

    manager = http_manager(handler)
    monkeypatch.setattr("backend.utils.llm_client.get_llm_manager", lambda: manager)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("extract", encoding="utf-8")
    chunks = tmp_path / "step1_srt_chunks"
    chunks.mkdir()
    for index, offset in enumerate((0, 90)):
        (chunks / f"chunk_{index}.json").write_text(json.dumps([
            dict(cue(offset, offset + 5), index=1),
            dict(cue(offset + 25, offset + 55), index=2),
        ]), encoding="utf-8")
    outlines = tmp_path / "outline.json"
    outlines.write_text(json.dumps([
        {"title": name, "chunk_index": i, "subtopics": []}
        for i, name in enumerate(("chunk-a", "chunk-b"))
    ]), encoding="utf-8")

    for _run in range(2):
        hits.clear()
        result = step2_timeline.run_step2_timeline(
            outlines, metadata_dir=tmp_path, prompt_files={"timeline": prompt},
        )
        assert [item["outline"] for item in result] == ["chunk-a", "chunk-b"]
        assert hits == {"chunk-a": success_round, "chunk-b": success_round}
        assert all(count <= CHUNK_CALL_CAP for count in hits.values())
        assert json.loads((tmp_path / "step2_timeline.json").read_text()) == result


def test_token_parameter_resend_counts_against_chunk_budget(http_manager):
    hits = []

    def handler(request):
        body = json.loads(request.content)
        hits.append(body)
        if "max_tokens" in body:
            return httpx.Response(400, request=request, json={"error": {
                "message": "Use max_completion_tokens instead of max_tokens", "type": "invalid_request_error",
            }})
        return httpx.Response(500, request=request, json={"error": {"message": "unavailable"}})

    manager = http_manager(handler)
    with pytest.raises(RuntimeError) as caught:
        manager.call_with_retry("chunk-a", max_tokens=64)
    expected_status = 400 if "max_tokens" in hits[-1] else 500
    assert caught.value.status_code == expected_status
    assert "Use max_completion_tokens" not in str(caught.value)
    assert any("max_completion_tokens" in body for body in hits)
    assert len(hits) <= CHUNK_CALL_CAP


def test_each_outline_chunk_can_recover_in_third_round(tmp_path, monkeypatch, http_manager):
    hits = Counter()

    def handler(request):
        body = json.loads(request.content)
        chunk = json.loads(body["messages"][0]["content"].split("输入内容：\n", 1)[1])["text"]
        hits[chunk] += 1
        return _response(request, "[]" if hits[chunk] < 3 else json.dumps([{"title": chunk}]))

    extractor, srt = _outline(tmp_path, monkeypatch, http_manager(handler))
    outlines = extractor.extract_outline(srt)
    assert [item["title"] for item in outlines] == ["chunk-a", "chunk-b"]
    assert hits == {"chunk-a": 3, "chunk-b": 3}


@pytest.mark.parametrize("workers", [1, 2])
def test_timeline_outer_repair_rounds_share_http_budget(tmp_path, monkeypatch, http_manager, workers):
    from backend.tests.test_recent_feedback import cue, prepared_extractor

    monkeypatch.setenv("AUTOCLIP_LLM_CONCURRENCY", str(workers))
    hits = Counter()

    def handler(request):
        body = json.loads(request.content)
        data = json.loads(body["messages"][0]["content"].split("输入内容：\n", 1)[1])
        chunk = data["outline"][0]["title"]
        hits[chunk] += 1
        # Five HTTP sends per outer round: SDK retry, JSON repair, then a
        # valid range that refinement drops. This triggers timeline_empty.
        if hits[chunk] % 5 in (1, 3):
            return httpx.Response(500, request=request, json={"error": {"message": "unavailable"}})
        content = "[]" if hits[chunk] % 5 else json.dumps([{
            "outline": chunk, "start_time": 0 if chunk == "chunk-a" else 30,
            "end_time": 5 if chunk == "chunk-a" else 35,
        }])
        return _response(request, content)

    extractor = prepared_extractor(tmp_path)
    (extractor.srt_chunks_dir / "chunk_0.json").write_text(
        json.dumps([dict(cue(0, 5), index=1)]), encoding="utf-8",
    )
    (extractor.srt_chunks_dir / "chunk_1.json").write_text(
        json.dumps([dict(cue(30, 35), index=2)]), encoding="utf-8",
    )
    extractor.llm_client.call_with_retry = http_manager(handler).call_with_retry
    monkeypatch.setattr(step2_timeline, "TimelineExtractor", lambda *a, **k: extractor)
    outlines = tmp_path / "outline.json"
    outlines.write_text(json.dumps([
        {"title": name, "chunk_index": i, "subtopics": []}
        for i, name in enumerate(("chunk-a", "chunk-b"))
    ]), encoding="utf-8")
    rounds = []
    extract = extractor.extract_timeline

    def tracked_extract(*args, **kwargs):
        rounds.append(1)
        return extract(*args, **kwargs)

    monkeypatch.setattr(extractor, "extract_timeline", tracked_extract)
    with pytest.raises(PipelineFailure):
        step2_timeline.run_step2_timeline(outlines, metadata_dir=tmp_path)
    assert len(rounds) >= 2
    assert json.loads((tmp_path / "step2_timeline.json").read_text()) == []
    assert set(hits) == {"chunk-a", "chunk-b"}
    assert all(0 < count <= CHUNK_CALL_CAP for count in hits.values()), hits
