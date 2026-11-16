"""Notice a failure after studio.json is durable. Never writes generation or attempt state."""
from __future__ import annotations

import logging
import os
import threading

from backend.services.diagnostics.consent import load
from backend.services.diagnostics.service import DiagnosticsError, background_enqueue

logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
_PENDING: list[dict] = []
_KEYS = (
    "attempt_id", "flow_id", "sequence", "retry_of", "kind", "trigger", "state",
    "error_code", "failure_stage", "upstream_error_type", "unexpected_type",
    "secondary_error_codes", "secondary_upstream_error_types", "secondary_failure_stages",
    "finished_at", "summary",
)


def schedule_new_failures(project_id: str, previous: dict | None, data: dict) -> None:
    """Called under the studio lock. Copies identifiers only; does not read media or the network."""
    if not load().diagnostics:
        return
    prior = {
        row.get("attempt_id"): row.get("state")
        for row in ((previous or {}).get("attempts") or []) if isinstance(row, dict)
    }
    snaps = []
    for row in data.get("attempts") or []:
        if not isinstance(row, dict) or row.get("state") not in {"failed", "partial"}:
            continue
        if prior.get(row.get("attempt_id")) != "open":
            continue
        snaps.append({"project_id": project_id, "receipt": {key: row.get(key) for key in _KEYS}})
    if not snaps:
        return
    with _LOCK:
        _PENDING.extend(snaps)


def deliver_pending() -> None:
    with _LOCK:
        snaps = list(_PENDING)
        _PENDING.clear()
    if not snaps:
        return
    if os.getenv("AUTOCLIP_DIAGNOSTICS_SYNC") == "1":
        _enqueue_all(snaps)
        return
    threading.Thread(target=_enqueue_all, args=(snaps,), daemon=True, name="diagnostics-observe").start()


def _enqueue_all(snaps: list[dict]) -> None:
    for snap in snaps:
        try:
            background_enqueue(snap["project_id"], snap["receipt"])
        except (DiagnosticsError, OSError, RuntimeError, ValueError, TypeError):
            logger.warning("diagnostics enqueue skipped")
