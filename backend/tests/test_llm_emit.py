"""1.5.7 Line A: request/run telemetry, ASR probe, reserved validation hook, privacy."""
import json

import pytest

from backend.core import llm_emit as telem
from backend.core import llm_telemetry as schema
from backend.core.llm_providers import LLMProvider, LLMResponse
from backend.core.sentry_setup import studio_failure_context
from backend.pipeline.failures import PipelineFailure


class _StatusError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class _ProbeProvider(LLMProvider):
    def __init__(self, **kwargs):
        super().__init__(api_key=kwargs.pop("api_key", "sk-secret-key"), model_name="qwen-plus", **kwargs)
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def call(self, prompt, input_data=None, **kwargs):
        if kwargs.get("fail"):
            raise _StatusError("Error code: 429 - private body sk-secret", 429)
        return LLMResponse(
            content='{"ok":true}',
            usage={"prompt_tokens": 11, "completion_tokens": 4},
            model="qwen-plus",
            finish_reason="stop",
        )

    def test_connection(self):
        return True

    def get_available_models(self):
        return []


@pytest.fixture
def capture(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_POSTHOG_KEY", "phc_test")
    monkeypatch.delenv("VITE_PUBLIC_POSTHOG_KEY", raising=False)
    (tmp_path / "privacy.json").write_text('{"analytics":true}', encoding="utf-8")
    (tmp_path / "analytics.json").write_text(
        '{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}', encoding="utf-8")
    class _Bodies(list):
        def _ready(self):
            telem.wait_until_idle()

        def __iter__(self):
            self._ready()
            return super().__iter__()

        def __len__(self):
            self._ready()
            return super().__len__()

        def __getitem__(self, item):
            self._ready()
            return super().__getitem__(item)

        def __eq__(self, other):
            self._ready()
            return super().__eq__(other)

        def __bool__(self):
            self._ready()
            return super().__bool__()

    bodies = _Bodies()

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def urlopen(req, timeout=0):
        bodies.append(json.loads(req.data.decode()))
        return Resp()

    monkeypatch.setattr(telem.urllib.request, "urlopen", urlopen)
    return bodies


def test_hostname_and_model_never_keep_keys_or_urls():
    assert schema.hostname_of_base_url("https://dashscope.aliyuncs.com/compatible-mode/v1") == "dashscope.aliyuncs.com"
    assert schema.hostname_of_base_url("http://127.0.0.1:11434/v1") == "local"
    assert schema.sanitize_model("qwen-plus") == "qwen-plus"
    assert schema.sanitize_model("has space") == "redacted"
    assert schema.sanitize_model("用户口播：把这段广告词发到抖音") == "redacted"
    blob = json.dumps(telem.request_finished(
        provider="openai", model="sk-abc", base_url="https://api.openai.com/v1/chat/completions?k=1",
        outcome="success", http_status=200, duration_ms=12,
    ))
    assert "sk-" not in blob.lower()
    assert "chat/completions" not in blob
    assert '"base_url"' not in blob


def test_provider_call_success_and_failure_emit_llm_request_finished(capture):
    provider = _ProbeProvider()
    with telem.track_run(), telem.bind_context(provider="dashscope", model="qwen-plus", base_url=provider.base_url):
        response = provider.call("private prompt", {"caption": "secret subtitle"})
        assert response.content == '{"ok":true}'
        with pytest.raises(_StatusError) as caught:
            provider.call("private prompt", fail=True)
        snapshot = telem.run_snapshot(error=caught.value)  # the failed request's own record
    events = [row for row in capture if row["event"] == "llm_request_finished"]
    assert len(events) == 2
    ok, failed = events
    assert ok["distinct_id"] == "018f6b2a-7c3d-7b2a-8c11-111111111111"
    assert ok["properties"]["provider"] == "dashscope"
    assert ok["properties"]["model"] == "qwen-plus"
    assert ok["properties"]["base_url_host"] == "dashscope.aliyuncs.com"
    assert ok["properties"]["http_status"] == 200
    assert ok["properties"]["outcome"] == "success"
    assert ok["properties"]["prompt_tokens"] == 11
    assert ok["properties"]["kind"] == "text"
    assert "sk-" not in json.dumps(ok)
    assert "private" not in json.dumps(ok["properties"])
    assert failed["properties"]["outcome"] == "error"
    assert failed["properties"]["upstream_error_type"] == "rate_limited"
    assert failed["properties"]["http_status"] == 429
    assert failed["properties"]["failure_stage"]
    assert snapshot["upstream_error_type"] == "rate_limited"
    assert snapshot["billable_calls_before_failure"] == 1
    assert snapshot.get("retry_count", 0) == 0
    assert snapshot.get("degrade_count", 0) == 0


@pytest.mark.parametrize("second_status,event_type,snapshot_type", [
    (503, "upstream_unavailable", "upstream_unavailable"),
    (418, "unknown", "unknown"),
    (None, "timeout", None),
])
def test_consecutive_failures_keep_latest_error_in_run_and_store(
    capture, monkeypatch, tmp_path, second_status, event_type, snapshot_type,
):
    from backend.services.studio import store

    monkeypatch.setattr(telem, "configured_connection_fields", lambda: {})
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    (tmp_path / "p1").mkdir()
    fields = ("http_status", "upstream_error_type", "failure_stage", "retry_count")
    with telem.track_run():
        telem.request_finished(provider="openai", outcome="error", error=_StatusError("fixture", 429), stage="analyze")
        error = _StatusError("fixture", second_status) if second_status else TimeoutError()
        telem.request_finished(provider="openai", outcome="error", error=error, stage="production", retries=1)
        snapshot = telem.run_snapshot(error=error)
        try:  # the failure is written while its exception is handled (as the job workers do)
            raise error
        except Exception:
            store.write("p1", {
                "schema_version": 2,
                "generation": {"status": "failed"},
                "analysis": {"status": "failed", "phase": "production"},
            })

    events = [row["properties"] for row in capture if row["event"] == "llm_request_finished"]
    assert len(events) == 2
    assert events[0]["http_status"] == 429
    assert events[0]["upstream_error_type"] == "rate_limited"
    assert {key: events[1].get(key) for key in fields} == dict(zip(
        fields, (second_status, event_type, "production", 1)))
    saved = json.loads((tmp_path / "p1" / "metadata" / "studio.json").read_text())
    # A timeout without HTTP stays local: the request event names it, the snapshot does not.
    snapshot_status = second_status if snapshot_type else None
    for record in (snapshot, saved["generation"], saved["analysis"]):
        assert {key: record.get(key) for key in fields} == dict(zip(
            fields, (snapshot_status, snapshot_type, "production", 1)))


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_successful_recovery_clears_upstream_error_across_run_and_store(capture, monkeypatch, tmp_path, status):
    from backend.services.studio import store

    monkeypatch.setattr(telem, "configured_connection_fields", lambda: {})
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    (tmp_path / "p1").mkdir()
    provider = _ProbeProvider()
    with telem.track_run():
        with pytest.raises(_StatusError) as caught:
            provider.call("fixture", fail=True)
        assert telem.run_snapshot(error=caught.value)["upstream_error_type"] == "rate_limited"
        provider.call("fixture")
        snapshot = telem.run_snapshot()
        store.write("p1", {
            "schema_version": 2,
            "generation": {"status": status},
            "analysis": {"status": status, "phase": "production"},
        })

    events = [row["properties"] for row in capture if row["event"] == "llm_request_finished"]
    assert events[0]["upstream_error_type"] == "rate_limited"
    assert events[1]["outcome"] == "success"
    assert "upstream_error_type" not in events[1]
    assert "upstream_error_type" not in snapshot
    assert snapshot["llm_calls"] == 2
    assert snapshot["billable_calls_before_failure"] == 1
    saved = json.loads((tmp_path / "p1" / "metadata" / "studio.json").read_text())
    for name in ("generation", "analysis"):
        assert "upstream_error_type" not in saved[name]
        assert saved[name]["llm_calls"] == 2


@pytest.mark.parametrize("generation_status,analysis_status", [("completed", "completed"), ("production", "running")])
def test_reused_store_records_clear_stale_failure_telemetry(capture, monkeypatch, tmp_path, generation_status, analysis_status):
    from backend.services.studio import store

    monkeypatch.setattr(telem, "configured_connection_fields", lambda: {})
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    (tmp_path / "p1").mkdir()
    path = tmp_path / "p1" / "metadata" / "studio.json"
    state = {
        "schema_version": 2,
        "generation": {"status": "failed"},
        "analysis": {"status": "failed", "phase": "production"},
    }
    provider = _ProbeProvider()
    with telem.track_run():
        with pytest.raises(_StatusError) as caught:
            provider.call("fixture", fail=True)
        try:  # written while the failure is handled
            raise caught.value
        except _StatusError:
            store.write("p1", state)
        state = json.loads(path.read_text())
        for name in ("generation", "analysis"):
            assert state[name]["upstream_error_type"] == "rate_limited"
            assert state[name]["http_status"] == 429
            assert state[name]["failure_stage"] == "production"
            assert state[name]["billable_calls_before_failure"] == 0

        provider.call("fixture")
        state["generation"]["status"] = generation_status
        state["analysis"]["status"] = analysis_status
        store.write("p1", state)

    saved = json.loads(path.read_text())
    for name in ("generation", "analysis"):
        for key in ("http_status", "upstream_error_type", "failure_stage", "billable_calls_before_failure"):
            assert key not in saved[name]
        assert saved[name]["llm_calls"] == 2


def test_same_project_runs_persist_independent_usage(capture, monkeypatch, tmp_path):
    from backend.core import llm_usage
    from backend.services.studio import store

    monkeypatch.setattr(telem, "configured_connection_fields", lambda: {})
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    monkeypatch.setattr(llm_usage, "usage_path", lambda project_id: tmp_path / project_id / "metadata" / llm_usage.FILE)
    (tmp_path / "p1").mkdir()
    provider = _ProbeProvider()
    saved = []
    for run_id, calls, fail in (("run-1", 2, False), ("run-2", 1, True), ("run-3", 0, False)):
        with llm_usage.tracking("p1"), telem.track_run():
            assert telem.run_snapshot("p1").get("llm_calls", 0) == 0
            for _ in range(calls):
                response = provider.call("fixture")
                llm_usage.record(response.model, response.usage, prompt_chars=7, completion_chars=11)
            if fail:
                with pytest.raises(_StatusError):
                    provider.call("fixture", fail=True)
            status = "failed" if fail else "completed"
            store.write("p1", {
                "schema_version": 2,
                "generation": {"status": status},
                "analysis": {"status": status, "phase": "production", "run_id": run_id},
            })
            saved.append(json.loads((tmp_path / "p1" / "metadata" / "studio.json").read_text()))

    for state, expected in zip(saved, ((2, 22, 8), (2, 11, 4), (0, 0, 0))):
        for name in ("generation", "analysis"):
            record = state[name]
            assert tuple(record.get(key, 0) for key in ("llm_calls", "prompt_tokens", "completion_tokens")) == expected
    assert saved[1]["generation"]["billable_calls_before_failure"] == 1
    # Cost reporting remains project-wide, including previous attempts.
    assert llm_usage.summary("p1")["total"]["calls"] == 3
    assert llm_usage.summary("p1")["total"]["prompt_tokens"] == 33
    assert telem.run_snapshot("p1") == {"billable_calls_before_failure": 0}


@pytest.mark.parametrize("retry", [False, True])
def test_cross_stage_usage_persists_once_per_generation(capture, monkeypatch, tmp_path, retry):
    from backend.core.llm_manager import LLMManager
    from backend.services.studio import store

    monkeypatch.setattr(telem, "configured_connection_fields", lambda: {})
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    (tmp_path / "p1").mkdir()
    provider = _ProbeProvider()
    state = {
        "schema_version": 2,
        "generation": {"status": "screening", "created_at": "generation-1"},
        "analysis": {"status": "running", "phase": "screening", "run_id": "run-1", "instance": store.INSTANCE},
    }
    path = tmp_path / "p1" / "metadata" / "studio.json"
    with telem.track_run():
        provider.call("fixture")
        store.write("p1", state)
        store.write("p1", state)  # progress writes must not recount requests

    state = json.loads(path.read_text())
    state["generation"]["status"] = "production"
    state["analysis"]["phase"] = "production"
    with telem.track_run():
        if retry:
            manager = LLMManager.__new__(LLMManager)
            manager.settings = {"model_source": "user", "model_name": "qwen-plus"}
            manager.current_provider = provider
            manager._reload_if_settings_changed = lambda: None
            attempts = iter([True, False])
            manager.call = lambda *args, **kwargs: provider.call("fixture", fail=next(attempts))
            manager.call_with_retry("fixture")
        else:
            provider.call("fixture")
            provider.call("fixture")
        state["generation"]["status"] = "completed"
        state["analysis"]["status"] = "completed"
        store.write("p1", state)
        store.write("p1", json.loads(path.read_text()))

    for name in ("generation", "analysis"):
        record = json.loads(path.read_text())[name]
        assert record["llm_calls"] == 3
        assert record["prompt_tokens"] == (22 if retry else 33)
        assert record["completion_tokens"] == (8 if retry else 12)
        assert record["reasoning_tokens"] == 0
        assert record["retry_count"] == int(retry)

    # A zero-call render worker must preserve the retries used by final events.
    with telem.track_run():
        store.write("p1", json.loads(path.read_text()))
    final_state = json.loads(path.read_text())
    for name in ("generation", "analysis"):
        assert final_state[name]["llm_calls"] == 3
        assert final_state[name]["retry_count"] == int(retry)

    # A new generation carrying old fields must explicitly replace them with zero.
    state = json.loads(path.read_text())
    state["generation"]["created_at"] = "generation-2"
    state["analysis"]["run_id"] = "run-2"
    with telem.track_run():
        store.write("p1", state)
        store.write("p1", state)
    for name in ("generation", "analysis"):
        record = json.loads(path.read_text())[name]
        for key in ("llm_calls", "prompt_tokens", "completion_tokens", "reasoning_tokens", "retry_count", "degrade_count"):
            assert record[key] == 0


def test_usage_checkpoint_advances_only_after_successful_persistence(capture, monkeypatch, tmp_path):
    from backend.services.studio import store

    monkeypatch.setattr(telem, "configured_connection_fields", lambda: {})
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    (tmp_path / "p1").mkdir()
    state = {
        "schema_version": 2,
        "generation": {"status": "completed", "created_at": "generation-1"},
        "analysis": {"status": "completed", "phase": "production", "run_id": "run-1"},
    }
    path = tmp_path / "p1" / "metadata" / "studio.json"
    provider = _ProbeProvider()
    with telem.track_run():
        provider.call("fixture")
        store.write("p1", state)
        provider.call("fixture")
        with monkeypatch.context() as patch:
            def denied(*args):
                raise PermissionError("fixture")
            patch.setattr(store, "_replace_state", denied)
            with pytest.raises(PermissionError):
                store.write("p1", state)
        assert json.loads(path.read_text())["generation"]["llm_calls"] == 1
        store.write("p1", state)
        # Further requests within the same worker add only their new usage.
        provider.call("fixture")
        store.write("p1", state)
        store.write("p1", state)
    for name in ("generation", "analysis"):
        record = json.loads(path.read_text())[name]
        assert record["llm_calls"] == 3
        assert record["prompt_tokens"] == 33
        assert record["completion_tokens"] == 12


def test_opt_out_and_secret_payloads_are_not_posted(monkeypatch, tmp_path, capture):
    (tmp_path / "privacy.json").write_text('{"analytics":false}', encoding="utf-8")
    telem.request_finished(provider="openai", outcome="success", http_status=200)
    assert capture == []
    (tmp_path / "privacy.json").write_text('{"analytics":true}', encoding="utf-8")
    properties = telem.request_finished(provider="openai", model="gpt-4o-mini", outcome="success", http_status=200)
    assert properties["model"] == "gpt-4o-mini"
    leaked = dict(properties)
    leaked["authorization"] = "Bearer sk-secret"
    telem._post_event(schema.EVENT_LLM_REQUEST_FINISHED, leaked)
    assert all("sk-secret" not in json.dumps(row) for row in capture)


def test_asr_and_validation_hooks_are_allowlisted(capture):
    asr = telem.emit_asr_readiness_checked(
        provider="whisper_local", code="whisper_not_installed", has_subtitle=False, blocked=True)
    assert asr["provider"] == "whisper_local"
    assert asr["has_subtitle"] is False
    assert asr["blocked"] is True
    assert asr["code"] == "whisper_not_installed"
    validation = telem.emit_provider_validation_finished(
        provider="api88", base_url="https://88api.ai/v1/chat/completions",
        result="failed", error=_StatusError("invalid api key", 401))
    assert validation["provider"] == "api88"
    assert validation["base_url_host"] == "88api.ai"
    assert validation["result"] == "failed"
    assert validation["upstream_error_type"] == "invalid_key"
    events = {row["event"] for row in capture}
    assert events == {schema.EVENT_ASR_READINESS_CHECKED, schema.EVENT_PROVIDER_VALIDATION_FINISHED}
    assert all("timestamp" not in row for row in capture)
    assert "chat/completions" not in json.dumps(capture)


def test_failed_store_write_always_has_error_code_and_failure_stage(tmp_path, monkeypatch):
    from backend.services.studio import store
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    (tmp_path / "p1" / "metadata").mkdir(parents=True)
    store.write("p1", {
        "schema_version": 2,
        "generation": {"status": "failed"},
        "analysis": {"status": "failed", "phase": "ANALYZE"},
    })
    data = json.loads((tmp_path / "p1" / "metadata" / "studio.json").read_text(encoding="utf-8"))
    assert data["generation"]["error_code"] == "unexpected"
    assert data["generation"]["failure_stage"] in schema.FAILURE_STAGES
    assert data["analysis"]["error_code"] == "unexpected"
    assert data["analysis"]["failure_stage"] == "analyze"
    assert data["generation"]["billable_calls_before_failure"] == 0


def test_source_blocked_is_not_an_upstream_model_error():
    error = PipelineFailure("INGEST", "hint", code="source_blocked", http_status=403)
    assert studio_failure_context(error, "screening") == {"failure_stage": "ingest"}  # local carries no status


@pytest.mark.stdlib_only
def test_degrade_count_hook_is_integer_only_and_reaches_request_and_run(monkeypatch):
    monkeypatch.setattr(telem, "_post_event", lambda *args, **kwargs: None)
    with telem.track_run():
        assert telem.current_degrade_count() == 0
        assert telem.increment_degrade_count() == 1
        assert telem.increment_degrade_count() == 2
        props = telem.request_finished(
            provider="api88", model="gpt-4o-mini", base_url="https://88api.ai/v1",
            outcome="success", http_status=200, duration_ms=8,
        )
        snapshot = telem.run_snapshot()
    assert props["degrade_count"] == 2
    assert snapshot["degrade_count"] == 2
    dumped = json.dumps({"props": props, "snapshot": snapshot})
    assert "sk-" not in dumped
    assert "88api.ai/v1" not in dumped
    assert '"prompt"' not in dumped
    assert telem.current_degrade_count() == 0


def test_sentry_tags_are_allowlisted_strings():
    with telem.track_run():
        error = _StatusError("rate", 429)
        telem.request_finished(
            provider="api88", model="gpt-4o-mini", base_url="https://88api.ai/v1",
            outcome="error", http_status=429, error=error, failure_stage="analyze", duration_ms=9,
        )
        tags = telem.sentry_tags_for_error(error, "analyze")  # the same failure's record
    assert tags["provider"] == "api88"
    assert tags["upstream_error_type"] == "rate_limited"
    assert tags["failure_stage"] == "analyze"
    assert tags["http_status"] == "429"
    assert "sk-" not in json.dumps(tags)


def _analytics_dir(monkeypatch, tmp_path, *, key="phc_test", analytics=True):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    if key:
        monkeypatch.setenv("AUTOCLIP_POSTHOG_KEY", key)
    else:
        monkeypatch.delenv("AUTOCLIP_POSTHOG_KEY", raising=False)
    monkeypatch.delenv("VITE_PUBLIC_POSTHOG_KEY", raising=False)
    (tmp_path / "privacy.json").write_text(
        json.dumps({"analytics": analytics}), encoding="utf-8")
    (tmp_path / "analytics.json").write_text(
        '{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}', encoding="utf-8")


class _Quiet:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_model_call_does_not_wait_for_the_network(monkeypatch, tmp_path):
    import threading
    import time
    _analytics_dir(monkeypatch, tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def urlopen(req, timeout=0):
        entered.set()
        release.wait(5)
        return _Quiet()

    monkeypatch.setattr(telem.urllib.request, "urlopen", urlopen)
    try:
        started = time.monotonic()
        props = telem.request_finished(provider="openai", outcome="success", http_status=200, duration_ms=4)
        elapsed = time.monotonic() - started
        assert props["outcome"] == "success"
        assert elapsed < 0.3
    finally:
        release.set()
        assert telem.wait_until_idle()
    assert entered.is_set()


def test_model_call_does_not_queue_without_a_key_or_consent(monkeypatch, tmp_path):
    def urlopen(req, timeout=0):
        raise AssertionError("network")

    monkeypatch.setattr(telem.urllib.request, "urlopen", urlopen)
    _analytics_dir(monkeypatch, tmp_path, key="")
    telem.request_finished(provider="openai", outcome="success", http_status=200)
    assert telem.wait_until_idle()
    with telem._events_guard:
        assert len(telem._events) == 0
    _analytics_dir(monkeypatch, tmp_path, analytics=False)
    telem.request_finished(provider="openai", outcome="success", http_status=200)
    telem.emit_asr_readiness_checked(provider="whisper_local", code="whisper_not_installed", has_subtitle=False, blocked=True)
    assert telem.wait_until_idle()
    with telem._events_guard:
        assert len(telem._events) == 0


def test_llm_event_queue_drops_the_oldest_when_full(monkeypatch, tmp_path):
    import threading
    _analytics_dir(monkeypatch, tmp_path)
    entered = threading.Event()
    release = threading.Event()
    seen = []

    def urlopen(req, timeout=0):
        seen.append(json.loads(req.data.decode())["properties"]["duration_ms"])
        entered.set()
        release.wait(5)
        return _Quiet()

    monkeypatch.setattr(telem.urllib.request, "urlopen", urlopen)
    try:
        telem.request_finished(provider="openai", outcome="success", http_status=200, duration_ms=900_000)
        assert entered.wait(2)
        for i in range(telem._EVENT_LIMIT + 5):
            telem.request_finished(provider="openai", outcome="success", http_status=200, duration_ms=i)
        with telem._events_guard:
            queued = [item[1]["duration_ms"] for item in telem._events]
        assert len(queued) == telem._EVENT_LIMIT
        assert queued[0] == 5
        assert queued[-1] == telem._EVENT_LIMIT + 4
    finally:
        release.set()
        assert telem.wait_until_idle()
    assert 900_000 in seen
    assert 0 not in seen
    assert telem._EVENT_LIMIT + 4 in seen
