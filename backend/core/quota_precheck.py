"""1.5.9 3A: New API billing probe before paid Studio calls.

Fail-open: missing probe config, HTTP errors, timeouts, and non-JSON all become
``unavailable`` and production continues. Results cache for 60 seconds. Never
reports balance numbers — only the enum ``skipped|ok|exhausted|unavailable``.
"""
from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

RESULTS = frozenset({'skipped', 'ok', 'exhausted', 'unavailable'})
_CACHE_TTL = 60.0
_TIMEOUT = 3.0
_lock = threading.Lock()
_cache: dict[str, tuple[float, str]] = {}


def _preset_billing_probe(provider: str | None) -> str | None:
    if not provider:
        return None
    try:
        from backend.presets import load_provider_presets
        presets = load_provider_presets()
    except Exception:  # noqa: BLE001
        try:
            import json
            from pathlib import Path
            raw = json.loads((Path(__file__).resolve().parent.parent / 'presets' / 'provider_presets.json').read_text(encoding='utf-8'))
            presets = raw.get('providers') or {}
        except Exception:  # noqa: BLE001
            return None
    row = (presets.get(provider) if isinstance(presets, dict) else None) or {}
    probe = row.get('billing_probe')
    return probe if isinstance(probe, str) and probe else None


def _dashboard_base(base_url: str) -> str | None:
    """Strip a trailing /v1 (or similar) to reach the New API dashboard root."""
    if not base_url or not isinstance(base_url, str):
        return None
    raw = base_url.strip().rstrip('/')
    if not raw:
        return None
    parsed = urlparse(raw if '://' in raw else f'https://{raw}')
    if not parsed.netloc:
        return None
    path = parsed.path.rstrip('/')
    if path.endswith('/v1'):
        path = path[:-3]
    root = f'{parsed.scheme}://{parsed.netloc}{path}'.rstrip('/')
    return root or None


def _get_json(url: str, api_key: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'User-Agent': 'AutoClip-QuotaPrecheck/1.5.9',
        },
        method='GET',
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 - operator-configured HTTPS
        import json
        return json.loads(resp.read().decode('utf-8'))


def _probe_new_api(base_url: str, api_key: str) -> str:
    root = _dashboard_base(base_url)
    if not root or not api_key:
        return 'unavailable'
    today = date.today().isoformat()
    try:
        sub = _get_json(f'{root}/dashboard/billing/subscription', api_key)
        usage = _get_json(f'{root}/dashboard/billing/usage?start_date={today}&end_date={today}', api_key)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, TypeError, OSError) as error:
        logger.info('quota precheck unavailable: %s', type(error).__name__)
        return 'unavailable'
    except Exception as error:  # noqa: BLE001 - fail-open
        logger.info('quota precheck unavailable: %s', type(error).__name__)
        return 'unavailable'
    if not isinstance(sub, dict) or not isinstance(usage, dict):
        return 'unavailable'
    try:
        hard_limit = float(sub.get('hard_limit_usd'))
        total_usage_cents = float(usage.get('total_usage'))
    except (TypeError, ValueError):
        return 'unavailable'
    remaining = hard_limit - (total_usage_cents / 100.0)
    return 'exhausted' if remaining <= 0 else 'ok'


def check_quota(*, provider: str | None, base_url: str | None, api_key: str | None,
                force: bool = False) -> str:
    """Return a quota_precheck enum. Never raises. Never returns balance numbers."""
    probe = _preset_billing_probe(provider)
    if probe != 'new_api':
        return 'skipped'
    if not base_url or not api_key:
        return 'unavailable'
    cache_key = f'{provider}|{base_url.strip()}|{api_key[:8]}'
    now = time.monotonic()
    with _lock:
        hit = _cache.get(cache_key)
        if not force and hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
    result = _probe_new_api(base_url, api_key) if probe == 'new_api' else 'skipped'
    if result not in RESULTS:
        result = 'unavailable'
    with _lock:
        _cache[cache_key] = (now, result)
    return result


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def check_for_analysis_settings() -> tuple[str, dict]:
    """Probe using the currently selected analysis connection. Returns (enum, extras)."""
    extras: dict = {}
    try:
        from backend.services import ai_model_settings as ai_models
        settings = ai_models.load()
        binding = settings.analysis
        if binding is None:
            return 'skipped', extras
        connection = next((c for c in settings.connections if c.id == binding.connection_id), None)
        if connection is None:
            return 'skipped', extras
        result = check_quota(
            provider=getattr(connection, 'provider', None),
            base_url=getattr(connection, 'base_url', None),
            api_key=getattr(connection, 'api_key', None) or None,
        )
        extras['provider'] = getattr(connection, 'provider', None)
        return result, extras
    except Exception:  # noqa: BLE001
        return 'unavailable', extras


class QuotaExhausted(Exception):
    """Raised when precheck returns exhausted; mapped to provider_error / insufficient_quota."""

    def __init__(self, *, quota_precheck: str = 'exhausted'):
        super().__init__('insufficient_quota')
        self.quota_precheck = quota_precheck
        self.code = 'provider_error'
        self.upstream_error_type = 'insufficient_quota'
