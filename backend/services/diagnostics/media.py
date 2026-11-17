"""Task-scoped media selection. Paths come from the project directory, never from the caller."""
from __future__ import annotations

import base64
import hashlib
import subprocess
from pathlib import Path

from backend.services.diagnostics.allowlist_data import ROLE_MAX_BYTES
from backend.services.studio import store

_VIDEO_NAMES = ("input.mp4", "input.mov", "input.mkv", "input.webm", "input.m4v")
_SUBTITLE_RELATIVE = (("raw", "input.srt"), ("metadata", "input.srt"))


class MediaRejected(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def project_root(project_id: str) -> Path:
    root = store.directory(project_id)
    if root.is_symlink():
        raise MediaRejected("symlink_root")
    return root


def _contained(root: Path, candidate: Path) -> Path | None:
    """Regular file inside root. Symlinks and paths that escape root are rejected."""
    try:
        root_real = root.resolve(strict=True)
    except OSError:
        return None
    if candidate.is_symlink():
        return None
    current = root_real
    try:
        relative = candidate.resolve(strict=False).relative_to(root_real)
    except (OSError, ValueError):
        return None
    for part in relative.parts:
        if part in {"", ".", ".."}:
            return None
        current = current / part
        if current.is_symlink():
            return None
    try:
        if not current.is_file() or current.is_symlink():
            return None
        current.resolve(strict=True).relative_to(root_real)
    except (OSError, ValueError):
        return None
    return current


def _source_video(root: Path) -> Path | None:
    raw = root / "raw"
    for name in _VIDEO_NAMES:
        found = _contained(root, raw / name)
        if found is not None:
            return found
    return None


def _subtitle(root: Path) -> Path | None:
    for parts in _SUBTITLE_RELATIVE:
        found = _contained(root, root.joinpath(*parts))
        if found is not None:
            return found
    return None


def part_md5s(path: Path, size: int, part_bytes: int) -> list[str]:
    """Base64 MD5 of each part. One part is kept in memory at a time."""
    if size <= part_bytes:
        return []
    digests = []
    offset = 0
    while offset < size:
        length = min(part_bytes, size - offset)
        digest = hashlib.md5()
        remaining = length
        with path.open("rb") as handle:
            handle.seek(offset)
            while remaining:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise MediaRejected("short_read")
                digest.update(chunk)
                remaining -= len(chunk)
        digests.append(base64.b64encode(digest.digest()).decode("ascii"))
        offset += length
    return digests


def sha256_file(path: Path, *, limit: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise MediaRejected("too_large")
            digest.update(chunk)
    return digest.hexdigest(), size


def describe(path: Path, *, role: str, probe=None) -> dict:
    limit = ROLE_MAX_BYTES["subtitle" if role == "subtitle" else "original"]
    digest, size = sha256_file(path, limit=limit)
    facts = {"size_bytes": size, "sha256": digest, "role": role}
    if probe is not None and role != "subtitle":
        try:
            extra = probe(path) or {}
        except Exception:  # noqa: BLE001 - a probe miss only drops codec facts
            extra = {}
        if isinstance(extra, dict):
            from backend.services.diagnostics.manifest import media_facts
            facts.update(media_facts(extra))
            facts["size_bytes"] = size
    return facts


def candidates(project_id: str, *, probe=None) -> list[dict]:
    """Metadata for this task's source and subtitle. No directory walk, no path in the result."""
    root = project_root(project_id)
    rows = []
    video = _source_video(root)
    if video is not None:
        try:
            rows.append(describe(video, role="original", probe=probe))
        except MediaRejected:
            rows.append({"role": "original", "rejected": "too_large"})
    subtitle = _subtitle(root)
    if subtitle is not None:
        try:
            rows.append(describe(subtitle, role="subtitle"))
        except MediaRejected:
            rows.append({"role": "subtitle", "rejected": "too_large"})
    if video is not None:
        rows.append({
            "role": "excerpt",
            "available": True,
            "limitation": "first_60s_may_miss_late_failure",
        })
    return rows


def resolve_role(project_id: str, role: str) -> Path:
    if role not in {"original", "subtitle"}:
        raise MediaRejected("role")
    root = project_root(project_id)
    found = _source_video(root) if role == "original" else _subtitle(root)
    if found is None:
        raise MediaRejected("missing")
    return found


def default_cut(source: Path, dest: Path, *, start_sec: float = 0, duration_sec: float = 60) -> Path:
    """Copy the first minute. Late timeouts may not appear in this excerpt."""
    if start_sec < 0 or duration_sec <= 0 or duration_sec > 180:
        raise MediaRejected("excerpt_window")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or (dest.exists() and not dest.is_file()):
        raise MediaRejected("excerpt_dest")
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    try:
        subprocess.run(
            [get_ffmpeg_path(), "-hide_banner", "-nostdin", "-y", "-ss", str(start_sec),
             "-t", str(duration_sec), "-i", str(source), "-c", "copy", str(dest)],
            check=True, capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MediaRejected("excerpt_unavailable") from exc
    if not dest.is_file() or dest.is_symlink() or dest.stat().st_size > ROLE_MAX_BYTES["excerpt"]:
        dest.unlink(missing_ok=True)
        raise MediaRejected("excerpt_unavailable")
    return dest


def materialize(project_id: str, roles: list[str], *, excerpt_dir: Path, cut=None) -> list[dict]:
    """Return local file descriptors for roles the caller already authorized."""
    files = []
    root = project_root(project_id)
    for role in roles:
        if role == "excerpt":
            source = _source_video(root)
            if source is None:
                raise MediaRejected("missing")
            dest = excerpt_dir / "excerpt.mp4"
            cutter = cut or default_cut
            cutter(source, dest)
            contained = _contained(excerpt_dir, dest) or _contained(root, dest)
            if contained is None:
                raise MediaRejected("excerpt_escaped")
            facts = describe(contained, role="excerpt")
            if facts["size_bytes"] > ROLE_MAX_BYTES["excerpt"]:
                raise MediaRejected("too_large")
            files.append({**facts, "path": str(contained), "content_type": "video/mp4"})
            continue
        if role not in {"original", "subtitle"}:
            raise MediaRejected("role")
        path = resolve_role(project_id, role)
        facts = describe(path, role=role)
        cap = ROLE_MAX_BYTES[role]
        if facts["size_bytes"] > cap:
            raise MediaRejected("too_large")
        content = "video/mp4" if role == "original" else "application/x-subrip"
        files.append({**facts, "path": str(path), "content_type": content})
    return files


def reroot(path: str, roots: list[Path]) -> Path | None:
    """Re-check a queued path immediately before reading bytes."""
    candidate = Path(path)
    if candidate.is_symlink():
        return None
    for root in roots:
        found = _contained(root, candidate)
        if found is not None:
            return found
    return None


def read_range(path: Path, offset: int, length: int) -> bytes:
    if offset < 0 or length < 0 or length > 8 * 1024 * 1024:
        raise MediaRejected("range")
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(length)
    if len(data) != length:
        raise MediaRejected("short_read")
    return data
