"""Unregistered events and missing required fields fail the tracking-plan catalog."""
import json
import logging
from pathlib import Path

import pytest

from backend.core import event_catalog
from backend.core import llm_emit as telem
from backend.core import llm_telemetry as schema


@pytest.fixture
def unavailable_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_EVENT_CATALOG', str(tmp_path / 'missing.json'))
    event_catalog.load_catalog.cache_clear()
    yield
    event_catalog.load_catalog.cache_clear()


def test_platform_detection_never_loads_catalog(monkeypatch):
    def forbidden():
        raise AssertionError('platform detection must not load a catalog')
    monkeypatch.setattr(event_catalog, 'load_catalog', forbidden)
    monkeypatch.setenv('AUTOCLIP_NATIVE_OS', 'darwin')
    monkeypatch.setenv('AUTOCLIP_NATIVE_ARCH', 'arm64')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'validation')
    assert event_catalog.detect_os() == 'macos'
    assert event_catalog.detect_arch() == 'aarch64'
    assert event_catalog.envelope_properties()['analytics_environment'] == 'validation'


def test_runtime_constants_match_tracking_plan():
    common = json.loads((Path(__file__).resolve().parents[2] / 'docs/analytics/event_catalog.json').read_text())['common']
    assert list(event_catalog.CANONICAL_OS) == common['os']
    assert event_catalog.OS_ALIASES == common['os_aliases']
    assert list(event_catalog.CANONICAL_ARCH) == common['arch']
    assert list(event_catalog.ANALYTICS_ENVIRONMENTS) == common['analytics_environment']


def test_catalog_prefers_packaged_resource(tmp_path, monkeypatch):
    module = tmp_path / 'backend/core/event_catalog.py'
    module.parent.mkdir(parents=True)
    packaged = module.with_suffix('.json')
    packaged.write_text('{"events":{"packaged_event":{}}}')
    monkeypatch.setattr(event_catalog, '__file__', str(module))
    monkeypatch.delenv('AUTOCLIP_EVENT_CATALOG', raising=False)
    event_catalog.load_catalog.cache_clear()
    try:
        assert event_catalog.catalog_path() == packaged
        assert event_catalog.listed_events() == {'packaged_event'}
    finally:
        event_catalog.load_catalog.cache_clear()


