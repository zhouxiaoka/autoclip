"""#419 I538 extension (Dong): tests never inherit a Sentry DSN or a PostHog key - conftest `_no_ambient_telemetry`.

A child pytest runs telemetry_workload_419 (create_app + the QA, LLM and MCP PostHog events) with a fake DSN and a
fake PostHog key under every env name the code reads. With the fixture: 0 network calls, Sentry never initialized,
no PostHog worker started. The probe refuses every connection, so nothing leaves the machine either way.
The DSN and key here are fakes (example.invalid / phc_fake...)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAKE = {
    'SENTRY_DSN': 'https://public@example.invalid/1',
    'AUTOCLIP_POSTHOG_KEY': 'phc_fake_i538_autoclip',
    'VITE_PUBLIC_POSTHOG_KEY': 'phc_fake_i538_vite',
    'AUTOCLIP_POSTHOG_HOST': 'https://posthog.example.invalid',
}


def test_fake_dsn_and_posthog_key_never_reach_the_network(tmp_path):
    out = tmp_path / 'probe.json'
    env = {**os.environ, **FAKE, 'TELEMETRY_PROBE_OUT': str(out), 'PYTHONDONTWRITEBYTECODE': '1'}
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'no:randomly',
                          '-p', 'backend.tests.telemetry_leak_probe', 'backend/tests/telemetry_workload_419.py'],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert out.exists(), run.stdout[-2000:] + run.stderr[-2000:]
    probe = json.loads(out.read_text(encoding='utf-8'))
    assert probe['network_calls'] == [], probe            # no PostHog / Sentry request was even attempted
    assert probe['sentry_inits'] == 0, probe              # init_sentry never initialized the SDK
    assert probe['sentry_client_active'] is False, probe  # no Sentry client bound
    assert probe['posthog_worker_started'] is False, probe  # the MCP PostHog sender was never started
    assert run.returncode == 0, run.stdout[-2000:]     # incl. the workload's own check that no telemetry env name is set
