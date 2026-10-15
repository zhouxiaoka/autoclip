"""Unified log redaction exit point: one Filter covers API, desktop, Celery, CLI."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import pytest

SECRET = "AIzaSyX2-FAKE-SECRET-never-real-0123456789"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models?key={SECRET}"


def _emit(filter_, msg, *args, exc=None):
    record = logging.LogRecord("t", logging.INFO, __file__, 1, msg, args,
                               (type(exc), exc, exc.__traceback__) if exc else None)
    filter_.filter(record)
    return logging.Formatter().format(record)


@pytest.mark.stdlib_only
def test_filter_redacts_gemini_key_url_in_msg_args_and_exception():
    from backend.core.log_redaction import RedactingFilter
    f = RedactingFilter()
    assert SECRET not in _emit(f, "GET %s failed", GEMINI_URL)
    assert SECRET not in _emit(f, f"HTTP Request: GET {GEMINI_URL} 401")
    try:
        raise RuntimeError(f"Client error '401' for url '{GEMINI_URL}'")
    except RuntimeError as e:
        out = _emit(f, "boom", exc=e)
    assert SECRET not in out and "?key=[REDACTED]" in out


@pytest.mark.stdlib_only
@pytest.mark.parametrize("raw,secret", [
    ("Authorization: Bearer sk-live-abcdef123456789", "abcdef123456789"),
    ("api_key=sk-proj-AAAABBBBCCCC", "AAAABBBBCCCC"),
    ('{"api_key": "plainsecret99"}', "plainsecret99"),
    ("model=sk-1234567890abcdef", "1234567890abcdef"),  # X3: key pasted in model field
    ("x-goog-api-key: AIzaSyFAKE1234567890", "FAKE1234567890"),
])
def test_filter_redacts_common_key_shapes(raw, secret):
    from backend.core.log_redaction import RedactingFilter
    assert secret not in _emit(RedactingFilter(), "%s", raw)


@pytest.mark.stdlib_only
def test_filter_keeps_safe_text():
    from backend.core.log_redaction import RedactingFilter
    out = _emit(RedactingFilter(), "封面生图 provider=%s model=%s", "gemini", "gemini-2.5-flash-image")
    assert out == "封面生图 provider=gemini model=gemini-2.5-flash-image"


_SCRIPT = """
import importlib, json, logging, sys
logging.basicConfig(level=logging.INFO, stream=sys.stderr, force=True)
for n in ("httpx", "httpcore", "openai"):
    logging.getLogger(n).setLevel(logging.NOTSET)
{setup}
logging.getLogger("backend.core.model_catalog").info("拉取失败 url=%s", {url!r})
logging.getLogger("backend.core.image_providers").warning("封面生图 model=%s", "sk-abcdefghijklmnop1234")
logging.getLogger("httpx").info("HTTP Request: GET %s", {url!r})
print(json.dumps({{n: logging.getLogger(n).level for n in ("httpx", "httpcore", "openai")}}))
"""


def _run(tmp_path, setup):
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT") if k in os.environ}
    env.update({
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
        "HOME": str(tmp_path), "AUTOCLIP_APP_DIR": str(tmp_path), "AUTOCLIP_DATA_DIR": str(tmp_path),
        "DATABASE_URL": "sqlite:///:memory:", "REDIS_URL": "memory://",
    })
    res = subprocess.run([sys.executable, "-c", _SCRIPT.format(setup=setup, url=GEMINI_URL)],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr[-2000:]
    return res


@pytest.mark.stdlib_only
@pytest.mark.parametrize("setup", [
    'importlib.import_module("backend.core.celery_app")',
    'importlib.import_module("backend.core.log_redaction").install_celery_log_redaction()\n'
    'from celery.signals import after_setup_logger\n'
    'h = logging.StreamHandler(sys.stderr); logging.getLogger().addHandler(h)\n'
    'after_setup_logger.send(sender=None, logger=logging.getLogger())',
], ids=["celery_import", "celery_signal_new_handler"])
def test_celery_path_redacts_and_quiets_sdk(tmp_path, setup):
    res = _run(tmp_path, setup)
    assert SECRET not in res.stderr
    assert "sk-abcdefghijklmnop1234" not in res.stderr
    assert "拉取失败" in res.stderr
    assert "HTTP Request" not in res.stderr  # httpx INFO suppressed (S1)
    assert json.loads(res.stdout.strip().splitlines()[-1]) == {n: logging.WARNING for n in ("httpx", "httpcore", "openai")}


def test_api_app_factory_installs_filter(tmp_path):
    res = _run(tmp_path, 'importlib.import_module("backend.app_factory").create_app(mode="web")')
    assert SECRET not in res.stderr
    assert "sk-abcdefghijklmnop1234" not in res.stderr
    assert "HTTP Request" not in res.stderr


@pytest.mark.stdlib_only
def test_every_entry_point_calls_unified_filter():
    root = Path(__file__).resolve().parents[1]
    for rel in ("app_factory.py", "desktop_main.py", "core/celery_app.py", "desktop_celery.py",
                "services/local_runner.py"):
        assert "install_" in (root / rel).read_text(encoding="utf-8") and \
            "log_redaction" in (root / rel).read_text(encoding="utf-8"), rel
