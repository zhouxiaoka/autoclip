"""Preview, one-click submit, and consent changes. Generation state is read, never written."""
from __future__ import annotations

import hashlib
import json
import logging
import os

from backend.core.path_utils import get_data_directory, get_log_file_path
from backend.services.diagnostics import media, queue, upload
from backend.services.diagnostics.consent import Consent, load, update
from backend.services.diagnostics.manifest import build_manifest, validate_manifest
from backend.services.diagnostics.redact import sanitized_log_file
from backend.services.studio import store

logger = logging.getLogger(__name__)

_RECEIPT_KEYS = (
    "attempt_id", "flow_id", "sequence", "retry_of", "kind", "trigger", "state",
    "error_code", "failure_stage", "upstream_error_type", "unexpected_type",
    "secondary_error_codes", "secondary_upstream_error_types", "secondary_failure_stages",
    "finished_at", "summary",
)


class DiagnosticsError(ValueError):
    def __init__(self, reason: str, status: int = 422):
        super().__init__(reason)
        self.reason = reason
        self.status = status


def _state(project_id: str) -> dict:
    try:
        path = store.directory(project_id) / "metadata" / "studio.json"
    except Exception as exc:
        raise DiagnosticsError("project", 404) from exc
    if not path.is_file():
        raise DiagnosticsError("project", 404)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DiagnosticsError("project_unreadable", 409) from exc
    return raw if isinstance(raw, dict) else {}


def _receipt(state: dict, attempt_id: str) -> dict:
    rows = [row for row in state.get("attempts") or [] if isinstance(row, dict)]
    if attempt_id:
        match = next((row for row in rows if row.get("attempt_id") == attempt_id), None)
        if match is None:
            raise DiagnosticsError("attempt", 404)
        if match.get("state") not in {"failed", "partial"}:
            raise DiagnosticsError("not_failed", 409)
        chosen = match
    else:
        failed = [row for row in rows if row.get("state") in {"failed", "partial"}]
        if not failed:
            raise DiagnosticsError("attempt", 404)
        chosen = max(failed, key=lambda row: row.get("sequence") or 0)
    return {key: chosen.get(key) for key in _RECEIPT_KEYS}


def _log_text(project_id: str) -> str:
    records = sanitized_log_file(get_log_file_path(), project_id=project_id, limit=50)
    return "\n".join(
        f"{row['timestamp']} {row['level']} {row['message']}" for row in records
    )


def preview(project_id: str, attempt_id: str, *, probe=None) -> dict:
    receipt = _receipt(_state(project_id), attempt_id)
    manifest = build_manifest(receipt, log_text=_log_text(project_id), project_id=project_id)
    consent = load()
    view = consent.public()
    view["endpoint_configured"] = bool(upload.endpoint())
    return {
        "manifest": manifest,
        "files": media.candidates(project_id, probe=probe),
        "consent": view,
        "purpose": "troubleshooting_and_product_improvement",
        "not_for_training": True,
        "excerpt_limitation": "A short excerpt starts at the beginning and can miss a failure that happens later.",
    }


