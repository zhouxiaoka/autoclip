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
# Codes that are decisively LOCAL in any layer. Other non-model codes (``unexpected``, ``validation``...)
# cannot decide: the walk looks past them.
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
    """Errors that are decisively LOCAL in ANY layer of the chain (I450): our own machine failed
    (store lock, subprocess, disk full / read-only, permissions, missing file or directory)."""
    import subprocess
    from backend.core.file_lock import LockTimeout
    return (LockTimeout, subprocess.TimeoutExpired, subprocess.CalledProcessError,
            PermissionError, FileNotFoundError, IsADirectoryError, NotADirectoryError)


_LOCAL_ERRNOS = frozenset({28, 30, 13, 1, 122})  # ENOSPC, EROFS, EACCES, EPERM, EDQUOT


def _is_local(link: BaseException, local: tuple, coded: tuple) -> bool:
    if isinstance(link, local):
        return True
    if isinstance(link, OSError) and getattr(link, "errno", None) in _LOCAL_ERRNOS:
        return True
    return bool(coded) and isinstance(link, coded) and getattr(link, "code", "") in LOCAL_ERROR_CODES


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


def _sent_and_answered(link: BaseException) -> bool:
    """A request record on this link whose request was SENT and got an error back from the provider
    (it carries the provider's HTTP status). A record alone is not proof (I450: a PermissionError raised
    inside the call before any network I/O also gets a record)."""
    record = getattr(link, _RECORD_ATTR, None)
    return record is not None and isinstance(getattr(record, "http_status", None), int)


def _is_model(link: BaseException, coded: tuple, api: tuple) -> bool:
    if coded and isinstance(link, coded):
        return getattr(link, "code", "") in MODEL_ERROR_CODES
    if api and isinstance(link, api):
        return True
    return _sent_and_answered(link)


def classify_failure(error: BaseException | None) -> Classification:
    """R28 (Dong R27 I450): LOCAL first, then MODEL, nothing else.

    1. any layer of the chain is a local error (lock timeout, subprocess, disk full, permissions, file not
       found, a local pipeline/vision code) -> LOCAL; no request record is read;
    2. walking from the outermost layer inward, skipping layers that cannot decide (OSError from a socket,
       RuntimeError, ``unexpected`` wrappers...), the first provider error -> MODEL: an API error from the
       provider SDK, a pipeline/vision failure with a model code, or a request that was sent and answered
       with an error. The record of that request rides along;
    3. otherwise LOCAL (a status code or a record alone never makes a model failure); no error -> NONE.
    Known limitation: a real model failure surfacing only as our own ValueError (no type/status/record)
    is LOCAL; the pipeline wraps those as ``invalid_response`` (a model code)."""
    if error is None:
        return Classification(FailureKind.NONE)
    local, coded, api = _local_types(), _coded_types(), _api_types()
    links = list(chain(error))
    for link in links:
        if _is_local(link, local, coded):
            return Classification(FailureKind.LOCAL, link)
    for link in links:
        if _is_model(link, coded, api):
            return Classification(FailureKind.MODEL, link, record_of(error))
    return Classification(FailureKind.LOCAL, error)


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
    def _make(cls, source: str, identity: dict | None = None, *, http_status=None,
              upstream_error_type=None, failure_stage=None) -> "FailureAttribution":
        ident = _paired_identity(identity)
        if source == SOURCE_LOCAL:
            http_status = upstream_error_type = None  # explicit: local never takes an upstream status
        return cls(source, **ident, http_status=http_status if isinstance(http_status, int) else None,
                   upstream_error_type=upstream_error_type or None, failure_stage=failure_stage or None)

    @classmethod
    def from_fields(cls, fields: dict) -> "FailureAttribution":
        """Restore a snapshot already stored (read via read_attribution); not a new assembly."""
        return cls(**{k: fields.get(k) for k in SNAPSHOT_FIELDS})

    def to_fields(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in SNAPSHOT_FIELDS if getattr(self, k) not in (None, "")}


