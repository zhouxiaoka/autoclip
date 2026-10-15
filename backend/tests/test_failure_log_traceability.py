"""S2: failure diagnostics retain identifiers without retaining user data."""
import json
import logging
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.stdlib_only

PROJECT = "3cacd2f0-01c0-4c66-a056-eb63d6b8719b"
PRIVATE = "fixture private prompt subtitle title response"
ERROR = PRIVATE + " sk-fixture-secret https://fixture.invalid/private?key=fixture-key /private/input.srt"


def fail(*args, **kwargs):
    raise RuntimeError(ERROR)


@pytest.mark.parametrize("stage", [
    "outline", "timeline", "score_backend", "score_chunk", "title", "cluster", "retry", "degrade",
])
def test_failing_chunk_logs_ids_without_content(stage, tmp_path, monkeypatch, caplog):
    from backend.core import project_cancellation
    from backend.pipeline import step1_outline, step2_timeline, step3_scoring, step4_title, step5_clustering
    from backend.pipeline.failures import PipelineFailure

    monkeypatch.setenv("AUTOCLIP_LLM_CONCURRENCY", "1")
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    caplog.set_level(logging.DEBUG)
    clips = [{"id": "17", "chunk_index": 0, "outline": PRIVATE, "content": PRIVATE, "final_score": .9}]
    client = SimpleNamespace(call_with_retry=fail)
    with project_cancellation.bind(PROJECT):
        if stage == "outline":
            prompt = tmp_path / "prompt.txt"
            prompt.write_text(PRIVATE)
            monkeypatch.setattr(step1_outline, "LLMClient", lambda: client)
            extractor = step1_outline.OutlineExtractor(tmp_path, {"outline": prompt})
            srt = tmp_path / "input.srt"
            srt.write_text("1\n00:00:01,000 --> 00:00:12,000\n" + PRIVATE + "\n")
            with pytest.raises(PipelineFailure):
                extractor.extract_outline(srt)
            module = step1_outline
        elif stage == "timeline":
            prompt = tmp_path / "prompt.txt"
            prompt.write_text(PRIVATE)
            monkeypatch.setattr(step2_timeline, "LLMClient", lambda: client)
            chunks = tmp_path / "step1_srt_chunks"
            chunks.mkdir()
            (chunks / "chunk_0.json").write_text(json.dumps([
                {"index": 1, "start_time": "00:00:01,000", "end_time": "00:00:12,000", "text": PRIVATE},
            ]))
            extractor = step2_timeline.TimelineExtractor(tmp_path, {"timeline": prompt})
            assert extractor.extract_timeline([{"title": PRIVATE, "subtopics": [], "chunk_index": 0}]) == []
            module = step2_timeline
        elif stage.startswith("score"):
            scorer = object.__new__(step3_scoring.ClipScorer)
            scorer._srt_entries = []
            scorer.scoring_backend = SimpleNamespace(score=fail)
            if stage == "score_chunk":
                scorer._get_llm_evaluation = fail
            scorer.score_clips(clips)
            module = step3_scoring
        elif stage == "cluster":
            engine = object.__new__(step5_clustering.ClusteringEngine)
            engine.max_clips = 5
            engine.clustering_prompt = PRIVATE
            engine.llm_client = client
            engine.cluster_clips(clips_with_titles=clips)
            module = step5_clustering
        else:
            if stage in {"retry", "degrade"}:
                from backend.core import llm_degrade
                from backend.core.llm_manager import LLMManager, _CallRoute
                from backend.utils.llm_client import LLMClient

                def rejected(*args, **kwargs):
                    error = RuntimeError(ERROR)
                    error.status_code = 429 if stage == "degrade" else 503
                    error.body = {"error": {"code": "rate_limit_exceeded" if stage == "degrade" else "server_error"}}
                    raise error

                provider = SimpleNamespace(call=rejected, model_name="fixture-model")
                settings = {"model_source": "preset", "model_name": "fixture-model"}
                manager = object.__new__(LLMManager)
                manager._snapshot_call_route = lambda: _CallRoute(provider, settings, {})
                monkeypatch.setattr(llm_degrade, "candidates_for_call", lambda settings: ("fixture-model", "fixture-next"))
                monkeypatch.setattr("backend.core.llm_manager._llm_cache_path", lambda *args: None)
                client = object.__new__(LLMClient)
                client.llm_manager = manager
            generator = object.__new__(step4_title.TitleGenerator)
            generator.title_prompt = PRIVATE
            generator.llm_raw_output_dir = tmp_path / "raw"
            generator.llm_client = client
            assert generator.generate_titles(clips) == clips
            module = step4_title

    step = module.__name__.rsplit(".", 1)[-1]
    messages = [record.getMessage() for record in caplog.records
                if record.name == module.__name__ and record.levelno >= logging.ERROR]
    assert messages, "the triggering failure must actually be logged"
    for message in messages:
        assert f"step={step}" in message
        assert f"project_id={PROJECT}" in message
        if stage != "cluster":
            assert "chunk_index=0" in message
        if stage not in {"outline", "timeline"}:
            assert "clip_ids=17" in message
    if stage in {"retry", "degrade"}:
        manager_logs = [record.getMessage() for record in caplog.records
                        if record.name == "backend.core.llm_manager" and record.levelno >= logging.WARNING]
        assert any("重试" in message for message in manager_logs)
        assert any("same-provider" in message for message in manager_logs) == (stage == "degrade")
        for message in manager_logs:
            for identifier in (f"step={step}", f"project_id={PROJECT}", "chunk_index=0", "clip_ids=17"):
                assert identifier in message
    for private in (PRIVATE, "sk-fixture-secret", "https://", "/private", "fixture-key", str(tmp_path)):
        assert private not in caplog.text


