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

``restart_reason`` is the finer value stored on a recovered generation. It keeps the shell
intent that ``shutdown_kind`` folds into ``clean``: ``user_quit`` / ``update`` stay themselves;
a missing marker is ``crash``; ``parent_lost`` (shell killed or crashed) is ``crash`` because
the analytics set has no separate kill value (``shutdown_kind`` still records ``parent_lost``);
``unacked``, unreadable, invalid content, and a missing/invalid instance id stay ``unknown``.
``unacked`` is not promoted to ``crash``.
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
_restart_cached: dict[tuple[str, str], str] = {}
RESTART_REASONS = ('user_quit', 'update', 'unknown', 'crash')
CRASH_EXITS = (
    'access_violation', 'stack_overflow', 'heap_corruption', 'abort',
    'sigsegv', 'sigkill', 'oom', 'nonzero_other', 'zero', 'unknown',
)
CRASH_STAGES = ('screening', 'download', 'subtitle', 'analyze', 'render', 'idle', 'unknown')
CRASH_UPTIME_BUCKETS = ('lt_1m', 'lt_10m', 'lt_1h', 'ge_1h', 'unknown')
CRASH_RSS_BUCKETS = ('lt_1g', 'lt_2g', 'lt_4g', 'ge_4g', 'unknown')
CRASH_DISK_BUCKETS = ('lt_1g', 'lt_5g', 'ge_5g', 'unknown')
_crash_exit_cached: dict[tuple[str, str], str] = {}
_crash_scene_cached: dict[tuple[str, str], dict] = {}

# Windows NTSTATUS / Unix signal → enum. Raw numbers never leave the box.
_EXIT_ENUM = {
    0xC0000005: 'access_violation',  # 3221225477
    0xC00000FD: 'stack_overflow',    # 3221225725
    0xC0000374: 'heap_corruption',   # 3221226356
    # N5: bare exit:3 is not SIGABRT (that is signal:6 / exit:134). Keep 3 → nonzero_other.
    137: 'oom',  # 128 + SIGKILL on Linux OOM-kill convention
}
_SIGNAL_ENUM = {
    6: 'abort',    # SIGABRT
    9: 'sigkill',  # SIGKILL
    11: 'sigsegv', # SIGSEGV
}


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
    # B7: heartbeat / fault sidecars are not marker records; never prune them as such.
    records = sorted(
        (
            (p, m) for p, m in entries
            if not p.name.startswith('.')
            and not p.name.endswith('.hb')
            and not p.name.endswith('.fault')
        ),
        key=lambda item: item[1],
    )
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
                for side in _sidecar_paths(root, path.name):
                    # Only drop sidecars when the instance itself is unprotected.
                    if side.exists() and not store.index_protects(index, side.name):
                        side.unlink(missing_ok=True)
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


def _marker_text(path: Path) -> str | None:
    """Marker body, ``''`` when unreadable, ``None`` when the file is missing."""
    if not path.exists():
        return None
    try:
        return path.read_text(encoding='ascii').strip()
    except (OSError, UnicodeDecodeError):
        return ''


def _kind_from_text(content: str | None) -> str:
    if content is None:
        return 'crash'
    if content in INTENT_KINDS:
        return 'clean'
    if content == 'parent_lost':
        return 'parent_lost'
    if content.startswith('exit:') or content.startswith('signal:'):
        return 'crash'
    return 'unknown'  # 'unacked' or anything unexpected


def _restart_from_text(content: str | None) -> str:
    if content is None:
        return 'crash'
    if content in INTENT_KINDS:
        return content
    if content == 'parent_lost':
        return 'crash'  # shell killed/crashed; shutdown_kind keeps parent_lost
    if content is not None and (content.startswith('exit:') or content.startswith('signal:')):
        return 'crash'
    return 'unknown'  # unacked, unreadable, invalid — not a crash


