"""Bounded ffmpeg helpers. Failures stay inside the checker; paths never leave it."""
from __future__ import annotations

import json
import subprocess


class ProbeError(Exception):
    """A measurement could not be read. `reason` is a skip bucket, not a path."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def run(cmd: list[str], timeout: float, *, text: bool = False):
    try:
        return subprocess.run(
            cmd, capture_output=True, timeout=max(0.05, timeout), check=False, text=text,
        )
    except subprocess.TimeoutExpired:
        raise ProbeError('timeout') from None
    except OSError:
        raise ProbeError('unreadable') from None


def probe_json(path, timeout: float) -> dict:
    from backend.utils.ffmpeg_utils import get_ffprobe_path
    proc = run([
        get_ffprobe_path(), '-v', 'error', '-show_entries', 'stream=codec_type,start_time',
        '-of', 'json', str(path),
    ], timeout, text=True)
    if proc.returncode != 0 or not proc.stdout:
        raise ProbeError('unreadable')
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise ProbeError('unreadable') from error
    if not isinstance(data, dict):
        raise ProbeError('unreadable')
    return data
