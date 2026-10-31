"""RL: independent workers must add usage and never erase earlier stage totals."""
import json

import pytest

from backend.core import llm_emit
from backend.core.llm_providers import LLMProvider, LLMResponse
from backend.services.studio import store


class UsageProvider(LLMProvider):
    def call(self, prompt, input_data=None, **kwargs):
        return LLMResponse(content="ok", model=self.model_name, finish_reason="stop",
                           usage={"prompt_tokens": 11, "completion_tokens": 4, "reasoning_tokens": 2})

    def test_connection(self):
        return True

    def get_available_models(self):
        return []


@pytest.mark.parametrize("render_calls", [0, 1])
@pytest.mark.parametrize("retry_stage", ["screening", "production", "both"])
def test_usage_accumulates_across_screening_production_render(render_calls, retry_stage, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "directory", lambda project_id: tmp_path / project_id)
    monkeypatch.setattr(llm_emit, "configured_connection_fields", lambda: {})
    (tmp_path / "rl-project").mkdir()
    path = tmp_path / "rl-project/metadata/studio.json"
    provider = UsageProvider(api_key="", model_name="gpt-4o-mini")
    state = {
        "schema_version": 2,
        "generation": {"status": "screening", "created_at": "rl-generation"},
        "analysis": {"status": "running", "phase": "screening", "run_id": "rl-run", "instance": store.INSTANCE},
    }
    calls_so_far = retries_so_far = 0
    retry_observations = []
    # Each track_run is a fresh worker, with the same persisted generation identity.
    screening_retries = 1 if retry_stage in ("screening", "both") else 0
    production_retries = 2 if retry_stage in ("production", "both") else 0
    for phase, calls, retries in (("screening", 1, screening_retries), ("production", 2, production_retries), ("render", render_calls, 0)):
        if path.exists():
            state = json.loads(path.read_text())
        state["generation"]["status"] = phase
        state["analysis"]["phase"] = phase
        calls_so_far += calls
        retries_so_far += retries
        with llm_emit.track_run():
            token = llm_emit.set_retry_count(retries)
            try:
                for _ in range(calls):
                    provider.call("synthetic fixture")
            finally:
                llm_emit.reset_retry_count(token)
            for _ in range(2):  # Repeated progress saves must not count a worker twice.
                store.write("rl-project", state)
                state = json.loads(path.read_text())
                for role in ("generation", "analysis"):
                    record = state[role]
                    assert record["llm_calls"] == calls_so_far, phase
                    assert record["prompt_tokens"] == calls_so_far * 11, phase
                    assert record["completion_tokens"] == calls_so_far * 4, phase
                    assert record["reasoning_tokens"] == calls_so_far * 2, phase
                    retry_observations.append((phase, role, record["retry_count"], retries_so_far))
    # Check after every worker ran, so a retry violation cannot hide render/zero-call coverage.
    for phase, role, actual, expected in retry_observations:
        assert actual == expected, (phase, role)
