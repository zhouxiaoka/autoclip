"""Workload for test_r32_419_telemetry_isolation (#419): run only in a child pytest, never collected by a
normal run (no test_ prefix). Exercises every backend telemetry entry with whatever DSN / PostHog key the
environment carries: create_app (init_sentry), the QA event, the LLM event and the MCP event."""
import os
import time

TELEMETRY_ENV = ('SENTRY_DSN', 'VITE_PUBLIC_SENTRY_DSN', 'SENTRY_AUTH_TOKEN', 'AUTOCLIP_POSTHOG_KEY', 'AUTOCLIP_POSTHOG_HOST',
                 'VITE_PUBLIC_POSTHOG_KEY', 'VITE_PUBLIC_POSTHOG_HOST', 'POSTHOG_KEY', 'POSTHOG_HOST', 'POSTHOG_PERSONAL_API_KEY')


def test_no_telemetry_env_name_is_inherited():
    assert [name for name in TELEMETRY_ENV if name in os.environ] == []


def test_every_telemetry_entry(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))   # no privacy.json -> analytics allowed (product default)
    from backend.app_factory import create_app
    create_app(mode='web')
    from backend.services.studio.qa import telemetry as qa_telemetry
    qa_telemetry.emit_checked({'checks': [], 'duration_ms': 1}, 'probe')
    from backend.core import llm_emit
    llm_emit._post_event('llm_call_finished', {'outcome': 'success'})
    from backend.services import mcp_telemetry
    mcp_telemetry.record('probe_tool', 'probe-client', time.perf_counter(), ok=True, error_code='none')
    mcp_telemetry.flush(1)
