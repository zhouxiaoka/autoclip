"""Build a diagnostic manifest from allowlisted fields. Raw logs, paths and secrets never enter it."""
from __future__ import annotations

import json
import re
from typing import Any

from backend.core.event_catalog import app_version, detect_arch, detect_os
from backend.core.failure_codes import error_code_pattern
from backend.core.llm_telemetry import (
    FAILURE_STAGES,
    hostname_of_base_url,
    sanitize_model,
    sanitize_provider,
    sanitize_run_properties,
)
from backend.services.diagnostics.allowlist_data import (
    CONSENT_TEXT_VERSION,
    FORBIDDEN_KEYS,
    MANIFEST_KEYS,
    PURPOSE,
    ROLE_MAX_BYTES,
    SCHEMA,
)
from backend.services.diagnostics.redact import sanitized_log_records

_TOKEN = re.compile(r"^t-[a-f0-9]{32}$")
_ERROR = error_code_pattern()
_RESUMED = frozenset({"none", "subtitle", "step1", "step2", "step3", "step4"})
_RETRY_KIND = frozenset({"same", "switch_model", "after_install"})
_QUOTA = frozenset({"skipped", "ok", "exhausted", "unavailable"})
_ATTRIBUTION = frozenset({"request", "phase", "local"})
_KINDS = frozenset({"generation", "production"})
_TRIGGERS = frozenset({"initial", "retry", "variant_retry"})
_STATES = frozenset({"failed", "partial"})
_CODECS = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
_INT_KEYS = (
    "llm_calls", "prompt_tokens", "completion_tokens", "reasoning_tokens",
    "retry_count", "degrade_count", "billable_calls_before_failure", "duration_ms",
    "source_duration_sec", "platform_count", "http_status",
)


def _token(value: Any) -> str | None:
    return value if isinstance(value, str) and _TOKEN.fullmatch(value) else None


