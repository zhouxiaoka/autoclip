"""Preview, one-click submit, and consent changes. Generation state is read, never written."""
from __future__ import annotations

import hashlib
import json
import logging
import os

from backend.core.path_utils import get_data_directory, get_log_file_path
from backend.services.diagnostics import media, queue, upload
from backend.services.diagnostics.consent import Consent, commit, load
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
    files = [get_log_file_path(), get_data_directory() / "logs" / "autoclip.log"]
    records = []
    for file in files:
        records.extend(sanitized_log_file(file, project_id=project_id, limit=50))
    return "\n".join(
        f"{row['timestamp']} {row['level']} {row['message']}" for row in records[:50]
    )


def preview(project_id: str, attempt_id: str, *, probe=None) -> dict:
    receipt = _receipt(_state(project_id), attempt_id)
    _origin, source_link = _input_for_diagnostics(project_id)
    manifest = build_manifest(
        receipt, log_text=_log_text(project_id), project_id=project_id, source_link=source_link,
    )
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


def _enqueue_with_media(item: dict, roles: list[str], *, cut=None) -> dict:
    """A new excerpt belongs to this producer until the durable queue accepts it."""
    def command_key(selected):
        return _key(item["attempt_id"], selected, item["manifest"], item["explicit"])

    item["idempotency_key"] = command_key(roles)
    existing = queue.by_key(item["idempotency_key"], item["disposition"])
    if existing is not None:
        return existing
    owns_excerpt = "excerpt" in roles
    try:
        if roles:
            directory = get_data_directory() / "diagnostics" / "excerpts" / item["id"]
            try:
                if directory.is_symlink():
                    raise media.MediaRejected("path")
                item["files"] = media.materialize(item["project_id"], roles, excerpt_dir=directory, cut=cut)
            except media.MediaRejected as exc:
                if item["explicit"]:
                    raise DiagnosticsError(exc.reason, 422) from exc
                logger.warning("diagnostics media skipped")
                item["idempotency_key"] = command_key([])
        stored = queue.enqueue(item)
        if (stored["id"] == item["id"] and stored.get("error") != "queue_full"
                and any(row["role"] == "excerpt" for row in item["files"])):
            owns_excerpt = False
        return stored
    finally:
        if owns_excerpt:
            queue.discard_excerpt(item["id"])


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
        if consent.unreadable:
            raise DiagnosticsError("consent_unreadable", 422)
        _previous, consent = commit(
            diagnostics=True, media=consent.media, full_original=consent.full_original, informed=True,
        )
    origin, source_link = _input_for_diagnostics(project_id)
    if origin != "file":
        wanted = []
    receipt = _receipt(_state(project_id), attempt_id)
    manifest = build_manifest(
        receipt, log_text=_log_text(project_id), project_id=project_id, source_link=source_link,
    )
    if validate_manifest(manifest):
        raise DiagnosticsError("manifest_rejected", 422)
    item_id = queue.new_id()
    item = {
        "id": item_id,
        "project_id": project_id,
        "attempt_id": receipt["attempt_id"],
        "created_at": queue.now_iso(),
        "updated_at": queue.now_iso(),
        "status": "queued",
        "epoch": consent.epoch,
        "consent_version": consent.text_version,
        "explicit": True,
        "save_local": bool(save_local),
        "disposition": "local" if save_local else "upload",
        "version": 1,
        "manifest": manifest,
        "files": [],
        "attempts": 0,
        "upload": {},
    }
    stored = _enqueue_with_media(item, wanted, cut=cut)
    if stored.get("status") == "failed" and stored.get("error") == "queue_full":
        raise DiagnosticsError("queue_full", 429)
    upload.wake()
    if os.getenv("AUTOCLIP_DIAGNOSTICS_SYNC") == "1":
        upload.pump_once(transport)
        stored = next((row for row in queue.list_items() if row.get("id") == stored["id"]), stored)
    return _public_item(stored)


def _release_changed(items: list[dict]) -> None:
    for item in items:
        current = queue.get(str(item.get("id") or "")) or item
        queue.release_local_residue(current)


def set_consent(*, diagnostics: bool, media: bool, full_original: bool, informed: bool, transport=None) -> Consent:
    previous, consent = commit(
        diagnostics=diagnostics, media=media, full_original=full_original, informed=informed,
    )
    changed: list[dict] = []
    if previous.diagnostics and not consent.diagnostics:
        changed = queue.cancel_before(consent.epoch)
    elif consent.diagnostics:
        roles: set[str] = set()
        if previous.full_original and not consent.full_original:
            roles.add("original")
        if previous.media and not consent.media:
            roles.update({"excerpt", "subtitle"})
        if roles:
            changed = queue.cancel_with_roles(roles)
    if changed:
        _abort_remote(changed, transport)
        _release_changed(changed)
    return consent


def _abort_remote(items: list[dict], transport) -> None:
    if transport is None and upload.endpoint():
        transport = upload.UrllibTransport()
    if transport is None:
        return
    for item in items:
        if item.get("status") != "delete_pending":
            continue
        current = queue.get(str(item.get("id") or "")) or item
        upload.finish_delete(current, transport)


def delete_local(item_id: str, *, transport=None) -> dict:
    found = queue.get(item_id)
    if found is None:
        raise DiagnosticsError("case", 404)
    if found.get("status") == "deleted":
        return _public_item(found)
    finished = upload.finish_delete(found, transport or upload.UrllibTransport())
    return _public_item(finished)


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


def _input_for_diagnostics(project_id: str) -> tuple[str, str | None]:
    from backend.services.diagnostics.source import classify, sanitize_source_link
    decision = classify(project_id)
    link = sanitize_source_link(decision.source_url) if decision.origin == "link" else None
    return decision.origin, link


def background_enqueue(project_id: str, receipt: dict, *, cut=None) -> dict | None:
    consent = load()
    if not consent.diagnostics or consent.unreadable:
        return None
    finished = receipt.get("finished_at")
    if not isinstance(finished, str):
        return None
    if consent.persisted and consent.diagnostics_at:
        from datetime import datetime, timezone
        def parse(value: str) -> datetime:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        try:
            if parse(finished) < parse(consent.diagnostics_at):
                return None
        except ValueError:
            return None
    origin, source_link = _input_for_diagnostics(project_id)
    roles: list[str] = []
    if origin == "file":
        if consent.full_original:
            roles.append("original")
        elif consent.media:
            roles.append("excerpt")
    manifest = build_manifest(
        receipt, log_text=_log_text(project_id), project_id=project_id, source_link=source_link,
    )
    item_id = queue.new_id()
    item = {
        "id": item_id,
        "project_id": project_id,
        "attempt_id": receipt.get("attempt_id"),
        "created_at": queue.now_iso(),
        "updated_at": queue.now_iso(),
        "status": "queued",
        "epoch": consent.epoch,
        "consent_version": consent.text_version,
        "explicit": False,
        "save_local": False,
        "disposition": "upload",
        "version": 1,
        "manifest": manifest,
        "files": [],
        "attempts": 0,
        "upload": {},
    }
    stored = _enqueue_with_media(item, roles, cut=cut or media.cut_for_receipt(receipt))
    upload.wake()
    return stored
