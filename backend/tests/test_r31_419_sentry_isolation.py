"""R31-pre #419: tests never inherit SENTRY_DSN, and init_sentry() state does not outlive a test.

create_app() calls init_sentry(), which sets the module-level `_initialized` for the whole
process. Before the conftest fixture `_no_ambient_sentry`, a DSN in the developer's shell
made any create_app test (test_422_beginner_hint, test_r7_d1_d7, test_r8_e1_e5) turn the SDK
on for real and leave `_initialized` True, so test_sentry_setup's no-DSN check failed in a
full run. The two tests below run in file order: the first initializes the way create_app
does, the second must still start clean.
"""
import os

from backend.core import sentry_setup


def test_a_init_like_create_app_sets_the_process_flag(monkeypatch, tmp_path):
    import sentry_sdk
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.invalid/0")
    monkeypatch.setattr(sentry_sdk, "init", lambda **options: None)  # never a real client
    assert sentry_setup.init_sentry("web") is True
    assert sentry_setup._initialized is True  # set by init_sentry itself, not by monkeypatch


def test_b_next_test_starts_without_a_dsn_or_an_initialized_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    assert "SENTRY_DSN" not in os.environ
    assert sentry_setup._initialized is False
    assert sentry_setup.init_sentry("desktop") is False
