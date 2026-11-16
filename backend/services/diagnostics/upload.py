"""Upload pump. No endpoint means no network. Revocation is checked before every authorization."""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from backend.core.path_utils import get_data_directory
from backend.services.diagnostics import media, queue
from backend.services.diagnostics.consent import load as load_consent
from backend.services.diagnostics.manifest import validate_manifest

logger = logging.getLogger(__name__)

_WAKE = threading.Event()
_THREAD_LOCK = threading.Lock()
_STARTED = False


class Offline(Exception):
    pass


class Revoked(Exception):
    pass


def endpoint() -> str:
    env = os.getenv("AUTOCLIP_DIAGNOSTICS_ENDPOINT", "").strip()
    if env:
        return env.rstrip("/")
    file = get_data_directory() / "diagnostics" / "endpoint.json"
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    value = raw.get("endpoint") if isinstance(raw, dict) else ""
    return value.strip().rstrip("/") if isinstance(value, str) else ""


def allowed_upload_url(url: str) -> bool:
    """Presigned object-storage URLs, or loopback for tests. Never file:, credentials, or link-local."""
    parsed = urlparse(url)
    if parsed.username or parsed.password or parsed.scheme not in {"https", "http"}:
        return False
    host = (parsed.hostname or "").lower()
    if host.endswith(".r2.cloudflarestorage.com") and parsed.scheme == "https":
        return True
    return host in {"127.0.0.1", "localhost", "::1"}


def _roots(item: dict) -> list[Path]:
    roots = []
    project_id = item.get("project_id")
    if isinstance(project_id, str):
        try:
            roots.append(media.project_root(project_id))
        except media.MediaRejected:
            pass
    excerpt = get_data_directory() / "diagnostics" / "excerpts" / str(item.get("id"))
    roots.append(excerpt)
    export = get_data_directory() / "diagnostics" / "exports" / str(item.get("id"))
    roots.append(export)
    return roots


def _still_authorized(item: dict) -> None:
    consent = load_consent()
    if not isinstance(item.get("epoch"), int) or item["epoch"] != consent.epoch:
        raise Revoked()
    roles = {row.get("role") for row in item.get("files") or []}
    if item.get("explicit"):
        return
    if not consent.diagnostics:
        raise Revoked()
    if "original" in roles and not consent.full_original:
        raise Revoked()
    if roles.intersection({"excerpt", "subtitle"}) and not consent.media:
        raise Revoked()


def _export_local(item: dict) -> str:
    dest = get_data_directory() / "diagnostics" / "exports" / item["id"]
    dest.mkdir(parents=True, exist_ok=True)
    manifest = item.get("manifest") or {}
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in item.get("files") or []:
        path = media.reroot(str(row.get("path") or ""), _roots(item))
        if path is None:
            continue
        target = dest / ("subtitle.srt" if row.get("role") == "subtitle" else f"{row.get('role')}.mp4")
        if target.exists():
            continue
        shutil.copyfile(path, target)
    return str(dest)