def _key(attempt_id: str, roles: list[str], manifest: dict, explicit: bool) -> str:
    payload = json.dumps(
        {"attempt_id": attempt_id, "roles": sorted(roles), "explicit": explicit, "manifest": manifest},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def submit(project_id: str, attempt_id: str, *, roles: list[str], informed: bool,
           full_original_ack: bool = False, subtitle_ack: bool = False,
           also_enable_background: bool = False, save_local: bool = False,
           transport=None, cut=None) -> dict:
    if not informed:
        raise DiagnosticsError("informed_required", 422)
    wanted = []
    for role in roles:
        if role not in {"excerpt", "original", "subtitle"}:
            raise DiagnosticsError("role", 422)
        if role not in wanted:
            wanted.append(role)
    if "original" in wanted and not full_original_ack:
        raise DiagnosticsError("full_original_required", 422)
    if "subtitle" in wanted and not subtitle_ack:
        raise DiagnosticsError("subtitle_required", 422)
    consent = load()
    if also_enable_background:
        consent = update(diagnostics=True, media=consent.media, full_original=consent.full_original, informed=True)
    receipt = _receipt(_state(project_id), attempt_id)
    manifest = build_manifest(receipt, log_text=_log_text(project_id), project_id=project_id)
    if validate_manifest(manifest):
        raise DiagnosticsError("manifest_rejected", 422)
    item_id = queue.new_id()
    files = []
    if wanted:
        excerpt_dir = get_data_directory() / "diagnostics" / "excerpts" / item_id
        if excerpt_dir.is_symlink():
            raise DiagnosticsError("path", 422)
        try:
            files = media.materialize(project_id, wanted, excerpt_dir=excerpt_dir, cut=cut)
        except media.MediaRejected as exc:
            raise DiagnosticsError(exc.reason, 422) from exc
    item = {
        "id": item_id,
        "idempotency_key": _key(attempt_id, wanted, manifest, True),
        "project_id": project_id,
        "attempt_id": attempt_id,
        "created_at": queue.now_iso(),
        "updated_at": queue.now_iso(),
        "status": "queued",
        "epoch": consent.epoch,
        "consent_version": consent.text_version,
        "explicit": True,
        "save_local": bool(save_local) or not upload.endpoint(),
        "manifest": manifest,
        "files": files,
        "attempts": 0,
        "upload": {},
    }
    stored = queue.enqueue(item)
    if stored.get("status") == "failed" and stored.get("error") == "queue_full":
        raise DiagnosticsError("queue_full", 429)
    upload.wake()
    if os.getenv("AUTOCLIP_DIAGNOSTICS_SYNC") == "1":
        upload.pump_once(transport)
        stored = next((row for row in queue.list_items() if row.get("id") == stored["id"]), stored)
    return _public_item(stored)


def set_consent(*, diagnostics: bool, media: bool, full_original: bool, informed: bool, transport=None) -> Consent:
    previous = load()
    consent = update(diagnostics=diagnostics, media=media, full_original=full_original, informed=informed)
    if consent.epoch != previous.epoch:
        cancelled = queue.cancel_before(consent.epoch)
        _abort_remote(cancelled, transport)
    return consent


def _abort_remote(items: list[dict], transport) -> None:
    base = upload.endpoint()
    if not base or transport is None:
        transport = upload.UrllibTransport() if base else None
    if transport is None:
        return
    for item in items:
        session = item.get("upload") if isinstance(item.get("upload"), dict) else {}
        case_id = session.get("case_id") or item.get("case_id")
        capability = session.get("capability")
        if case_id and capability:
            try:
                transport.abort(base, case_id, capability)
            except (OSError, RuntimeError, ValueError, TypeError):
                logger.warning("diagnostics abort failed")
                continue


def delete_local(item_id: str, *, transport=None) -> dict:
    found = next((row for row in queue.list_items() if row.get("id") == item_id), None)
    if found is None:
        raise DiagnosticsError("case", 404)
    session = found.get("upload") if isinstance(found.get("upload"), dict) else {}
    capability = session.get("capability")
    case_id = session.get("case_id") or found.get("case_id")
    base = upload.endpoint()
    if base and capability and case_id:
        transport = transport or upload.UrllibTransport()
        try:
            if hasattr(transport, "delete"):
                transport.delete(base, case_id, capability)
            else:
                transport.abort(base, case_id, capability)
        except Exception as exc:
            raise DiagnosticsError("delete_failed", 502) from exc
    updated = queue.update(item_id, status="deleted", updated_at=queue.now_iso())
    return _public_item(updated or found)


def _public_item(item: dict) -> dict:
    session = item.get("upload") if isinstance(item.get("upload"), dict) else {}
    return {
        "id": item.get("id"),
        "status": item.get("status"),
        "attempt_id": item.get("attempt_id"),
        "case_id": session.get("case_id") or item.get("case_id"),
        "error": item.get("error") or "",
        "deletable": bool(session.get("capability") or item.get("case_id")),
        "export_ready": item.get("status") == "saved_local",
        "export_path": item.get("export_path") or "",
    }


def background_enqueue(project_id: str, receipt: dict, *, cut=None) -> dict | None:
    consent = load()
    if not consent.diagnostics or not consent.diagnostics_at:
        return None
    finished = receipt.get("finished_at")
    if not isinstance(finished, str):
        return None
    from datetime import datetime, timezone
    def parse(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    try:
        if parse(finished) < parse(consent.diagnostics_at):
            return None
    except ValueError:
        return None
    roles: list[str] = []
    if consent.full_original:
        roles.append("original")
    elif consent.media:
        roles.append("excerpt")
    manifest = build_manifest(receipt, log_text=_log_text(project_id), project_id=project_id)
    item_id = queue.new_id()
    files = []
    if roles:
        excerpt_dir = get_data_directory() / "diagnostics" / "excerpts" / item_id
        files = media.materialize(project_id, roles, excerpt_dir=excerpt_dir, cut=cut)
    item = {
        "id": item_id,
        "idempotency_key": _key(str(receipt.get("attempt_id")), roles, manifest, False),
        "project_id": project_id,
        "attempt_id": receipt.get("attempt_id"),
        "created_at": queue.now_iso(),
        "updated_at": queue.now_iso(),
        "status": "queued",
        "epoch": consent.epoch,
        "consent_version": consent.text_version,
        "explicit": False,
        "save_local": False,
        "manifest": manifest,
        "files": files,
        "attempts": 0,
        "upload": {},
    }
    stored = queue.enqueue(item)
    upload.wake()
    return stored
