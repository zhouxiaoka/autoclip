"""1.5.8: tell a crash from a clean quit/update when a run is recovered as service_restarted.

A graceful shutdown (project_cancellation.begin_shutdown) drops an empty file named after this
process's store.INSTANCE. On recovery the dead run's instance decides ``shutdown_kind``:
``clean`` (marker present), ``crash`` (markers exist but not this one), ``unknown`` (no instance
or no marker ever written, e.g. pre-1.5.8 runs). Enum only; nothing else leaves the box.
"""
from __future__ import annotations

import re
from pathlib import Path

SHUTDOWN_KINDS = ('clean', 'crash', 'unknown')
_KEEP = 50


def _root() -> Path:
    from backend.core.path_utils import get_projects_directory
    return get_projects_directory().parent / 'shutdown_markers'


def mark_clean(instance: str | None = None) -> None:
    try:
        if instance is None:
            from backend.services.studio.store import INSTANCE as instance
        root = _root()
        root.mkdir(parents=True, exist_ok=True)
        (root / instance).touch()
        markers = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime)
        for old in markers[:-_KEEP]:
            old.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001,S110 - a marker must never block shutdown
        return


def shutdown_kind(instance: str | None) -> str:
    if not instance or not re.fullmatch(r'[0-9a-f]{32}', str(instance)):
        return 'unknown'
    try:
        root = _root()
        if (root / instance).exists():
            return 'clean'
        return 'crash' if root.is_dir() and any(root.iterdir()) else 'unknown'
    except OSError:
        return 'unknown'
