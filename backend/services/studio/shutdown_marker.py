"""1.5.8: tell a crash from a clean quit/update when a run is recovered as service_restarted.

R16 #42: the desktop shell (Rust BackendManager::stop) calls POST /api/v1/health/shutdown-intent
right before it kills the backend on a normal quit or update; that writes a ``clean`` marker named
after this process's store.INSTANCE. When the parent watch sees the desktop app vanish (kill -9,
crash) it writes ``parent_lost`` instead. begin_shutdown() writes nothing: it is hit on both paths.
On recovery the dead run's instance decides ``shutdown_kind``: the marker's kind, ``crash``
(markers exist but not this one), ``unknown`` (no instance or no marker ever written, e.g.
pre-1.5.8 runs). Enum only; nothing else leaves the box.
"""
from __future__ import annotations

import re
from pathlib import Path

SHUTDOWN_KINDS = ('clean', 'parent_lost', 'crash', 'unknown')
MARKER_KINDS = ('clean', 'parent_lost')
_KEEP = 50


def _root() -> Path:
    from backend.core.path_utils import get_projects_directory
    return get_projects_directory().parent / 'shutdown_markers'


def mark_clean(instance: str | None = None) -> None:
    mark('clean', instance)


def mark(kind: str, instance: str | None = None) -> None:
    if kind not in MARKER_KINDS:
        return
    try:
        if instance is None:
            from backend.services.studio.store import INSTANCE as instance
        root = _root()
        root.mkdir(parents=True, exist_ok=True)
        path = root / instance
        if kind == 'parent_lost' and path.exists() and path.read_text(encoding='ascii', errors='ignore').strip() in ('', 'clean'):
            return  # the shell announced a clean quit first; the watch only saw that quit
        path.write_text(kind, encoding='ascii')
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
        path = root / instance
        if path.exists():
            kind = path.read_text(encoding='ascii', errors='ignore').strip()
            return kind if kind in MARKER_KINDS else 'clean'  # pre-R16 markers were empty
        return 'crash' if root.is_dir() and any(root.iterdir()) else 'unknown'
    except OSError:
        return 'unknown'
