"""Behavior tests that the suite never inherits a Sentry DSN or a PostHog key."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core import sentry_setup
"""pre #419 : tests never inherit SENTRY_DSN, and nothing init_sentry does outlives a test.
create_app calls init_sentry, which reads SENTRY_DSN from the environment, binds the sentry_sdk client
and sets the module-level `_initialized` for the whole process. Before the conftest fixture
`_no_ambient_sentry` (now `_no_ambient_telemetry`), a DSN in the developer's shell made the create_app tests (test_422_beginner_hint's
client fixture, test_r7_d1_d7, test_r8_e1_e5) turn the SDK on for real sending test events and the
later test_sentry_setup::test_init_sentry_noop_without_dsn failed in a full run.
The DSN used here is always a fake (example.invalid) and every client gets a counting fake transport."""

ROOT = Path(__file__).resolve().parents[2]
FAKE_DSN = 'https://public@example.invalid/1'
TARGET = 'backend/tests/test_sentry_setup.py::test_init_sentry_noop_without_dsn'
POLLUTERS = [
    'backend/tests/test_422_beginner_hint.py::test_overlong_key_says_key_too_long_in_chinese',
    'backend/tests/test_runtime_blockers.py',
]


@pytest.mark.parametrize('polluter', POLLUTERS, ids=['test_422_beginner_hint', 'test_runtime_blockers'])
def test_a_dsn_in_the_environment_never_reaches_sentry_from_tests(polluter, tmp_path):
    """Child pytest with a fake DSN in its environment: polluter first, then the no-DSN check."""
    out = tmp_path / 'probe.json'
    env = {**os.environ, 'SENTRY_DSN': FAKE_DSN, 'SENTRY_PROBE_OUT': str(out), 'PYTHONDONTWRITEBYTECODE': '1'}
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'no:randomly',
                          '-p', 'backend.tests.sentry_leak_probe', polluter, TARGET],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    probe = json.loads(out.read_text(encoding='utf-8'))
    assert probe['inits'] == 0, probe                      # Sentry was never initialized inside a test
    assert probe['client_bound_after'] == [], probe        # no sentry_sdk client left bound after any test
    assert probe['initialized_after'] == [], probe         # sentry_setup init state reset after every test
    assert probe['envelopes'] == 0, probe                  # nothing was sent
    assert run.returncode == 0, run.stdout[-2000:]         # the no-DSN check passes after the polluter


def test_b_a_test_that_sets_a_dsn_itself_does_not_initialize(monkeypatch, tmp_path):
    """pytest must not init Sentry, even when the test sets a release-shaped environment."""
    import sentry_sdk
    from backend.tests.sentry_leak_probe import CountingTransport
    real_init = sentry_sdk.init
    calls = []
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('SENTRY_DSN', FAKE_DSN)
    monkeypatch.setenv('AUTOCLIP_APP_VERSION', '1.5.7')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    monkeypatch.setattr(sentry_sdk, 'init', lambda **options: calls.append(options) or real_init(**{**options, 'transport': CountingTransport}))
    assert sentry_setup.init_sentry('web') is False
    assert sentry_setup.init_sentry('desktop') is False
    assert calls == []
    assert sentry_setup._initialized is False and not sentry_sdk.get_client().is_active()


def test_c_next_test_starts_without_a_dsn_or_an_initialized_flag(monkeypatch, tmp_path):
    import sentry_sdk
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    assert 'SENTRY_DSN' not in os.environ
    assert sentry_setup._initialized is False and not sentry_sdk.get_client().is_active()
    assert sentry_setup.init_sentry('desktop') is False
"""extension : tests never inherit a Sentry DSN or a PostHog key conftest `_no_ambient_telemetry`.
A child pytest runs telemetry_workload_419 (create_app + the QA, LLM and MCP PostHog events) with a fake DSN and a
fake PostHog key under every env name the code reads. With the fixture: 0 network calls, Sentry never initialized,
no PostHog worker started. The probe refuses every connection, so nothing leaves the machine either way.
The DSN and key here are fakes (example.invalid / phc_fake...)."""
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
