"""Allowlisted log lines. A line that is not the expected shape is dropped, not masked in place."""
from __future__ import annotations

import re
from pathlib import Path

from backend.core.log_redaction import redact_text

# desktop_main: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# local_runner file: "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DESKTOP = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - [\w.]+ - "
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) - (?P<rest>.*)$"
)
_RUNNER = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) "
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) [\w.]+: (?P<rest>.*)$"
)
_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?)\s+"
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+(?P<rest>.+)$"
)
_PATH = re.compile(r"(?:[A-Za-z]:\\|\\\\|[A-Za-z]:/|/)(?:[^\s'\"<>]|\\.){2,}")
_HOME = re.compile(r"(?:~|/Users/[^/\s]+|/home/[^/\s]+|C:\\Users\\[^\\\s]+)")
_SAFE_REST = re.compile(r"^[A-Za-z0-9_.=:\-\[\]<>, ]{1,300}$")
_SECRET_LEFT = re.compile(
    r"sk-|bearer\s|api[_-]?key|authorization|password|github_pat_|ghp_|xox[baprs]-|AIza",
    re.IGNORECASE,
)
_QUERY_URL = re.compile(r"https?://\S*[?&]\S+")
_SRT = re.compile(r"-->")


def scrub_fragment(text: str) -> str | None:
    """Return a safe fragment, or None when the fragment must not be kept."""
    cleaned = redact_text(text or "")
    cleaned = _HOME.sub("<path>", cleaned)
    cleaned = _PATH.sub("<path>", cleaned)
    cleaned = cleaned.replace("\n", " ").strip()
    if not cleaned or _SECRET_LEFT.search(cleaned) or _QUERY_URL.search(cleaned) or _SRT.search(cleaned):
        return None
    if not _SAFE_REST.fullmatch(cleaned):
        return None
    return cleaned


def sanitized_log_records(text: str, *, project_id: str | None = None, limit: int = 50) -> list[dict]:
    out: list[dict] = []
    marker = f"project_id={project_id}" if project_id else None
    for raw in (text or "").splitlines():
        match = _DESKTOP.match(raw.strip()) or _RUNNER.match(raw.strip()) or _LINE.match(raw.strip())
        if not match:
            continue
        rest = match.group("rest")
        if marker and marker not in rest:
            continue
        safe = scrub_fragment(rest)
        if safe is None:
            continue
        out.append({
            "timestamp": match.group("ts").replace(",", "."),
            "level": match.group("level"),
            "module": "log",
            "message": safe,
        })
        if len(out) >= limit:
            break
    return out


def sanitized_log_file(path: Path, *, project_id: str | None = None, limit: int = 50) -> list[dict]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    tail = data[-256_000:]
    text = tail.decode("utf-8", errors="ignore")
    # A partial first line from the tail cut is dropped by _LINE.
    return sanitized_log_records(text, project_id=project_id, limit=limit)
