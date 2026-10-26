"""THE failure-attribution rule (design, 157/415-attribution-design.md).

One classifier, one write-once snapshot, one reader. the layer closest to the provider call, where
the exception chain is still intact, builds the snapshot once; dicts, threads, store writes and events
carry it unchanged (an ``AttributedError`` carries it on ``.attribution``):

- ``classify_failure(error)``: walks the error chain from the outermost link inward; the first DECISIVE
  link wins. Local errors first (store lock timeout, subprocess, a pipeline/vision failure with a
  local code), then model errors (provider API errors, pipeline/vision failures with a model code),
  and only then the failed request's record. Never by type-name strings.
- ``FailureAttribution``: the snapshot. ``local`` never carries ``http_status``/``upstream_error_type``
  (validated on construction: ``ValueError``). Identity is a provider/config_source pair or nothing.
- ``write_attribution(record, snapshot)``: replaces the attribution group WHOLE (no merging).
- ``export_attribution(source)`` (``read_attribution`` is the same function): THE whitelist
  serializer every emitter and reader uses; legacy half records are cleaned at read time only, never
  written back.

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
LOCAL_ERROR_CODES = frozenset({"source_blocked", "file_locked", "source_not_found", "source_too_short", "source_no_audio", "source_unreadable",
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
    snapshot: Any = None  # the snapshot an AttributedError carried (returned as is)
    decided: bool = True  # False: LOCAL only because nothing in the chain decided (the fall-through)


class AttributedError(Exception):
    """the base of every redaction-boundary exception (``_LogSafeLLMError``,
    ``CloudTranscriptionError``, ``ImageError``) and of a failure rebuilt across the Celery boundary.

    The boundary calls ``build_attribution`` ONCE on the original exception while its chain is intact,
    then raises the safe exception ``from None`` with that snapshot on ``.attribution``. The snapshot holds
    only codes and ids (source, provider/config_source/model/base_url_host, http_status,
    upstream_error_type, failure_stage): never a message, URL or body. ``classify_failure`` returns it as
    is. ``None`` (the class default): the raise site had no provider failure to attribute.

    ``http_status`` is the provider's HTTP status FROZEN at the same boundary, by the same
    construction (``attributed``), because ``from None`` leaves no ``__cause__`` to read it from later.
    ``http_status_of`` reads this field; None: no HTTP response came back (or none was observed).

    ``error_code`` is the controlled studio code (``connection``/``timeout``/...,
    one of ``MODEL_ERROR_CODES``) FROZEN by the same ``attributed`` call, so a timeout and a refused
    connection stay apart after the redaction wrap. ``frozen_error_code`` reads it."""
    attribution: "FailureAttribution | None" = None
    http_status: int | None = None
    error_code: str | None = None


class ProviderTransportError(Exception):
    """a request that was SENT toward the provider and failed in transport (connect/read
    timeout, a refused connection) or came back with an HTTP error status, seen by a redaction boundary
    around an SDK this module does not know (httpx/requests). The boundary builds one of these from the
    original exception INSIDE its ``except`` (type name and status only: no message, URL or body), lets
    ``build_attribution`` classify it like any other link (``classify_failure``: MODEL by ``isinstance``),
    and never raises it: the safe error still goes out ``from None``."""

    def __init__(self, kind: str, *, http_status: int | None = None, timed_out: bool = False):
        super().__init__(kind)
        self.http_status = http_status if valid_status(http_status) else None
        self.error_code = _transport_code(kind, self.http_status, timed_out)


def valid_status(value) -> bool:
    """THE valid range of a provider HTTP status, everywhere a status is
    frozen or read: an error response, 400-599 (an int, not a bool). Nothing below 400 is ever frozen."""
    return type(value) is int and 400 <= value <= 599


def _transport_code(kind: str, status: int | None, timed_out: bool) -> str:
    """the controlled studio code of a transport failure, from its type and HTTP status ONLY
    (never a body): no response -> ``timeout`` or ``connection``; else the shared status rule."""
    if status is None:
        return "timeout" if timed_out else "connection"
    from backend.core.llm_retry import studio_code_for
    from backend.core.upstream_errors import classify_upstream_error
    return studio_code_for(classify_upstream_error(status, None, error_name=kind).error_type, status)


class ModelResponseInvalid(ValueError):
    """the model answered (HTTP 200) but its content failed our validation (JSON that does not
    parse, a schema/ID/range check). An explicit type, never a fallback: ``classify_failure`` judges it
    MODEL by ``isinstance`` and its studio error code is ``invalid_response``."""
    error_code = "invalid_response"


def attributed(error: BaseException, snapshot: "FailureAttribution | None", *,
               http_status: int | None = None, error_code: str | None = None) -> BaseException:
    """THE construction of a redaction boundary's frozen fields on its safe exception (an
    ``AttributedError``): the snapshot, the provider's HTTP status when a response came
    back, and the controlled studio error code. Returns the exception. A status outside
    ``valid_status`` (400-599, ) is not frozen; a code outside ``MODEL_ERROR_CODES`` is not
    frozen; an absent one leaves the field."""
    if snapshot is not None and not isinstance(snapshot, FailureAttribution):
        raise TypeError("attributed takes a FailureAttribution")
    error.attribution = snapshot
    if valid_status(http_status):
        error.http_status = http_status
    if isinstance(error_code, str) and error_code in MODEL_ERROR_CODES:
        error.error_code = error_code
    return error


def frozen_error_code(error: BaseException | None) -> str | None:
    """the studio code a redaction boundary froze on this safe error (``attributed``), else
    None. Only the error itself is read (its chain was dropped at the boundary)."""
    code = getattr(error, "error_code", None) if isinstance(error, AttributedError) else None
    return code if isinstance(code, str) and code in MODEL_ERROR_CODES else None


def with_request_record(error: BaseException, record) -> None:
    """The call boundary (llm_emit) attaches the failed request's record to the safe exception raised just
    inside it. A MODEL snapshot built at the redaction boundary had only the phase identity: THE factory
    gives it the request's identity now (``build_attribution(request_record=)``, ). Kind, status
    and upstream type stay exactly as the boundary built them."""
    if not isinstance(error, AttributedError) or not isinstance(getattr(error, "attribution", None), FailureAttribution):
        return
    if record is not None:
        error.attribution = build_attribution(error, request_record=record)


def http_status_of(error: BaseException | None) -> int | None:
    """(one traversal rule with ): THE provider HTTP status of a failure, 400-599 or None.

    Walks ``chain`` (the error, then its explicit ``__cause__`` links; never ``__context__``) and returns
    the first link's own status field: ``http_status`` (frozen on an ``AttributedError`` at its redaction
    boundary, or a pipeline failure's) or the SDK's ``status_code``. A safe error raised ``from None`` has
    no cause, so its frozen field is all there is; only raw, unwrapped exceptions have a cause to walk.
    An exception that merely happened to be handled when this one was raised never lends its status."""
    for link in chain(error):
        for attr in ("http_status", "status_code"):
            value = getattr(link, attr, None)
            if valid_status(value):
                return value
    return None


def chain(error: BaseException | None) -> Iterator[BaseException]:
    """The error, then its EXPLICIT ``__cause__`` links only (``raise ... from``), cycle-safe.

    the implicit ``__context__`` (an exception that merely happened to be handled when this one
    was raised, e.g. the ``FileNotFoundError`` of a cache miss before the real request) is never walked:
    only a cause the code chose to attach can decide."""
    seen: set[int] = set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__


def record_of(error: BaseException | None):
    """The failed request's record travelling with ``error`` or anywhere up its chain; else None."""
    for link in chain(error):
        record = getattr(link, _RECORD_ATTR, None)
        if record is not None and callable(getattr(record, "attribution", None)):
            return record
    return None


