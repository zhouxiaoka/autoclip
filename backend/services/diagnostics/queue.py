"""Bounded diagnostics queue in the data directory. It never writes studio.json."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.core.path_utils import get_data_directory

MAX_ITEMS = 32
TERMINAL = frozenset({"uploaded", "cancelled", "saved_local", "deleted", "failed"})
OPEN = frozenset({"queued", "uploading", "offline", "needs_endpoint"})
_LOCK = threading.Lock()
_CANNOT_BECOME = {
    "deleted": frozenset({"uploaded", "uploading", "queued", "offline", "saved_local", "needs_endpoint", "delete_pending"}),
    "delete_pending": frozenset({"uploaded", "uploading", "queued", "needs_endpoint", "saved_local", "offline"}),
    "saved_local": frozenset({"uploaded", "uploading", "queued"}),
    "cancelled": frozenset({"uploaded", "uploading", "queued"}),
    "uploaded": frozenset({"uploading", "queued", "offline"}),
    "failed": frozenset({"uploaded", "uploading"}),
}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return _now().isoformat()


def queue_path() -> Path:
    return get_data_directory() / "diagnostics" / "queue.json"


def _load() -> list[dict]:
    try:
        raw = json.loads(queue_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = raw.get("items") if isinstance(raw, dict) else None
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _save(items: list[dict]) -> None:
    file = queue_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps({"items": items[-MAX_ITEMS:]}, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, file)
    try:
        os.chmod(file, 0o600)
    except OSError:
        pass


def list_items() -> list[dict]:
    with _LOCK:
        return _load()


def by_key(key: str) -> dict | None:
    with _LOCK:
        return next((item for item in _load() if item.get("idempotency_key") == key), None)


def enqueue(item: dict) -> dict:
    """Insert or return the existing item with the same idempotency key. Drops oldest terminal rows."""
    with _LOCK:
        items = _load()
        key = item.get("idempotency_key")
        if isinstance(key, str):
            existing = next((row for row in items if row.get("idempotency_key") == key), None)
            if existing:
                return existing
        active = [row for row in items if row.get("status") not in TERMINAL]
        if len(active) >= MAX_ITEMS:
            item = {**item, "status": "failed", "error": "queue_full"}
            return item
        room = [row for row in items if row.get("status") in TERMINAL]
        terminal_budget = MAX_ITEMS - len(active) - 1
        keep_terminal = room[-terminal_budget:] if terminal_budget > 0 else []
        items = keep_terminal + active
        item.setdefault("version", 1)
        item.setdefault("disposition", "local" if item.get("save_local") is True else "upload")
        items.append(item)
        _save(items)
        return dict(item)


def get(item_id: str) -> dict | None:
    with _LOCK:
        return next((dict(row) for row in _load() if row.get("id") == item_id), None)


def update(item_id: str, *, if_version: int | None = None, if_status: frozenset[str] | set[str] | None = None, **values) -> dict | None:
    """Compare-and-set. A stale version or a forbidden terminal move changes nothing."""
    with _LOCK:
        items = _load()
        found = next((row for row in items if row.get("id") == item_id), None)
        if found is None:
            return None
        if if_version is not None and found.get("version") != if_version:
            return None
        if if_status is not None and found.get("status") not in if_status:
            return None
        new_status = values.get("status", found.get("status"))
        if new_status in _CANNOT_BECOME.get(found.get("status"), frozenset()):
            return None
        if values.get("disposition") not in (None, found.get("disposition")):
            return None
        found["version"] = int(found.get("version") or 0) + 1
        found.update(values)
        found["disposition"] = found.get("disposition") or "upload"
        _save(items)
        return dict(found)


def capability_path(item_id: str) -> Path:
    if not _ID.fullmatch(item_id):
        raise ValueError("capability_id")
    return get_data_directory() / "diagnostics" / "capabilities" / item_id


def write_capability(item_id: str, secret: str) -> None:
    """The secret lives outside the queue file, mode 0600, and is never copied into an export."""
    path = capability_path(item_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(secret, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def read_capability(item_id: str) -> str:
    try:
        return capability_path(item_id).read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return ""


def cancel_before(epoch: int) -> list[dict]:
    """Mark non-terminal items authorized under an older epoch as cancelled."""
    with _LOCK:
        items = _load()
        changed = []
        for row in items:
            if row.get("status") in TERMINAL or row.get("status") == "delete_pending":
                continue
            if isinstance(row.get("epoch"), int) and row["epoch"] < epoch:
                row["version"] = int(row.get("version") or 0) + 1
                remote = bool((row.get("upload") or {}).get("case_id") or row.get("case_id"))
                row["status"] = "delete_pending" if remote else "cancelled"
                row["error"] = "revoked"
                row["updated_at"] = now_iso()
                changed.append(dict(row))
        if changed:
            _save(items)
        return changed


def new_id() -> str:
    return "c-" + uuid.uuid4().hex


def backoff_seconds(attempts: int) -> int:
    return min(300, 2 ** max(0, min(attempts, 8)))


def due(item: dict, now: datetime | None = None) -> bool:
    raw = item.get("next_attempt_at")
    if not isinstance(raw, str) or not raw:
        return True
    try:
        when = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when <= (now or _now())


def schedule_retry(attempts: int, now: datetime | None = None) -> str:
    base = now or _now()
    return (base + timedelta(seconds=backoff_seconds(attempts))).isoformat()
