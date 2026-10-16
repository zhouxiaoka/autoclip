"""Reap ffmpeg/ffprobe left behind by a previous AutoClip backend that was killed (kill -9, crash).

`mark_environment()` stamps `AUTOCLIP_BACKEND_OWNER=<pid>:<create_time>` into os.environ at startup,
so every ffmpeg the backend spawns inherits it. `reap_orphans()` later scans ffmpeg/ffprobe processes
and kills only those carrying a marker whose owner backend no longer runs (pid + create time, so PID
reuse is safe). Unmarked ffmpeg (the user's own, other apps) is never touched. Works with psutil on
macOS, Windows and Linux; processes whose environment cannot be read are skipped.
"""
from __future__ import annotations

import logging
import os
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

ENV = 'AUTOCLIP_BACKEND_OWNER'
TARGET_NAMES = ('ffmpeg', 'ffprobe')


def _owner_token(proc) -> str:
    return f'{proc.pid}:{proc.create_time():.3f}'


def mark_environment(environ=None) -> str:
    import psutil
    environ = os.environ if environ is None else environ
    token = _owner_token(psutil.Process())
    environ[ENV] = token
    return token


def _parse(token: str) -> Optional[tuple]:
    try:
        pid, created = token.split(':', 1)
        return int(pid), float(created)
    except (ValueError, AttributeError):
        return None


def _owner_alive(pid: int, created: float) -> bool:
    import psutil
    try:
        return abs(psutil.Process(pid).create_time() - created) < 0.01
    except psutil.NoSuchProcess:
        return False
    except psutil.Error:
        return True  # unclear: never kill


def _is_target(proc) -> bool:
    name = (proc.info.get('name') or '').lower()
    stem = name[:-4] if name.endswith('.exe') else name
    return stem in TARGET_NAMES


def find_orphans(processes: Optional[Iterable] = None) -> list:
    import psutil
    me = os.getpid()
    current = os.environ.get(ENV)
    orphans = []
    for proc in processes if processes is not None else psutil.process_iter(['name']):
        try:
            if proc.pid == me or not _is_target(proc):
                continue
            token = proc.environ().get(ENV)
        except psutil.Error:
            continue
        if not token or token == current:
            continue
        owner = _parse(token)
        if owner and not _owner_alive(*owner):
            orphans.append(proc)
    return orphans


LAST_RESULT: dict = {}


def reap_orphans(timeout: float = 3.0) -> int:
    """Kill orphaned AutoClip ffmpeg/ffprobe. Returns how many were found. Never raises.

    R11: outcomes are counted separately — exited (gone after kill), access_denied (kill
    refused), still_alive (kill sent but the process outlived the wait) — and logged so a
    support log tells "nothing to do" from "could not clean up".
    """
    global LAST_RESULT
    result = {'found': 0, 'exited': 0, 'access_denied': 0, 'still_alive': 0}
    try:
        import psutil
        orphans = find_orphans()
        result['found'] = len(orphans)
        signalled = []
        for proc in orphans:
            try:
                proc.kill()
                signalled.append(proc)
            except psutil.NoSuchProcess:
                result['exited'] += 1
            except psutil.AccessDenied:
                result['access_denied'] += 1
            except psutil.Error:
                result['still_alive'] += 1
        if signalled:
            gone, alive = psutil.wait_procs(signalled, timeout=timeout)
            result['exited'] += len(gone)
            result['still_alive'] += len(alive)
        if orphans:
            logger.warning(
                'Orphaned ffmpeg from a previous backend: found=%d exited=%d access_denied=%d still_alive=%d',
                result['found'], result['exited'], result['access_denied'], result['still_alive'])
        LAST_RESULT = result
        return result['found']
    except Exception as error:  # noqa: BLE001
        logger.warning('Orphan reaper unavailable: %s', type(error).__name__)
        LAST_RESULT = result
        return 0