def _local_types() -> tuple[type, ...]:
    """Errors that are decisively LOCAL in ANY layer of the chain our own machine failed
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
    (it carries the provider's HTTP status). A record alone is not proof (a PermissionError raised
    inside the call before any network I/O also gets a record)."""
    record = getattr(link, _RECORD_ATTR, None)
    return record is not None and isinstance(getattr(record, "http_status", None), int)


def _is_model(link: BaseException, coded: tuple, api: tuple) -> bool:
    if isinstance(link, (ModelResponseInvalid, ProviderTransportError)):
        return True
    if coded and isinstance(link, coded):
        return getattr(link, "code", "") in MODEL_ERROR_CODES
    if api and isinstance(link, api):
        return True
    return _sent_and_answered(link)


def classify_failure(error: BaseException | None) -> Classification:
    """LOCAL first, then MODEL, nothing else.

    1. any layer of the chain is a local error (lock timeout, subprocess, disk full, permissions, file not
       found, a local pipeline/vision code) -> LOCAL; no request record is read;
    2. walking from the outermost layer inward, skipping layers that cannot decide (OSError from a socket,
       RuntimeError, ``unexpected`` wrappers...), the first provider error -> MODEL: an API error from the
       provider SDK, a pipeline/vision failure with a model code, or a request that was sent and answered
       with an error. The record of that request rides along;
    3. otherwise LOCAL (a status code or a record alone never makes a model failure); no error -> NONE.
    only the explicit ``__cause__`` chain is walked. An ``AttributedError`` carrying a snapshot
    decides with that snapshot, returned unchanged (it was built where the chain was intact). A
    ``ModelResponseInvalid`` (200 + content failed validation) is MODEL. A connection error or timeout is
    MODEL too (the request was sent toward the provider); error_code tells them apart.
    a ``ProviderTransportError`` (a redaction boundary's view of an httpx/requests failure) is MODEL by
    ``isinstance``; this is the only place that decides it (no ``sent`` override in the factory)."""
    if error is None:
        return Classification(FailureKind.NONE)
    local, coded, api = _local_types(), _coded_types(), _api_types()
    links = list(chain(error))
    for link in links:
        if _is_local(link, local, coded):
            return Classification(FailureKind.LOCAL, link)
        snap = getattr(link, "attribution", None) if isinstance(link, AttributedError) else None
        if isinstance(snap, FailureAttribution):  # built where the chain was intact: returned as is
            kind = FailureKind.LOCAL if snap.attribution_source == SOURCE_LOCAL else FailureKind.MODEL
            return Classification(kind, link, snapshot=snap)
    for link in links:
        if _is_model(link, coded, api):
            return Classification(FailureKind.MODEL, link, record_of(error))
    return Classification(FailureKind.LOCAL, error, decided=False)


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
        """Restore a snapshot already stored (read via export_attribution); not a new assembly."""
        return cls(**{k: fields.get(k) for k in SNAPSHOT_FIELDS})

    def to_fields(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in SNAPSHOT_FIELDS if getattr(self, k) not in (None, "")}


