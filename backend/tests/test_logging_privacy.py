"""Behavior tests that logs and SDK traffic do not expose private data."""
import json
import logging
from types import SimpleNamespace

import httpx
import openai
import pytest

from backend.core.log_redaction import redact_text
"""real SDK traffic and pipeline diagnostics must not expose private data."""

BODY = "fixture-private-title-subtitle-response"
KEY = "sk-fixture-private-sdk-key"
URL = "https://sdk.example.invalid/private-endpoint?key=fixture-query-key"
PRIVATE_ERROR = f"{BODY} {KEY} {URL} /fixture-private-folder/input.srt"


def fail(*args, **kwargs):
    raise RuntimeError(PRIVATE_ERROR)


def assert_private_data_absent(text, tmp_path):
    for private in (BODY, KEY, URL, "fixture-query-key", "sdk.example.invalid",
                    "/private-endpoint", "/fixture-private-folder", str(tmp_path)):
        assert private not in text


@pytest.mark.stdlib_only
@pytest.mark.parametrize("entrypoint", ["desktop", "web", "cli", "cli_verbose"])
@pytest.mark.parametrize("scenario", ["success", "retry", "unauthorized"])
def test_real_sdk_logs_hide_url_key_and_body(entrypoint, scenario, tmp_path, monkeypatch, caplog):
    # Run the actual entrypoint logging setup, then restore pytest's capture handlers.
    root = logging.getLogger()
    capture_handlers = root.handlers[:]
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.DEBUG)
    for name in ("httpx", "httpcore", "openai"):
        monkeypatch.setattr(logging.getLogger(name), "level", logging.NOTSET)
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "sdk.log"))
    (tmp_path / "logs").mkdir()
    if entrypoint == "desktop":
        from backend.desktop_main import DesktopServiceManager
        manager = object.__new__(DesktopServiceManager)
        manager.config = SimpleNamespace(log_level="DEBUG", paths=SimpleNamespace(data_dir=tmp_path))
        manager._setup_logging()
    elif entrypoint == "web":
        from backend import app_factory
        monkeypatch.setattr(app_factory, "get_logging_config", lambda: {
            "level": "DEBUG", "format": "%(message)s", "file": str(tmp_path / "sdk.log"),
        })
        monkeypatch.setattr("backend.core.sentry_setup.init_sentry", lambda mode: None)
        app_factory.create_app(mode="web")
    else:
        from backend.services.local_runner import setup_logging
        setup_logging(verbose=entrypoint == "cli_verbose")
    for handler in root.handlers:
        handler.close()
    root.handlers = capture_handlers
    caplog.set_level(logging.DEBUG)
    caplog.clear()

    calls = []

    def respond(request):
        calls.append(request)
        if scenario == "unauthorized" or (scenario == "retry" and len(calls) == 1):
            return httpx.Response(401 if scenario == "unauthorized" else 503,
                                  headers={"retry-after-ms": "1"},
                                  json={"error": {"message": PRIVATE_ERROR}})
        return httpx.Response(200, json={
            "id": "fixture", "object": "chat.completion", "created": 0, "model": "fixture",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": BODY},
                         "finish_reason": "stop"}],
        })

    with openai.OpenAI(api_key=KEY, base_url=URL, max_retries=1,
                       http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
        if scenario == "unauthorized":
            with pytest.raises(openai.AuthenticationError):
                client.chat.completions.create(model="fixture", messages=[{"role": "user", "content": BODY}])
        else:
            result = client.chat.completions.create(model="fixture", messages=[{"role": "user", "content": BODY}])
            assert result.choices[0].message.content == BODY
    assert len(calls) == (2 if scenario == "retry" else 1)
    assert calls[0].headers["authorization"] == f"Bearer {KEY}"
    assert BODY.encode() in calls[0].content
    assert_private_data_absent(caplog.text, tmp_path)
    for name in ("httpx", "httpcore", "openai"):
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING


@pytest.mark.stdlib_only
@pytest.mark.parametrize("parsed", [{"1": BODY}, [BODY], {}])
@pytest.mark.parametrize("outline", [BODY, {"title": BODY}])
def test_title_logs_only_lengths_and_preserves_results(parsed, outline, tmp_path, monkeypatch, caplog):
    from backend.pipeline import concurrency
    from backend.pipeline.step4_title import TitleGenerator
    generator = object.__new__(TitleGenerator)
    generator.llm_raw_output_dir = tmp_path / "step4_llm_raw_output"
    generator.title_prompt = BODY
    generator.llm_client = SimpleNamespace(call_with_retry=lambda *args: json.dumps(parsed),
                                           parse_json_response=json.loads)
    monkeypatch.setattr(concurrency, "map_chunks", lambda fn, items: map(fn, items))
    caplog.set_level(logging.DEBUG)
    clips = [{"id": "1", "chunk_index": 0, "outline": outline, "content": BODY}]
    result = generator.generate_titles(clips)
    assert result == clips
    if isinstance(parsed, dict):
        assert result[0]["generated_title"] == (BODY if parsed else outline)
    generator.save_clips_with_titles(result, tmp_path / "titles.json")
    assert_private_data_absent(caplog.text, tmp_path)
    for diagnostic in generator.llm_raw_output_dir.glob("*.txt"):
        assert_private_data_absent(diagnostic.read_text(), tmp_path)


@pytest.mark.stdlib_only
@pytest.mark.parametrize("stage", ["score_backend", "score_chunk", "score_settings", "title", "cluster", "cluster_validation"])
def test_pipeline_exception_logs_only_type_and_message_length(stage, tmp_path, monkeypatch, caplog):
    from backend.pipeline import concurrency, step3_scoring, step4_title, step5_clustering
    monkeypatch.setattr(concurrency, "map_chunks", lambda fn, items: map(fn, items))
    caplog.set_level(logging.DEBUG)
    clips = [{"id": "1", "chunk_index": 0, "outline": BODY, "final_score": .9}]
    if stage.startswith("score"):
        scorer = object.__new__(step3_scoring.ClipScorer)
        scorer._srt_entries = []
        scorer.scoring_backend = SimpleNamespace(score=fail)
        if stage == "score_settings":
            monkeypatch.setattr(step3_scoring, "MIN_SCORE_OVERRIDE", None)
            monkeypatch.setattr("backend.core.llm_manager.get_llm_manager", fail)
            assert step3_scoring.resolve_min_score_threshold() == float(step3_scoring.MIN_SCORE_THRESHOLD)
        elif stage == "score_chunk":
            scorer._get_llm_evaluation = fail
            assert scorer.score_clips(clips) == []
        else:
            assert scorer.score_clips(clips)[0]["score_source"] == "fallback"
    elif stage == "title":
        generator = object.__new__(step4_title.TitleGenerator)
        generator.llm_raw_output_dir = tmp_path / "raw"
        generator.title_prompt = BODY
        generator.llm_client = SimpleNamespace(call_with_retry=fail)
        assert generator.generate_titles(clips) == clips
    else:
        engine = object.__new__(step5_clustering.ClusteringEngine)
        engine.max_clips = 5
        engine.clustering_prompt = BODY
        engine.llm_client = SimpleNamespace(call_with_retry=fail)
        if stage == "cluster_validation":
            class BrokenCollection(dict):
                __getitem__ = fail
            assert engine._validate_collections([BrokenCollection.fromkeys(
                ["collection_title", "collection_summary", "clips"])], clips) == []
        else:
            assert engine.cluster_clips(clips) == []
    assert "RuntimeError" in caplog.text
    assert f"message_length={len(PRIVATE_ERROR)}" in caplog.text
    assert_private_data_absent(caplog.text, tmp_path)


@pytest.mark.stdlib_only
def test_score_and_collection_save_logs_hide_paths_and_missing_outline(tmp_path, caplog):
    from backend.pipeline.step3_scoring import ClipScorer
    from backend.pipeline.step5_clustering import ClusteringEngine
    caplog.set_level(logging.DEBUG)
    scorer = object.__new__(ClipScorer)
    assert scorer.score_clips([{"outline": BODY}]) == []
    scorer.save_scores([], tmp_path / "scores.json")
    engine = object.__new__(ClusteringEngine)
    assert engine.save_collections([], tmp_path / "collections.json").exists()
    assert_private_data_absent(caplog.text, tmp_path)
"""Digest / quoted-with-space Authorization and spaced api_key values must not leak."""

FAKE = "FAKEsecretTOKEN123"  # not a real key

CASES = [
    f'Authorization: Digest username="u", realm="r", response="{FAKE}"',
    f'Proxy-Authorization: Digest username="u", nonce="n", response="{FAKE}"',
    f'{{"Authorization": "Digest username=\\"u\\", response=\\"{FAKE}\\""}}',
    f"{{'Authorization': 'Bearer abc {FAKE}'}}",
    f'Authorization: "Token prefix {FAKE}"',
    f'api_key="prefix {FAKE}"',
    f"api_key='prefix {FAKE}'",
    f'{{"api_key": "prefix {FAKE}", "model": "m"}}',
    f'{{"x-api-key": "a b {FAKE}"}}',
    f'password="two words {FAKE}"',
    f"https://h/v1?api_key=prefix%20{FAKE}&model=m",
    f"api_key=prefix+{FAKE}&model=m",
]


@pytest.mark.parametrize("text", CASES)
def test_spaced_and_digest_credentials_redacted(text):
    out = redact_text(text)
    assert FAKE not in out, out
    assert "[REDACTED]" in out


def test_neighbouring_fields_kept():
    out = redact_text(f'{{"api_key": "prefix {FAKE}", "model": "gemini-x"}}')
    assert '"model": "gemini-x"' in out
    out = redact_text(f"{{'Authorization': 'Digest a=\"b\" {FAKE}', 'Accept': 'json'}}")
    assert FAKE not in out and "'Accept': 'json'" in out


def test_idempotent():
    once = redact_text(f'Authorization: Digest response="{FAKE}"')
    assert redact_text(once) == once
