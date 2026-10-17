"""R27 #415: THE failure-attribution rule (Dong R26 design, 157/415-attribution-design.md).

One classifier, one write-once snapshot, one reader:

- ``classify_failure(error)``: walks the error chain from the outermost link inward; the first DECISIVE
  link wins. Local errors first (store lock timeout, subprocess, a pipeline/vision failure with a
  local code), then model errors (provider API errors, pipeline/vision failures with a model code),
  and only then the failed request's record. Never by type-name strings.
- ``FailureAttribution``: the snapshot. ``local`` never carries ``http_status``/``upstream_error_type``
  (validated on construction: ``ValueError``). Identity is a provider/config_source pair or nothing.
- ``write_attribution(record, snapshot)``: replaces the attribution group WHOLE (no merging).
- ``read_attribution(record)``: the cleaned projection every reader uses; legacy half records are
  cleaned at read time only, never written back.

This module imports nothing from llm_emit/sentry_setup (no cycles): both import it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator

SOURCE_REQUEST = "request"
SOURCE_PHASE = "phase"
SOURCE_LOCAL = "local"
SOURCES = frozenset({SOURCE_REQUEST, SOURCE_PHASE, SOURCE_LOCAL})

IDENTITY_FIELDS = ("provider", "config_source", "model", "base_url_host")
UPSTREAM_FIELDS = ("http_status", "upstream_error_type")
FAILURE_FIELDS = (*UPSTREAM_FIELDS, "failure_stage")
ATTRIBUTION_FIELDS = (*IDENTITY_FIELDS, *FAILURE_FIELDS)
SNAPSHOT_FIELDS = (*ATTRIBUTION_FIELDS, "attribution_source")
FAILED_STATUSES = ("failed", "partial")

# Codes a failed model call carries (PipelineFailure / VisionRequestError). Everything else is local.
MODEL_ERROR_CODES = frozenset({"timeout", "connection", "authentication", "rate_limited", "provider_error",
                               "invalid_response", "output_truncated", "refused", "llm_auth_invalid"})
# Codes that are decisively LOCAL (never a provider failure, whatever they wrap). Other non-model
# codes (``unexpected``, ``validation``...) are not decisive: the chain below them decides.
LOCAL_ERROR_CODES = frozenset({"source_blocked", "source_too_short", "source_no_audio", "source_unreadable",
                               "service_restarted", "whisper_not_installed", "whisper_install_failed",
                               "transcription_empty", "subtitle_setup", "timeline_empty", "store_lock_timeout",
                               "frame_extract_failed", "llm_not_configured", "missing_resource"})
_RECORD_ATTR = "_autoclip_request_record"


class FailureKind(str, Enum):
    LOCAL = "local"
    MODEL = "model"
    NONE = "none"


@dataclass(frozen=True)
class Classification:
    kind: FailureKind
    decisive: BaseException | None = None
    record: Any = None  # the failed request's record; only ever set for MODEL


def chain(error: BaseException | None) -> Iterator[BaseException]:
    """The error, then BOTH its ``__cause__`` and ``__context__`` (breadth-first, cycle-safe; R26 #398)."""
    seen: set[int] = set()
    queue = [error]
    while queue:
        current = queue.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        queue.extend((current.__cause__, current.__context__))


def record_of(error: BaseException | None):
    """The failed request's record travelling with ``error`` or anywhere up its chain; else None."""
    for link in chain(error):
        record = getattr(link, _RECORD_ATTR, None)
        if record is not None and callable(getattr(record, "attribution", None)):
            return record
    return None


def _local_types() -> tuple[type, ...]:
    import subprocess
    from backend.core.file_lock import LockTimeout
    return (LockTimeout, subprocess.TimeoutExpired, subprocess.CalledProcessError)


def _coded_types() -> tuple[type, ...]:
    out: list[type] = []
    try:
        from backend.pipeline.failures import PipelineFailure
        out.append(PipelineFailure)
    except ImportError:  # pragma: no cover
        pass
    try:
        from backend.services.studio.intelligence import VisionRequestError
        out.append(VisionRequestError)
    except ImportError:  # pragma: no cover
        pass
    return tuple(out)


def _api_types() -> tuple[type, ...]:
    try:
        from openai import APIError
    except ImportError:  # pragma: no cover
        return ()
    return (APIError,)


def _verdict(link: BaseException, local: tuple, coded: tuple, api: tuple) -> FailureKind | None:
    if isinstance(link, local):
        return FailureKind.LOCAL
    if coded and isinstance(link, coded):
        code = getattr(link, "code", "")
        if code in MODEL_ERROR_CODES:
            return FailureKind.MODEL
        if code in LOCAL_ERROR_CODES:
            return FailureKind.LOCAL
    if api and isinstance(link, api):
        return FailureKind.MODEL
    return None  # not decisive (OSError, RuntimeError, ...): look further in


def classify_failure(error: BaseException | None) -> Classification:
    """1. local (incl. lock timeout) -> LOCAL, no request record is read;
    2. model error -> MODEL, with the failed request's record when one travels with the error;
    3. no decisive link: a failed request's record, or a provider HTTP error status in the chain -> MODEL;
       any other error -> LOCAL; no error -> NONE."""
    if error is None:
        return Classification(FailureKind.NONE)
    local, coded, api = _local_types(), _coded_types(), _api_types()
    for link in chain(error):
        kind = _verdict(link, local, coded, api)
        if kind is FailureKind.LOCAL:
            return Classification(FailureKind.LOCAL, link)
        if kind is FailureKind.MODEL:
            return Classification(FailureKind.MODEL, link, record_of(error))
    record = record_of(error)
    if record is not None or _http_status(error) is not None:
        return Classification(FailureKind.MODEL, error, record)
    return Classification(FailureKind.LOCAL, error)


def _http_status(error: BaseException) -> int | None:
    try:
        from backend.pipeline.failures import http_status_of
    except ImportError:  # pragma: no cover
        return None
    try:
        status = http_status_of(error)
    except Exception:  # noqa: BLE001 - classification never fails the caller
        return None
    return status if isinstance(status, int) and 400 <= status <= 599 else None


def _paired_identity(fields: dict | None) -> dict[str, Any]:
    fields = fields if isinstance(fields, dict) else {}
    if not all(isinstance(fields.get(k), str) and fields[k] for k in ("provider", "config_source")):
        return {}
    return {k: fields[k] for k in IDENTITY_FIELDS if fields.get(k) not in (None, "")}


@dataclass(frozen=True)
class FailureAttribution:
    attribution_source: str
    provider: str | None = None
    config_source: str | None = None
    model: str | None = None
    base_url_host: str | None = None
    http_status: int | None = None
    upstream_error_type: str | None = None
    failure_stage: str | None = None

    def __post_init__(self):
        if self.attribution_source not in SOURCES:
            raise ValueError(f"unknown attribution_source {self.attribution_source!r}")
        if self.attribution_source == SOURCE_LOCAL and (self.http_status is not None or self.upstream_error_type):
            raise ValueError("a local failure carries no http_status/upstream_error_type")
        if bool(self.provider) != bool(self.config_source):
            raise ValueError("identity is a provider/config_source pair or nothing")

    @classmethod
    def build(cls, source: str, identity: dict | None = None, *, http_status=None,
              upstream_error_type=None, failure_stage=None) -> "FailureAttribution":
        ident = _paired_identity(identity)
        if source == SOURCE_LOCAL:
            http_status = upstream_error_type = None  # explicit: local never takes an upstream status
        return cls(source, **ident, http_status=http_status if isinstance(http_status, int) else None,
                   upstream_error_type=upstream_error_type or None, failure_stage=failure_stage or None)

    def to_fields(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in SNAPSHOT_FIELDS if getattr(self, k) not in (None, "")}


def write_attribution(record: dict, snapshot: FailureAttribution) -> None:
    """Replace the attribution group whole: every field goes, then the snapshot's fields are written."""
    if not isinstance(snapshot, FailureAttribution):
        raise TypeError("write_attribution takes a FailureAttribution")
    for key in SNAPSHOT_FIELDS:
        record.pop(key, None)
    record.update(snapshot.to_fields())


def read_attribution(record: dict | None) -> dict[str, Any]:
    """The attribution every reader uses (store, history, Sentry; the frontend's pickAttribution mirrors
    it). Cleans legacy half records in the returned projection only:
    - identity without its provider/config_source pair -> no identity;
    - ``local`` -> no http_status/upstream_error_type;
    - a record that did not fail -> no failure fields;
    - an unknown attribution_source is dropped."""
    if not isinstance(record, dict):
        return {}
    out = _paired_identity(record)
    source = record.get("attribution_source")
    if source in SOURCES:
        out["attribution_source"] = source
    if record.get("status") in FAILED_STATUSES or record.get("status") is None:
        for key in FAILURE_FIELDS:
            if record.get(key) not in (None, ""):
                out[key] = record[key]
        if source == SOURCE_LOCAL:
            for key in UPSTREAM_FIELDS:
                out.pop(key, None)
    return out


def project_attribution(record: dict | None) -> None:
    """Read-time cleanup in place on a record just read (never written back by the read itself)."""
    if not isinstance(record, dict):
        return
    clean = read_attribution(record)
    for key in SNAPSHOT_FIELDS:
        record.pop(key, None)
    record.update(clean)