def crash_exit_from_text(content: str | None) -> str:
    """Map shell exit/signal marker text to a crash_exit enum. Never returns a raw number."""
    if content is None:
        return 'unknown'
    if content.startswith('exit:'):
        raw = content[5:].strip()
        if raw == 'unknown' or raw == '':
            return 'unknown'
        try:
            code = int(raw, 10)
        except ValueError:
            return 'unknown'
        if code in _EXIT_ENUM:
            return _EXIT_ENUM[code]
        if code == 0:
            return 'zero'
        # SIGABRT often surfaces as exit status 134 (128+6) on Unix without signal().
        if code == 134:
            return 'abort'
        if code == 139:  # 128+11 SIGSEGV
            return 'sigsegv'
        return 'nonzero_other'
    if content.startswith('signal:'):
        raw = content[7:].strip()
        try:
            sig = int(raw, 10)
        except ValueError:
            return 'unknown'
        return _SIGNAL_ENUM.get(sig, 'nonzero_other')
    if content == 'parent_lost':
        return 'unknown'  # no exit code from the backend process itself
    return 'unknown'


def _remember(key: tuple[str, str], path: Path) -> tuple[str, str]:
    content = _marker_text(path)
    kind, reason = _kind_from_text(content), _restart_from_text(content)
    _consumed[key] = kind
    _restart_cached[key] = reason
    _crash_exit_cached[key] = crash_exit_from_text(content) if reason == 'crash' else 'unknown'
    return kind, reason


def _instance_key(instance: str | None):
    if not instance or not re.fullmatch(r'[0-9a-f]{32}', str(instance)):
        return None
    try:
        root = _root()
    except Exception:  # noqa: BLE001
        return None
    return (str(root), instance), root / instance


def shutdown_kind(instance: str | None) -> str:
    located = _instance_key(instance)
    if located is None:
        return 'unknown'
    key, path = located
    with _lock:
        if key in _consumed:  # several projects can share one dead instance
            return _consumed[key]
        kind, _reason = _remember(key, path)
    return kind


def restart_reason(instance: str | None) -> str:
    """Why a recovered ``service_restarted`` run stopped. See the module note.

    Cached with ``shutdown_kind`` so a later project of the same dead instance still
    sees the reason after ``release`` deletes the marker file.
    """
    located = _instance_key(instance)
    if located is None:
        return 'unknown'
    key, path = located
    with _lock:
        if key in _restart_cached:
            return _restart_cached[key]
        if key in _consumed:
            # shutdown_kind was seeded without a reason; keep that kind, read the marker for this field.
            reason = _restart_from_text(_marker_text(path))
            _restart_cached[key] = reason
            return reason
        _kind, reason = _remember(key, path)
    return reason


def crash_exit(instance: str | None) -> str:
    """Enum-only exit classification for a crash restart. Safe when no marker."""
    located = _instance_key(instance)
    if located is None:
        return 'unknown'
    key, path = located
    with _lock:
        if key in _crash_exit_cached:
            return _crash_exit_cached[key]
        if key not in _restart_cached:
            _remember(key, path)
        return _crash_exit_cached.get(key, 'unknown')


def crash_scene(instance: str | None) -> dict:
    """Buckets from the dead instance's heartbeat / .fault. Missing files → unknown / false."""
    located = _instance_key(instance)
    empty = {
        'crash_stage': 'unknown',
        'crash_uptime_bucket': 'unknown',
        'crash_rss_bucket': 'unknown',
        'crash_disk_bucket': 'unknown',
        'crash_has_fault': False,
    }
    if located is None:
        return dict(empty)
    key, path = located
    with _lock:
        if key in _crash_scene_cached:
            return dict(_crash_scene_cached[key])
    try:
        from backend.services.studio import run_heartbeat
        scene = run_heartbeat.read_scene(path)
    except Exception:  # noqa: BLE001 - scene must never block recovery
        scene = dict(empty)
    with _lock:
        _crash_scene_cached[key] = dict(scene)
    return dict(scene)


def crash_fields(instance: str | None) -> dict:
    """Fields to attach on a service_restarted recovery when restart_reason is crash."""
    reason = restart_reason(instance)
    if reason != 'crash':
        return {}
    fields = {'crash_exit': crash_exit(instance), **crash_scene(instance)}
    # crash_has_fault is bool; keep it for store / Sentry, not for event enums that require strings.
    return fields


def _sidecar_paths(root: Path, instance: str) -> list[Path]:
    return [root / f'{instance}.hb', root / f'{instance}.fault']


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
                for side in _sidecar_paths(root, instance):
                    side.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 - cleanup only; _prune bounds leftovers
        pass
