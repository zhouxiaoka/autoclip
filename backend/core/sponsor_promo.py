"""Signed sponsor-promotion documents.

The packaged provider catalog stays local. A promotion document may only
reorder built-in sponsor ids, pick the new-user default, and attach a status
or a short notice. It cannot name an API host, a key, or a model.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "autoclip.sponsor-promo/v1"
STATUSES = frozenset({"healthy", "fault", "out_of_service"})
LOCALES = frozenset({"zh", "en", "ja", "ko", "es", "fr", "pt", "ru"})
PAYLOAD_KEYS = frozenset({
    "schema", "sequence", "issued_at", "expires_at", "min_app", "max_app",
    "rollback_of", "sponsors",
})
SPONSOR_KEYS = frozenset({"id", "order", "new_user_default", "status", "notices", "register_url"})
BUNDLED_CHOICES = ("apimart", "api88", "other")
BUNDLED_DEFAULT = "apimart"
# Status notices may name a built-in provider that is no longer promoted.
NOTICE_PROVIDER_IDS = frozenset({"api88", "infistar", "apimart"})
_MAX_NOTICE = 240
_CLOCK_SKEW = timedelta(minutes=5)


@dataclass(frozen=True)
class PromoDecision:
    ok: bool
    reason: str
    payload: Optional[dict] = None
    retire_sequence: Optional[int] = None


def canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def bundled_view() -> dict:
    return {
        "source": "bundled",
        "enabled": False,
        "choices": list(BUNDLED_CHOICES),
        "default": BUNDLED_DEFAULT,
        "statuses": {},
        "notices": {},
        "register_urls": {},
        "sequence": None,
    }


def notice_provider_ids() -> set[str]:
    from backend.core.provider_presets import get_provider
    return {item for item in NOTICE_PROVIDER_IDS if get_provider(item)}


def builtin_sponsor_hosts() -> dict[str, str]:
    """Built-in sponsor id → registration hostname. No API base URL leaves this map."""
    from backend.core.provider_presets import iter_providers

    hosts: dict[str, str] = {}
    for item in iter_providers():
        sponsor = item.sponsor or {}
        host = (urlparse(sponsor.get("register_url") or "").hostname or "").lower().rstrip(".")
        if host:
            hosts[item.id] = host
    return hosts


def verify_signature(payload: Mapping[str, Any], signature: str, public_key: str) -> bool:
    try:
        raw_key = base64.b64decode(public_key, validate=True)
        raw_sig = base64.b64decode(signature, validate=True)
        if len(raw_key) != 32 or len(raw_sig) != 64 or "PRIVATE" in public_key:
            return False
        Ed25519PublicKey.from_public_bytes(raw_key).verify(raw_sig, canonical_bytes(payload))
        return True
    except (InvalidSignature, ValueError):
        return False


def _version(value: str) -> Optional[tuple[int, int, int]]:
    text = (value or "").strip().lstrip("vV").split("-", 1)[0]
    parts = text.split(".")
    if len(parts) != 3:
        return None
    try:
        return tuple(int(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def _stamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _notice(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > _MAX_NOTICE:
        return None
    if any(ord(char) < 32 for char in text) or "<" in text or ">" in text or "://" in text.lower():
        return None
    return text


def _register_url(sponsor_id: str, value: str, hosts: Mapping[str, str]) -> bool:
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    digits = host.replace(".", "")
    return (
        parsed.scheme == "https"
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
        and port in (None, 443)
        and bool(host)
        and not digits.isdigit()
        and host == hosts.get(sponsor_id)
    )


def validate_payload(
    payload: Any,
    *,
    app_version: str,
    now: datetime,
    hosts: Mapping[str, str],
    min_sequence: int,
    cache_sequence: Optional[int],
    retired: set[int],
    current_sequence: Optional[int] = None,
) -> PromoDecision:
    required = {"schema", "sequence", "issued_at", "expires_at", "min_app", "sponsors"}
    if not isinstance(payload, dict) or set(payload) - PAYLOAD_KEYS or not required <= set(payload):
        return PromoDecision(False, "schema")
    if payload.get("schema") != SCHEMA or not isinstance(payload.get("sponsors"), list):
        return PromoDecision(False, "schema")
    sequence = payload.get("sequence")
    rollback_of = payload.get("rollback_of")
    if type(sequence) is not int or sequence < 1:
        return PromoDecision(False, "sequence")
    if rollback_of is not None and (type(rollback_of) is not int or rollback_of < 1):
        return PromoDecision(False, "sequence")
    if sequence in retired:
        return PromoDecision(False, "retired")
    if sequence < min_sequence:
        return PromoDecision(False, "below_min_sequence")
    high_water = cache_sequence or 0
    current = current_sequence if current_sequence is not None else (cache_sequence or 0)
    # Restoring old content uses a higher sequence. A lower sequence is never accepted.
    if high_water:
        if sequence == current:
            return PromoDecision(False, "replay")
        if sequence <= high_water:
            return PromoDecision(False, "downgrade")
    issued = _stamp(payload.get("issued_at"))
    expires = _stamp(payload.get("expires_at"))
    if issued is None or expires is None or issued > expires:
        return PromoDecision(False, "time")
    if issued > now + _CLOCK_SKEW:
        return PromoDecision(False, "not_yet_valid")
    if expires <= now:
        return PromoDecision(False, "expired")
    app = _version(app_version)
    minimum = _version(str(payload.get("min_app") or ""))
    maximum = _version(str(payload["max_app"])) if "max_app" in payload else None
    if app is None or minimum is None or (maximum is None and "max_app" in payload):
        return PromoDecision(False, "version")
    if app < minimum or (maximum is not None and app > maximum):
        return PromoDecision(False, "incompatible")
    sponsors = _sponsors(payload["sponsors"], hosts, notice_provider_ids())
    if sponsors is None:
        return PromoDecision(False, "sponsors")
    cleaned = dict(payload)
    cleaned["sponsors"] = sponsors
    return PromoDecision(True, "ok", cleaned, None)


def _sponsors(rows: list, hosts: Mapping[str, str], allowed: set[str]) -> Optional[list]:
    if len(rows) > len(allowed):
        return None
    seen: set[str] = set()
    orders: set[int] = set()
    defaults = 0
    cleaned = []
    for row in rows:
        if not isinstance(row, dict) or set(row) - SPONSOR_KEYS or not {"id", "order", "status"} <= set(row):
            return None
        sponsor_id = row.get("id")
        order = row.get("order")
        status = row.get("status")
        if not isinstance(sponsor_id, str) or not isinstance(status, str):
            return None
        if sponsor_id not in allowed or sponsor_id in seen or type(order) is not int or status not in STATUSES:
            return None
        if row.get("new_user_default") not in (None, True, False):
            return None
        notices = row.get("notices", {})
        if not isinstance(notices, dict) or set(notices) - LOCALES:
            return None
        text = {}
        for locale, notice in notices.items():
            cleaned_notice = _notice(notice)
            if cleaned_notice is None:
                return None
            text[locale] = cleaned_notice
        register_url = row.get("register_url")
        if register_url is not None and (not isinstance(register_url, str) or not _register_url(sponsor_id, register_url, hosts)):
            return None
        if row.get("new_user_default") is True:
            if sponsor_id not in hosts:
                return None
            defaults += 1
        seen.add(sponsor_id)
        orders.add(order)
        item = {"id": sponsor_id, "order": order, "status": status, "new_user_default": row.get("new_user_default") is True, "notices": text}
        if register_url:
            item["register_url"] = register_url
        cleaned.append(item)
    if defaults > 1 or len(orders) != len(cleaned):
        return None
    return cleaned


def promotion_view(payload: Mapping[str, Any], *, enabled: bool, source: str) -> dict:
    """New-user choices exclude paused and non-promoted providers. Status stays for saved users."""
    rows = sorted(payload.get("sponsors") or [], key=lambda item: item["order"])
    promoted = set(builtin_sponsor_hosts())
    visible = [row for row in rows if row["status"] != "out_of_service" and row["id"] in promoted]
    choices = [row["id"] for row in visible] + ["other"]
    marked = next((row["id"] for row in visible if row.get("new_user_default")), None)
    default = marked or (choices[0] if choices else "other")
    if default not in choices:
        default = "other"
    return {
        "source": source,
        "enabled": enabled,
        "choices": choices,
        "default": default,
        "statuses": {row["id"]: row["status"] for row in rows},
        "notices": {row["id"]: row.get("notices") or {} for row in rows if row.get("notices")},
        "register_urls": {row["id"]: row["register_url"] for row in visible if row.get("register_url")},
        "sequence": payload.get("sequence"),
    }
