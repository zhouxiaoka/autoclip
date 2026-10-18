"""1.5.7 / tell a clean quit/update from a lost parent or a crash when a run is recovered
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
/#99: one record per instance in ONE directory (``<data dir>/shutdown_markers/<instance>``), one
prune rule (run once at startup, in the background; never on the quit path). 's "shell got no 200 in time" is the same record with content ``unacked``, written by
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
import time
from pathlib import Path

SHUTDOWN_KINDS = ('clean', 'parent_lost', 'crash', 'unknown')
INTENT_KINDS = ('user_quit', 'update')
MARKER_KINDS = (*INTENT_KINDS, 'parent_lost')
_KEEP = 50
_lock = threading.Lock()
_consumed: dict[tuple[str, str], str] = {}


MARKER_DIR_ENV = 'AUTOCLIP_SHUTDOWN_MARKER_DIR'
_TMP_MAX_AGE = 3600.0


def _root() -> Path:
    """the desktop shell resolves the marker dir once and passes it in ``MARKER_DIR_ENV``;
    the shell writes ``unacked`` into that same dir. Without the shell (CLI/dev): the data dir."""
    configured = os.environ.get(MARKER_DIR_ENV, '').strip()
    if configured:
        return Path(configured).expanduser()
    from backend.core.path_utils import get_projects_directory
    return get_projects_directory().parent / 'shutdown_markers'


def mark(kind: str, instance: str | None = None) -> bool:
    """Atomically write this process's marker. Returns True once the marker is on disk.

    Runs on the quit path inside the shell's 3 s budget: it writes one file and never scans projects
    . Pruning happens once at startup (``prune_in_background``)."""
    if kind not in MARKER_KINDS:
        return False
    tmp = None
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
            tmp = None
        return True
    except Exception:  # noqa: BLE001 - a marker must never block shutdown
        return False
    finally:
        if tmp is not None:  # a failed write leaves no.tmp behind
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


def _referenced(instance: str) -> bool:
    try:
        from backend.services.studio.store import index_protects, reference_index
        return index_protects(reference_index(), instance)
    except Exception:  # noqa: BLE001 - unsure -> keep the record
        return True


def prune(root: Path | None = None) -> int:
    """Bound the record dir: keep the newest ``_KEEP`` records, never drop one an unrecovered project
    may still reference (studio.json or its reference ledger, ), and drop orphan ``.tmp`` files
    older than an hour. ONE project scan total. Returns how many files were removed."""
    try:
        root = root or _root()
        entries = [(p, p.stat().st_mtime) for p in root.iterdir() if p.is_file()]
    except OSError:
        return 0
    removed = 0
    now = time.time()
    for path, mtime in entries:
        if path.name.startswith('.') and path.name.endswith('.tmp') and now - mtime > _TMP_MAX_AGE:
            path.unlink(missing_ok=True)
            removed += 1
    records = sorted(((p, m) for p, m in entries if not p.name.startswith('.')), key=lambda item: item[1])
    candidates = records[:-_KEEP] if _KEEP else records
    if not candidates:
        return removed
    try:
        from backend.services.studio import store
    except Exception:  # noqa: BLE001 - cannot tell -> keep everything
        return removed
    # scan, re-check and delete under the SAME lock every project writer holds, so a
    # reference written after the scan can never land between the check and the unlink.
    with store.lock:
        try:
            index = store.reference_index()
        except Exception:  # noqa: BLE001 - cannot tell -> keep everything
            return removed
        for path, _mtime in candidates:
            if not store.index_protects(index, path.name):
                path.unlink(missing_ok=True)
                removed += 1
    return removed


def prune_in_background() -> threading.Thread:
    """Startup: prune off the request and quit paths (/#202)."""
    def run():
        try:
            prune()
        except Exception:  # noqa: BLE001 - cleanup only
            pass
    thread = threading.Thread(target=run, name='shutdown-marker-prune', daemon=True)
    thread.start()
    return thread


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
    return 'unknown'  # 'unacked' or anything unexpected


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
    """Delete a dead instance's record once no project references it any more.

    Call only after the caller's own terminal state was written."""
    if not instance or not re.fullmatch(r'[0-9a-f]{32}', str(instance)):
        return
    try:
        root = _root()
        from backend.services.studio import store
        with store.lock, _lock:  # lock order store -> marker, same as read/prune
            record = root / instance
            if (str(root), instance) in _consumed and record.exists() and not _referenced(instance):
                record.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 - cleanup only; _prune bounds leftovers
        pass