def build_attribution(error: BaseException | None = None, *, phase_identity: dict | None = None,
                      start_identity: dict | None = None, failure_stage: str | None = None,
                      local: bool = False) -> FailureAttribution | None:
    """THE one place a failure-attribution snapshot is assembled (llm_emit.attribution, sentry_setup's
    studio_failure_context and store all call this).

    - MODEL with the failed request's record -> ``request``: that request's identity + status, whole;
    - MODEL without a record -> ``phase``: the phase identity + the provider status/upstream of THIS error;
    - LOCAL (or ``local=True``: a receipt, no exception object) -> ``local``: the phase identity, else the
      attempt's start identity; never a status/upstream;
    - no error -> the phase identity as ``phase`` (no status), or None when there is none.
    ``failure_stage`` defaults to the stage the job itself recorded on ``start_identity`` (its record)."""
    if failure_stage is None and isinstance(start_identity, dict):
        failure_stage = start_identity.get("failure_stage") or None
    verdict = Classification(FailureKind.LOCAL) if local else classify_failure(error)
    if verdict.kind is FailureKind.MODEL and verdict.record is not None:
        found = verdict.record.attribution()
        if found.get("provider") and found.get("config_source"):
            return FailureAttribution._make(SOURCE_REQUEST, found, http_status=found.get("http_status"),
                                            upstream_error_type=found.get("upstream_error_type"),
                                            failure_stage=failure_stage or found.get("failure_stage"))
    if verdict.kind is FailureKind.LOCAL:
        identity = _paired_identity(phase_identity) or _paired_identity(start_identity)
        record = None if local else record_of(error)
        if failure_stage is None and record is not None:  # WHERE it failed, never WHO/status
            failure_stage = record.attribution().get("failure_stage") or None
        return FailureAttribution._make(SOURCE_LOCAL, identity, failure_stage=failure_stage)
    status = upstream = None
    if verdict.kind is FailureKind.MODEL:
        status, upstream = _provider_status(error)
    identity = _paired_identity(phase_identity)
    if error is None and not identity:
        return None
    if not identity and status is None and not upstream and not failure_stage:
        return None
    return FailureAttribution._make(SOURCE_PHASE, identity, http_status=status, upstream_error_type=upstream,
                                    failure_stage=failure_stage)


def _provider_status(error: BaseException | None) -> tuple[int | None, str | None]:
    try:
        from backend.core.llm_telemetry import classify_run_upstream
        from backend.pipeline.failures import http_status_of
    except ImportError:  # pragma: no cover
        return None, None
    status = http_status_of(error)
    status = status if isinstance(status, int) and 400 <= status <= 599 else None
    return status, classify_run_upstream(error, status)


def write_attribution(record: dict, snapshot: FailureAttribution) -> None:
    """Replace the attribution group whole: every field goes, then the snapshot's fields are written."""
    if not isinstance(snapshot, FailureAttribution):
        raise TypeError("write_attribution takes a FailureAttribution")
    for key in SNAPSHOT_FIELDS:
        record.pop(key, None)
    record.update(snapshot.to_fields())


def has_snapshot(record: dict | None) -> bool:
    return isinstance(record, dict) and record.get("attribution_source") in SOURCES


def is_failed_terminal(record: dict | None) -> bool | None:
    """I451: the record ended in a failure when ``status`` OR ``outcome`` is failed/partial (``completed`` +
    ``outcome=partial`` is a valid partial). None: no status at all (legacy/summary) - undecided."""
    if not isinstance(record, dict):
        return False
    if record.get("status") in FAILED_STATUSES or record.get("outcome") in FAILED_STATUSES:
        return True
    return None if record.get("status") in (None, "") else False


def read_attribution(record: dict | None) -> dict[str, Any]:
    """The attribution every reader uses (store, history, Sentry; frontend pickAttribution has the same
    rules). Cleans by snapshot completeness, in the returned projection only:
    - identity without its provider/config_source pair -> no identity;
    - ``local`` -> no http_status/upstream_error_type;
    - failure fields stay on a failed terminal (status OR outcome failed/partial) and on a record with no
      status (undecided: nothing is deleted); a record that ended without failing has none;
    - an unknown attribution_source is dropped."""
    if not isinstance(record, dict):
        return {}
    out = _paired_identity(record)
    source = record.get("attribution_source")
    if source in SOURCES:
        out["attribution_source"] = source
    if is_failed_terminal(record) is not False:
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
