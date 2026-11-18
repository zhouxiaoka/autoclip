"""Task input origin for diagnostics. This module never fetches or opens a URL."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from backend.services.studio import store

_ORIGIN_NAME = "input_origin.json"
_SECRET_PARTS = frozenset({
    "token", "secret", "signature", "sign", "password", "passwd", "pwd",
    "credential", "cookie", "apikey", "key", "sig", "sid", "auth",
})


@dataclass(frozen=True)
class InputSource:
    origin: str
    source_url: str | None = None


def record_input_origin(project_id: str, origin: str, *, source_url: str | None = None) -> None:
    """Remember whether the user started from a link or a local file. Does not change download."""
    if origin not in {"link", "file"}:
        return
    payload: dict[str, str] = {"origin": origin}
    if origin == "link" and isinstance(source_url, str) and source_url.strip():
        payload["source_url"] = source_url.strip()[:2000]
    root = store.directory(project_id)
    folder = root / "metadata"
    path = folder / _ORIGIN_NAME
    if root.is_symlink() or folder.is_symlink() or path.is_symlink():
        return
    folder.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def classify(project_id: str) -> InputSource:
    """Link, local file, or unknown. Unknown must not auto-upload media."""
    try:
        disk = _sidecar(project_id)
        if disk == "invalid":
            return InputSource("unknown")
        db = _database(project_id)
    except Exception:  # noqa: BLE001 - a lookup miss is unknown, not a local file
        return InputSource("unknown")
    disk_origin = disk.origin if isinstance(disk, InputSource) else None
    db_origin = db.origin if isinstance(db, InputSource) else None
    if disk_origin in {"link", "file"} and db_origin in {"link", "file"} and disk_origin != db_origin:
        return InputSource("unknown")
    chosen = disk if isinstance(disk, InputSource) else db
    if not isinstance(chosen, InputSource) or chosen.origin not in {"link", "file"}:
        return InputSource("unknown")
    return chosen


def classify_metadata(meta: dict | None) -> InputSource:
    """Legacy project row. A saved null source_url is a local file. A missing record is unknown."""
    if not isinstance(meta, dict):
        return InputSource("unknown")
    origin = meta.get("input_origin")
    url = meta.get("source_url")
    if origin == "file":
        if _http_url(url):
            return InputSource("unknown")
        return InputSource("file")
    if origin == "link":
        return InputSource("link", url if isinstance(url, str) else None)
    if isinstance(url, str) and url.strip():
        return InputSource("link", url.strip())
    if "source_url" in meta and url is None:
        return InputSource("file")
    if meta.get("via") == "cli":
        return InputSource("file")
    return InputSource("unknown")


def _http_url(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))


def _decode_bounded(value: str, rounds: int = 3) -> str:
    current = value
    for _ in range(rounds):
        try:
            decoded = unquote(current)
        except Exception:
            break
        if decoded == current or len(decoded) > 2000:
            break
        current = decoded
    return current


def _name_parts(name: str) -> list[str]:
    folded = _decode_bounded(name).lower().replace("-", "_")
    return [part for part in re.split(r"[^a-z0-9_]+", folded) if part]


def _secret_name(name: str) -> bool:
    parts: list[str] = []
    for piece in _name_parts(name):
        parts.extend(part for part in piece.split("_") if part)
    return any(part in _SECRET_PARTS for part in parts)


def _unsafe_text(value: str) -> bool:
    samples = {value, _decode_bounded(value)}
    for sample in samples:
        folded = sample.lower().replace("\\", "/")
        if "sk-" in folded or "/users/" in folded:
            return True
    return False


def sanitize_source_link(value: str | None) -> str | None:
    """Keep a public video URL. Drop secrets. Never fetch the URL and never log the raw value."""
    try:
        return _sanitize_source_link(value)
    except Exception:
        return None


def _sanitize_source_link(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or len(raw) > 2000 or any(char.isspace() for char in raw):
        return None
    lowered = raw.lower()
    if lowered.startswith(("file:", "data:", "javascript:", "blob:")):
        return None
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    if _unsafe_text(parts.path):
        return None
    kept = []
    for key, item in parse_qsl(parts.query, keep_blank_values=False):
        if _secret_name(key) or _unsafe_text(item) or any(char in item for char in "\r\n"):
            continue
        if len(key) > 40 or len(item) > 200:
            continue
        kept.append((key, item))
    host = parts.hostname
    netloc = f"[{host}]" if ":" in host else host
    if port:
        netloc = f"{netloc}:{port}"
    cleaned = urlunsplit((parts.scheme.lower(), netloc, parts.path, urlencode(kept), ""))
    if (
        not cleaned
        or len(cleaned) > 300
        or _unsafe_text(cleaned)
        or "@" in urlsplit(cleaned).netloc
    ):
        return None
    return cleaned


def _sidecar(project_id: str) -> InputSource | None | str:
    root = store.directory(project_id)
    path = root / "metadata" / _ORIGIN_NAME
    if root.is_symlink() or path.is_symlink():
        return "invalid"
    if not path.is_file():
        return None
    try:
        if path.stat().st_size > 8192:
            return "invalid"
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "invalid"
    if not isinstance(payload, dict):
        return "invalid"
    origin = payload.get("origin")
    if origin not in {"link", "file"}:
        return "invalid"
    if origin == "file" and _http_url(payload.get("source_url")):
        return "invalid"
    url = payload.get("source_url") if origin == "link" and isinstance(payload.get("source_url"), str) else None
    return InputSource(origin, url)


def _database(project_id: str) -> InputSource | None:
    try:
        from sqlalchemy.engine import make_url
        from backend.core.config import get_database_url
        url = make_url(get_database_url())
        if url.get_backend_name() != "sqlite":
            return None
        database = url.database
        if not database or database == ":memory:":
            return None
        path = Path(database)
        if not path.is_file():
            return None
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1) as conn:
            row = conn.execute(
                "select project_metadata from projects where id = ?",
                (project_id,),
            ).fetchone()
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return None
    if row is None or not isinstance(row[0], str) or not row[0]:
        return None
    try:
        meta = json.loads(row[0])
    except ValueError:
        return InputSource("unknown")
    return classify_metadata(meta if isinstance(meta, dict) else None)