def _enum(value: Any, allowed: frozenset[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _count(value: Any, *, minimum: int = 0, maximum: int = 10**12) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = int(value)
    if number < minimum or number > maximum:
        return None
    return number


def _codes(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    out = []
    for item in value[:3]:
        if isinstance(item, str) and _ERROR.fullmatch(item):
            out.append(item)
    return out or None


def attempt_view(receipt: dict) -> dict:
    """Identity and failure enums from one AttemptReceipt. No prose, no paths."""
    view: dict[str, Any] = {}
    for key in ("attempt_id", "flow_id", "retry_of"):
        token = _token(receipt.get(key))
        if token:
            view[key] = token
    sequence = _count(receipt.get("sequence"), minimum=1, maximum=100_000)
    if sequence is not None:
        view["sequence"] = sequence
    for key, allowed in (("kind", _KINDS), ("trigger", _TRIGGERS), ("state", _STATES)):
        item = _enum(receipt.get(key), allowed)
        if item:
            view[key] = item
    code = receipt.get("error_code")
    if isinstance(code, str) and _ERROR.fullmatch(code):
        view["error_code"] = code
    stage = _enum(receipt.get("failure_stage"), FAILURE_STAGES)
    if stage:
        view["failure_stage"] = stage
    upstream = receipt.get("upstream_error_type")
    if isinstance(upstream, str) and upstream:
        from backend.core.llm_telemetry import sanitize_upstream_error_type
        clean = sanitize_upstream_error_type(upstream)
        if clean:
            view["upstream_error_type"] = clean
    unexpected = receipt.get("unexpected_type")
    if isinstance(unexpected, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,40}", unexpected):
        from backend.core.event_catalog import load_catalog
        allowed = set((load_catalog().get("enums") or {}).get("unexpected_type") or [])
        if unexpected in allowed:
            view["unexpected_type"] = unexpected
    for key, builder in (
        ("secondary_error_codes", _codes),
        ("secondary_upstream_error_types", lambda value: [
            item for item in (value or [])[:3] if isinstance(item, str) and re.fullmatch(r"[a-z0-9_]{1,40}", item)
        ] or None),
        ("secondary_failure_stages", lambda value: [
            item for item in (value or [])[:3] if isinstance(item, str) and item in FAILURE_STAGES
        ] or None),
    ):
        cleaned = builder(receipt.get(key))
        if cleaned:
            view[key] = cleaned
    return view


def run_view(summary: dict | None) -> dict:
    raw = summary if isinstance(summary, dict) else {}
    safe = sanitize_run_properties({k: raw.get(k) for k in _INT_KEYS if k in raw} | {
        "provider": raw.get("provider"),
        "model": raw.get("model"),
        "base_url_host": raw.get("base_url_host") or raw.get("base_url"),
        "upstream_error_type": raw.get("upstream_error_type"),
        "failure_stage": raw.get("failure_stage"),
        "config_source": raw.get("config_source"),
    })
    # sanitize_run_properties adds success_rate_schema_version; it is not a diagnostic field.
    safe.pop("success_rate_schema_version", None)
    provider = sanitize_provider(raw.get("provider")) if isinstance(raw.get("provider"), str) else safe.get("provider")
    if provider:
        safe["provider"] = provider
    model = sanitize_model(raw.get("model")) if isinstance(raw.get("model"), str) else None
    if model:
        safe["model"] = model
    host = raw.get("base_url_host") or raw.get("base_url")
    if isinstance(host, str):
        try:
            cleaned = hostname_of_base_url(host)
        except ValueError:
            cleaned = None
        if cleaned:
            safe["base_url_host"] = cleaned
    attribution = _enum(raw.get("attribution_source"), _ATTRIBUTION)
    if attribution:
        safe["attribution_source"] = attribution
    resumed = _enum(raw.get("resumed_from"), _RESUMED)
    if resumed:
        safe["resumed_from"] = resumed
    retry_kind = _enum(raw.get("retry_kind"), _RETRY_KIND)
    if retry_kind:
        safe["retry_kind"] = retry_kind
    quota = _enum(raw.get("quota_precheck"), _QUOTA)
    if quota:
        safe["quota_precheck"] = quota
    ratio = raw.get("eta_error_ratio")
    if isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and 0 <= float(ratio) <= 1000:
        safe["eta_error_ratio"] = round(float(ratio), 3)
    eta = raw.get("eta_initial_min")
    if isinstance(eta, (int, float)) and not isinstance(eta, bool) and 0 <= float(eta) <= 10_000:
        safe["eta_initial_min"] = round(float(eta), 2)
    for key in _INT_KEYS:
        if key in raw and key not in safe:
            number = _count(raw.get(key))
            if number is not None:
                safe[key] = number
    return {k: v for k, v in safe.items() if v is not None and v != ""}


def media_facts(raw: dict | None) -> dict:
    src = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}
    for key in ("container", "vcodec", "acodec"):
        value = src.get(key)
        if isinstance(value, str) and _CODECS.fullmatch(value) and "sk-" not in value.lower():
            out[key] = value
    for key in ("width", "height"):
        number = _count(src.get(key), maximum=100_000)
        if number:
            out[key] = number
    duration = src.get("duration_sec")
    if isinstance(duration, (int, float)) and not isinstance(duration, bool) and 0 < float(duration) < 100_000:
        out["duration_sec"] = round(float(duration), 2)
    if isinstance(src.get("audio_present"), bool):
        out["audio_present"] = src["audio_present"]
    size = _count(src.get("size_bytes"), maximum=ROLE_MAX_BYTES["original"])
    if size is not None:
        out["size_bytes"] = size
    return out


def build_manifest(receipt: dict, *, summary: dict | None = None, media: dict | None = None,
                   log_text: str = "", project_id: str | None = None, source_link: str | None = None) -> dict:
    summary = summary if summary is not None else (receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {})
    manifest = {
        "schema": SCHEMA,
        "purpose": PURPOSE,
        "not_for_training": True,
        "consent_text_version": CONSENT_TEXT_VERSION,
        "runtime": {
            "app_version": app_version(),
            "os": detect_os(),
            "arch": detect_arch(),
            "runtime": "python",
        },
        "attempt": attempt_view(receipt),
        "run": run_view(summary),
        "media_facts": media_facts(media),
        "log_lines": sanitized_log_records(log_text, project_id=project_id, limit=50),
        "limits": {
            "manifest_max_bytes": ROLE_MAX_BYTES["manifest"],
            "subtitle_max_bytes": ROLE_MAX_BYTES["subtitle"],
            "excerpt_max_bytes": ROLE_MAX_BYTES["excerpt"],
            "original_max_bytes": ROLE_MAX_BYTES["original"],
            "approval": "pending",
        },
    }
    if isinstance(source_link, str) and source_link:
        manifest["source_link"] = source_link
    problems = validate_manifest(manifest)
    if problems and "source_link" in manifest:
        manifest.pop("source_link", None)
        problems = validate_manifest(manifest)
    if problems:
        raise ValueError("manifest_rejected")
    return manifest


def validate_manifest(manifest: dict) -> list[str]:
    """Return reasons the manifest must not be uploaded. Empty means it passed."""
    problems: list[str] = []
    if not isinstance(manifest, dict):
        return ["not_object"]
    extra = set(manifest) - MANIFEST_KEYS
    if extra:
        problems.append("extra_keys")
    if manifest.get("schema") != SCHEMA or manifest.get("purpose") != PURPOSE:
        problems.append("schema")
    if manifest.get("not_for_training") is not True:
        problems.append("purpose")
    blob = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    if len(blob.encode("utf-8")) > ROLE_MAX_BYTES["manifest"]:
        problems.append("too_large")
    _walk(manifest, problems)
    from backend.services.diagnostics.source import sanitize_source_link
    link = manifest.get("source_link") if isinstance(manifest, dict) else None
    if isinstance(manifest, dict) and "source_link" in manifest and sanitize_source_link(link if isinstance(link, str) else None) != link:
        problems.append("source_link")
    scanned = dict(manifest) if isinstance(manifest, dict) else {}
    scanned.pop("source_link", None)
    blob = json.dumps(scanned, ensure_ascii=False, sort_keys=True)
    if re.search(r"sk-|Bearer |api[_-]?key\s*[:=]|/[Uu]sers/|\\\\Users\\\\|https?://\S+\?", blob):
        problems.append("secret_or_path")
    return problems


def _walk(value: Any, problems: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                problems.append("forbidden_key")
            _walk(item, problems)
    elif isinstance(value, list):
        for item in value:
            _walk(item, problems)
    elif isinstance(value, str) and ("\n" in value or len(value) > 400):
        problems.append("prose")
