"""Fail-closed, single-host admission shared by API and worker processes.

Reservations are deliberately not refunded: a failed/timeout request may be billed.
This limits operations, input bytes and reserved output tokens, not currency.
"""
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from pathlib import Path


class UsageDenied(ValueError):
    """Non-retryable local admission failure."""


def limit(name, default):
    try:
        value = int(os.getenv('AUTOCLIP_' + name, default))
        if value < 1:
            raise ValueError()
        return value
    except (TypeError, ValueError) as exc:
        raise UsageDenied('Invalid server usage-limit configuration') from exc


def security_directory():
    # Never resolve from client-editable settings or project/data directories.
    directory = Path(os.getenv('AUTOCLIP_SECURITY_DIR', str(Path.home() / '.autoclip-security'))).expanduser().resolve()
    if os.getenv('AUTOCLIP_DEPLOYMENT_HOSTS', '1') != '1':
        raise UsageDenied('Usage storage supports one host only; multi-host deployment is denied')
    from backend.core.path_utils import get_data_directory
    data = get_data_directory().resolve()
    if directory == data or data in directory.parents:
        raise UsageDenied('Usage storage must be outside the served data directory')
    return directory


@contextmanager
def transaction():
    db = None
    try:
        directory = security_directory()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        path = directory / 'usage.sqlite3'
        db = sqlite3.connect(path, timeout=5, isolation_level=None)
        os.chmod(path, 0o600)
        db.execute('PRAGMA busy_timeout=5000')
        db.execute('CREATE TABLE IF NOT EXISTS counters (key TEXT PRIMARY KEY, amount INTEGER NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS leases (id TEXT PRIMARY KEY, kind TEXT NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.execute('COMMIT')
    except UsageDenied:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise UsageDenied('Usage storage unavailable; operation denied') from exc
    finally:
        if db is not None:
            if db.in_transaction:
                db.rollback()
            db.close()


def reserve(counters=(), kind=None, capacity=None, lease_id=None):
    with transaction() as db:
        for key, amount, maximum in counters:
            row = db.execute('SELECT amount FROM counters WHERE key=?', (key,)).fetchone()
            if (row[0] if row else 0) + amount > maximum:
                raise UsageDenied('Usage allowance exhausted')
        if kind:
            if db.execute('SELECT count(*) FROM leases WHERE kind=?', (kind,)).fetchone()[0] >= capacity:
                raise UsageDenied('Outstanding operation limit reached')
            lease_id = lease_id or uuid.uuid4().hex
            db.execute('INSERT INTO leases VALUES (?,?)', (lease_id, kind))
        for key, amount, maximum in counters:
            db.execute('INSERT INTO counters VALUES (?,?) ON CONFLICT(key) DO UPDATE SET amount=amount+excluded.amount', (key, amount))
    return lease_id


def release(lease_id):
    with transaction() as db:
        db.execute('DELETE FROM leases WHERE id=?', (lease_id,))


def admit_http(principal, expensive=False):
    minute = int(time.time() // 60)
    maximum = limit('HTTP_PER_MINUTE', 120)
    counters = [(f'http:{minute}:global', 1, maximum), (f'http:{minute}:{principal}', 1, maximum)]
    if expensive:
        maximum = limit('EXPENSIVE_PER_MINUTE', 10)
        counters += [(f'expensive:{minute}:global', 1, maximum), (f'expensive:{minute}:{principal}', 1, maximum)]
    reserve(counters)


def reserve_paid(input_bytes=0, output_tokens=0, attempts=1, max_input=None):
    if input_bytes > (max_input or limit('PAID_INPUT_BYTES', 262144)) or input_bytes < 0:
        raise UsageDenied('Provider input is too large')
    if output_tokens > limit('OUTPUT_TOKENS', 8192) or output_tokens < 0:
        raise UsageDenied('Provider output allowance is too large')
    day = int(time.time() // 86400)
    return reserve([
        (f'paid:{day}', attempts, limit('DAILY_PAID_REQUESTS', 100)),
        (f'output:{day}', output_tokens * attempts, limit('DAILY_OUTPUT_TOKENS', 819200)),
        (f'input:{day}', input_bytes * attempts, limit('DAILY_INPUT_BYTES', 16777216)),
    ], 'paid', limit('CONCURRENT_PAID', 2))


@contextmanager
def paid_operation(input_bytes=0, output_tokens=0, attempts=1, max_input=None):
    lease = reserve_paid(input_bytes, output_tokens, attempts, max_input)
    try:
        yield
    finally:
        release(lease)


def guarded_llm(method):
    @wraps(method)
    def wrapped(self, prompt, input_data=None, **kwargs):
        cap = limit('OUTPUT_TOKENS', 8192)
        for key in ('max_tokens', 'max_output_tokens', 'max_completion_tokens'):
            if key in kwargs and kwargs[key] is not None:
                cap = min(cap, int(kwargs[key]))
        if cap < 1 or kwargs.get('n', 1) != 1 or kwargs.get('stream', False):
            raise UsageDenied('Unsupported unbounded provider request')
        kwargs.pop('max_output_tokens', None)
        kwargs.pop('max_completion_tokens', None)
        if kwargs.get('extra_body'):
            raise UsageDenied('Arbitrary provider body overrides are not allowed')
        kwargs['max_tokens'] = cap
        size = len(self._build_full_input(prompt, input_data).encode('utf-8'))
        # Pinned DashScope native SDK retries a dropped connection once.
        attempts = 2 if getattr(self, 'mode', None) == 'native' else 1
        with paid_operation(size, cap, attempts):
            return method(self, prompt, input_data, **kwargs)
    return wrapped


def paid_post(session, url, **kwargs):
    """Each image/OCR/audio HTTP attempt reserves independently, including retries."""
    retain_lease = kwargs.pop('_retain_lease', False)
    payload = kwargs.get('json', kwargs.get('data', {}))
    size = len(json.dumps(payload, default=str).encode('utf-8'))
    for item in (kwargs.get('files') or {}).values():
        stream = item[1] if isinstance(item, tuple) else item
        if hasattr(stream, 'fileno'):
            size += os.fstat(stream.fileno()).st_size
        elif isinstance(stream, bytes):
            size += len(stream)
    output = 0
    if isinstance(payload, dict):
        if str(payload.get("n", 1)) != "1":
            raise UsageDenied("Only one image/output per provider request")
        if "chat/completions" in url:
            output = min(int(payload.get("max_tokens") or 8192), limit("OUTPUT_TOKENS", 8192))
            payload["max_tokens"] = output
        elif "multimodal-generation" in url:
            output = limit("OUTPUT_TOKENS", 8192)
            payload.setdefault("parameters", {})["max_tokens"] = output
    lease = reserve_paid(size, output, max_input=limit("MEDIA_INPUT_BYTES", 16777216))
    try:
        response = session.post(url, **kwargs)
        return (response, lease) if retain_lease else response
    finally:
        if not retain_lease:
            release(lease)


def start_guarded_thread(*, target, args=(), daemon=True, name=None):
    """Bound work not submitted through Celery, including cover generation."""
    import threading
    lease = reserve(kind='queue', capacity=limit('OUTSTANDING_TASKS', 20))
    def run():
        try:
            target(*args)
        finally:
            release(lease)
    thread = threading.Thread(target=run, daemon=daemon, name=name)
    try:
        thread.start()
    except Exception:
        release(lease)
        raise
    return thread
