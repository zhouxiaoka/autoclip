"""Celery workers must suppress SDK request logs at startup."""

import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.stdlib_only
def test_celery_import_sets_sdk_loggers_to_warning(tmp_path):
    # A fresh process avoids inheriting desktop/web logging setup or cached imports.
    script = """
import importlib
import json
import logging

names = ("httpx", "httpcore", "openai")
logging.basicConfig(level=logging.INFO)
for name in names:
    logging.getLogger(name).setLevel(logging.NOTSET)
importlib.import_module("backend.core.celery_app")
print(json.dumps({name: logging.getLogger(name).level for name in names}))
"""
    env = {name: os.environ[name] for name in ("PATH", "SYSTEMROOT") if name in os.environ}
    env.update({
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
        "HOME": str(tmp_path),
        "AUTOCLIP_APP_DIR": str(tmp_path),
        "AUTOCLIP_DATA_DIR": str(tmp_path),
        "DATABASE_URL": "sqlite:///:memory:",
        "REDIS_URL": "memory://",
    })
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, "Celery import failed in the isolated process"
    levels = json.loads(result.stdout)
    assert levels == {name: logging.WARNING for name in ("httpx", "httpcore", "openai")}
