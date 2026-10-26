"""One error-code table: copies and sentences must match the catalog."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core import failure_codes
from backend.core.event_catalog import load_catalog
from backend.core.sentry_setup import STUDIO_ERROR_CODES
from backend.core.upstream_errors import HINT_KEYS, UPSTREAM_ERROR_TYPES, UpstreamErrorType
from backend.pipeline.failures import MODEL_CALL_MESSAGES, PipelineFailure

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "analytics" / "event_catalog.json"
PACKAGED = ROOT / "backend" / "core" / "event_catalog.json"
LOCALES = ROOT / "frontend" / "src" / "i18n" / "locales"
LANGS = ("zh", "en", "ja", "ko", "es", "pt", "ru", "fr")
RETIRED = (
    "密钥无效或已过期，请到「设置 → 模型」检查密钥后重试。",
    "API Key 无效或已过期，请检查后重试",
    "账户余额或令牌额度不足，请充值或更换令牌后再试。",
    "当前令牌没有该模型权限或分组不对，请到服务商控制台勾选模型或更换分组。",
)
HISTORICAL_SENTRY = {
    "validation", "missing_resource", "unexpected", "timeout", "connection", "authentication",
    "rate_limited", "provider_error", "invalid_response", "output_truncated", "refused",
    "llm_not_configured", "llm_auth_invalid", "whisper_not_installed", "whisper_install_failed",
    "transcription_empty", "subtitle_setup", "timeline_empty", "source_blocked", "file_locked", "source_not_found", "source_too_short",
    "no_complete_version",
    "source_no_audio", "source_unreadable", "service_restarted", "frame_extract_failed",
    "store_lock_timeout", "network", "disk", "corrupt",
}
def _catalogs():
    return json.loads(PACKAGED.read_text(encoding="utf-8")), json.loads(DOCS.read_text(encoding="utf-8"))


@pytest.mark.stdlib_only
def test_codes_come_from_both_catalogs():
    packaged, docs = _catalogs()
    assert packaged == docs
    assert failure_codes.studio_codes() == set(packaged["enums"]["studio_error_code"]) == set(load_catalog()["enums"]["studio_error_code"])
    from backend.core.connection_test_codes import CONNECTION_TEST_ERROR_CODES
    assert set(CONNECTION_TEST_ERROR_CODES) == set(packaged["enums"]["connection_test_error_code"])
    assert failure_codes.download_codes() == set(packaged["enums"]["download_error_code"]) == {"disk", "corrupt"}
    assert failure_codes.sentry_codes() == HISTORICAL_SENTRY == set(STUDIO_ERROR_CODES)
    assert failure_codes.stored_codes() == HISTORICAL_SENTRY | {"multiple"}
    assert "unknown" not in failure_codes.sentry_codes()
    assert "disk" not in failure_codes.studio_codes()
    with pytest.raises(ValueError):
        failure_codes.require_code("not_a_code")
    assert failure_codes.require_code("http_429") == "http_429"
    assert failure_codes.require_code("disk") == "disk"


@pytest.mark.stdlib_only
def test_missing_catalog_override_keeps_packaged_codes(monkeypatch, tmp_path):
    from backend.core.event_catalog import reload_catalog
    monkeypatch.setenv("AUTOCLIP_EVENT_CATALOG", str(tmp_path / "missing-catalog.json"))
    reload_catalog()
    try:
        assert "unexpected" in failure_codes.sentry_codes()
        assert failure_codes.download_codes() == {"disk", "corrupt"}
    finally:
        monkeypatch.delenv("AUTOCLIP_EVENT_CATALOG", raising=False)
        reload_catalog()


@pytest.mark.stdlib_only
def test_frontend_and_ingest_patterns_match_the_catalog():
    pattern = failure_codes.error_code_pattern()
    studio = failure_codes.studio_codes()
    for code in studio:
        assert pattern.fullmatch(code), code
    assert pattern.fullmatch("http_429") and pattern.fullmatch("http_500")
    for rejected in ("disk", "corrupt", "not_a_code", "cancelled", "user_cancelled"):
        assert pattern.fullmatch(rejected) is None
    import importlib.util
    spec = importlib.util.spec_from_file_location("ingest_app_feedback", ROOT / "scripts/ingest_app_feedback.py")
    ingest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ingest)
    for code in studio | {"http_429", "source_unreadable"}:
        assert ingest.ERROR_CODE_RE.fullmatch(code)
    assert ingest.ERROR_CODE_RE.fullmatch("disk") is None
    workflow = (ROOT / "frontend/src/analytics/workflow.ts").read_text(encoding="utf-8")
    draft = (ROOT / "frontend/src/analytics/feedbackDraft.ts").read_text(encoding="utf-8")
    assert "const ERROR_CODE = /^" not in workflow and "const ERROR_CODE = /^" not in draft
    assert "failureCodes" in workflow and "failureCodes" in draft


@pytest.mark.stdlib_only
def test_one_sentence_per_code_and_no_retired_copies():
    table = failure_codes.messages()
    required = failure_codes.studio_codes() | failure_codes.download_codes() | UPSTREAM_ERROR_TYPES
    assert required <= set(table)
    assert set(table) <= required
    assert "更换令牌" in table["insufficient_quota"]
    assert "服务商控制台" in table["permission_denied"] and "勾选模型" in table["permission_denied"]
    for code in ("missing_resource", "disk", "corrupt", "frame_extract_failed", "source_unreadable"):
        assert "模型" not in table[code] and "设置" not in table[code], code
    assert table["invalid_key"] == table["llm_auth_invalid"] == table["authentication"]
    assert table["unexpected"] == table["unknown"]
    assert "模型" not in table["unexpected"] and "设置" not in table["unexpected"] and "配置" not in table["unexpected"]
    assert "模型" in table["provider_error"]
    assert HINT_KEYS[UpstreamErrorType.INVALID_KEY] == table["invalid_key"]
    assert HINT_KEYS[UpstreamErrorType.INSUFFICIENT_QUOTA] == table["insufficient_quota"]
    assert HINT_KEYS[UpstreamErrorType.PERMISSION_DENIED] == table["permission_denied"]
    assert MODEL_CALL_MESSAGES["llm_auth_invalid"] == table["llm_auth_invalid"]
    assert MODEL_CALL_MESSAGES["timeout"] == HINT_KEYS[UpstreamErrorType.TIMEOUT]
    catalogs = {lang: json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8")) for lang in LANGS}
    for sentence in set(table.values()):
        for lang, catalog in catalogs.items():
            assert sentence in catalog, f"{lang} missing {sentence}"
    for path in (ROOT / "backend").rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for retired in RETIRED:
            assert retired not in text, path
    for pattern in ("frontend/src/**/*.ts", "frontend/src/**/*.tsx", "scripts/**/*.py"):
        for path in ROOT.glob(pattern):
            text = path.read_text(encoding="utf-8")
            for retired in RETIRED:
                assert retired not in text, path
    handwritten = "whisper_install_failed|transcription_empty"
    for path in ROOT.glob("frontend/src/**/*.ts"):
        assert handwritten not in path.read_text(encoding="utf-8"), path
    assert handwritten not in (ROOT / "scripts/ingest_app_feedback.py").read_text(encoding="utf-8")


@pytest.mark.stdlib_only
def test_provider_text_stays_out_of_the_user_message(caplog):
    raw = "Error code: 401 - {'error': {'message': 'Incorrect API key sk-secret'}}"
    visible = failure_codes.user_visible_error(RuntimeError(raw))
    assert visible == failure_codes.sentence("unexpected")
    assert "sk-secret" not in visible and "Incorrect API key" not in visible
    assert raw in caplog.text
    authored = "视觉模型不可用，请配置后重新确认；原素材已保留"
    assert failure_codes.user_visible_error(ValueError(authored)) == failure_codes.sentence("validation")
    assert "视觉模型不可用" not in failure_codes.user_visible_error(ValueError(authored))
    kept = failure_codes.user_visible_error(failure_codes.UserFacingError(authored))
    assert kept.startswith("视觉模型不可用")
    chinese = failure_codes.user_visible_error(RuntimeError("服务商返回：账户余额不足，请到控制台充值后再试"))
    assert chinese == failure_codes.sentence("unexpected")
    assert "控制台" not in chinese and "余额" not in chinese
    import errno, subprocess
    missing = failure_codes.user_visible_error(FileNotFoundError("/tmp/missing.mp4"))
    full = failure_codes.user_visible_error(OSError(errno.ENOSPC, "No space left on device"))
    render = failure_codes.user_visible_error(subprocess.CalledProcessError(1, ["ffmpeg"]))
    assert missing == failure_codes.sentence("missing_resource")
    assert full == failure_codes.sentence("disk")
    assert render == failure_codes.sentence("frame_extract_failed")
    for text in (missing, full, render):
        assert "模型" not in text and "设置" not in text
    failure = PipelineFailure("ANALYZE", failure_codes.sentence("llm_auth_invalid"), code="llm_auth_invalid")
    assert failure_codes.user_visible_error(failure) == failure_codes.sentence("llm_auth_invalid")
    catalog = failure_codes.sentence("invalid_response")
    assert failure_codes.user_visible_error(ValueError(catalog)) == catalog
    from backend.core.failure_attribution import AttributedError, FailureAttribution, attributed
    class _Safe(AttributedError, RuntimeError):
        pass
    wrapped = _Safe("redacted")
    attributed(
        wrapped,
        FailureAttribution._make("request", http_status=503, upstream_error_type="upstream_unavailable"),
        http_status=503,
        error_code="provider_error",
    )
    assert failure_codes.user_visible_error(wrapped) == failure_codes.sentence("upstream_unavailable")
    assert "无法识别" not in failure_codes.user_visible_error(wrapped)
    unknown = _Safe("redacted")
    attributed(unknown, FailureAttribution._make("request", http_status=500, upstream_error_type="unknown"),
               http_status=500, error_code="provider_error")
    assert failure_codes.user_visible_error(unknown) == failure_codes.sentence("provider_error")


@pytest.mark.stdlib_only
def test_model_dumps_and_internal_value_errors_stay_out_of_the_ui():
    import json
    from backend.services.studio.planning import Recommendation
    try:
        Recommendation.model_validate({"content_type": "nope", "goal": "highlight", "reason": "画面说明", "confidence": 0.5})
    except Exception as caught:
        dump = caught
    else:
        raise AssertionError("expected a validation error")
    visible = failure_codes.user_visible_error(dump)
    assert visible == failure_codes.sentence("validation")
    assert "nope" not in visible and "画面说明" not in visible and str(dump) not in visible
    try:
        json.loads("{")
    except json.JSONDecodeError as caught:
        raw = caught
    visible = failure_codes.user_visible_error(raw)
    assert visible == failure_codes.sentence("validation")
    assert str(raw) not in visible and "Expecting" not in visible
    english = ValueError("Expected a JSON object")
    visible = failure_codes.user_visible_error(english)
    assert visible == failure_codes.sentence("validation")
    assert "Expected a JSON object" not in visible and "JSON" not in visible


@pytest.mark.stdlib_only
def test_dashscope_failed_text_is_not_the_image_error(caplog):
    from backend.core.image_providers import ImageError, _dashscope_bytes
    secret = "FAILED InvalidParameter sk-cover-secret ref_img not support"
    with pytest.raises(ImageError) as caught:
        _dashscope_bytes({"output": {"task_status": "FAILED", "message": secret}}, session=None)
    assert str(caught.value) == failure_codes.sentence("unexpected")
    assert "sk-cover-secret" not in str(caught.value)
    assert caught.value.unsupported_edit is True
    assert "omitted from UI" in caplog.text and "ref_img not support" in caplog.text

import re
from pathlib import Path

from backend.core import event_catalog, sentry_setup
from backend.services.studio import planning
"""follow-up: new codes are classified consistently in the catalog, success-rate SQL
and analytics docs. frame_extract_failed is a counted (product) failure; the subtitle-route /
fallback codes are degrade reasons on successful runs, never failures."""
DEGRADES = {
    planning.VISION_FALLBACK_CODE, planning.VISION_INVALID_FALLBACK_CODE,
    planning.FRAME_EXTRACT_FALLBACK_CODE, planning.SOURCE_TOO_LONG_CODE,
}


def _excluded_codes(sql):
    """v4 (#416): exclusion lists are the `ec IN (...)` / `ue IN (...)` blocks of user_hard / user_x."""
    return [set(re.findall(r"'(\w+)'", block)) for block in
            re.findall(r"\b(?:ec|ue) IN\s*\(([^)]*)\)", sql)]


def test_catalog_classifies_new_codes():
    for path in ('docs/analytics/event_catalog.json', 'backend/core/event_catalog.json'):
        import json
        catalog = json.loads((ROOT / path).read_text(encoding='utf-8'))
        attr = catalog['attribution']
        assert 'frame_extract_failed' in attr['product_error_codes'], path
        assert 'frame_extract_failed' not in attr['user_caused_error_codes'] + attr['environment_error_codes']
        assert set(catalog['enums']['degrade_reason']) == DEGRADES, path
        assert not DEGRADES & set(attr['user_caused_error_codes'] + attr['environment_error_codes'] + attr['product_error_codes'])
    assert set(event_catalog.load_catalog()['attribution']['product_error_codes']) <= sentry_setup.STUDIO_ERROR_CODES


def test_success_rate_sql_counts_frame_extract_failed_and_reports_degrades():
    sql = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
    blocks = _excluded_codes(sql)
    assert len(blocks) >= 2
    for codes in blocks:
        assert 'frame_extract_failed' not in codes  # a failure that counts against success
        assert not DEGRADES & codes  # degrades are not failure codes
    assert 'frame_extract_failed' in sql  # documented explicitly as counted
    degrade_query = sql[sql.index('degrade_reason'):]
    for code in DEGRADES:
        assert f"'{code}'" in degrade_query, code


def test_empty_model_body_is_a_usable_sentence_and_bare_error_is_replaced():
    """api88 and other gateways can return a 200 with no choices. That is not bad user input,
    and a failure card must not show only 「错误」."""
    from backend.core import sentry_setup
    for text in ("empty completion", "invalid completion", "completion was not an object"):
        error = ValueError(text)
        assert sentry_setup.studio_error_code(error) == "invalid_response"
        visible = failure_codes.user_visible_error(error)
        assert visible == failure_codes.sentence("invalid_response")
        assert visible != "错误"
    assert sentry_setup.studio_error_code(IndexError("choices")) == "invalid_response"
    bare = failure_codes.user_visible_error(RuntimeError("错误"))
    assert bare == failure_codes.sentence("unexpected") and bare != "错误"
    authored = failure_codes.user_visible_error(failure_codes.UserFacingError("错误"))
    assert authored == failure_codes.sentence("validation") and authored != "错误"


def test_docs_list_new_codes():
    for doc in ('TRACKING_PLAN.md', 'STUDIO_MONITORING.md', 'LLM_TELEMETRY.md'):
        text = (ROOT / 'docs/analytics' / doc).read_text(encoding='utf-8')
        for code in ('frame_extract_failed', planning.FRAME_EXTRACT_FALLBACK_CODE, planning.SOURCE_TOO_LONG_CODE):
            assert code in text, (doc, code)