def test_parallel_chunk_failure_ids_are_isolated(tmp_path, monkeypatch, caplog):
    from backend.core import project_cancellation
    from backend.pipeline.step4_title import TitleGenerator

    monkeypatch.setenv("AUTOCLIP_LLM_CONCURRENCY", "2")
    generator = object.__new__(TitleGenerator)
    generator.title_prompt = PRIVATE
    generator.llm_raw_output_dir = tmp_path / "raw"
    generator.llm_client = SimpleNamespace(call_with_retry=fail)
    clips = [{"id": str(17 + index), "chunk_index": index, "outline": PRIVATE} for index in range(2)]
    with project_cancellation.bind(PROJECT):
        assert generator.generate_titles(clips) == clips
    messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(messages) == 2
    for index in range(2):
        message = next((message for message in messages if f"chunk_index={index}" in message), "")
        assert f"project_id={PROJECT}" in message
        assert f"clip_ids={17 + index}" in message
        assert f"clip_ids={18 - index}" not in message
    caplog.clear()
    from backend.utils.llm_client import LLMClient
    client = object.__new__(LLMClient)
    client.llm_manager = SimpleNamespace(call=fail)
    with pytest.raises(RuntimeError):
        client.call(PRIVATE)
    assert "chunk_index=" not in caplog.text
    assert "clip_ids=" not in caplog.text
    assert "step=" not in caplog.text
    assert "project_id=" not in caplog.text


@pytest.mark.parametrize("bad_id", [PRIVATE, "sk-fixture-secret", "https://fixture.invalid/input", "/private/input", "private-title"])
def test_failure_context_rejects_non_identifier_fields(bad_id, tmp_path, monkeypatch, caplog):
    from backend.pipeline.step4_title import TitleGenerator

    monkeypatch.setenv("AUTOCLIP_LLM_CONCURRENCY", "1")
    generator = object.__new__(TitleGenerator)
    generator.title_prompt = PRIVATE
    generator.llm_raw_output_dir = tmp_path / "raw"
    generator.llm_client = SimpleNamespace(call_with_retry=fail)
    generator.generate_titles([{"id": bad_id, "chunk_index": 0, "outline": PRIVATE}])
    assert bad_id not in caplog.text
