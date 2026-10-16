"""R16 #42: per-launch shutdown-intent secret from the desktop shell.

Read from the environment exactly once, as early as the ``backend`` package is imported, and
popped right away so no child process (ffmpeg, Whisper/SenseVoice, Playwright Chrome, Celery)
inherits it. Never logged, never sent anywhere; only compared in backend.api.internal.
"""
from __future__ import annotations

import os

TOKEN_ENV = 'AUTOCLIP_SHUTDOWN_TOKEN'
_token = ''


def capture() -> None:
    """Move the token from os.environ into this module (idempotent; a later set env wins)."""
    global _token
    value = os.environ.pop(TOKEN_ENV, None)
    if value is not None:
        _token = value


def get() -> str:
    capture()
    return _token


capture()
