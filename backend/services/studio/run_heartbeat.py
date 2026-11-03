"""1.5.9: low-rate run heartbeat so a crash recovery can report stage/uptime/rss/disk buckets.

Writes ``<marker_dir>/<instance>.hb`` as JSON every 15s while producing (60s when idle).
Never takes ``store.lock`` and never runs on a request thread (A1-8). Sidecars are
cleaned by ``shutdown_marker.release`` / ``prune``.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

_INTERVAL_ACTIVE = 15.0
_INTERVAL_IDLE = 60.0
_STALE_S = 120.0

_lock = threading.Lock()
_stage = 'idle'
# N1: per-thread stack so nested _tracked(render) inside production cannot pop the outer stage to idle.
_active_stages: dict[int, list[str]] = {}
_started_at = time.monotonic()
_thread: threading.Thread | None = None
_stop = threading.Event()
_fault_handle = None  # kept open for faulthandler

_STAGES = frozenset({'screening', 'download', 'subtitle', 'analyze', 'render', 'idle'})
# Prefer later pipeline stages when several threads are active.
_STAGE_RANK = {'screening': 1, 'download': 2, 'subtitle': 3, 'analyze': 4, 'render': 5}


def _resolve_stage(active: dict[int, list[str]]) -> str:
    tops = [stack[-1] for stack in active.values() if stack]
    if not tops:
        return 'idle'
    return max(tops, key=lambda s: _STAGE_RANK.get(s, 0))


def set_stage(stage: str) -> None:
    """Workers call this at phase boundaries. Unknown values collapse to idle.

    Concurrent + nested (N1): each thread keeps a stack. ``set_stage(non-idle)`` pushes;
    ``set_stage('idle')`` pops one frame so a nested render finishing cannot blank the
    outer production stage on the same thread. Across threads, heartbeat reports the
    highest-ranked top-of-stack.
    """
    value = stage if stage in _STAGES else 'idle'
    tid = threading.get_ident()
    with _lock:
        global _stage
        stack = _active_stages.setdefault(tid, [])
        if value == 'idle':
            if stack:
                stack.pop()
            if not stack:
                _active_stages.pop(tid, None)
        else:
            stack.append(value)
        _stage = _resolve_stage(_active_stages)


def current_stage() -> str:
    with _lock:
        return _stage


def _rss_mb() -> int | None:
    """Current RSS in MiB. Prefer psutil (Win/macOS/Linux); fail-open → None."""
    try:
        import psutil
        return int(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))
    except Exception:  # noqa: BLE001 - heartbeat must not crash
        return None


def _free_disk_mb(root: Path) -> int | None:
    """Free disk MiB via shutil.disk_usage (works on Windows). Fail-open → None."""
    try:
        import shutil
        return int(shutil.disk_usage(root).free / (1024 * 1024))
    except Exception:  # noqa: BLE001
        return None


def _ffmpeg_children() -> int:
    try:
        import psutil
        count = 0
        for child in psutil.Process(os.getpid()).children(recursive=True):
            try:
                name = (child.name() or '').lower()
            except Exception:  # noqa: BLE001
                continue
            if 'ffmpeg' in name:
                count += 1
        return count
    except Exception:  # noqa: BLE001
        return 0


def uptime_bucket(uptime_s: float | None) -> str:
    if uptime_s is None:
        return 'unknown'
    if uptime_s < 60:
        return 'lt_1m'
    if uptime_s < 600:
        return 'lt_10m'
    if uptime_s < 3600:
        return 'lt_1h'
    return 'ge_1h'


def rss_bucket(rss_mb: int | None) -> str:
    if rss_mb is None:
        return 'unknown'
    if rss_mb < 1024:
        return 'lt_1g'
    if rss_mb < 2048:
        return 'lt_2g'
    if rss_mb < 4096:
        return 'lt_4g'
    return 'ge_4g'


def disk_bucket(free_mb: int | None) -> str:
    if free_mb is None:
        return 'unknown'
    if free_mb < 1024:
        return 'lt_1g'
    if free_mb < 5120:
        return 'lt_5g'
    return 'ge_5g'


def _payload(root: Path) -> dict:
    with _lock:
        stage = _stage
        uptime = time.monotonic() - _started_at
    return {
        'ts': time.time(),
        'uptime_s': round(uptime, 1),
        'rss_mb': _rss_mb(),
        'free_disk_mb': _free_disk_mb(root),
        'stage': stage,
        'ffmpeg_children': _ffmpeg_children(),
    }


def write_once(root: Path | None = None, instance: str | None = None) -> Path | None:
    """Atomically replace ``<instance>.hb``. Returns the path or None on skip/failure."""
    try:
        from backend.services.studio.shutdown_marker import _root
        from backend.services.studio import store
        root = root or _root()
        instance = instance or store.INSTANCE
        if not instance:
            return None
        root.mkdir(parents=True, exist_ok=True)
        path = root / f'{instance}.hb'
        tmp = root / f'.{instance}.{os.getpid()}.hb.tmp'
        body = json.dumps(_payload(root), separators=(',', ':'), ensure_ascii=True)
        with open(tmp, 'w', encoding='ascii') as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        return path
    except Exception:  # noqa: BLE001 - heartbeat must never break the app
        try:
            tmp.unlink(missing_ok=True)  # type: ignore[name-defined]
        except Exception:  # noqa: BLE001
            pass
        return None


def read_scene(marker_path: Path) -> dict:
    """Buckets + fault flag for the instance whose marker is ``marker_path``."""
    empty = {
        'crash_stage': 'unknown',
        'crash_uptime_bucket': 'unknown',
        'crash_rss_bucket': 'unknown',
        'crash_disk_bucket': 'unknown',
        'crash_has_fault': False,
    }
    hb = Path(str(marker_path) + '.hb')
    fault = Path(str(marker_path) + '.fault')
    out = dict(empty)
    try:
        if fault.is_file() and fault.stat().st_size > 0:
            out['crash_has_fault'] = True
    except OSError:
        pass
    if not hb.is_file():
        return out
    try:
        data = json.loads(hb.read_text(encoding='ascii'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return out
    if not isinstance(data, dict):
        return out
    stage = data.get('stage')
    out['crash_stage'] = stage if stage in _STAGES else 'unknown'
    out['crash_uptime_bucket'] = uptime_bucket(data.get('uptime_s') if isinstance(data.get('uptime_s'), (int, float)) else None)
    rss = data.get('rss_mb')
    out['crash_rss_bucket'] = rss_bucket(int(rss) if isinstance(rss, (int, float)) else None)
    disk = data.get('free_disk_mb')
    out['crash_disk_bucket'] = disk_bucket(int(disk) if isinstance(disk, (int, float)) else None)
    # Stale heartbeat (>120s) still counts as crash context; reason stays crash via missing marker.
    try:
        ts = float(data.get('ts') or 0)
        if ts and time.time() - ts > _STALE_S:
            pass  # keep buckets; restart_reason already crash when marker missing
    except (TypeError, ValueError):
        pass
    return out


def read_fault_frames(marker_path: Path) -> list[dict]:
    """Parse ``.fault`` into Sentry-like frames: filename (basename) + function + lineno only."""
    fault = Path(str(marker_path) + '.fault')
    frames = []
    try:
        text = fault.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return frames
    import re
    # faulthandler: File "path", line N in name
    for match in re.finditer(r'File "([^"]+)", line (\d+)(?: in (\S+))?', text):
        path_raw, lineno, func = match.group(1), match.group(2), match.group(3) or '<unknown>'
        filename = path_raw.replace('\\', '/').rsplit('/', 1)[-1]
        frames.append({'filename': filename, 'lineno': int(lineno), 'function': func, 'in_app': True})
    return frames


def enable_faulthandler(instance: str | None = None) -> None:
    """Point faulthandler at ``<marker_dir>/<instance>.fault`` (all threads)."""
    global _fault_handle
    try:
        import faulthandler
        from backend.services.studio.shutdown_marker import _root
        from backend.services.studio import store
        instance = instance or store.INSTANCE
        if not instance:
            return
        root = _root()
        root.mkdir(parents=True, exist_ok=True)
        path = root / f'{instance}.fault'
        handle = open(path, 'w', encoding='utf-8')  # noqa: SIM115 - kept for process life
        faulthandler.enable(file=handle, all_threads=True)
        _fault_handle = handle
    except Exception:  # noqa: BLE001
        pass


def start(instance: str | None = None) -> None:
    """Daemon heartbeat thread. Idempotent."""
    global _thread, _started_at
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _started_at = time.monotonic()
        _stop.clear()

        def run():
            while not _stop.is_set():
                write_once(instance=instance)
                stage = current_stage()
                _stop.wait(_INTERVAL_IDLE if stage == 'idle' else _INTERVAL_ACTIVE)

        _thread = threading.Thread(target=run, name='studio-run-heartbeat', daemon=True)
        _thread.start()


def stop() -> None:
    _stop.set()
