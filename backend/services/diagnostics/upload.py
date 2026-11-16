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
    """Presigned R2 URLs, or loopback for tests. Never file:, credentials, or link-local."""
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
        request = urllib.request.Request(
            f"{base}/v1/cases/{case_id}/abort", data=b"{}", method="POST",
            headers={"Authorization": f"Bearer {capability}", "Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(request, timeout=20).close()
        except (OSError, urllib.error.URLError):
            return

    def put_part(self, url: str, data: bytes, headers: dict) -> None:
        if not allowed_upload_url(url):
            raise Offline("upload_url_rejected")
        request = urllib.request.Request(url, data=data, method="PUT", headers=headers)
        try:
            urllib.request.urlopen(request, timeout=120).close()
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


def upload_item(item: dict, transport, *, now: datetime | None = None) -> dict:
    """One attempt. Does not touch the generation attempt that produced the failure."""
    item_id = item["id"]
    try:
        _still_authorized(item)
    except Revoked:
        return queue.update(item_id, status="cancelled", error="revoked", updated_at=queue.now_iso()) or item
    problems = validate_manifest(item.get("manifest") or {})
    if problems:
        return queue.update(item_id, status="failed", error="manifest_rejected", updated_at=queue.now_iso()) or item
    base = endpoint()
    if not base:
        exported = _export_local(item) if item.get("save_local") or item.get("explicit") else ""
        status = "saved_local" if exported else "needs_endpoint"
        return queue.update(
            item_id, status=status, export_path=exported or None, error="" if exported else "no_endpoint",
            updated_at=queue.now_iso(),
        ) or item
    attempts = int(item.get("attempts") or 0)
    if not queue.due(item, now):
        return item
    try:
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
            try:
                _still_authorized(item)
            except Revoked:
                capability = created.get("capability")
                case_id = created.get("case_id")
                if capability and case_id:
                    try:
                        transport.abort(base, case_id, capability)
                    except (OSError, RuntimeError, ValueError, TypeError):
                        logger.warning("diagnostics abort after revoke failed")
                return queue.update(item_id, status="cancelled", error="revoked", upload={}, updated_at=queue.now_iso()) or item
            session = {
                "case_id": created.get("case_id"),
                "capability": created.get("capability"),
                "objects": created.get("uploads") or [],
                "done": [],
            }
            queue.update(item_id, upload=session, status="uploading", updated_at=queue.now_iso())
        for row in item.get("files") or []:
            path = media.reroot(str(row.get("path") or ""), _roots(item))
            if path is None:
                raise RuntimeError("path_rejected")
            digest, size = media.sha256_file(path, limit=row["size_bytes"])
            if digest != row.get("sha256") or size != row.get("size_bytes"):
                raise RuntimeError("byte_mismatch")
            obj = next((entry for entry in session.get("objects") or [] if entry.get("role") == row["role"]), None)
            if obj is None:
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
            for part in parts:
                marker = f"{row['role']}:{part.get('number')}"
                if marker in session.get("done", []):
                    continue
                _still_authorized(item)
                payload = media.read_range(path, int(part["offset"]), int(part["length"]))
                headers = dict(part.get("headers") or {})
                headers["Content-Length"] = str(part["length"])
                url = part.get("url")
                if not isinstance(url, str):
                    raise TypeError("missing_upload_url")
                transport.put_part(url, payload, headers)
                session.setdefault("done", []).append(marker)
                queue.update(item_id, upload=session, updated_at=queue.now_iso())
            _still_authorized(item)
            transport.complete(base, session["case_id"], session["capability"], {
                "object_id": obj.get("object_id"), "sha256": row["sha256"], "bytes": size,
            })
        return queue.update(
            item_id, status="uploaded", case_id=session.get("case_id"), error="", updated_at=queue.now_iso(),
        ) or item
    except Revoked:
        session = item.get("upload") if isinstance(item.get("upload"), dict) else {}
        if session.get("case_id") and session.get("capability"):
            try:
                transport.abort(base, session["case_id"], session["capability"])
            except (OSError, RuntimeError, ValueError, TypeError):
                logger.warning("diagnostics abort after revoke failed")
        return queue.update(item_id, status="cancelled", error="revoked", updated_at=queue.now_iso()) or item
    except Offline as exc:
        attempts += 1
        status = "failed" if attempts >= 8 else "offline"
        return queue.update(
            item_id, status=status, attempts=attempts, error=str(exc)[:80],
            next_attempt_at=queue.schedule_retry(attempts, now), updated_at=queue.now_iso(),
        ) or item
    except Exception as exc:  # noqa: BLE001 - a bad case must not be retried forever, and must not affect generation
        return queue.update(item_id, status="failed", error=type(exc).__name__, updated_at=queue.now_iso()) or item


def pump_once(transport=None, *, now: datetime | None = None) -> list[dict]:
    transport = transport or UrllibTransport()
    results = []
    for item in queue.list_items():
        if item.get("status") not in {"queued", "uploading", "offline", "needs_endpoint"}:
            continue
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
