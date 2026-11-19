"""Bounded diagnostics queue in the data directory. It never writes studio.json."""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
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


def _same_command(item: dict, key: str, disposition: str) -> bool:
    # Pre-upgrade rows may only have save_local. Keep their remote keys replayable.
    target = item.get("disposition") or ("local" if item.get("save_local") else "upload")
    if disposition == "local" and item.get("status") in {"deleted", "failed", "cancelled"}:
        return False
    return item.get("idempotency_key") == key and target == disposition


def by_key(key: str, disposition: str = "upload") -> dict | None:
    with _LOCK:
        return next((item for item in _load() if _same_command(item, key, disposition)), None)


def enqueue(item: dict) -> dict:
    """Insert or return the existing item with the same idempotency key. Drops oldest terminal rows."""
    with _LOCK:
        items = _load()
        key = item.get("idempotency_key")
        if isinstance(key, str):
            disposition = item.get("disposition") or ("local" if item.get("save_local") else "upload")
            existing = next((row for row in items if _same_command(row, key, disposition)), None)
            if existing:
                return existing
        active = [row for row in items if row.get("status") not in TERMINAL or row.get("inflight_create") is True]
        if len(active) >= MAX_ITEMS:
            item = {**item, "status": "failed", "error": "queue_full"}
            return item
        room = [row for row in items if row.get("status") in TERMINAL and row.get("inflight_create") is not True]
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
        original_upload = values.get("upload") if isinstance(values.get("upload"), dict) else None
        if original_upload is not None:
            values = dict(values)
            stored_upload = dict(original_upload)
            stored_upload["objects"] = _without_upload_grants(original_upload.get("objects"))
            values["upload"] = stored_upload
        found.update(values)
        found["disposition"] = found.get("disposition") or "upload"
        _save(items)
        returned = dict(found)
        if original_upload is not None:
            returned["upload"] = original_upload
        return returned


def _without_upload_grants(uploads) -> list:
    """Keep part geometry. Presigned URLs and signed headers stay in memory for this process only."""
    cleaned = []
    for entry in uploads or []:
        if not isinstance(entry, dict):
            continue
        parts = []
        for part in entry.get("parts") or []:
            if isinstance(part, dict):
                parts.append({key: part.get(key) for key in ("number", "offset", "length")})
        cleaned.append({
            "object_id": entry.get("object_id"), "role": entry.get("role"), "bytes": entry.get("bytes"),
            "already_complete": entry.get("already_complete"), "parts": parts,
        })
    return cleaned


def attach_remote_case(item_id: str, *, case_id: str, uploads: list, endpoint: str, expires_at: str = "") -> dict | None:
    """Record a remote case that a create call already produced.

    A premature ``deleted`` or ``cancelled`` mark cannot drop this identity.
    The generic status guard stays in place; this is the only writer that may
    reopen cleanup for that in-flight create. Confirmed deletion of the same
    case, and an uploaded row, are left unchanged.
    """
    if not case_id:
        return None
    with _LOCK:
        items = _load()
        found = next((row for row in items if row.get("id") == item_id), None)
        if found is None:
            return None
        existing = found.get("case_id") or (found.get("upload") or {}).get("case_id")
        if isinstance(existing, str) and existing and existing != case_id:
            return dict(found)
        if found.get("status") == "deleted" and existing == case_id:
            return dict(found)
        if found.get("status") == "uploaded":
            return dict(found)
        session = dict(found.get("upload") or {}) if isinstance(found.get("upload"), dict) else {}
        session["case_id"] = case_id
        session["objects"] = _without_upload_grants(uploads)
        live_objects = uploads
        if expires_at:
            session["expires_at"] = expires_at
        found["refresh_plan"] = False
        session.setdefault("done", [])
        session.setdefault("acked", [])
        found["upload"] = session
        found["case_id"] = case_id
        if isinstance(endpoint, str) and endpoint and not found.get("cleanup_endpoint"):
            found["cleanup_endpoint"] = endpoint
        found["inflight_create"] = False
        if found.get("status") in {"deleted", "cancelled", "delete_pending"}:
            found["status"] = "delete_pending"
            found["error"] = "delete_retry"
        elif found.get("status") in OPEN or found.get("status") == "uploading":
            found["status"] = "uploading"
        found["version"] = int(found.get("version") or 0) + 1
        found["updated_at"] = now_iso()
        _save(items)
        returned = dict(found)
        live = dict(session)
        live["objects"] = live_objects
        returned["upload"] = live
        return returned


def capability_path(item_id: str) -> Path:
    if not _ID.fullmatch(item_id):
        raise ValueError("capability_id")
    return get_data_directory() / "diagnostics" / "capabilities" / item_id


