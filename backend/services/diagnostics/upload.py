"""Upload pump. Consent is checked before every authorization.

The built-in Worker is used when neither the environment nor endpoint.json
sets an address. Opt-in stays off until the user enables it.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from backend.core.event_catalog import app_version
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


class UploadAuthorizationExpired(Offline):
    pass


class PermanentUploadError(Exception):
    """A deterministic storage rejection. It must not be retried as an offline outage."""


class Revoked(Exception):
    pass


DEFAULT_ENDPOINT = "https://autoclip-diagnostics-api.autoclip-val-3f71ee83.workers.dev"


def diagnostics_user_agent() -> str:
    return f"AutoClip/{app_version()} diagnostics"


def _worker_headers(extra: dict | None = None) -> dict[str, str]:
    """Worker JSON calls identify the app. Presigned object-storage requests keep their signed headers."""
    headers = {"Content-Type": "application/json"}
    if extra:
        headers.update(extra)
    headers["User-Agent"] = diagnostics_user_agent()
    return headers


def endpoint() -> str:
    """env AUTOCLIP_DIAGNOSTICS_ENDPOINT, then endpoint.json, then the built-in Worker."""
    env = os.getenv("AUTOCLIP_DIAGNOSTICS_ENDPOINT", "").strip()
    if env:
        return env.rstrip("/")
    file = get_data_directory() / "diagnostics" / "endpoint.json"
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_ENDPOINT
    value = raw.get("endpoint") if isinstance(raw, dict) else ""
    if isinstance(value, str) and value.strip():
        return value.strip().rstrip("/")
    return DEFAULT_ENDPOINT


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
            raise media.MediaRejected("missing")
        target = dest / ("subtitle.srt" if row.get("role") == "subtitle" else f"{row.get('role')}.mp4")
        if target.exists():
            continue
        shutil.copyfile(path, target)
    return str(dest)


PART_BYTES = 8 * 1024 * 1024


class UrllibTransport:
    """Used only when an endpoint is configured. Tests inject their own transport."""

    def create_case(self, base: str, body: dict, idempotency_key: str) -> dict:
        return self._json(base + "/v1/cases", body, {"Idempotency-Key": idempotency_key}, allowed_base=base)

    def cancel_creation(self, base: str, idempotency_key: str, recovery_token: str) -> dict:
        return self._json(base + "/v1/cases/cancel", {
            "idempotency_key": idempotency_key, "recovery_token": recovery_token,
        }, {}, allowed_base=base)

    def complete(self, base: str, case_id: str, capability: str, body: dict) -> dict:
        return self._json(
            f"{base}/v1/cases/{case_id}/files/{body['object_id']}/complete",
            body, {"Authorization": f"Bearer {capability}"}, allowed_base=base,
        )

    def abort(self, base: str, case_id: str, capability: str) -> None:
        self.delete(base, case_id, capability)

    def delete(self, base: str, case_id: str, capability: str) -> None:
        request = urllib.request.Request(
            f"{base}/v1/cases/{case_id}", data=b"{}", method="DELETE",
            headers=_worker_headers({"Authorization": f"Bearer {capability}"}),
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
        # Presigned object-storage URLs sign content-length, host, and checksum or content-md5.
        # User-Agent is not one of those headers. Leave the signed set unchanged.
        if not allowed_upload_url(url):
            raise Offline("upload_url_rejected")
        request = urllib.request.Request(url, data=data, method="PUT", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.headers.get("ETag") or response.headers.get("Etag") or ""
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise UploadAuthorizationExpired(f"http_{exc.code}") from exc
            if exc.code == 400:
                raise PermanentUploadError(f"http_{exc.code}") from exc
            raise Offline(f"http_{exc.code}") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise Offline("offline") from exc

    def _json(self, url: str, body: dict, headers: dict, *, allowed_base: str = "") -> dict:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        configured = urlparse(allowed_base or endpoint()).hostname
        if host not in {"127.0.0.1", "localhost", "::1"} and host != (configured or "").lower():
            raise Offline("endpoint_host_rejected")
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url, data=payload, method="POST",
            headers=_worker_headers(headers),
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


def _released(item: dict | None) -> dict | None:
    if isinstance(item, dict):
        queue.release_local_residue(item)
    return item


def finish_delete(item: dict, transport) -> dict:
    result = _finish_delete(item, transport)
    released = _released(result)
    return released if isinstance(released, dict) else result


def _finish_delete(item: dict, transport) -> dict:
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
    stored_endpoint = current.get("cleanup_endpoint")
    base = stored_endpoint if isinstance(stored_endpoint, str) and stored_endpoint else (endpoint() or "")
    if current.get("inflight_create") is True and not case_id:
        # An interrupted create may have committed remotely. Cancel by its
        # durable request identity, never by replaying the media-bearing create.
        secret = queue.recovery_token(item_id)
        cancel = getattr(transport, "cancel_creation", None)
        if not base or not secret or not callable(cancel):
            held = queue.update(item_id, if_version=current.get("version"), if_status={"delete_pending"},
                                error="delete_wait", updated_at=queue.now_iso())
            return held or current
        try:
            response = cancel(base, current["idempotency_key"], secret)
            if not isinstance(response, dict) or response.get("deleted") is not True:
                raise Offline("delete_unconfirmed")
        except (Offline, OSError, RuntimeError, ValueError, TypeError):
            kept = queue.update(item_id, if_version=current.get("version"), if_status={"delete_pending"},
                                error="delete_retry", updated_at=queue.now_iso())
            return kept or _live(item_id, current)
        done = queue.update(item_id, if_version=current.get("version"), if_status={"delete_pending"},
                            status="deleted", inflight_create=False, error="", updated_at=queue.now_iso())
        return done or _live(item_id, current)
    if _local_only(current) or (not case_id and not current.get("inflight_create")):
        done = queue.update(item_id, if_version=current.get("version"), if_status={"delete_pending"}, status="deleted", error="")
        return done or _live(item_id, current)
    if not base or not capability:
        return current  # An unknown credential/endpoint is not proof of remote erasure.
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
    try:
        exported = _export_local(item)
    except (OSError, media.MediaRejected) as error:
        failed = queue.update(item["id"], if_version=item.get("version"), if_status=queue.OPEN,
                              status="failed", error=type(error).__name__, updated_at=queue.now_iso())
        if failed:
            queue.discard_export(item["id"])
            queue.discard_excerpt(item["id"])
        return failed or _live(item["id"], item)
    saved = queue.update(
        item["id"], if_version=item.get("version"),
        if_status={item.get("status"), "queued", "uploading", "offline", "needs_endpoint"},
        status="saved_local", export_path=exported, error="", updated_at=queue.now_iso(),
    )
    if saved:
        return saved
    return _released(_live(item["id"], item))


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


def _bind_created(item_id: str, created: dict, base: str) -> dict:
    """Persist the remote identity before any cleanup attempt."""
    _remember_capability(item_id, created if isinstance(created, dict) else {})
    case_id = created.get("case_id") if isinstance(created, dict) else None
    uploads = created.get("uploads") if isinstance(created, dict) and isinstance(created.get("uploads"), list) else []
    if not isinstance(case_id, str) or not case_id:
        return _live(item_id, {})
    attached = queue.attach_remote_case(item_id, case_id=case_id, uploads=uploads, endpoint=base,
                                        expires_at=str(created.get("upload_expires_at") or ""))
    return attached or _live(item_id, {})


def _cleanup_bound(item: dict, transport) -> dict:
    if item.get("status") != "delete_pending":
        moved = queue.update(
            item["id"], if_version=item.get("version"),
            status="delete_pending", error="delete_retry", updated_at=queue.now_iso(),
        )
        item = moved or _live(item["id"], item)
    return finish_delete(item, transport)


def _part_geometry(value: dict) -> list[tuple]:
    return [(part.get("number"), part.get("offset"), part.get("length")) for part in value.get("parts") or []]


def _with_memory_grants(memory: dict, stored: dict | None) -> dict:
    """Disk copies omit presigned URLs. This process keeps the grants it already received."""
    if not isinstance(stored, dict):
        return memory if isinstance(memory, dict) else {}
    if not isinstance(memory, dict) or memory.get("case_id") != stored.get("case_id"):
        return stored
    previous = {entry.get("object_id"): entry for entry in memory.get("objects") or [] if isinstance(entry, dict)}
    objects = []
    for entry in stored.get("objects") or []:
        if not isinstance(entry, dict):
            objects.append(entry)
            continue
        old = previous.get(entry.get("object_id"))
        if not isinstance(old, dict) or _part_geometry(old) != _part_geometry(entry):
            objects.append(entry)
            continue
        merged = dict(entry)
        if not merged.get("url") and old.get("url"):
            merged["url"] = old["url"]
            merged["headers"] = old.get("headers") or {}
        old_parts = {part.get("number"): part for part in old.get("parts") or [] if isinstance(part, dict)}
        parts = []
        for part in merged.get("parts") or []:
            if not isinstance(part, dict):
                continue
            prior = old_parts.get(part.get("number"))
            if isinstance(prior, dict) and not part.get("url") and prior.get("url"):
                part = {**part, "url": prior["url"], "headers": prior.get("headers") or {}}
            parts.append(part)
        merged["parts"] = parts
        objects.append(merged)
    restored = dict(stored)
    restored["objects"] = objects
    for key in ("done", "etags", "acked"):
        if key not in restored and key in memory:
            restored[key] = memory[key]
    return restored


def _upload_file(item: dict, row: dict) -> dict:
    body = {"role": row["role"], "bytes": row["size_bytes"], "sha256": row["sha256"], "content_type": row.get("content_type")}
    size = int(row["size_bytes"])
    if size > PART_BYTES:
        path = media.reroot(str(row.get("path") or ""), _roots(item))
        if path is None:
            raise RuntimeError("path_rejected")
        body["part_md5s"] = media.part_md5s(path, size, PART_BYTES)
    return body


def _expires_at(session: dict):
    raw = session.get("expires_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        expires = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return "invalid"
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires


def _plan_expired(session: dict, now: datetime | None = None) -> bool:
    expires = _expires_at(session)
    if expires is None:
        return False
    if expires == "invalid":
        return True
    return expires <= (now or datetime.now(timezone.utc))


def _plan_due(session: dict, now: datetime | None = None, margin_seconds: int = 60) -> bool:
    """Refresh before the signed part URLs lapse. This does not extend the server TTL."""
    expires = _expires_at(session)
    if expires is None:
        return False
    if expires == "invalid":
        return True
    current = now or datetime.now(timezone.utc)
    return expires <= current + timedelta(seconds=margin_seconds)


def _put_part_attempts(transport, url: str, payload: bytes, headers: dict) -> str:
    """Retry one part at most twice. Earlier parts stay stored by the caller."""
    last = None
    for attempt in range(3):
        try:
            return transport.put_part(url, payload, headers)
        except (UploadAuthorizationExpired, PermanentUploadError):
            raise
        except Offline as exc:
            if str(exc) in {"http_401", "http_403"}:
                raise UploadAuthorizationExpired(str(exc)) from exc
            last = exc
            if attempt == 2:
                raise
    raise last


def _drop_blocked_media(item: dict) -> dict:
    """A link, or an origin we cannot prove, must not upload a downloaded video."""
    from backend.services.diagnostics.source import classify, sanitize_source_link
    decision = classify(str(item.get("project_id") or ""))
    if decision.origin == "file":
        return item
    changes: dict = {}
    if item.get("files"):
        changes["files"] = []
    manifest = item.get("manifest") if isinstance(item.get("manifest"), dict) else {}
    if decision.origin == "link" and not manifest.get("source_link"):
        link = sanitize_source_link(decision.source_url)
        if link:
            updated = dict(manifest)
            updated["source_link"] = link
            if not validate_manifest(updated):
                changes["manifest"] = updated
    if not changes:
        return {**item, "files": []} if item.get("files") else item
    stored = queue.update(
        item["id"], if_version=item.get("version"), updated_at=queue.now_iso(), **changes,
    )
    if stored is None:
        live = _live(item["id"], item)
        return {**live, "files": []}
    return stored


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
        if item.get("inflight_create") or item.get("case_id") or (item.get("upload") or {}).get("case_id"):
            return _cleanup_bound(item, transport)
        cancelled = queue.update(item_id, if_version=item.get("version"), status="cancelled", error="revoked", updated_at=queue.now_iso())
        return _released(cancelled or _live(item_id, item)) or _live(item_id, item)
    problems = validate_manifest(item.get("manifest") or {})
    if problems:
        failed = queue.update(item_id, if_version=item.get("version"), status="failed", error="manifest_rejected", updated_at=queue.now_iso())
        return failed or _live(item_id, item)
    base = item.get("cleanup_endpoint") or endpoint()
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
        item = _drop_blocked_media(item)
        session = item.get("upload") if isinstance(item.get("upload"), dict) else {}
        if not session.get("case_id") or item.get("refresh_plan") or _plan_expired(session, now):
            recovery = queue.recovery_token(item_id, create=True)
            marked = queue.update(
                item_id, if_version=item.get("version"), if_status=queue.OPEN,
                inflight_create=not bool(session.get("case_id")), cleanup_endpoint=base, status="uploading", updated_at=queue.now_iso(),
            )
            if marked is None:
                live = _live(item_id, item)
                return _divert(live, transport) or live
            item = marked
            body = {
                "manifest": item["manifest"],
                "recovery_token": recovery,
                "consent_version": item.get("consent_version"),
                "purpose": "troubleshooting_and_product_improvement",
                "not_for_training": True,
                "files": [_upload_file(item, row) for row in item.get("files") or []],
            }
            created = transport.create_case(base, body, item["idempotency_key"])
            if session.get("case_id"):
                if not isinstance(created, dict) or created.get("case_id") != session["case_id"]:
                    raise RuntimeError("refresh_case_mismatch")
                previous = {entry.get("role"): entry for entry in session.get("objects") or []}
                for entry in created.get("uploads") or []:
                    old = previous.get(entry.get("role")) or {}
                    if old.get("object_id") != entry.get("object_id"):
                        raise RuntimeError("refresh_object_mismatch")
                    if not entry.get("already_complete"):
                        if _part_geometry(old) != _part_geometry(entry):
                            raise RuntimeError("refresh_parts_mismatch")
            item = _bind_created(item_id, created, base)
            if item.get("status") in {"delete_pending", "deleted", "cancelled"}:
                return finish_delete(item, transport)
            try:
                _still_authorized(item)
            except Revoked:
                return _cleanup_bound(item, transport)
            objects = (item.get("upload") or {}).get("objects") or []
            selected = {row.get("role") for row in item.get("files") or []}
            planned = {entry.get("role") for entry in objects if isinstance(entry, dict)}
            if selected - planned:
                raise RuntimeError("incomplete_plan")
            session = item.get("upload") if isinstance(item.get("upload"), dict) else {}
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
            session = _with_memory_grants(session, item.get("upload"))
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
                stored = queue.update(item_id, if_version=item.get("version"), if_status=queue.OPEN, upload=session, auth_refreshes=0, updated_at=queue.now_iso())
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
                if _plan_due(session, now) or not part.get("url"):
                    refreshes = int(item.get("auth_refreshes") or 0) + 1
                    refreshed = queue.update(item_id, if_version=item.get("version"), if_status=queue.OPEN,
                                             refresh_plan=True, auth_refreshes=refreshes,
                                             status="failed" if refreshes >= 3 else "queued",
                                             error="expired_grant", updated_at=queue.now_iso())
                    return refreshed or _live(item_id, item)
                payload = media.read_range(path, int(part["offset"]), int(part["length"]))
                headers = dict(part.get("headers") or {})
                headers["Content-Length"] = str(part["length"])
                url = part.get("url")
                if not isinstance(url, str):
                    raise TypeError("missing_upload_url")
                etag = _put_part_attempts(transport, url, payload, headers) or ""
                if len(parts) > 1 and not etag:
                    raise RuntimeError("missing_etag")
                session.setdefault("done", []).append(marker)
                session.setdefault("etags", {})[marker] = etag
                etags.append({"partNumber": part.get("number"), "etag": etag})
                stored = queue.update(item_id, if_version=item.get("version"), if_status=queue.OPEN, upload=session, auth_refreshes=0, updated_at=queue.now_iso())
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
        return _released(uploaded or _live(item_id, item)) or _live(item_id, item)
    except Revoked:
        current = _live(item_id, item)
        capability = queue.read_capability(item_id)
        case_id = (current.get("upload") or {}).get("case_id")
        if case_id and capability and base:
            try:
                transport.delete(base, case_id, capability)
            except (Offline, OSError, RuntimeError, ValueError, TypeError):
                logger.warning("diagnostics delete after revoke failed")
                pending = queue.update(item_id, status="delete_pending", error="delete_retry", updated_at=queue.now_iso())
                return _released(pending or _live(item_id, current)) or _live(item_id, current)
            erased = queue.update(item_id, if_version=current.get("version"), status="deleted", error="", updated_at=queue.now_iso())
            return _released(erased or _live(item_id, current)) or _live(item_id, current)
        cancelled = queue.update(item_id, if_version=current.get("version"), status="cancelled", error="revoked", updated_at=queue.now_iso())
        return _released(cancelled or _live(item_id, current)) or _live(item_id, current)
    except UploadAuthorizationExpired as exc:
        current = _live(item_id, item)
        diverted = _divert(current, transport)
        if diverted is not None:
            return diverted
        refreshes = int(current.get("auth_refreshes") or 0) + 1
        paused = queue.update(item_id, if_version=current.get("version"), if_status=queue.OPEN,
                              status="failed" if refreshes >= 3 else "queued", refresh_plan=True,
                              auth_refreshes=refreshes, error=str(exc), updated_at=queue.now_iso())
        return paused or _live(item_id, current)
    except Offline as exc:
        current = _live(item_id, item)
        # Keep inflight_create durable: a timeout cannot tell whether the server committed.
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
    except PermanentUploadError as exc:
        current = _live(item_id, item)
        diverted = _divert(current, transport)
        if diverted is not None:
            return diverted
        failed = queue.update(
            item_id, if_version=current.get("version"), if_status=queue.OPEN,
            status="failed", error=str(exc)[:80], updated_at=queue.now_iso(),
        )
        return failed or _live(item_id, current)
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
