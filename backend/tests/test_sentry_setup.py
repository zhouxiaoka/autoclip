"""崩溃报告开关与 DSN 缺省行为。"""
import json
from pathlib import Path

import pytest

from backend.core import sentry_setup as sentry_setup


def test_crash_reports_default_on(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    assert sentry_setup.crash_reports_enabled() is True


def test_crash_reports_reads_privacy_file(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    (tmp_path / "privacy.json").write_text(json.dumps({"crash_reports": False}), encoding="utf-8")
    assert sentry_setup.crash_reports_enabled() is False


def test_write_privacy_roundtrip(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    sentry_setup.write_privacy(crash_reports=False)
    assert sentry_setup.crash_reports_enabled() is False
    sentry_setup.write_privacy(crash_reports=True)
    assert sentry_setup.crash_reports_enabled() is True


def test_init_sentry_noop_without_dsn(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert sentry_setup.init_sentry("desktop") is False


def test_before_send_rechecks_opt_out_without_restart(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    event = {"exception": {"values": [{"type": "ValueError", "value": "secret"}]}}
    assert sentry_setup.before_send(event, {}) is not None
    sentry_setup.write_privacy(crash_reports=False)
    assert sentry_setup.before_send(event, {}) is None
    sentry_setup.write_privacy(crash_reports=True)
    assert sentry_setup.before_send(event, {}) is not None


def test_before_send_splits_import_failures_without_keeping_the_message(monkeypatch, tmp_path):
    """配置类失败用固定 fingerprint；正文仍被抹掉，未预期故障不覆盖默认归组。"""
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    from backend.tasks.import_processing import (
        ImportMissingCredential,
        ImportProcessingError,
        ImportSubtitleUnavailable,
    )

    subtitle_message = "没有字幕可分析：/Users/private/talk.mp4 的口播内容"
    key_message = "缺少 API Key sk-live-secret"
    unexpected_message = "broker down /Users/private/input.mp4"

    subtitle = sentry_setup.before_send(
        {"exception": {"values": [{"type": "ImportSubtitleUnavailable", "value": subtitle_message}]}},
        {"exc_info": (ImportSubtitleUnavailable, ImportSubtitleUnavailable(subtitle_message), None)},
    )
    missing_key = sentry_setup.before_send(
        {"exception": {"values": [{"type": "ImportMissingCredential", "value": key_message}]}},
        {},
    )
    unexpected = sentry_setup.before_send(
        {"exception": {"values": [{"type": "ImportProcessingError", "value": unexpected_message}]}},
        {"exc_info": (ImportProcessingError, ImportProcessingError(unexpected_message), None)},
    )

    assert subtitle["fingerprint"] == ["import-processing", "missing-subtitle"]
    assert subtitle["tags"] == {"import_failure": "missing-subtitle"}
    assert subtitle["exception"]["values"][0]["type"] == "ImportSubtitleUnavailable"
    assert missing_key["fingerprint"] == ["import-processing", "missing-key"]
    assert missing_key["tags"] == {"import_failure": "missing-key"}
    assert missing_key["exception"]["values"][0]["type"] == "ImportMissingCredential"
    assert "fingerprint" not in unexpected
    assert unexpected["tags"] == {"import_failure": "unexpected"}
    assert unexpected["exception"]["values"][0]["type"] == "ImportProcessingError"

    blob = json.dumps({"subtitle": subtitle, "key": missing_key, "unexpected": unexpected}, ensure_ascii=False)
    assert "private" not in blob
    assert "sk-live-secret" not in blob
    assert "口播" not in blob
    assert subtitle["exception"]["values"][0]["value"] == "[message omitted for privacy]"


def test_before_send_keeps_code_locations_without_private_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    event = {"release": "autoclip-backend@1.3.1", "request": {"data": "private"},
             "breadcrumbs": ["private"], "extra": {"key": "private"}, "server_name": "private",
             "exception": {"values": [{"type": "ValueError", "value": "private",
                 "stacktrace": {"frames": [{"filename": "/Users/private/backend/service.py",
                     "lineno": 42, "function": "run", "vars": {"text": "private"},
                     "context_line": "private"}]}}]}}
    clean = sentry_setup.before_send(event, {})
    assert "private" not in json.dumps(clean)
    frame = clean["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame == {"filename": "service.py", "lineno": 42, "function": "run"}
    assert sentry_setup.before_send({"logentry": {"message": "private"}}, {}) is None


def test_corrupt_privacy_file_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    (tmp_path / "privacy.json").write_text("invalid json")
    assert sentry_setup.crash_reports_enabled() is False


def test_privacy_uses_web_data_directory(monkeypatch, tmp_path):
    from backend.core import path_utils
    monkeypatch.delenv("AUTOCLIP_APP_DIR", raising=False)
    monkeypatch.delenv("AUTOCLIP_DATA_DIR", raising=False)
    monkeypatch.setattr(path_utils, "get_data_directory", lambda: tmp_path)
    sentry_setup.write_privacy(crash_reports=False)
    assert (tmp_path / "privacy.json").is_file()
    assert sentry_setup.crash_reports_enabled() is False


def test_studio_tags_allowlisted_and_opt_out(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    event = {'exception': {'values': [{'type':'RuntimeError', 'value':'secret'}]},
             'tags': {'area':'studio', 'phase':'production', 'goal':'promo', 'analysis_mode':'visual',
                      'build_environment':'validation', 'telemetry_test':'true', 'url':'secret', 'runtime':'secret'}}
    clean = sentry_setup.before_send(event)
    assert clean['tags'] == {k:v for k,v in event['tags'].items() if k not in ('url','runtime')}
    assert 'secret' not in json.dumps(clean)
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    sentry_setup.write_privacy(crash_reports=False)
    assert sentry_setup.capture_studio_exception(RuntimeError('secret'), 'render') is None


def test_studio_capture_uses_isolated_scope_and_never_breaks_worker(monkeypatch, tmp_path):
    import sentry_sdk
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    captured=[]
    def capture(error):
        captured.append(dict(sentry_sdk.get_current_scope()._tags))
        raise RuntimeError('transport unavailable')
    monkeypatch.setattr(sentry_sdk, 'capture_exception', capture)
    assert sentry_setup.capture_studio_exception(ValueError('secret'), 'production', goal='promo') is None
    assert captured[0]['phase'] == 'production'
    assert sentry_sdk.get_current_scope()._tags.get('area') != 'studio'


def test_studio_failure_context_keeps_stage_and_http_status_without_messages():
    from backend.pipeline.failures import PipelineFailure
    from backend.services.studio.intelligence import VisionRequestError

    pipeline = PipelineFailure('SUBTITLE', 'private whisper path', code='whisper_not_installed')
    assert sentry_setup.studio_failure_context(pipeline, 'production') == {'failure_stage': 'subtitle'}

    vision = VisionRequestError('provider_error', 'private body', http_status=429)
    assert sentry_setup.studio_failure_context(vision, 'screening') == {
        'failure_stage': 'screening', 'http_status': 429}
    assert sentry_setup.studio_failure_context(vision, 'production') == {
        'failure_stage': 'vision', 'http_status': 429}

    timeout = sentry_setup.studio_failure_context(TimeoutError('private'), 'render')
    assert timeout == {'failure_stage': 'render'}
    assert 'private' not in json.dumps(timeout)


class _ProviderStatusError(Exception):
    """Mimics openai.APIStatusError: the HTTP status lives on `status_code`."""

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def test_studio_failure_context_reads_http_status_from_wrapped_provider_error():
    # RC156 Win QA #1: step1_outline raises `PipelineFailure("ANALYZE", ...) from last_error`.
    # The provider 500 is on __cause__, so the top-level-only lookup recorded http_status=None.
    from backend.pipeline.failures import PipelineFailure

    def wrapped(cause, **kw):
        try:
            raise cause
        except Exception as error:
            try:
                raise PipelineFailure('ANALYZE', 'private detail', code='provider_error', **kw) from error
            except PipelineFailure as failure:
                return failure

    context = sentry_setup.studio_failure_context(wrapped(_ProviderStatusError('private body', 500)), 'production')
    assert context == {'failure_stage': 'analyze', 'http_status': 500}
    assert 'private' not in json.dumps(context)

    # Two levels deep (provider error re-wrapped by a client layer), explicit and implicit chaining.
    def client_layer():
        try:
            raise _ProviderStatusError('private body', 502)
        except _ProviderStatusError:
            raise RuntimeError('client wrapper')  # implicit __context__
    try:
        client_layer()
    except RuntimeError as inner:
        failure = wrapped(inner)
    assert sentry_setup.studio_failure_context(failure, 'production') == {
        'failure_stage': 'analyze', 'http_status': 502}

    # The nearest valid status wins; non-HTTP and out-of-range values are ignored.
    outer = _ProviderStatusError('proxy', 503)
    outer.__cause__ = _ProviderStatusError('origin', 500)
    assert sentry_setup.studio_failure_context(outer, 'screening')['http_status'] == 503
    for bogus in (200, 302, 600, '500', True, None):
        assert 'http_status' not in sentry_setup.studio_failure_context(
            wrapped(_ProviderStatusError('x', bogus)), 'production')

    # An explicit status on the failure itself (timeline aggregation has no cause to walk).
    assert sentry_setup.studio_failure_context(
        PipelineFailure('ANALYZE', 'x', code='provider_error', http_status=429), 'production') == {
        'failure_stage': 'analyze', 'http_status': 429}


def test_studio_failure_context_without_status_in_chain_and_with_cycles():
    from backend.pipeline.failures import PipelineFailure

    try:
        try:
            raise ConnectionError('private host unreachable')
        except ConnectionError as error:
            raise PipelineFailure('ANALYZE', 'private', code='connection') from error
    except PipelineFailure as failure:
        assert sentry_setup.studio_failure_context(failure, 'production') == {'failure_stage': 'analyze'}

    # `raise ... from None` suppresses the implicit context, like traceback does.
    try:
        try:
            raise _ProviderStatusError('private', 500)
        except _ProviderStatusError:
            raise PipelineFailure('ANALYZE', 'private', code='provider_error') from None
    except PipelineFailure as failure:
        assert sentry_setup.studio_failure_context(failure, 'production') == {'failure_stage': 'analyze'}

    # A cyclic chain must terminate.
    a, b = RuntimeError('a'), RuntimeError('b')
    a.__cause__, b.__cause__ = b, a
    assert sentry_setup.studio_failure_context(a, 'render') == {'failure_stage': 'render'}


def test_studio_expected_pipeline_failure_keeps_code_and_warning(monkeypatch, tmp_path):
    from backend.pipeline.failures import PipelineFailure
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    error = PipelineFailure('ANALYZE', 'private key text', code='llm_not_configured')
    assert sentry_setup.studio_error_code(error) == 'llm_not_configured'
    clean = sentry_setup.before_send({'tags': {'area':'studio', 'phase':'production', 'error_code':'llm_not_configured'},
        'exception': {'values': [{'type':'PipelineFailure', 'value':str(error)}]}})
    assert clean['level'] == 'warning'
    assert clean['fingerprint'] == ['studio', 'production', 'llm_not_configured']
    assert 'private' not in json.dumps(clean)


def test_auto_frame_phase_survives_scrubbing_without_content(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    event = {'tags': {'area': 'studio', 'phase': 'auto_frame', 'error_code': 'unexpected', 'private': 'secret'},
             'exception': {'values': [{'type': 'RuntimeError', 'value': 'private video title'}]}}
    clean = sentry_setup.before_send(event)
    assert clean['tags']['phase'] == 'auto_frame'
    assert 'private' not in clean['tags']
    assert 'private video title' not in str(clean)


@pytest.mark.parametrize('kind,code,status', [
    ('AuthenticationError', 'authentication', 401),
    ('PermissionDeniedError', 'authentication', 403),
    ('RateLimitError', 'rate_limited', 429),
    ('InternalServerError', 'provider_error', 503),
    ('APITimeoutError', 'timeout', None),
    ('APIConnectionError', 'connection', None),
])
def test_text_sdk_failures_keep_provider_code_in_rewrite_and_render(monkeypatch, tmp_path, kind, code, status):
    import httpx
    import openai
    import sentry_sdk
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    request = httpx.Request('POST', 'https://synthetic.example/v1/chat/completions')
    cls = getattr(openai, kind)
    error = cls(request=request) if status is None else cls('private-provider-body synthetic-key',
        response=httpx.Response(status, request=request), body={'private': 'synthetic-key'})
    captured = []
    def capture(exc):
        captured.append(dict(sentry_sdk.get_current_scope()._tags))
    monkeypatch.setattr(sentry_sdk, 'capture_exception', capture)
    for phase in ('rewrite', 'render'):
        sentry_setup.capture_studio_exception(error, phase)
        assert captured[-1]['error_code'] == code
        assert captured[-1]['phase'] == phase
        clean = sentry_setup.before_send({'level': 'error', 'tags': captured[-1],
            'exception': {'values': [{'type': kind, 'value': str(error)}]}})
        assert 'private-provider-body' not in str(clean) and 'synthetic-key' not in str(clean)
        assert clean['level'] == ('warning' if code in ('authentication', 'rate_limited') else 'error')
    assert sentry_setup.studio_error_code(RuntimeError('unrelated programming defect')) == 'unexpected'
    assert sentry_setup.studio_error_code(PermissionError('private-local-file')) == 'unexpected'


def test_source_blocked_is_classified_and_never_sent(monkeypatch, tmp_path):
    # RC156 Win QA #9: a site refusing this network (Bilibili 412) is expected, not a crash.
    import sentry_sdk
    from backend.pipeline.failures import PipelineFailure
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    error = PipelineFailure('INGEST', 'hint', code='source_blocked', http_status=412)
    assert 'source_blocked' in sentry_setup.STUDIO_ERROR_CODES
    assert sentry_setup.studio_error_code(error) == 'source_blocked'

    monkeypatch.setattr(sentry_setup, '_initialized', True)
    sent = []
    monkeypatch.setattr(sentry_sdk, 'capture_exception', lambda e: sent.append(e) or 'event-id')
    assert sentry_setup.capture_studio_exception(error, 'screening') is None
    assert sent == []
    # Other studio failures are still captured.
    assert sentry_setup.capture_studio_exception(RuntimeError('x'), 'screening') == 'event-id'

    event = {'exception': {'values': [{'type': 'PipelineFailure', 'value': 'hint'}]},
             'tags': {'area': 'studio', 'phase': 'screening', 'error_code': 'source_blocked'}}
    assert sentry_setup.before_send(event) is None
