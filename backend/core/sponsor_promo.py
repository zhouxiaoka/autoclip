"""Signed sponsor-promotion documents.

The packaged provider catalog stays local. A promotion document may reorder
ids whose register host this package already trusts, pick the new-user
default, and attach a status or a short notice. It cannot name an API host,
a key, a model, an unknown provider, or a register host this package has
not already trusted. Current bundled promotion is a separate list.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "autoclip.sponsor-promo/v1"
SCHEMA_V2 = "autoclip.sponsor-promo/v2"
SCHEMAS = frozenset({SCHEMA, SCHEMA_V2})
STATUSES = frozenset({"healthy", "fault", "out_of_service"})
LOCALES = frozenset({
    "zh", "en", "ja", "ko", "es", "fr", "pt", "ru", "id", "tr", "vi", "de",
    "it", "pl", "th", "nl", "uk", "hi", "ar",
})
PAYLOAD_KEYS = frozenset({
    "schema", "sequence", "issued_at", "expires_at", "min_app", "max_app",
    "rollback_of", "sponsors",
})
PAYLOAD_KEYS_V2 = PAYLOAD_KEYS | frozenset({"providers"})
SPONSOR_KEYS = frozenset({
    "id", "order", "new_user_default", "status", "notices",
    "register_url", "register_urls", "locales", "badge",
})
DYNAMIC_PROVIDER_KEYS = frozenset({
    "id", "name", "base_url", "register_url", "docs_url",
    "placeholder", "capabilities", "hint", "offer", "candidates", "icon_url", "group", "locales",
})
DYNAMIC_CAPABILITIES = frozenset({"language", "vision", "image", "video", "asr"})
DYNAMIC_CANDIDATE_ROLES = frozenset({"analysis", "vision", "asr", "image"})
DYNAMIC_GROUPS = frozenset({"popular", "recommended"})
MAX_DYNAMIC_PROVIDERS = 16
_DYNAMIC_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_LOCALE_CODE_RE = re.compile(r"^[a-z]{2,3}$")
_RESERVED_DYNAMIC_IDS = frozenset({"other", "compatible", "custom", "local", "default", "system"})
BUNDLED_CHOICES = ("apimart", "other")
BUNDLED_DEFAULT = "apimart"
# Status notices may name a built-in provider that is no longer promoted.
NOTICE_PROVIDER_IDS = frozenset({"api88", "infistar", "apimart", "cometapi", "novita", "poyo"})
_MAX_NOTICE = 240
_CLOCK_SKEW = timedelta(minutes=5)


def normalize_locale(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    code = value.strip().lower().split("-", 1)[0].split("_", 1)[0]
    return code if code in LOCALES else None


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


# Register hosts this package already trusts. Independent of whether the
# bundled catalog currently promotes the provider. A signature cannot add one.
_TRUSTED_REGISTER_HOSTS = {
    "api88": "88api.ai",
    "infistar": "www.infistar.cc",
    "cometapi": "www.cometapi.com",
    "novita": "novita.ai",
    "poyo": "poyo.ai",
}


def builtin_sponsor_hosts() -> dict[str, str]:
    """Provider id → registration hostname. No API base URL leaves this map."""
    from backend.core.provider_presets import get_provider, iter_providers

    hosts: dict[str, str] = {}
    for item in iter_providers():
        sponsor = item.sponsor or {}
        host = (urlparse(sponsor.get("register_url") or "").hostname or "").lower().rstrip(".")
        if host:
            hosts[item.id] = host
    for sponsor_id, host in _TRUSTED_REGISTER_HOSTS.items():
        if sponsor_id not in hosts and get_provider(sponsor_id):
            hosts[sponsor_id] = host
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


def _public_https_url(value: Any, *, allow_query: bool = True, max_len: int = 256) -> Optional[str]:
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url or len(url) > max_len:
        return None
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.fragment
        or (not allow_query and parsed.query)
        or port not in (None, 443)
        or not host
        or "." not in host
        or host == "localhost"
        or host.endswith((".localhost", ".local", ".internal", ".home.arpa"))
    ):
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    return url


def _clean_text(value: Any, *, max_len: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or len(text) > max_len:
        return None
    if any(ord(char) < 32 for char in text) or "<" in text or ">" in text or "://" in text.lower():
        return None
    return text


def _valid_locale_code(value: Any) -> bool:
    return isinstance(value, str) and bool(_LOCALE_CODE_RE.match(value))


def _parse_locale_list(raw: Any) -> Optional[tuple[list[str], list[str]]]:
    """Validate a non-empty list of unique ISO locale codes; return (all_valid, known_subset)."""
    if not isinstance(raw, list) or not raw:
        return None
    seen_locales: set[str] = set()
    all_valid: list[str] = []
    known: list[str] = []
    for entry in raw:
        if not _valid_locale_code(entry) or entry in seen_locales:
            return None
        seen_locales.add(entry)
        all_valid.append(entry)
        if entry in LOCALES:
            known.append(entry)
    return all_valid, known


def _localized_text(raw: Any, *, max_len: int, require_en: bool = False) -> Optional[dict[str, str]]:
    if isinstance(raw, str):
        cleaned = _clean_text(raw, max_len=max_len)
        return {"en": cleaned} if cleaned is not None else None
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, str] = {}
    for locale, text in raw.items():
        if not _valid_locale_code(locale):
            return None
        cleaned = _clean_text(text, max_len=max_len)
        if cleaned is None:
            return None
        if locale in LOCALES:
            out[locale] = cleaned
    if require_en and "en" not in out:
        return None
    return out


def _builtin_provider_ids() -> set[str]:
    from backend.core.provider_presets import load_provider_catalog

    return set(load_provider_catalog().providers) | set(NOTICE_PROVIDER_IDS) | set(_RESERVED_DYNAMIC_IDS)


def _providers(rows: Any) -> Optional[list[dict[str, Any]]]:
    if not isinstance(rows, list) or len(rows) > MAX_DYNAMIC_PROVIDERS:
        return None
    reserved = _builtin_provider_ids()
    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) - DYNAMIC_PROVIDER_KEYS:
            return None
        if not {"id", "name", "base_url", "register_url", "docs_url", "capabilities"} <= set(row):
            return None
        pid = row.get("id")
        if not isinstance(pid, str) or not _DYNAMIC_ID_RE.match(pid) or pid in reserved or pid in seen:
            return None
        name = _localized_text(row.get("name"), max_len=48, require_en=True)
        base_url = _public_https_url(row.get("base_url"), allow_query=False)
        register_url = _public_https_url(row.get("register_url"), allow_query=True)
        docs_url = _public_https_url(row.get("docs_url"), allow_query=True)
        if not name or not base_url or not register_url or not docs_url:
            return None
        if base_url.rstrip("/").lower().endswith("/chat/completions"):
            return None
        raw_caps = row.get("capabilities")
        if not isinstance(raw_caps, list) or not raw_caps:
            return None
        caps: list[str] = []
        for cap in raw_caps:
            if not isinstance(cap, str) or cap not in DYNAMIC_CAPABILITIES or cap in caps:
                return None
            caps.append(cap)
        placeholder = _clean_text(row.get("placeholder", "sk-…"), max_len=32)
        if placeholder is None:
            return None
        group = row.get("group", "popular")
        if not isinstance(group, str) or group not in DYNAMIC_GROUPS:
            return None
        hint: dict[str, str] = {}
        if "hint" in row and row["hint"] is not None:
            parsed_hint = _localized_text(row["hint"], max_len=_MAX_NOTICE, require_en=False)
            if parsed_hint is None:
                return None
            hint = parsed_hint
        offer: dict[str, str] = {}
        if "offer" in row and row["offer"] is not None:
            parsed_offer = _localized_text(row["offer"], max_len=64, require_en=False)
            if parsed_offer is None:
                return None
            offer = parsed_offer
        icon_url: Optional[str] = None
        if "icon_url" in row and row["icon_url"] is not None:
            icon_url = _public_https_url(row["icon_url"], allow_query=True)
            if icon_url is None:
                return None
        candidates: dict[str, list[str]] = {}
        if "candidates" in row and row["candidates"] is not None:
            raw_cand = row["candidates"]
            if not isinstance(raw_cand, dict) or set(raw_cand) - DYNAMIC_CANDIDATE_ROLES:
                return None
            for role, models in raw_cand.items():
                if not isinstance(models, list) or len(models) > 8:
                    return None
                clean_models: list[str] = []
                for model in models:
                    clean_model = _clean_text(model, max_len=128)
                    if clean_model is None:
                        return None
                    clean_models.append(clean_model)
                candidates[role] = clean_models
        provider_locales: Optional[list[str]] = None
        if "locales" in row and row["locales"] is not None:
            parsed_locales = _parse_locale_list(row["locales"])
            if parsed_locales is None:
                return None
            provider_locales = parsed_locales[1]
        seen.add(pid)
        item: dict[str, Any] = {
            "id": pid,
            "name": name,
            "base_url": base_url.rstrip("/"),
            "register_url": register_url,
            "docs_url": docs_url,
            "placeholder": placeholder,
            "capabilities": caps,
            "group": group,
        }
        if hint:
            item["hint"] = hint
        if offer:
            item["offer"] = offer
        if icon_url:
            item["icon_url"] = icon_url
        if candidates:
            item["candidates"] = candidates
        if provider_locales is not None:
            item["locales"] = provider_locales
        cleaned.append(item)
    return cleaned


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
    if not isinstance(payload, dict) or not required <= set(payload):
        return PromoDecision(False, "schema")
    schema = payload.get("schema")
    if schema not in SCHEMAS or not isinstance(payload.get("sponsors"), list):
        return PromoDecision(False, "schema")
    allowed_keys = PAYLOAD_KEYS_V2 if schema == SCHEMA_V2 else PAYLOAD_KEYS
    if set(payload) - allowed_keys:
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
    dynamic_providers: list[dict[str, Any]] = []
    if schema == SCHEMA_V2 and "providers" in payload:
        parsed_providers = _providers(payload["providers"])
        if parsed_providers is None:
            return PromoDecision(False, "providers")
        dynamic_providers = parsed_providers
    effective_hosts = dict(hosts)
    effective_allowed = set(notice_provider_ids())
    for dp in dynamic_providers:
        effective_allowed.add(dp["id"])
        host = (urlparse(dp["register_url"]).hostname or "").lower().rstrip(".")
        if host:
            effective_hosts[dp["id"]] = host
    sponsors = _sponsors(payload["sponsors"], effective_hosts, effective_allowed)
    if sponsors is None:
        return PromoDecision(False, "sponsors")
    cleaned = dict(payload)
    cleaned["sponsors"] = sponsors
    if dynamic_providers:
        cleaned["providers"] = dynamic_providers
    return PromoDecision(True, "ok", cleaned, None)


def _sponsors(rows: list, hosts: Mapping[str, str], allowed: set[str]) -> Optional[list]:
    if len(rows) > len(allowed):
        return None
    seen: set[str] = set()
    orders: set[int] = set()
    defaults_by_locale: dict[str, int] = {}
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
        raw_locales = row.get("locales")
        locales: Optional[list[str]] = None
        all_target_locales: Optional[list[str]] = None
        if raw_locales is not None:
            parsed_locales = _parse_locale_list(raw_locales)
            if parsed_locales is None:
                return None
            all_target_locales, locales = parsed_locales
        notices = row.get("notices", {})
        if not isinstance(notices, dict):
            return None
        text = {}
        for locale, notice in notices.items():
            if not _valid_locale_code(locale):
                return None
            cleaned_notice = _notice(notice)
            if cleaned_notice is None:
                return None
            if locale in LOCALES:
                text[locale] = cleaned_notice
        register_url = row.get("register_url")
        if register_url is not None and (not isinstance(register_url, str) or not _register_url(sponsor_id, register_url, hosts)):
            return None
        raw_register_urls = row.get("register_urls")
        localized_urls: dict[str, str] = {}
        if raw_register_urls is not None:
            if not isinstance(raw_register_urls, dict) or not raw_register_urls:
                return None
            for locale, url in raw_register_urls.items():
                if not _valid_locale_code(locale) or not isinstance(url, str) or not _register_url(sponsor_id, url, hosts):
                    return None
                if locale in LOCALES:
                    localized_urls[locale] = url
        raw_badge = row.get("badge")
        badge: Optional[Any] = None
        if "badge" in row and raw_badge is not None:
            if raw_badge == "":
                badge = ""
            else:
                parsed_badge = _localized_text(raw_badge, max_len=48, require_en=False)
                if parsed_badge is None:
                    return None
                if parsed_badge:
                    badge = parsed_badge
        if row.get("new_user_default") is True:
            if sponsor_id not in hosts:
                return None
            if all_target_locales is None:
                if defaults_by_locale:
                    return None
                defaults_by_locale["*"] = 1
                for locale in LOCALES:
                    defaults_by_locale[locale] = 1
            else:
                if defaults_by_locale.get("*"):
                    return None
                for locale in all_target_locales:
                    defaults_by_locale[locale] = defaults_by_locale.get(locale, 0) + 1
                    if defaults_by_locale[locale] > 1:
                        return None
        seen.add(sponsor_id)
        orders.add(order)
        item: dict[str, Any] = {
            "id": sponsor_id,
            "order": order,
            "status": status,
            "new_user_default": row.get("new_user_default") is True,
            "notices": text,
        }
        if register_url:
            item["register_url"] = register_url
        if localized_urls:
            item["register_urls"] = localized_urls
        if locales is not None:
            item["locales"] = locales
        if badge is not None:
            item["badge"] = badge
        cleaned.append(item)
    if len(orders) != len(cleaned):
        return None
    return cleaned


def _resolve_register_url(row: Mapping[str, Any], locale_key: Optional[str]) -> Optional[str]:
    localized = row.get("register_urls")
    if isinstance(localized, Mapping) and locale_key:
        direct = localized.get(locale_key)
        if isinstance(direct, str) and direct:
            return direct
        if locale_key != "zh":
            fallback_en = localized.get("en")
            if isinstance(fallback_en, str) and fallback_en:
                return fallback_en
    url = row.get("register_url")
    if isinstance(url, str) and url:
        return url
    if isinstance(localized, Mapping):
        for key in ("en", "zh"):
            candidate = localized.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def _locale_slice(visible: list[dict[str, Any]], locale_key: Optional[str]) -> dict[str, Any]:
    matched = [
        row for row in visible
        if row.get("locales") is None
        or (locale_key is None and bool(row["locales"]))
        or (locale_key is not None and locale_key in row["locales"])
    ]
    choices = [row["id"] for row in matched] + ["other"]
    marked = next((row["id"] for row in matched if row.get("new_user_default")), None)
    default = marked or (choices[0] if choices else "other")
    if default not in choices:
        default = "other"
    register_urls: dict[str, str] = {}
    for row in matched:
        resolved = _resolve_register_url(row, locale_key)
        if resolved:
            register_urls[row["id"]] = resolved
    return {
        "choices": choices,
        "default": default,
        "register_urls": register_urls,
    }


def promotion_view(payload: Mapping[str, Any], *, enabled: bool, source: str, locale: Optional[str] = None) -> dict:
    """New-user choices exclude paused and non-promoted providers. Status stays for saved users."""
    rows = sorted(payload.get("sponsors") or [], key=lambda item: item["order"])
    dynamic_providers = [dp for dp in (payload.get("providers") or []) if isinstance(dp, Mapping) and isinstance(dp.get("id"), str)]
    promoted = set(builtin_sponsor_hosts()) | {dp["id"] for dp in dynamic_providers}
    visible = [row for row in rows if row["status"] != "out_of_service" and row["id"] in promoted]
    locale_key = normalize_locale(locale)
    active = _locale_slice(visible, locale_key)
    view: dict[str, Any] = {
        "source": source,
        "enabled": enabled,
        "choices": active["choices"],
        "default": active["default"],
        "statuses": {row["id"]: row["status"] for row in rows},
        "notices": {row["id"]: row.get("notices") or {} for row in rows if row.get("notices")},
        "register_urls": active["register_urls"],
        "sequence": payload.get("sequence"),
    }
    if dynamic_providers:
        view["providers"] = dynamic_providers
    badges = {row["id"]: row["badge"] for row in rows if "badge" in row}
    if badges:
        view["badges"] = badges
    if any(row.get("locales") is not None or row.get("register_urls") for row in rows):
        view["by_locale"] = {
            loc: _locale_slice(visible, loc)
            for loc in sorted(LOCALES)
        }
    return view
