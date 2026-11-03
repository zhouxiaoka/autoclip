"""Unified log redaction exit point (round 6 X2/X3/S1).

Every process entry (API app_factory, desktop_main, Celery, CLI local_runner)
calls ``install_log_redaction()``. It attaches one ``RedactingFilter`` to every
root handler (and to handlers added later via Celery's logging signals), and
pins chatty HTTP SDK loggers to WARNING. Per-call-site sanitizers stay as a
second layer; this filter is the primary defense.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

REDACTED = "[REDACTED]"
NOISY_SDK_LOGGERS = ("httpx", "httpcore", "openai")

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # URL userinfo: https://user:password@host → keep scheme, drop credentials
    (re.compile(r"(?i)(://)([^/?#@\s\"'<>]+@)"), r"\1" + REDACTED + "@"),
    # E3: every URL query value is redacted (names kept for diagnosis). No allow-list of
    # "secret" names: signed URLs use arbitrary parameter names (auth, __cld_token__, …).
    (re.compile(r"([?&][^=&#\s\"'<>?]+=)[^&#\s\"'<>]+"), r"\1" + REDACTED),
    # E3: the whole Authorization / Proxy-Authorization value, whatever the scheme
    # (Bearer, Basic, Key, Token, raw). Header form and JSON/dict form.
    # - quoted value (JSON / dict / quoted header) → whole quoted string, including
    # spaces and escaped quotes (Digest username=\"u\", response=\"…\").
    (re.compile(r"(?i)((?:proxy-)?authorization[\"']?\s*[:=]\s*)([\"'])(?:\\.|(?!\2)[^\\\r\n])*\2"), r"\1\2" + REDACTED + r"\2"),
    # - unquoted header value → everything to end of line (Digest k="v", k2="v2").
    (re.compile(r"(?i)((?:proxy-)?authorization[\"']?\s*[:=]\s*)(?![\s\"'])[^\r\n]+"), r"\1" + REDACTED),
    # Bare bearer / basic tokens outside a header
    (re.compile(r"(?i)\b(bearer|basic)\s+(?!\[REDACTED\])[A-Za-z0-9._~+/=\-]{6,}"), r"\1 " + REDACTED),
    # - quoted credential values may contain spaces: api_key="prefix x"
    (re.compile(r"(?i)([\"']?(?:x-goog-api-key|x-api-key|api[_-]?key|apikey|access[_-]?token|secret[_-]?key|password)[\"']?\s*[:=]\s*)([\"'])(?:\\.|(?!\2)[^\\\r\n])*\2"), r"\1\2" + REDACTED + r"\2"),
    # key=value / "key": "value" credential fields
    (re.compile(r"(?i)([\"']?(?:x-goog-api-key|x-api-key|api[_-]?key|apikey|access[_-]?token|secret[_-]?key|password)[\"']?\s*[:=]\s*[\"']?)(?!\[REDACTED\])[^\s\"',;}&]+"), r"\1" + REDACTED),
    # Pydantic truncates long inputs as input_value='sk-…TAIL'. The sk- pattern
    # stops at the ellipsis and would leave the key tail in logs and 422 bodies.
    (re.compile(r"input_value=.*?(?=,\s*input_type=)", re.DOTALL), "input_value=" + REDACTED),
    # Well-known key shapes
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), REDACTED),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{10,}"), REDACTED),
    (re.compile(r"\b(?:xai|gsk|fal|r8)_[A-Za-z0-9]{16,}"), REDACTED),
)


def redact_text(text: str) -> str:
    if not text:
        return text
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    """Rewrite msg/args/exc_text so no handler ever formats a raw credential."""

    _formatter = logging.Formatter()

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "_autoclip_redacted", False):
            return True
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - bad format args; fall back to raw msg
            message = str(record.msg)
        record.msg = redact_text(message)
        record.args = ()
        if record.exc_info and not record.exc_text:
            record.exc_text = self._formatter.formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        if record.stack_info:
            record.stack_info = redact_text(record.stack_info)
        record._autoclip_redacted = True
        return True


_FILTER = RedactingFilter()


def _attach(handlers: Iterable[logging.Handler]) -> None:
    for handler in handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(_FILTER)


def install_log_redaction(*extra_loggers: logging.Logger) -> RedactingFilter:
    """Idempotent. Call after logging handlers are configured."""
    for name in NOISY_SDK_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    root = logging.getLogger()
    _attach(root.handlers)
    if not any(isinstance(f, RedactingFilter) for f in root.filters):
        root.addFilter(_FILTER)  # records logged directly on root
    for lg in extra_loggers:
        _attach(lg.handlers)
    for name in ("celery", "celery.task", "uvicorn", "uvicorn.error", "uvicorn.access"):
        _attach(logging.getLogger(name).handlers)
    return _FILTER


def install_celery_log_redaction() -> None:
    """Hook Celery so handlers it (re)creates also get the filter."""
    install_log_redaction()
    try:
        from celery.signals import after_setup_logger, after_setup_task_logger
    except Exception:  # noqa: BLE001
        return

    def _hook(logger=None, **_kw):
        install_log_redaction(*( [logger] if logger is not None else []))

    after_setup_logger.connect(_hook, weak=False)
    after_setup_task_logger.connect(_hook, weak=False)
