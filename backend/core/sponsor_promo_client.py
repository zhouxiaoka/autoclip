"""Fetch a signed sponsor promotion without touching saved settings or jobs.

Remote fetch stays off until the packaged config sets enabled, an https URL
and a raw Ed25519 public key together. A failure keeps the last verified
document, then the bundled chooser.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from backend.core.sponsor_promo import (
    builtin_sponsor_hosts,
    bundled_view,
    canonical_bytes,
    promotion_view,
    validate_payload,
    verify_signature,
)

logger = logging.getLogger(__name__)
STATE_NAME = "sponsor-promo-state.json"
BACKUP_NAME = "sponsor-promo-state.bak"
CHECKPOINT_NAME = "sponsor-promo-checkpoint.json"
_STARTUP_GAP_SECONDS = 60


@dataclass(frozen=True)
class PromoConfig:
    enabled: bool
    url: str
    public_key: str
    min_sequence: int = 0
    max_bytes: int = 65536
    timeout_seconds: float = 4
    refresh_seconds: float = 21600


def load_packaged_config() -> PromoConfig:
    from importlib.resources import files

    raw = json.loads(files("backend.presets").joinpath("sponsor_promo_config.json").read_text(encoding="utf-8"))
    return parse_config(raw)


def parse_config(raw: Any) -> PromoConfig:
    if not isinstance(raw, dict):
        return PromoConfig(False, "", "")
    enabled = raw.get("enabled") is True
    url = raw.get("url") if isinstance(raw.get("url"), str) else ""
    key = raw.get("public_key") if isinstance(raw.get("public_key"), str) else ""
    if not enabled or not _https_url(url) or not _public_key(key):
        return PromoConfig(False, "", "")
    return PromoConfig(
        enabled=True,
        url=url,
        public_key=key.strip(),
        min_sequence=raw.get("min_sequence") if type(raw.get("min_sequence")) is int and raw["min_sequence"] >= 0 else 0,
        max_bytes=raw.get("max_bytes") if type(raw.get("max_bytes")) is int and 1024 <= raw["max_bytes"] <= 65536 else 65536,
        timeout_seconds=float(raw["timeout_seconds"]) if isinstance(raw.get("timeout_seconds"), (int, float)) and 0 < float(raw["timeout_seconds"]) <= 10 else 4,
        refresh_seconds=float(raw["refresh_seconds"]) if isinstance(raw.get("refresh_seconds"), (int, float)) and float(raw["refresh_seconds"]) >= 60 else 21600,
    )


def _public_key(value: str) -> bool:
    import base64
    if not value or "PRIVATE" in value:
        return False
    try:
        raw = base64.b64decode(value.strip(), validate=True)
    except Exception:
        return False
    return len(raw) == 32


def _https_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return False
    return parsed.scheme == "https" and not parsed.username and bool(parsed.hostname) and port in (None, 443)


class SponsorPromoClient:
    def __init__(
        self,
        config: PromoConfig,
        *,
        data_dir: Path,
        app_version: str,
        http_get: Optional[Callable[..., Any]] = None,
        now: Optional[Callable[[], datetime]] = None,
        busy: Optional[Callable[[], bool]] = None,
    ):
        self.config = config
        self.data_dir = data_dir
        self.app_version = app_version
        self._http_get = http_get
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._busy = busy or _pipeline_busy
        self._lock = threading.Lock()
        self._inflight = False
        self._deferred = ""
        # Revision is process-local. Instance changes on restart so a higher
        # sequence is not dropped just because this counter went back to zero.
        self._instance = uuid.uuid4().hex
        self._revision = 0
        self._waiters: list = []
        self._last_attempt: Optional[datetime] = None
        from backend.core.project_cancellation import add_idle_listener
        add_idle_listener(self.note_generation_idle)

    def view(self, *, trigger: str = "", locale: Optional[str] = None) -> dict:
        if trigger:
            if self._busy():
                self._deferred = trigger
            else:
                self.schedule(self._deferred or trigger)
                self._deferred = ""
        state, health = self._read_security()
        shown = self._shown(state, health, locale=locale)
        shown["revision"] = self._revision
        shown["instance"] = self._instance
        shown["pending"] = self._inflight or bool(self._deferred)
        shown["enabled"] = self.config.enabled
        return shown

    def wait_for_change(self, revision: int, timeout: float, *, locale: Optional[str] = None) -> dict:
        """One bounded read of the accepted state. Not a polling loop."""
        limit = max(0.0, min(float(timeout or 0), 3.0))
        event = threading.Event()
        with self._lock:
            if self._revision != revision:
                changed = True
            else:
                changed = False
                self._waiters.append(event)
        if changed:
            return self.view(locale=locale)
        event.wait(limit)
        with self._lock:
            if event in self._waiters:
                self._waiters.remove(event)
        return self.view(locale=locale)

    def note_generation_idle(self) -> None:
        trigger = ""
        with self._lock:
            if not self._deferred or self._inflight:
                return
            trigger = self._deferred
            self._deferred = ""
        if trigger and not self._busy():
            self.schedule(trigger)

    def schedule(self, trigger: str) -> bool:
        if not self.config.enabled or self._busy():
            return False
        now = self._now()
        if trigger == "resume":
            gap = 0
        elif trigger == "interval":
            gap = self.config.refresh_seconds
        else:
            gap = _STARTUP_GAP_SECONDS
        with self._lock:
            if self._inflight:
                return False
            if self._last_attempt and (now - self._last_attempt).total_seconds() < gap:
                return False
            self._inflight = True
        threading.Thread(target=self._refresh, name="sponsor-promo", daemon=True).start()
        return True

    def refresh_sync(self) -> str:
        """Test and maintenance entry. Returns a reason code and never raises."""
        if not self.config.enabled:
            return "disabled"
        if self._busy():
            return "busy"
        return self._fetch()

    def _refresh(self) -> None:
        try:
            self._fetch()
        except Exception:
            logger.info("sponsor promo refresh failed")
        finally:
            with self._lock:
                self._inflight = False
            self._publish_revision()

    def _publish_revision(self) -> None:
        with self._lock:
            self._revision += 1
            waiters = list(self._waiters)
        for event in waiters:
            event.set()

    def _fetch(self) -> str:
        self._last_attempt = self._now()
        try:
            body = self._download()
        except Exception:
            logger.info("sponsor promo fetch failed")
            return "unreachable"
        if not isinstance(body, dict) or set(body) != {"payload", "signature"}:
            return "corrupt"
        payload = body.get("payload")
        signature = body.get("signature")
        if not isinstance(payload, dict) or not isinstance(signature, str):
            return "corrupt"
        if not verify_signature(payload, signature, self.config.public_key):
            return "unsigned"
        state, health = self._read_security()
        if health == "security_state" and not state:
            return "security_state"
        if self._exact_accepted(payload, signature, state):
            try:
                self._commit(self._document(payload, signature, state))
            except OSError:
                return "store"
            return "current"
        high = int((state or {}).get("high_water") or 0)
        accepted = (state or {}).get("accepted") if isinstance((state or {}).get("accepted"), dict) else {}
        decision = validate_payload(
            payload,
            app_version=self.app_version,
            now=self._now(),
            hosts=builtin_sponsor_hosts(),
            min_sequence=self.config.min_sequence,
            cache_sequence=high or None,
            current_sequence=accepted.get("sequence") if accepted else (high or None),
            retired=set((state or {}).get("retired") or []),
        )
        if not decision.ok or decision.payload is None:
            logger.info("sponsor promo rejected: %s", decision.reason)
            return decision.reason
        try:
            self._commit(self._document(payload, signature, state))
        except OSError:
            logger.info("sponsor promo store failed")
            return "store"
        return "ok"

    def _document(self, payload: dict, signature: str, state: Optional[dict]) -> dict:
        digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        previous = int((state or {}).get("high_water") or 0)
        return {
            "high_water": max(previous, int(payload["sequence"])),
            "retired": list((state or {}).get("retired") or []),
            "accepted": {
                "sequence": payload["sequence"],
                "digest": digest,
                "signature": signature,
                "payload": payload,
            },
        }

    def _exact_accepted(self, payload: dict, signature: str, state: Optional[dict]) -> bool:
        if not isinstance(state, dict):
            return False
        digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        accepted = state.get("accepted") if isinstance(state.get("accepted"), dict) else None
        if accepted:
            return (
                accepted.get("sequence") == payload.get("sequence")
                and accepted.get("signature") == signature
                and accepted.get("digest") == digest
            )
        return state.get("digest") == digest and state.get("sequence") == payload.get("sequence")

    def _download(self) -> Any:
        getter = self._http_get or _bounded_get
        return getter(self.config.url, timeout=self.config.timeout_seconds, max_bytes=self.config.max_bytes)

    def _shown(self, state: Optional[dict], health: str, *, locale: Optional[str] = None) -> dict:
        if health == "security_state" or not state or not isinstance(state.get("accepted"), dict):
            shown = bundled_view()
            if health == "security_state":
                shown["security_state"] = "error"
            return shown
        accepted = state["accepted"]
        payload = accepted.get("payload")
        signature = accepted.get("signature")
        sequence = accepted.get("sequence")
        if sequence in set(state.get("retired") or []) or sequence != accepted.get("sequence"):
            shown = bundled_view()
            shown["security_state"] = "error"
            return shown
        if not isinstance(payload, dict) or not isinstance(signature, str) or not verify_signature(payload, signature, self.config.public_key):
            shown = bundled_view()
            shown["security_state"] = "error"
            return shown
        decision = validate_payload(
            payload,
            app_version=self.app_version,
            now=self._now(),
            hosts=builtin_sponsor_hosts(),
            min_sequence=self.config.min_sequence,
            cache_sequence=None,
            retired=set(),
        )
        if not decision.ok or decision.payload is None:
            return bundled_view()
        shown = promotion_view(decision.payload, enabled=True, source="cache", locale=locale)
        return shown

    def _read_security(self) -> tuple[Optional[dict], str]:
        """Highest committed waterline wins. A stale backup cannot lower it."""
        checkpoint, checkpoint_reason = self._load_state(self.data_dir / CHECKPOINT_NAME)
        primary, primary_reason = self._load_state(self.data_dir / STATE_NAME)
        backup, backup_reason = self._load_state(self.data_dir / BACKUP_NAME)
        copies = [
            ("checkpoint", checkpoint, checkpoint_reason),
            ("primary", primary, primary_reason),
            ("backup", backup, backup_reason),
        ]
        usable = [(name, body) for name, body, reason in copies if reason == "ok" and isinstance(body, dict)]
        if not usable:
            if checkpoint_reason == primary_reason == backup_reason == "missing":
                return {"high_water": 0, "retired": [], "accepted": None}, "missing"
            return None, "security_state"
        authority = max(usable, key=lambda item: int(item[1].get("high_water") or 0))[1]
        high = int(authority.get("high_water") or 0)
        accepted = authority.get("accepted") if isinstance(authority.get("accepted"), dict) else None
        digest = accepted.get("digest") if accepted else authority.get("digest")
        current = None
        for _name, body in usable:
            if int(body.get("high_water") or 0) != high:
                continue
            body_accepted = body.get("accepted") if isinstance(body.get("accepted"), dict) else None
            body_digest = body_accepted.get("digest") if body_accepted else body.get("digest")
            if body_digest == digest and body_accepted:
                current = body
                break
        if current is None:
            held = {
                "high_water": high,
                "retired": list(authority.get("retired") or []),
                "accepted": None,
                "digest": digest,
                "sequence": accepted.get("sequence") if accepted else authority.get("sequence"),
                "signature": accepted.get("signature") if accepted else authority.get("signature"),
            }
            return held, "security_state"
        self._repair_copies(current, primary, primary_reason, backup, backup_reason, checkpoint, checkpoint_reason)
        if primary_reason == "ok" and primary == current:
            return current, "ok"
        if primary_reason == "ok" and isinstance(primary, dict) and (primary.get("accepted") or {}).get("digest") == digest and int(primary.get("high_water") or 0) == high:
            return primary, "ok"
        return current, "backup"

    def _load_state(self, path: Path) -> tuple[Optional[dict], str]:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None, "missing"
        except (OSError, UnicodeError):
            return None, "unreadable"
        try:
            raw = json.loads(text)
        except ValueError:
            return None, "truncated"
        if not self._state_shape(raw):
            return None, "malformed"
        return raw, "ok"

    def _state_shape(self, raw: Any) -> bool:
        if not isinstance(raw, dict):
            return False
        high = raw.get("high_water")
        retired = raw.get("retired", [])
        if type(high) is not int or high < 0 or not isinstance(retired, list):
            return False
        if any(type(item) is not int or item < 1 for item in retired):
            return False
        accepted = raw.get("accepted")
        if accepted is None:
            return high == 0 and retired == []
        if not isinstance(accepted, dict):
            return False
        sequence = accepted.get("sequence")
        signature = accepted.get("signature")
        payload = accepted.get("payload")
        digest = accepted.get("digest")
        if type(sequence) is not int or sequence < 1 or sequence in retired or sequence > high:
            return False
        if not isinstance(signature, str) or not isinstance(payload, dict) or not isinstance(digest, str):
            return False
        return hashlib.sha256(canonical_bytes(payload)).hexdigest() == digest

    def _repair_copies(self, good: dict, primary, primary_reason, backup, backup_reason, checkpoint, checkpoint_reason) -> None:
        """Best-effort redundancy repair. A write failure leaves the waterline untouched."""
        try:
            if checkpoint_reason != "ok" or checkpoint != good:
                self._atomic_write(self.data_dir / CHECKPOINT_NAME, good)
            if primary_reason != "ok" or primary != good:
                self._atomic_write(self.data_dir / STATE_NAME, good)
            if backup_reason != "ok" or backup != good:
                self._atomic_write(self.data_dir / BACKUP_NAME, good)
        except OSError:
            logger.info("sponsor promo redundancy repair failed")

    def _commit(self, body: dict) -> None:
        """Checkpoint first, then primary, then backup. Each write is fsynced before replace."""
        self._atomic_write(self.data_dir / CHECKPOINT_NAME, body)
        self._atomic_write(self.data_dir / STATE_NAME, body)
        self._atomic_write(self.data_dir / BACKUP_NAME, body)

    def _atomic_write(self, path: Path, body: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f"{path.name}.tmp"
        encoded = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        except OSError:
            os.close(fd)
            temporary.unlink(missing_ok=True)
            raise
        os.close(fd)
        os.replace(temporary, path)
        self._fsync_dir(path.parent)

    def _fsync_dir(self, directory: Path) -> None:
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _pipeline_busy() -> bool:
    """Readonly process-wide generation state. A ContextVar on this request is not enough."""
    try:
        from backend.core.project_cancellation import any_worker_bound
        return any_worker_bound()
    except Exception:
        return True


def _bounded_get(url: str, *, timeout: float, max_bytes: int) -> Any:
    import requests

    response = requests.get(
        url,
        timeout=timeout,
        allow_redirects=False,
        stream=True,
        headers={"Accept": "application/json"},
    )
    try:
        if response.status_code != 200 or response.is_redirect or response.is_permanent_redirect:
            raise OSError("sponsor promo was not a direct 200")
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=4096):
            size += len(chunk)
            if size > max_bytes:
                raise OSError("sponsor promo exceeded the size cap")
            chunks.append(chunk)
        return json.loads(b"".join(chunks).decode("utf-8"))
    finally:
        response.close()


_client: Optional[SponsorPromoClient] = None
_client_lock = threading.Lock()


def get_client() -> SponsorPromoClient:
    global _client
    with _client_lock:
        if _client is None:
            from backend import __version__
            from backend.core.path_utils import get_data_directory

            _client = SponsorPromoClient(load_packaged_config(), data_dir=get_data_directory(), app_version=__version__)
        return _client


def current_view(*, trigger: str = "settings") -> dict:
    return get_client().view(trigger=trigger)
