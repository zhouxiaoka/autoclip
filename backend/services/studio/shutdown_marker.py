"""1.5.8 / R16 #42: tell a clean quit/update from a lost parent or a crash when a run is recovered
as service_restarted.

- Normal quit / update: the desktop shell (Rust BackendManager::stop) calls
  POST /internal/shutdown-intent {kind: user_quit|update} with the per-launch local token and waits
  (<=3 s) for 200 before it kills the backend. The endpoint writes the marker atomically and
  returns; it never starts a shutdown itself.
- Parent loss (desktop app killed / crashed): parent_watch writes ``parent_lost``; it never
  overwrites a user_quit/update marker and is never reported as clean.
- begin_shutdown() writes nothing: it runs on both paths.

On the next start the dead run's instance record is classified (cached per process):
user_quit/update -> ``clean``, parent_lost -> ``parent_lost``, unacked -> ``unknown``, missing -> ``crash``,
unreadable or invalid content -> ``unknown`` (also for a missing/invalid instance id).
R20 #134/#99: one record per instance in ONE directory (``<data dir>/shutdown_markers/<instance>``), one
prune rule. R19 #98's "shell got no 200 in time" is the same record with content ``unacked``, written by
the shell only when no marker exists yet (a marker that landed in time wins). A record is released only
when no project still references that instance, so several projects of one dead instance all read the
same classification even if one of them fails to persist and the app restarts again. Pruning keeps the
newest ``_KEEP`` records and never drops one that an unrecovered project still references.
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
        _prune(root)
        return True
    except Exception:  # noqa: BLE001 - a marker must never block shutdown
        return False


def _referenced(instance: str) -> bool:
    try:
        from backend.services.studio.store import instance_referenced
        return instance_referenced(instance)
    except Exception:  # noqa: BLE001 - unsure -> keep the record
        return True


def _prune(root: Path) -> None:
    records = sorted((p for p in root.iterdir() if not p.name.startswith('.')), key=lambda p: p.stat().st_mtime)
    for old in records[:-_KEEP]:
        if not _referenced(old.name):
            old.unlink(missing_ok=True)


def _classify(path: Path) -> str:
    if not path.exists():
        return 'crash'
    try:
        content = path.read_text(encoding='ascii').strip()
    except (OSError, UnicodeDecodeError):
        return 'unknown'
    if content in INTENT_KINDS:
        return 'clean'
    if content == 'parent_lost':
        return 'parent_lost'
    return 'unknown'  # 'unacked' (R19 #98) or anything unexpected


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
    """Delete a dead instance's record once no project references it any more (R20 #99).

    Call only after the caller's own terminal state was written."""
    if not instance or not re.fullmatch(r'[0-9a-f]{32}', str(instance)):
        return
    try:
        root = _root()
        with _lock:
            if (str(root), instance) in _consumed and not _referenced(instance):
                (root / instance).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 - cleanup only; _prune bounds leftovers
        pass
