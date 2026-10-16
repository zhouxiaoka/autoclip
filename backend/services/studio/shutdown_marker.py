"""1.5.8 / R16 #42: tell a clean quit/update from a lost parent or a crash when a run is recovered
as service_restarted.

- Normal quit / update: the desktop shell (Rust BackendManager::stop) calls
  POST /internal/shutdown-intent {kind: user_quit|update} with the per-launch local token and waits
  (<=3 s) for 200 before it kills the backend. The endpoint writes the marker atomically and
  returns; it never starts a shutdown itself.
- Parent loss (desktop app killed / crashed): parent_watch writes ``parent_lost``; it never
  overwrites a user_quit/update marker and is never reported as clean.
- begin_shutdown() writes nothing: it runs on both paths.

On the next start the dead run's instance marker is classified once (cached per process) and only
deleted by release() after the recovered terminal is on disk (R19 #99), so a failed write followed by
another restart still reads the same classification:
user_quit/update -> ``clean``, parent_lost -> ``parent_lost``, missing -> ``crash``,
unreadable or invalid content -> ``unknown`` (also for a missing/invalid instance id).
R19 #98: when the shell's intent got no 200 in time (slow disk, busy backend) it writes
``<AUTOCLIP_APP_DIR>/shutdown_unacked/<instance>`` before killing; a missing marker with that record is
``unknown`` (we cannot tell), never ``crash``. A marker that did land in time still wins.
Enum only; nothing else leaves the box.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

SHUTDOWN_KINDS = ('clean', 'parent_lost', 'crash', 'unknown')
INTENT_KINDS = ('user_quit', 'update')
MARKER_KINDS = (*INTENT_KINDS, 'parent_lost')
_KEEP = 50
_lock = threading.Lock()
_consumed: dict[tuple[str, str], str] = {}


def _root() -> Path:
    from backend.core.path_utils import get_projects_directory
    return get_projects_directory().parent / 'shutdown_markers'


def mark(kind: str, instance: str | None = None) -> bool:
    """Atomically write this process's marker. Returns True once the marker is on disk."""
    if kind not in MARKER_KINDS:
        return False
    try:
        if instance is None:
            from backend.services.studio.store import INSTANCE as instance
        root = _root()
        root.mkdir(parents=True, exist_ok=True)
        path = root / instance
        with _lock:
            if kind == 'parent_lost' and path.exists():
                try:
                    if path.read_text(encoding='ascii').strip() in INTENT_KINDS:
                        return True  # the shell announced the quit first; keep it
                except (OSError, UnicodeDecodeError):
                    pass
            tmp = root / f'.{instance}.{os.getpid()}.tmp'
            with open(tmp, 'w', encoding='ascii') as handle:
                handle.write(kind)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        markers = sorted((p for p in root.iterdir() if not p.name.startswith('.')), key=lambda p: p.stat().st_mtime)
        for old in markers[:-_KEEP]:
            old.unlink(missing_ok=True)
        return True
    except Exception:  # noqa: BLE001 - a marker must never block shutdown
        return False


def _unacked(instance: str) -> Path | None:
    app_dir = os.getenv('AUTOCLIP_APP_DIR')
    return Path(app_dir).expanduser() / 'shutdown_unacked' / instance if app_dir else None


def _classify(path: Path) -> str:
    if not path.exists():
        unacked = _unacked(path.name)
        try:
            if unacked is not None and unacked.exists():
                return 'unknown'
        except OSError:
            return 'unknown'
        return 'crash'
    try:
        content = path.read_text(encoding='ascii').strip()
    except (OSError, UnicodeDecodeError):
        return 'unknown'
    if content in INTENT_KINDS:
        return 'clean'
    if content == 'parent_lost':
        return 'parent_lost'
    return 'unknown'


def shutdown_kind(instance: str | None) -> str:
    if not instance or not re.fullmatch(r'[0-9a-f]{32}', str(instance)):
        return 'unknown'
    try:
        root = _root()
    except Exception:  # noqa: BLE001
        return 'unknown'
    key = (str(root), instance)
    with _lock:
        if key in _consumed:  # several projects can share one dead instance
            return _consumed[key]
        kind = _classify(root / instance)
        _consumed[key] = kind
    return kind


def release(instance: str | None) -> None:
    """R19 #99: delete a dead instance's marker; call only after its terminal state was written."""
    if not instance or not re.fullmatch(r'[0-9a-f]{32}', str(instance)):
        return
    try:
        root = _root()
        with _lock:
            if (str(root), instance) in _consumed:
                (root / instance).unlink(missing_ok=True)
                unacked = _unacked(instance)
                if unacked is not None:
                    unacked.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 - cleanup only; _KEEP pruning bounds leftovers
        pass