def restore_attribution(fields: dict | None) -> FailureAttribution | None:
    """/ THE one restore point for a snapshot that crossed a boundary as fields (the adapter's
    result dict across ``apply().get()``). The fields are taken whole, never re-judged; None if absent."""
    if not isinstance(fields, dict) or fields.get("attribution_source") not in SOURCES:
        return None
    return FailureAttribution.from_fields(fields)


def build_attribution(error: BaseException | None = None, *, phase_identity: dict | None = None,
                      start_identity: dict | None = None, failure_stage: str | None = None,
                      local: bool = False, request_record: Any = None) -> FailureAttribution | None:
    """THE one place a failure-attribution snapshot is assembled (llm_emit.attribution, sentry_setup's
    studio_failure_context and store all call this).

    - MODEL with the failed request's record -> ``request``: that request's identity + status, whole;
    - MODEL without a record -> ``phase``: the phase identity + the provider status/upstream of THIS error;
    - LOCAL (or ``local=True``: a receipt, no exception object) -> ``local``: the phase identity, else the
      attempt's start identity; never a status/upstream;
    - no error -> the phase identity as ``phase`` (no status), or None when there is none.
    ``failure_stage`` defaults to the stage the job itself recorded on ``start_identity`` (its record).
    an error carrying a boundary snapshot (``AttributedError``) gets that snapshot back unchanged,
    never re-judged. the only two things ever added to a carried snapshot are added HERE, by
    parameter: ``request_record`` (the call boundary's failed request) gives a ``phase`` snapshot that
    request's identity (-> ``request``), and a missing ``failure_stage`` is filled in."""
    if failure_stage is None and isinstance(start_identity, dict):
        failure_stage = start_identity.get("failure_stage") or None
    verdict = Classification(FailureKind.LOCAL) if local else classify_failure(error)
    if verdict.snapshot is not None:
        snap = verdict.snapshot  # carried from the boundary: never re-judged
        source, identity = snap.attribution_source, snap.to_fields()
        stage = snap.failure_stage or failure_stage
        found = request_record.attribution() if callable(getattr(request_record, "attribution", None)) else {}
        if source == SOURCE_PHASE and found.get("provider") and found.get("config_source"):
            source, identity = SOURCE_REQUEST, found
            stage = snap.failure_stage or found.get("failure_stage") or failure_stage
        if (source, stage) == (snap.attribution_source, snap.failure_stage):
            return snap
        return FailureAttribution._make(source, identity, http_status=snap.http_status,
                                        upstream_error_type=snap.upstream_error_type, failure_stage=stage)
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
    if verdict.kind is not FailureKind.MODEL and not identity and not failure_stage:
        return None  # a MODEL failure always gets its snapshot (it must survive a redaction wrap)
    return FailureAttribution._make(SOURCE_PHASE, identity, http_status=status, upstream_error_type=upstream,
                                    failure_stage=failure_stage)


def _provider_status(error: BaseException | None) -> tuple[int | None, str | None]:
    """The provider's HTTP status on the EXPLICIT chain (/ only a response actually received;
    a connection error or timeout has none), and its upstream type."""
    try:
        from backend.core.llm_telemetry import classify_run_upstream
    except ImportError:  # pragma: no cover
        return None, None
    status = http_status_of(error)  # THE one status rule
    upstream = classify_run_upstream(error, status)
    if not upstream and error is not None:
        # A boundary that never sent a request (missing ASR key) still froze an enum cause.
        frozen = getattr(error, "upstream_error_type", None)
        if isinstance(frozen, str) and frozen not in ("", "unknown"):
            from backend.core.llm_telemetry import sanitize_upstream_error_type
            upstream = sanitize_upstream_error_type(frozen)
    return status, upstream


