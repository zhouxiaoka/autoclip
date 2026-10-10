"""Queue shadow QA after the export is already completed.

The render thread only enqueues. A below-normal child process runs the checkers
and is killed, with its ffmpeg children, when the hard cap expires.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.core.sentry_setup import capture_studio_exception
from backend.services.render_limits import low_priority
from backend.services.studio.qa.report import HARD_CAP_S, QaCheckerError, skipped_report

logger = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='studio-qa')
_ROOT = str(Path(__file__).resolve().parents[4])


def schedule_after_render(project_id: str, draft, job_id: str, result):
    """Return the queued future, or None when QA is off. Never blocks on the checkers."""
    if os.environ.get('AUTOCLIP_QA_DISABLED') == '1':
        return None
    try:
        from backend.services.studio.qa.record import effective_mode
        from backend.services.studio.store import read
        features = (read(project_id).get('generation') or {}).get('features')
        if effective_mode(features) != 'shadow':
            return None
    except Exception as error:  # noqa: BLE001 - scheduling must not fail the export
        logger.warning('QA schedule skipped: %s', type(error).__name__)
        capture_studio_exception(QaCheckerError('runner'), 'qa')
        return None
    return _pool.submit(_execute, project_id, draft, job_id, result)


def drain(timeout: float = 30) -> None:
    """Wait until work already queued on the single QA thread has finished."""
    _pool.submit(lambda: None).result(timeout=timeout)


def _command() -> tuple[list[str], dict]:
    cmd, kwargs = low_priority([sys.executable, '-m', 'backend.services.studio.qa.worker'])
    if os.name == 'nt':
        flags = int(kwargs.get('creationflags') or 0)
        flags |= int(getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200))
        return cmd, {**kwargs, 'creationflags': flags}
    return cmd, {**kwargs, 'start_new_session': True}


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                capture_output=True, timeout=5, check=False,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        proc.kill()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def _popen() -> subprocess.Popen:
    cmd, kwargs = _command()
    env = os.environ.copy()
    env['PYTHONPATH'] = _ROOT + os.pathsep + env.get('PYTHONPATH', '')
    return subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env=env, **kwargs,
    )


def _spawn(payload: dict) -> dict:
    """Start the child, write the payload, and kill the process group past the cap."""
    proc = _popen()
    raw = json.dumps(payload, ensure_ascii=False).encode()
    try:
        out, _err = proc.communicate(input=raw, timeout=HARD_CAP_S)
    except subprocess.TimeoutExpired:
        _kill(proc)
        return skipped_report('timeout', round(HARD_CAP_S * 1000))
    return _finish(proc, out)


def _finish(proc: subprocess.Popen, out: bytes | None) -> dict:
    from backend.services.studio.models import QaReport
    if proc.returncode != 0 or not out:
        return skipped_report('error', 0)
    try:
        report = json.loads(out.decode())
        QaReport.model_validate(report)
    except (json.JSONDecodeError, UnicodeError, ValueError):
        return skipped_report('error', 0)
    return report


def _execute(project_id: str, draft, job_id: str, result) -> None:
    try:
        from backend.services.studio.qa.record import prepare, store_report
        payload = prepare(project_id, draft, job_id, result)
        if payload is None:
            return
        strategy = payload.pop('strategy_for_event', 'original')
        report = _spawn(payload)
        store_report(project_id, job_id, report, strategy)
    except Exception as error:  # noqa: BLE001 - the video is already saved
        logger.warning('QA record failed: %s', type(error).__name__)
        capture_studio_exception(QaCheckerError('runner'), 'qa')
