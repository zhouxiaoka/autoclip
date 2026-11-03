"""per-launch shutdown-intent secret from the desktop shell.

Read from the environment exactly once, as early as the ``backend`` package is imported, and
popped right away so no child process (ffmpeg, Whisper/SenseVoice, Playwright Chrome, Celery)
inherits it. Never logged, never sent anywhere; only compared in backend.api.internal.
"""
from __future__ import annotations

import os

TOKEN_ENV = 'AUTOCLIP_SHUTDOWN_TOKEN'
# per-launch instance id chosen by the shell (not a secret) so it can leave an "intent not
# acknowledged" record for exactly this process; popped too so child Python processes get their own.
INSTANCE_ENV = 'AUTOCLIP_INSTANCE_ID'
_token = ''
_instance = ''


def capture() -> None:
    """Move the token from os.environ into this module (idempotent; a later set env wins)."""
    global _token, _instance
    value = os.environ.pop(TOKEN_ENV, None)
    if value is not None:
        _token = value
    instance = os.environ.pop(INSTANCE_ENV, None)
    if instance is not None:
        _instance = instance


def instance_id() -> str | None:
    """The shell-assigned instance id (32 lowercase hex) or None."""
    import re
    capture()
    return _instance if re.fullmatch(r'[0-9a-f]{32}', _instance or '') else None


def get() -> str:
    capture()
    return _token


capture()