def write_attribution(record: dict, snapshot: FailureAttribution) -> None:
    """Replace the attribution group whole: every field goes, then the snapshot's fields are written."""
    if not isinstance(snapshot, FailureAttribution):
        raise TypeError("write_attribution takes a FailureAttribution")
    for key in SNAPSHOT_FIELDS:
        record.pop(key, None)
    record.update(export_attribution(snapshot))


def has_snapshot(record: dict | None) -> bool:
    return isinstance(record, dict) and record.get("attribution_source") in SOURCES


def is_failed_terminal(record: dict | None) -> bool | None:
    """the record ended in a failure when ``status`` OR ``outcome`` is failed/partial (``completed`` +
    ``outcome=partial`` is a valid partial). None: no status at all (legacy/summary) - undecided."""
    if not isinstance(record, dict):
        return False
    if record.get("status") in FAILED_STATUSES or record.get("outcome") in FAILED_STATUSES:
        return True
    return None if record.get("status") in (None, "") else False


def _valid(key: str, value: Any) -> bool:
    if key == "http_status":
        return valid_status(value)
    if key == "attribution_source":
        return value in SOURCES
    return isinstance(value, str) and value != ""


def export_attribution(source: "FailureAttribution | dict | None", *, failed: bool | None = None) -> dict[str, Any]:
    """THE whitelist serializer. Every attribution that leaves a record or a snapshot
    (Sentry tags/context, the PostHog run snapshot, the store's history summary and read projection, the
    stored group itself) goes through here; the frontend twin is ``pickAttribution`` (workflow.ts).

    Only ``SNAPSHOT_FIELDS`` are copied, one by one, each type-checked (a status is an int 400-599, the
    source one of ``SOURCES``, every other field a non-empty string); nothing else in ``source`` (extra
    keys, prose, URLs) can come out. Then the reader rules, on the copy only:
    - identity without its provider/config_source pair -> no identity;
    - ``local`` -> no http_status/upstream_error_type;
    - failure fields stay on a failed terminal (status OR outcome failed/partial) and on an undecided one
      (no status; a bare snapshot is undecided unless ``failed`` says otherwise); a record that ended
      without failing has none;
    - an unknown attribution_source is dropped."""
    if isinstance(source, FailureAttribution):
        fields = {k: getattr(source, k) for k in SNAPSHOT_FIELDS}
        terminal = failed
    elif isinstance(source, dict):
        fields = source
        terminal = is_failed_terminal(source) if failed is None else failed
    else:
        return {}
    clean = {k: fields[k] for k in SNAPSHOT_FIELDS if _valid(k, fields.get(k))}
    out = _paired_identity(clean)
    origin = clean.get("attribution_source")
    if origin is not None:
        out["attribution_source"] = origin
    if terminal is not False:
        for key in FAILURE_FIELDS:
            if key in clean:
                out[key] = clean[key]
        if origin == SOURCE_LOCAL:
            for key in UPSTREAM_FIELDS:
                out.pop(key, None)
    return out


read_attribution = export_attribution  # the record reader IS the serializer (one implementation)


def project_attribution(record: dict | None) -> None:
    """Read-time cleanup in place on a record just read (never written back by the read itself)."""
    if not isinstance(record, dict):
        return
    clean = export_attribution(record)
    for key in SNAPSHOT_FIELDS:
        record.pop(key, None)
    record.update(clean)


# (PM rule, one rule with docs/analytics/success_rate.sql): which failure a multi-goal
# attempt is attributed to. Tiers come from the catalog's attribution.success_rate_v4. A cause is
# user_hard (out of both denominators), user_x (out of the product denominator only) or product.
# The primary cause is the first failure of the most product-like tier; the rest are secondary.
# This does not build connection-test snapshots; classify_failure / export_attribution stay the
# only snapshot rule above.
PRODUCT, USER_X, USER_HARD = 0, 1, 2


def _v4() -> dict:
    from backend.core import event_catalog
    return (event_catalog.load_catalog().get("attribution") or {}).get("success_rate_v4") or {}


def cause_tier(failure: dict) -> int:
    v4 = _v4()
    code, upstream = failure.get("error_code"), failure.get("upstream_error_type")
    if code in v4.get("overall_excluded_error_codes", ()) or upstream in v4.get("overall_excluded_upstream_types", ()):
        return USER_HARD
    if code in v4.get("product_extra_excluded_error_codes", ()):
        return USER_X
    return PRODUCT


def rank_failures(failures: list) -> list:
    """Failures in the order they failed -> primary first (most product-like tier, then earliest)."""
    return sorted(failures, key=cause_tier)  # stable: within a tier the earliest failure stays first
