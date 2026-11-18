"""Local diagnostics consent. Unset defaults on. This is not analytics and not model training."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.core.path_utils import get_data_directory
from backend.services.diagnostics.allowlist_data import CONSENT_TEXT_VERSION, PURPOSE

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def consent_path() -> Path:
    return get_data_directory() / "diagnostics" / "consent.json"


@dataclass(frozen=True)
class Consent:
    diagnostics: bool
    media: bool
    full_original: bool
    epoch: int
    text_version: str
    diagnostics_at: str | None
    updated_at: str | None
    notice_seen: bool = False
    persisted: bool = False
    unreadable: bool = False

    def public(self) -> dict:
        return {
            "diagnostics": self.diagnostics,
            "media": self.media,
            "full_original": self.full_original,
            "epoch": self.epoch,
            "text_version": self.text_version,
            "purpose": PURPOSE,
            "not_for_training": True,
            "diagnostics_at": self.diagnostics_at,
            "updated_at": self.updated_at,
            "notice_seen": self.notice_seen,
            "unreadable": self.unreadable,
            "endpoint_configured": False,
        }


def _unset() -> Consent:
    """No saved choice. Diagnostics and excerpts upload by default; the notice is only a disclosure."""
    return Consent(True, True, False, 0, CONSENT_TEXT_VERSION, None, None, False, False, False)


def _unreadable() -> Consent:
    """A present file that cannot be read is not treated as a fresh opt-in."""
    return Consent(False, False, False, 0, CONSENT_TEXT_VERSION, None, None, False, True, True)


def _parse(raw: dict) -> Consent:
    diagnostics = raw.get("diagnostics") is True
    media = raw.get("media") is True and diagnostics
    full = raw.get("full_original") is True and media
    epoch = raw.get("epoch")
    epoch = epoch if isinstance(epoch, int) and 0 <= epoch <= 1_000_000 else 0
    at = raw.get("diagnostics_at") if isinstance(raw.get("diagnostics_at"), str) else None
    updated = raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else None
    version = raw.get("text_version") if isinstance(raw.get("text_version"), str) else ""
    # Files written before notice_seen existed are explicit saved choices.
    notice_seen = raw.get("notice_seen") is True if "notice_seen" in raw else True
    return Consent(
        diagnostics, media, full, epoch, version or CONSENT_TEXT_VERSION, at, updated,
        notice_seen, True, False,
    )


def load() -> Consent:
    file = consent_path()
    if not file.exists():
        return _unset()
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _unreadable()
    return _parse(raw) if isinstance(raw, dict) else _unreadable()


def _stored(consent: Consent) -> dict:
    payload = consent.public()
    payload.pop("endpoint_configured", None)
    payload.pop("unreadable", None)
    return payload


def _atomic(consent: Consent) -> None:
    file = consent_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = _stored(consent)
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, file)
    try:
        os.chmod(file, 0o600)
    except OSError:
        pass


def update(*, diagnostics: bool, media: bool, full_original: bool, informed: bool) -> Consent:
    """A saved choice is explicit. Turning the main switch on or off changes the epoch."""
    _previous, nxt = commit(diagnostics=diagnostics, media=media, full_original=full_original, informed=informed)
    return nxt


def commit(*, diagnostics: bool, media: bool, full_original: bool, informed: bool) -> tuple[Consent, Consent]:
    """Read and write the choice under one lock. The first value is the state before the write."""
    diagnostics = bool(diagnostics)
    media = bool(media) and diagnostics
    full_original = bool(full_original) and media
    if (diagnostics or media or full_original) and not informed:
        raise PermissionError("informed_required")
    with _LOCK:
        current = load()
        if not current.persisted or current.unreadable:
            master_changed = current.diagnostics != diagnostics
            epoch = current.epoch + 1 if master_changed else current.epoch
            nxt = Consent(
                diagnostics, media, full_original, epoch, CONSENT_TEXT_VERSION,
                _now() if diagnostics else None, _now(), True, True, False,
            )
            _atomic(nxt)
            return current, nxt
        epoch = current.epoch + (1 if current.diagnostics != diagnostics else 0)
        diagnostics_at = None if not diagnostics else current.diagnostics_at
        if diagnostics and not current.diagnostics:
            diagnostics_at = _now()
        nxt = Consent(
            diagnostics, media, full_original, epoch, CONSENT_TEXT_VERSION,
            diagnostics_at, _now(), True, True, False,
        )
        _atomic(nxt)
        return current, nxt
