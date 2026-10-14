"""Unregistered events and missing required fields fail the tracking-plan catalog."""
import json

import pytest

from backend.core import event_catalog
from backend.core import llm_emit as telem
from backend.core import llm_telemetry as schema


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


def test_producers_are_all_registered():
    leftover = event_catalog.unregistered_producers()
    assert leftover == [], leftover


def test_emitted_line_a_events_match_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_POSTHOG_KEY", "phc_test")
    monkeypatch.setenv("AUTOCLIP_APP_VERSION", "1.5.8")
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
    assert bodies
    for row in bodies:
        errors = event_catalog.validate_event(row["event"], row["properties"], envelope=True)
        assert errors == [], (row["event"], errors)
        assert row["properties"]["app_version"] == "1.5.8"
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


def test_envelope_does_not_look_like_production_in_tests():
    props = event_catalog.envelope_properties()
    assert props["analytics_environment"] in {"development", "validation"}
    assert props["runtime"] == "python"


@pytest.mark.parametrize("event,props", [
    ("asr_readiness_checked", {"provider": "whisper_local", "blocked": True}),
    ("provider_validation_finished", {"provider": "openai", "success_rate_schema_version": 1}),
    ("studio_generation_finished", {"outcome": "failed"}),
])
def test_core_events_reject_incomplete_payloads(event, props):
    errors = event_catalog.validate_event(event, props)
    assert errors and "unregistered" not in errors[0]


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