class UrllibTransport:
    """Used only when an endpoint is configured. Tests inject their own transport."""

    def create_case(self, base: str, body: dict, idempotency_key: str) -> dict:
        return self._json(base + "/v1/cases", body, {"Idempotency-Key": idempotency_key})

    def complete(self, base: str, case_id: str, capability: str, body: dict) -> dict:
        return self._json(
            f"{base}/v1/cases/{case_id}/files/{body['object_id']}/complete",
            body, {"Authorization": f"Bearer {capability}"},
        )

    def abort(self, base: str, case_id: str, capability: str) -> None:
        self.delete(base, case_id, capability)

    def delete(self, base: str, case_id: str, capability: str) -> None:
        request = urllib.request.Request(
            f"{base}/v1/cases/{case_id}", data=b"{}", method="DELETE",
            headers={"Authorization": f"Bearer {capability}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status not in {200, 202, 204}:
                    raise Offline(f"http_{response.status}")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return
            raise Offline(f"http_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise Offline("offline") from exc

    def put_part(self, url: str, data: bytes, headers: dict) -> str:
        if not allowed_upload_url(url):
            raise Offline("upload_url_rejected")
        request = urllib.request.Request(url, data=data, method="PUT", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.headers.get("ETag") or response.headers.get("Etag") or ""
        except urllib.error.HTTPError as exc:
            raise Offline(f"http_{exc.code}") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise Offline("offline") from exc

    def _json(self, url: str, body: dict, headers: dict) -> dict:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        configured = urlparse(endpoint()).hostname
        if host not in {"127.0.0.1", "localhost", "::1"} and host != (configured or "").lower():
            raise Offline("endpoint_host_rejected")
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {408, 429, 500, 502, 503, 504}:
                raise Offline(f"http_{exc.code}") from exc
            detail = exc.read().decode("utf-8", errors="ignore")[:200]
            raise RuntimeError(f"http_{exc.code}:{detail}") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise Offline("offline") from exc


def _live(item_id: str, fallback: dict) -> dict:
    return queue.get(item_id) or fallback


def _local_only(item: dict) -> bool:
    return item.get("disposition") == "local" or item.get("save_local") is True


def finish_delete(item: dict, transport) -> dict:
    """Remote erasure is confirmed only by a successful delete. Failures stay retryable."""
    item_id = item["id"]
    current = _live(item_id, item)
    if current.get("status") == "deleted":
        return current
    if current.get("status") != "delete_pending":
        moved = queue.update(item_id, if_version=current.get("version"), status="delete_pending", error="")
        current = moved or _live(item_id, current)
        if current.get("status") != "delete_pending":
            return current
    case_id = (current.get("upload") or {}).get("case_id") or current.get("case_id")
    capability = queue.read_capability(item_id)
    base = endpoint()
    if not base or not case_id or not capability or _local_only(current):
        done = queue.update(item_id, if_version=current.get("version"), if_status={"delete_pending"}, status="deleted", error="")
        return done or _live(item_id, current)
    try:
        transport.delete(base, case_id, capability)
    except (Offline, OSError, RuntimeError, ValueError, TypeError):
        kept = queue.update(
            item_id, if_version=current.get("version"), if_status={"delete_pending"},
            status="delete_pending", error="delete_retry", updated_at=queue.now_iso(),
        )
        return kept or _live(item_id, current)
    done = queue.update(item_id, if_version=current.get("version"), if_status={"delete_pending"}, status="deleted", error="")
    return done or _live(item_id, current)


def _save_only(item: dict) -> dict:
    if item.get("status") == "saved_local" and item.get("export_path"):
        return item
    exported = _export_local(item)
    saved = queue.update(
        item["id"], if_version=item.get("version"),
        if_status={item.get("status"), "queued", "uploading", "offline", "needs_endpoint"},
        status="saved_local", export_path=exported, error="", updated_at=queue.now_iso(),
    )
    return saved or _live(item["id"], item)


def _divert(item: dict, transport) -> dict | None:
    """Deletion wins over a local save, and both win over any in-flight upload step."""
    if item.get("status") == "delete_pending":
        return finish_delete(item, transport)
    if item.get("status") in queue.TERMINAL:
        return item
    if _local_only(item):
        return _save_only(item)
    return None


def _remember_capability(item_id: str, created: dict) -> None:
    secret = created.get("capability")
    if isinstance(secret, str) and secret:
        queue.write_capability(item_id, secret)


def _delete_created(item_id: str, created: dict, base: str, transport) -> None:
    case_id = created.get("case_id")
    capability = created.get("capability") or queue.read_capability(item_id)
    if not case_id or not capability:
        return
    try:
        transport.delete(base, case_id, capability)
    except (Offline, OSError, RuntimeError, ValueError, TypeError):
        logger.warning("diagnostics delete after revoke failed")
        queue.update(item_id, status="delete_pending", error="delete_retry", updated_at=queue.now_iso())


def upload_item(item: dict, transport, *, now: datetime | None = None) -> dict:
    """One attempt. Does not touch the generation attempt that produced the failure."""
    item_id = item["id"]
    item = _live(item_id, item)
    diverted = _divert(item, transport)
    if diverted is not None:
        return diverted
    try:
        _still_authorized(item)
    except Revoked:
        cancelled = queue.update(item_id, if_version=item.get("version"), status="cancelled", error="revoked", updated_at=queue.now_iso())
        return cancelled or _live(item_id, item)
    problems = validate_manifest(item.get("manifest") or {})
    if problems:
        failed = queue.update(item_id, if_version=item.get("version"), status="failed", error="manifest_rejected", updated_at=queue.now_iso())
        return failed or _live(item_id, item)
    base = endpoint()
    if not base:
        if item.get("explicit"):
            return _save_only(item)
        waiting = queue.update(
            item_id, if_version=item.get("version"), status="needs_endpoint", error="no_endpoint", updated_at=queue.now_iso(),
        )
        return waiting or _live(item_id, item)
    attempts = int(item.get("attempts") or 0)
    if not queue.due(item, now):
        return item
    try:
        item = _live(item_id, item)
        diverted = _divert(item, transport)
        if diverted is not None:
            return diverted
        _still_authorized(item)
        session = item.get("upload") if isinstance(item.get("upload"), dict) else {}
        if not session.get("case_id"):
            body = {
                "manifest": item["manifest"],
                "consent_version": item.get("consent_version"),
                "purpose": "troubleshooting_and_product_improvement",
                "not_for_training": True,
                "files": [
                    {"role": row["role"], "bytes": row["size_bytes"], "sha256": row["sha256"],
                     "content_type": row.get("content_type")}
                    for row in item.get("files") or []
                ],
            }
            created = transport.create_case(base, body, item["idempotency_key"])
            item = _live(item_id, item)
            diverted = _divert(item, transport)
            if diverted is not None:
                _remember_capability(item_id, created)
                case_id = created.get("case_id")
                capability = created.get("capability") or queue.read_capability(item_id)
                if case_id and capability:
                    try:
                        transport.delete(base, case_id, capability)
                    except (Offline, OSError, RuntimeError, ValueError, TypeError):
                        logger.warning("diagnostics delete after revoke failed")
                        queue.update(item_id, status="delete_pending", error="delete_retry", updated_at=queue.now_iso())
                return _live(item_id, diverted)
            objects = created.get("uploads") or []
            selected = {row.get("role") for row in item.get("files") or []}
            planned = {entry.get("role") for entry in objects if isinstance(entry, dict)}
            if selected - planned:
                raise RuntimeError("incomplete_plan")
            _remember_capability(item_id, created)
            session = {
                "case_id": created.get("case_id"),
                "objects": objects,
                "done": [],
                "acked": [],
            }
            stored = queue.update(
                item_id, if_version=item.get("version"), if_status=queue.OPEN,
                upload=session, case_id=created.get("case_id"), status="uploading", updated_at=queue.now_iso(),
            )
            if stored is None:
                live = _live(item_id, item)
                diverted = _divert(live, transport)
                if diverted is not None:
                    _remember_capability(item_id, created)
                    _delete_created(item_id, created, base, transport)
                    return diverted
                return live
            item = stored
            session = item["upload"]
            _still_authorized(item)
        capability = queue.read_capability(item_id)
        if not capability:
            raise RuntimeError("missing_capability")
        for row in item.get("files") or []:
            if row.get("role") in (session.get("acked") or []):
                continue
            item = _live(item_id, item)
            diverted = _divert(item, transport)
            if diverted is not None:
                return diverted
            session = item.get("upload") or session
            path = media.reroot(str(row.get("path") or ""), _roots(item))
            if path is None:
                raise RuntimeError("path_rejected")
            digest, size = media.sha256_file(path, limit=row["size_bytes"])
            if digest != row.get("sha256") or size != row.get("size_bytes"):
                raise RuntimeError("byte_mismatch")
            found = next((entry for entry in session.get("objects") or [] if entry.get("role") == row["role"]), None)
            obj = found if isinstance(found, dict) else None
            if obj is None:
                raise RuntimeError("incomplete_plan")
            if obj.get("already_complete") is True:
                if obj.get("bytes") != size:
                    raise RuntimeError("ack_mismatch")
                session.setdefault("acked", []).append(row["role"])
                stored = queue.update(item_id, if_version=item.get("version"), if_status=queue.OPEN, upload=session, updated_at=queue.now_iso())
                if stored is None:
                    return _divert(_live(item_id, item), transport) or _live(item_id, item)
                item = stored
                continue
            parts = obj.get("parts")
            if not parts:
                parts = [{"number": 1, "url": obj.get("url"), "headers": obj.get("headers") or {},
                          "offset": 0, "length": size}]
            planned = 0
            for part in parts:
                length = int(part.get("length") or 0)
                offset = int(part.get("offset") or 0)
                if length < 0 or offset < 0 or offset + length > size:
                    raise RuntimeError("byte_mismatch")
                planned += length
            if planned != size:
                raise RuntimeError("byte_mismatch")
            etags = []
            for part in parts:
                marker = f"{row['role']}:{part.get('number')}"
                item = _live(item_id, item)
                diverted = _divert(item, transport)
                if diverted is not None:
                    return diverted
                _still_authorized(item)
                if marker in (session.get("done") or []):
                    etags.append({"partNumber": part.get("number"), "etag": (session.get("etags") or {}).get(marker, "")})
                    continue
                payload = media.read_range(path, int(part["offset"]), int(part["length"]))
                headers = dict(part.get("headers") or {})
                headers["Content-Length"] = str(part["length"])
                url = part.get("url")
                if not isinstance(url, str):
                    raise TypeError("missing_upload_url")
                etag = transport.put_part(url, payload, headers) or ""
                if len(parts) > 1 and not etag:
                    raise RuntimeError("missing_etag")
                session.setdefault("done", []).append(marker)
                session.setdefault("etags", {})[marker] = etag
                etags.append({"partNumber": part.get("number"), "etag": etag})
                stored = queue.update(item_id, if_version=item.get("version"), if_status=queue.OPEN, upload=session, updated_at=queue.now_iso())
                if stored is None:
                    return _divert(_live(item_id, item), transport) or _live(item_id, item)
                item = stored
            item = _live(item_id, item)
            diverted = _divert(item, transport)
            if diverted is not None:
                return diverted
            _still_authorized(item)
            acknowledged = transport.complete(base, session["case_id"], capability, {
                "object_id": obj.get("object_id"), "sha256": row["sha256"], "bytes": size, "parts": etags,
            })
            if not isinstance(acknowledged, dict) or acknowledged.get("bytes") != size:
                raise RuntimeError("ack_mismatch")
            session.setdefault("acked", []).append(row["role"])
            stored = queue.update(item_id, if_version=item.get("version"), if_status=queue.OPEN, upload=session, updated_at=queue.now_iso())
            if stored is None:
                return _divert(_live(item_id, item), transport) or _live(item_id, item)
            item = stored
        selected = {row.get("role") for row in item.get("files") or []}
        if selected - set((item.get("upload") or {}).get("acked") or []):
            raise RuntimeError("incomplete_ack")
        uploaded = queue.update(
            item_id, if_version=item.get("version"), if_status=queue.OPEN,
            status="uploaded", error="", updated_at=queue.now_iso(),
        )
        return uploaded or _live(item_id, item)
    except Revoked:
        current = _live(item_id, item)
        capability = queue.read_capability(item_id)
        case_id = (current.get("upload") or {}).get("case_id")
        if case_id and capability and endpoint():
            try:
                transport.delete(endpoint(), case_id, capability)
            except (Offline, OSError, RuntimeError, ValueError, TypeError):
                logger.warning("diagnostics delete after revoke failed")
                pending = queue.update(item_id, status="delete_pending", error="delete_retry", updated_at=queue.now_iso())
                return pending or _live(item_id, current)
            erased = queue.update(item_id, if_version=current.get("version"), status="deleted", error="", updated_at=queue.now_iso())
            return erased or _live(item_id, current)
        cancelled = queue.update(item_id, if_version=current.get("version"), status="cancelled", error="revoked", updated_at=queue.now_iso())
        return cancelled or _live(item_id, current)
    except Offline as exc:
        current = _live(item_id, item)
        diverted = _divert(current, transport)
        if diverted is not None:
            return diverted
        attempts += 1
        status = "failed" if attempts >= 8 else "offline"
        paused = queue.update(
            item_id, if_version=current.get("version"), if_status=queue.OPEN,
            status=status, attempts=attempts, error=str(exc)[:80],
            next_attempt_at=queue.schedule_retry(attempts, now), updated_at=queue.now_iso(),
        )
        return paused or _live(item_id, current)
    except (RuntimeError, TypeError, ValueError, OSError, media.MediaRejected) as exc:
        current = _live(item_id, item)
        diverted = _divert(current, transport)
        if diverted is not None:
            return diverted
        failed = queue.update(
            item_id, if_version=current.get("version"), if_status=queue.OPEN,
            status="failed", error=type(exc).__name__, updated_at=queue.now_iso(),
        )
        return failed or _live(item_id, current)


def pump_once(transport=None, *, now: datetime | None = None) -> list[dict]:
    transport = transport or UrllibTransport()
    results = []
    for item in queue.list_items():
        if item.get("status") == "delete_pending":
            results.append(finish_delete(item, transport))
        elif item.get("status") in queue.OPEN:
            results.append(upload_item(item, transport, now=now))
    return results


def _loop() -> None:
    while True:
        _WAKE.wait(30)
        _WAKE.clear()
        try:
            pump_once()
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            logger.warning("diagnostics pump failed")
            continue


def wake() -> None:
    global _STARTED
    if os.getenv("AUTOCLIP_DIAGNOSTICS_SYNC") == "1":
        return
    with _THREAD_LOCK:
        if not _STARTED:
            threading.Thread(target=_loop, daemon=True, name="diagnostics-upload").start()
            _STARTED = True
    _WAKE.set()
