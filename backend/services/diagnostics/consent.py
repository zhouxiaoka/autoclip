"""Local diagnostics consent. Default off. This is not analytics and not model training."""
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
            "endpoint_configured": False,
        }


def _blank() -> Consent:
    return Consent(False, False, False, 0, CONSENT_TEXT_VERSION, None, None)


def _parse(raw: dict) -> Consent:
    diagnostics = raw.get("diagnostics") is True
    media = raw.get("media") is True and diagnostics
    full = raw.get("full_original") is True and media
    epoch = raw.get("epoch")
    epoch = epoch if isinstance(epoch, int) and 0 <= epoch <= 1_000_000 else 0
    at = raw.get("diagnostics_at") if isinstance(raw.get("diagnostics_at"), str) else None
    updated = raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else None
    version = raw.get("text_version") if isinstance(raw.get("text_version"), str) else ""
    return Consent(diagnostics, media, full, epoch, version or CONSENT_TEXT_VERSION, at, updated)


def load() -> Consent:
    try:
        raw = json.loads(consent_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _blank()
    return _parse(raw) if isinstance(raw, dict) else _blank()


def _atomic(consent: Consent) -> None:
    file = consent_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in consent.public().items() if k != "endpoint_configured"}
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
    """Any newly true scope requires informed consent. Narrowing or a new grant bumps epoch."""
    diagnostics = bool(diagnostics)
    media = bool(media) and diagnostics
    full_original = bool(full_original) and media
    if (diagnostics or media or full_original) and not informed:
        raise PermissionError("informed_required")
    with _LOCK:
        current = load()
        fresh_text = diagnostics and current.text_version != CONSENT_TEXT_VERSION
        narrowed = (
            (current.diagnostics and not diagnostics)
            or (current.media and not media)
            or (current.full_original and not full_original)
        )
        widened = (
            (diagnostics and not current.diagnostics)
            or (media and not current.media)
            or (full_original and not current.full_original)
            or fresh_text
        )
        epoch = current.epoch + (1 if narrowed or widened else 0)
        diagnostics_at = current.diagnostics_at
        if diagnostics and (not current.diagnostics or fresh_text):
            diagnostics_at = _now()
        nxt = Consent(
            diagnostics, media, full_original, epoch, CONSENT_TEXT_VERSION, diagnostics_at, _now(),
        )
        _atomic(nxt)
        return nxt