def test_missing_catalog_does_not_break_envelope_or_validation(unavailable_catalog, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_NATIVE_OS', 'darwin')
    monkeypatch.setenv('AUTOCLIP_NATIVE_ARCH', 'arm64')
    assert event_catalog.load_catalog() == {}
    props = event_catalog.envelope_properties()
    assert props['os'] == 'macos' and props['arch'] == 'aarch64'
    assert props['runtime'] == 'python' and props['app_version']
    assert event_catalog.validate_event('not_registered', props, envelope=True) == []


def test_sentry_initializes_without_catalog(unavailable_catalog, monkeypatch, tmp_path, caplog):
    import sentry_sdk
    from backend.core import sentry_setup
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('SENTRY_DSN', 'https://public@example.invalid/0')
    # Missing catalog must not break the packaged desktop path. This process is pytest
    # inside a checkout, so the two refusals are stubbed; the real refusals are in
    # test_sentry_volume.
    monkeypatch.setenv('AUTOCLIP_APP_VERSION', '1.5.7')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    monkeypatch.setattr(sentry_setup, '_under_pytest', lambda: False)
    monkeypatch.setattr(sentry_setup, '_running_from_source_tree', lambda: False)
    monkeypatch.setattr(sentry_setup, '_initialized', False)
    monkeypatch.setattr(sentry_sdk, 'init', lambda **options: None)
    with caplog.at_level(logging.INFO):
        assert sentry_setup.init_sentry('desktop') is True
    assert 'Sentry 已启用' in caplog.text
    assert 'Sentry 初始化失败' not in caplog.text


@pytest.mark.parametrize('contents', ['{', '[]', '\udcff'])
def test_invalid_catalog_is_optional(tmp_path, monkeypatch, contents):
    path = tmp_path / 'catalog.json'
    path.write_bytes(contents.encode('utf-8', errors='surrogateescape'))
    monkeypatch.setenv('AUTOCLIP_EVENT_CATALOG', str(path))
    event_catalog.load_catalog.cache_clear()
    try:
        assert event_catalog.load_catalog() == {}
        assert event_catalog.validate_event('event', envelope=True) == []
    finally:
        event_catalog.load_catalog.cache_clear()


def test_unreadable_catalog_is_optional(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_EVENT_CATALOG', str(tmp_path / 'catalog.json'))
    def denied(*args, **kwargs):
        raise PermissionError('unreadable')
    monkeypatch.setattr(Path, 'read_text', denied)
    event_catalog.load_catalog.cache_clear()
    try:
        assert event_catalog.load_catalog() == {}
        assert event_catalog.validate_event('event', envelope=True) == []
    finally:
        event_catalog.load_catalog.cache_clear()


def test_catalog_lists_the_success_rate_funnel():
    names = event_catalog.listed_events()
    for name in (
        "app_installed", "app_opened", "app_updated",
        "setup_presented", "setup_action", "import_blocked",
        "provider_configuration_save_finished", "provider_connection_test_finished",
        "provider_validation_finished", "asr_readiness_checked",
        "studio_import_requested", "studio_import_accepted", "studio_import_request_failed",
        "studio_screen_finished", "llm_request_finished",
        "studio_confirm_requested", "studio_generation_finished", "studio_production_finished",
        "studio_export_finished", "studio_download_requested", "studio_download_saved",
        "studio_download_failed",
    ):
        assert name in names
    catalog = event_catalog.load_catalog()
    attribution = catalog["attribution"]
    assert "insufficient_quota" in attribution["user_caused_upstream_types"]
    assert "source_no_audio" in attribution["user_caused_error_codes"]
    assert "source_blocked" in attribution["environment_error_codes"]


def test_unregistered_event_and_missing_fields_fail():
    errors = event_catalog.validate_event("not_a_real_event", {})
    assert errors == ["unregistered event: not_a_real_event"]
    missing = event_catalog.validate_event("llm_request_finished", {"provider": "openai"})
    assert any("missing required fields" in item for item in missing)
    assert "kind" in missing[0] and "outcome" in missing[0]


def test_valid_llm_request_and_privacy_rules():
    ok = {
        "success_rate_schema_version": 1,
        "provider": "openai",
        "kind": "text",
        "outcome": "success",
        "duration_ms": 12,
    }
    assert event_catalog.validate_event("llm_request_finished", ok) == []
    failed = {
        **ok, "outcome": "error", "kind": "vision",
    }
    assert any("missing required fields" in item for item in event_catalog.validate_event(
        "llm_request_finished", failed))
    failed["upstream_error_type"] = "insufficient_quota"
    failed["failure_stage"] = "analyze"
    assert event_catalog.validate_event("llm_request_finished", failed) == []
    leaked = {**ok, "api_key": "x", "note": "sk-secret", "href": "https://api.openai.com/v1/chat"}
    privacy = event_catalog.validate_event("llm_request_finished", leaked)
    assert any("forbidden property" in item for item in privacy)
    assert any("secret" in item for item in privacy)
    assert any("full URL" in item for item in privacy)
    counted = {**failed, "prompt_tokens": 12, "completion_tokens": 3}
    assert event_catalog.validate_event("llm_request_finished", counted) == []
    generation = {
        "schema_version": 2, "runtime": "python", "app_version": "1.5.8",
        "os": "linux", "arch": "x86_64", "analytics_environment": "validation",
        "studio_schema_version": 2, "outcome": "success", "prompt_tokens": 12,
        "completion_tokens": 3, "llm_calls": 1, "http_status": 200,
    }
    assert event_catalog.validate_event("studio_generation_finished", generation, envelope=True) == []
    assert any("secret" in item for item in event_catalog.validate_event(
        "llm_request_finished", {**ok, "note": "sk-secret"}))


def test_producers_are_all_registered():
    leftover = event_catalog.unregistered_producers()
    assert leftover == [], leftover


def test_emitted_line_a_events_match_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_POSTHOG_KEY", "phc_test")
    monkeypatch.setenv("AUTOCLIP_APP_VERSION", "1.5.7")
    monkeypatch.setenv("AUTOCLIP_BUILD_ENVIRONMENT", "validation")
    monkeypatch.delenv("VITE_PUBLIC_POSTHOG_KEY", raising=False)
    (tmp_path / "privacy.json").write_text('{"analytics":true}', encoding="utf-8")
    (tmp_path / "analytics.json").write_text(
        '{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}', encoding="utf-8")
    bodies = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def urlopen(req, timeout=0):
        bodies.append(json.loads(req.data.decode()))
        return Resp()

    monkeypatch.setattr(telem.urllib.request, "urlopen", urlopen)
    telem.request_finished(provider="openai", kind="text", outcome="success", duration_ms=9)
    telem.request_finished(
        provider="deepseek", kind="text", outcome="error", duration_ms=3,
        upstream_error_type="insufficient_quota", failure_stage="analyze", http_status=402)
    telem.emit_asr_readiness_checked(
        provider="whisper_local", code="whisper_not_installed", has_subtitle=False, blocked=True)
    telem.emit_provider_validation_finished(provider="api88", result="skipped")
    assert telem.wait_until_idle()
    assert bodies
    for row in bodies:
        errors = event_catalog.validate_event(row["event"], row["properties"], envelope=True)
        assert errors == [], (row["event"], errors)
        assert row["properties"]["app_version"] == "1.5.7"
        assert row["properties"]["os"] in {"macos", "windows", "linux", "unknown"}
        assert row["properties"]["analytics_environment"] == "validation"
        assert row["distinct_id"] == "018f6b2a-7c3d-7b2a-8c11-111111111111"
    assert {row["event"] for row in bodies} == {
        schema.EVENT_LLM_REQUEST_FINISHED,
        schema.EVENT_ASR_READINESS_CHECKED,
        schema.EVENT_PROVIDER_VALIDATION_FINISHED,
    }


def test_os_aliases_normalize_to_canonical_names():
    assert event_catalog.normalize_os("darwin") == "macos"
    assert event_catalog.normalize_os("win32") == "windows"
    assert event_catalog.normalize_os("linux") == "linux"
    assert event_catalog.normalize_os("beos") is None


@pytest.mark.parametrize('machine,expected', [('arm64', 'aarch64'), ('aarch64', 'aarch64'),
    ('AMD64', 'x86_64'), ('x86_64', 'x86_64'), ('x64', 'x86_64'), ('private path', 'unknown')])
def test_envelope_normalizes_architecture(monkeypatch, machine, expected):
    import platform
    monkeypatch.delenv('AUTOCLIP_NATIVE_ARCH', raising=False)
    monkeypatch.setattr(platform, 'machine', lambda: machine)
    assert event_catalog.envelope_properties()['arch'] == expected


def test_native_shell_facts_override_python_runtime(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_NATIVE_ARCH', 'ARM64')
    monkeypatch.setenv('AUTOCLIP_NATIVE_OS', 'darwin')
    props = event_catalog.envelope_properties()
    assert props['arch'] == 'aarch64'
    assert props['os'] == 'macos'
    assert any('canonical arch' in error for error in event_catalog.validate_event(
        'app_opened', {**props, 'arch': 'arm64'}, envelope=True))


def test_envelope_does_not_look_like_production_in_tests():
    props = event_catalog.envelope_properties()
    assert props["analytics_environment"] in {"development", "validation"}
    assert props["runtime"] == "python"


@pytest.mark.parametrize("event,props", [
    ("asr_readiness_checked", {"provider": "whisper_local", "blocked": True}),
    ("provider_validation_finished", {"provider": "openai", "success_rate_schema_version": 1}),
    ("studio_generation_finished", {"outcome": "error"}),
])
def test_core_events_reject_incomplete_payloads(event, props):
    errors = event_catalog.validate_event(event, props)
    assert errors and "unregistered" not in errors[0]


def test_studio_error_outcome_requires_failure_fields():
    missing = event_catalog.validate_event("studio_generation_finished", {"outcome": "error"})
    assert any("error_code" in item and "failure_stage" in item for item in missing)
    assert event_catalog.validate_event("studio_generation_finished", {
        "outcome": "error", "error_code": "provider_error", "failure_stage": "analyze",
    }) == []
    assert event_catalog.validate_event("studio_screen_finished", {
        "outcome": "error", "error_code": "source_no_audio", "failure_stage": "ingest",
    }) == []
    stale = event_catalog.validate_event("studio_generation_finished", {"outcome": "failed"})
    assert any("not in studio_outcome" in item for item in stale)


def test_feedback_submitted_may_include_user_text_and_contact():
    row = event_catalog.load_catalog()["events"]["feedback_submitted"]
    assert row["kind"] == "user_submitted"
    assert set(row["allow"]) == {"text", "contact"}
    assert event_catalog.validate_event("feedback_submitted", {
        "text": "进度停住了",
        "contact": "person@example.com",
    }) == []


def test_auto_events_reject_user_content():
    leaked = event_catalog.validate_event("llm_request_finished", {
        "success_rate_schema_version": 1,
        "provider": "openai",
        "kind": "text",
        "outcome": "success",
        "duration_ms": 12,
        "text": "用户口播",
        "contact": "person@example.com",
    })
    assert any("user content" in item for item in leaked)


@pytest.mark.parametrize("code", ["llm_auth_invalid", "llm_not_configured"])
def test_studio_auth_and_configuration_codes_validate(code):
    assert code in event_catalog.load_catalog()["attribution"]["user_caused_error_codes"]
    assert event_catalog.validate_event("studio_generation_finished", {
        "outcome": "error", "error_code": code, "failure_stage": "analyze",
    }) == []