def _write_secret(path: Path, secret: str) -> None:
    """Secrets live outside the queue and exports, with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(secret)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def write_capability(item_id: str, secret: str) -> None:
    _write_secret(capability_path(item_id), secret)


def recovery_token(item_id: str, *, create: bool = False) -> str:
    # Use the same validated ID, but a separate credential file. The recovery
    # token must survive a lost response (before the remote capability is known).
    path = capability_path(item_id).parent.parent / "recovery" / item_id
    with _LOCK:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            value = ""
        if not value and create:
            value = secrets.token_urlsafe(32)
            _write_secret(path, value)
        return value


def read_capability(item_id: str) -> str:
    try:
        return capability_path(item_id).read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return ""


def cancel_with_roles(roles: set[str]) -> list[dict]:
    """Stop queued work that still carries a media role the user just turned off."""
    with _LOCK:
        items = _load()
        changed = []
        for row in items:
            if (row.get("status") in TERMINAL and not row.get("inflight_create")) or row.get("status") == "delete_pending":
                continue
            present = {entry.get("role") for entry in (row.get("files") or []) if isinstance(entry, dict)}
            if not present.intersection(roles):
                continue
            row["version"] = int(row.get("version") or 0) + 1
            remote = bool(
                (row.get("upload") or {}).get("case_id") or row.get("case_id") or row.get("inflight_create") is True
            )
            row["status"] = "delete_pending" if remote else "cancelled"
            row["error"] = "revoked"
            row["updated_at"] = now_iso()
            changed.append(dict(row))
        if changed:
            _save(items)
        return changed


def _owned(kind: str, item_id: str) -> Path | None:
    if not _ID.fullmatch(item_id) or kind not in {"excerpts", "exports", "capabilities", "recovery"}:
        return None
    base = (get_data_directory() / "diagnostics" / kind).resolve()
    target = base / item_id
    if target.is_symlink():
        target.unlink()
        return None
    if not target.exists():
        return None
    resolved = target.resolve()
    if resolved.parent != base or resolved.name != item_id:
        return None
    return resolved


def discard_excerpt(item_id: str) -> None:
    excerpt = _owned("excerpts", item_id)
    if excerpt is not None:
        shutil.rmtree(excerpt)


def discard_export(item_id: str) -> None:
    export = _owned("exports", item_id)
    if export is not None:
        shutil.rmtree(export)


def clean_unclaimed_excerpts() -> None:
    """Recover old staging copies left by a crash or an older client losing deduplication."""
    folder = get_data_directory() / "diagnostics" / "excerpts"
    if folder.is_symlink() or not folder.is_dir():
        return
    cutoff = time.time() - timedelta(days=1).total_seconds()
    with _LOCK:
        # An unreadable ledger cannot establish that a copy is unclaimed.
        raw = json.loads(queue_path().read_text(encoding="utf-8"))
        rows = raw.get("items") if isinstance(raw, dict) else None
        if not isinstance(rows, list) or not all(isinstance(row, dict) and isinstance(row.get("id"), str) for row in rows):
            return
        owners = {row["id"] for row in rows}
        for directory in folder.iterdir():
            if directory.name in owners or not re.fullmatch(r"c-[0-9a-f]{32}", directory.name):
                continue
            if directory.is_symlink() or not directory.is_dir() or directory.stat().st_mtime >= cutoff:
                continue
            clip = directory / "excerpt.mp4"
            if clip.is_symlink() or not clip.is_file() or clip.stat().st_mtime >= cutoff:
                continue
            if list(directory.iterdir()) == [clip]:
                clip.unlink()
                directory.rmdir()


def release_local_residue(item: dict) -> None:
    """Remove this case's diagnostic copies and, once remote cleanup is done, its secrets.

    Project media outside diagnostics/ is never touched. A delete that still has to
    retry keeps the capability and recovery token.
    """
    status = item.get("status")
    if status not in {"deleted", "cancelled", "delete_pending", "uploaded"}:
        return
    item_id = str(item.get("id") or "")
    discard_excerpt(item_id)
    remote = bool(
        (item.get("upload") or {}).get("case_id") or item.get("case_id") or item.get("inflight_create") is True
    )
    if status in {"delete_pending", "uploaded"} or (status == "cancelled" and remote):
        return
    discard_export(item_id)
    for kind in ("capabilities", "recovery"):
        secret = _owned(kind, item_id)
        if secret is not None and secret.is_file():
            secret.unlink()


def cancel_before(epoch: int) -> list[dict]:
    """Mark non-terminal items authorized under an older epoch as cancelled."""
    with _LOCK:
        items = _load()
        changed = []
        for row in items:
            if (row.get("status") in TERMINAL and not row.get("inflight_create")) or row.get("status") == "delete_pending":
                continue
            if isinstance(row.get("epoch"), int) and row["epoch"] < epoch:
                row["version"] = int(row.get("version") or 0) + 1
                remote = bool(
                    (row.get("upload") or {}).get("case_id") or row.get("case_id") or row.get("inflight_create") is True
                )
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
