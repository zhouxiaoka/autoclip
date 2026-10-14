#!/usr/bin/env python3
"""Validate docs/analytics/event_inventory.json and, when present, event_catalog.json.

The tracking plan inventory is the source of truth. The emit-PR catalog must
list the same business events (status may be more specific). Missing catalog
is allowed on the docs-only branch.

Transition close is the 1.5.8 milestone (not a calendar date). This script
always checks that the plan and inventory say so. Producer scans (single os,
single outcome, app_version only, QA/MCP/feedback envelope, legacy stop-or-tag)
run only when backend.__version__ is 1.5.8 or newer, so 1.5.7 CI stays green.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "analytics" / "event_inventory.json"
CATALOG = ROOT / "docs" / "analytics" / "event_catalog.json"
PLAN = ROOT / "docs" / "analytics" / "TRACKING_PLAN.md"
ALLOWED_STATUS = {"core", "keep", "legacy", "deprecated", "reserved"}
REQUIRED_DATES = ("plan_effective", "close_transition", "stop_legacy_emit", "delete_wrappers")
MILESTONE = "1.5.8"
FORBIDDEN_CALENDAR = ("2027-01-12", "2027-02-09")
REQUIRED_TASKS = (
    "single_os_enum",
    "single_outcome_enum",
    "app_version_only",
    "common_envelope",
    "legacy_stopped_or_tagged",
)
PLAN_NEEDLES = (
    "1.5.8",
    "publish_export",
    "legacy=true",
    "outcome_canon",
    "os_canon",
    "ANALYTICS_V2.md",
    "event_inventory.json",
    "captureBusinessEvent",
    "single_os_enum",
    "single_outcome_enum",
    "app_version_only",
    "common_envelope",
    "legacy_stopped_or_tagged",
    "`macos` / `windows` / `linux`",
    "envelope_properties()",
    "用户主动提交",
    "QA / MCP / 反馈",
    "user_submitted",
    "ingest_app_feedback.py",
)
USER_CONTENT_KEYS = ("text", "contact")
USER_SUBMITTED_KIND = "user_submitted"
USER_SUBMITTED_EVENT = "feedback_submitted"
ANALYTICS_PRODUCERS = (
    "frontend/src/analytics/workflow.ts",
    "frontend/src/analytics/lifecycle.ts",
    "frontend/src/analytics/studio.ts",
    "frontend/src/analytics/experience.ts",
    "frontend/src/analytics/operations.ts",
    "frontend/src/analytics/events.ts",
    "frontend/src/analytics/feedback.ts",
    "frontend/src/analytics/feedbackDraft.ts",
    "frontend/src/analytics/observer.ts",
    "frontend/src/services/api.ts",
    "backend/core/llm_emit.py",
    "backend/core/event_catalog.py",
    "backend/services/studio/qa/telemetry.py",
    "backend/services/mcp_telemetry.py",
    "backend/services/studio/template_telemetry.py",
)
LEGACY_EVENT_NAMES = (
    "clips_exported",
    "video_imported",
    "processing_failed",
    "api_key_configured",
    "example_project_opened",
    "provider_test_requested",
    "provider_test_accepted",
    "provider_test_request_failed",
    "provider_test_finished",
    "publish_export_requested",
    "publish_export_accepted",
    "publish_export_request_failed",
    "publish_export_finished",
    "import_requested",
    "import_accepted",
    "import_request_failed",
    "import_finished",
    "processing_requested",
    "processing_accepted",
    "processing_request_failed",
    "processing_started",
    "processing_finished",
    "processing_task_observed",
    "media_download_requested",
    "media_download_accepted",
    "media_download_request_failed",
    "media_download_received",
    "media_download_saved",
)
LEGACY_OPERATION_PREFIXES = (
    "publish_export",
    "import",
    "processing",
    "provider_test",
    "media_download",
)
ENVELOPE_FIELDS = ("app_version", "os", "analytics_environment", "runtime", "schema_version")
_OS_ALLOWLIST = re.compile(
    r"""(?:\bos\s*:\s*\[|OPERATING_SYSTEMS\s*=\s*[(\[])([^\]\)]+)"""
)
_OUTCOME_ALLOWLIST = re.compile(r"""\boutcome\s*:\s*\[([^\]]+)\]""")
_EMITTED_NAME = re.compile(
    r"""(?:captureBusinessEvent|posthog\.capture|_post_event|_emit|trackEvent)\(\s*['\"]([a-z_][a-z0-9_]*)['\"]"""
    r"""|['\"]event['\"]\s*:\s*['\"]([a-z_][a-z0-9_]*)['\"]"""
    r"""|:\s*['\"](clips_exported|video_imported|processing_failed|api_key_configured|example_project_opened)['\"]"""
)
_LEGACY_FLAG = re.compile(r"""['\"]?legacy['\"]?\s*:\s*true""", re.IGNORECASE)
_OBSERVE_OPERATION = re.compile(r"""observeOperation\(\s*['\"]([a-z_]+)['\"]""")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def listed_catalog_events(catalog: dict) -> set[str]:
    names = set(catalog.get("events") or {})
    ignore = set((catalog.get("scan") or {}).get("ignore_events") or [])
    for family in (catalog.get("families") or {}).values():
        verbs = family.get("verbs") or []
        for prefix in (family.get("prefixes") or {}):
            for verb in verbs:
                names.add(f"{prefix}_{verb}")
    return {name for name in names if name not in ignore}


def parse_version(value: str) -> tuple[int, int, int]:
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", (value or "").strip())
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def app_version(root: Path) -> str:
    text = (root / "backend" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else "0.0.0"


def transition_due(version: str, milestone: str = MILESTONE) -> bool:
    return parse_version(version) >= parse_version(milestone)


def _producer_texts(root: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    for relative in ANALYTICS_PRODUCERS:
        path = root / relative
        if path.is_file():
            texts[relative] = path.read_text(encoding="utf-8")
    return texts


def producer_transition_errors(root: Path) -> list[str]:
    """1.5.8 producer acceptance. Empty list means the milestone work is done."""
    errors: list[str] = []
    texts = _producer_texts(root)
    if not texts:
        return ["1.5.8 producer scan found no analytics producer files"]

    for relative, text in texts.items():
        for block in _OS_ALLOWLIST.findall(text):
            if re.search(r"""['\"]darwin['\"]|['\"]win32['\"]""", block):
                errors.append(f"T1 single_os_enum: {relative} still allows darwin/win32")
        for block in _OUTCOME_ALLOWLIST.findall(text):
            if re.search(r"""['\"]completed['\"]""", block):
                errors.append(f"T2 single_outcome_enum: {relative} outcome allowlist still has completed")

    lifecycle = texts.get("frontend/src/analytics/lifecycle.ts", "")
    mcp = texts.get("backend/services/mcp_telemetry.py", "")
    if lifecycle and re.search(r"captureBusinessEvent\(\s*'app_installed'[^)]*\bversion\s*,", lifecycle):
        errors.append("T3 app_version_only: lifecycle still sends version on app_installed")
    if lifecycle and re.search(r"captureBusinessEvent\(\s*'app_opened'[^)]*\bversion\s*,", lifecycle):
        errors.append("T3 app_version_only: lifecycle still sends version on app_opened")
    if mcp and re.search(r"""['\"]version['\"]\s*:\s*__version__""", mcp):
        errors.append("T3 app_version_only: MCP still sends version instead of app_version")

    qa = texts.get("backend/services/studio/qa/telemetry.py", "")
    feedback = texts.get("frontend/src/analytics/feedback.ts", "")
    feedback_draft = texts.get("frontend/src/analytics/feedbackDraft.ts", "")
    if qa and "envelope_properties" not in qa:
        errors.append("T4 common_envelope: QA telemetry does not call envelope_properties()")
    if mcp and "envelope_properties" not in mcp:
        errors.append("T4 common_envelope: MCP telemetry does not call envelope_properties()")
    # feedback_submitted may POST /capture/ with text/contact; the payload still needs the envelope.
    if feedback or feedback_draft:
        blob = f"{feedback}\n{feedback_draft}"
        missing = [
            field
            for field in ENVELOPE_FIELDS
            if not re.search(rf"""['\"]?{re.escape(field)}['\"]?\s*:""", blob)
        ]
        if missing:
            errors.append(
                "T4 common_envelope: feedback path missing envelope fields "
                + ", ".join(missing)
            )

    for relative, text in texts.items():
        emitted = {name for match in _EMITTED_NAME.findall(text) for name in match if name}
        leftover = sorted({name for name in emitted if name in LEGACY_EVENT_NAMES})
        prefixes = sorted({
            name for name in _OBSERVE_OPERATION.findall(text) if name in LEGACY_OPERATION_PREFIXES
        })
        if (leftover or prefixes) and not _LEGACY_FLAG.search(text):
            parts = leftover + [
                f"{name}_*"
                for name in prefixes
                if not any(item.startswith(f"{name}_") for item in leftover)
            ]
            errors.append(
                "T5 legacy_stopped_or_tagged: "
                f"{relative} still emits {', '.join(parts)} without legacy=true"
            )
    return errors


def user_content_errors(data: dict) -> list[str]:
    """Auto-collected events must not allow user content; feedback_submitted may."""
    errors: list[str] = []
    events = data.get("events") or {}
    privacy = data.get("privacy") or {}
    content_keys = tuple(privacy.get("user_content_keys") or USER_CONTENT_KEYS)
    submitted = set(privacy.get("user_submitted_events") or [])
    if USER_SUBMITTED_EVENT not in submitted:
        errors.append(f"privacy.user_submitted_events must include {USER_SUBMITTED_EVENT}")
    extra = sorted(submitted - {USER_SUBMITTED_EVENT})
    if extra:
        errors.append("unexpected user_submitted events: " + ", ".join(extra))
    if set(content_keys) != set(USER_CONTENT_KEYS):
        errors.append("privacy.user_content_keys must be text and contact")

    spec = events.get(USER_SUBMITTED_EVENT) or {}
    if spec.get("kind") != USER_SUBMITTED_KIND:
        errors.append(f"{USER_SUBMITTED_EVENT} must be kind={USER_SUBMITTED_KIND}")
    allow = set(spec.get("allow") or [])
    if not set(USER_CONTENT_KEYS) <= allow:
        errors.append(f"{USER_SUBMITTED_EVENT} must allow text and contact")
    forbid = set(spec.get("forbid") or [])
    if forbid & set(USER_CONTENT_KEYS):
        errors.append(f"{USER_SUBMITTED_EVENT} must not forbid text or contact")

    for name, row in events.items():
        row = row or {}
        if name == USER_SUBMITTED_EVENT:
            continue
        if row.get("kind") == USER_SUBMITTED_KIND:
            errors.append(f"{name}: only {USER_SUBMITTED_EVENT} may be {USER_SUBMITTED_KIND}")
        leaked = sorted(set(row.get("allow") or []) & set(USER_CONTENT_KEYS))
        if leaked:
            errors.append(f"{name}: auto-collected events must not allow {', '.join(leaked)}")
    return errors


def _document_errors(root: Path, data: dict, plan: str) -> list[str]:
    errors: list[str] = []
    if not data.get("source_of_truth"):
        errors.append("event_inventory.json must set source_of_truth true")
    dates = data.get("dates") or {}
    for key in REQUIRED_DATES:
        if not dates.get(key):
            errors.append(f"dates.{key} is required")
    for key in ("close_transition", "stop_legacy_emit", "delete_wrappers"):
        if dates.get(key) != MILESTONE:
            errors.append(f"dates.{key} must be {MILESTONE}")
    blob = json.dumps(data, ensure_ascii=False)
    for stamp in FORBIDDEN_CALENDAR:
        if stamp in blob or stamp in plan:
            errors.append(f"transition must not use calendar date {stamp}; close in {MILESTONE}")
    events = data.get("events") or {}
    if not isinstance(events, dict) or len(events) < 80:
        errors.append("inventory events must list the global plan (80+ names)")
    for name, spec in events.items():
        status = (spec or {}).get("status")
        if status not in ALLOWED_STATUS:
            errors.append(f"{name}: invalid status {status!r}")
        if status in {"legacy", "deprecated"} and name not in {
            "api_key_configured", "example_project_opened",
        } and not (spec or {}).get("stop") and not (spec or {}).get("delete"):
            errors.append(f"{name}: legacy/deprecated events need stop or delete")
        for field in ("stop", "delete"):
            value = (spec or {}).get(field)
            if value in FORBIDDEN_CALENDAR:
                errors.append(f"{name}.{field} must be {MILESTONE}, not {value}")
            if value and value != MILESTONE and field in spec and status in {"legacy", "deprecated"}:
                if value not in {"already", "none"}:
                    errors.append(f"{name}.{field} must be {MILESTONE}, not {value}")
    required = (
        "feedback_submitted", "output_branding_save_requested", "publish_export_finished",
        "studio_draft_create_requested", "studio_rewrite_requested",
        "studio_analysis_preferences_requested", "studio_framing_install_finished",
        "studio_platform_append_requested", "studio_platforms_selected",
        "studio_post_save_requested",
    )
    missing = [name for name in required if name not in events]
    if missing:
        errors.append("inventory missing previously uncovered events: " + ", ".join(missing))
    errors.extend(user_content_errors(data))
    tasks = ((data.get("transition") or {}).get("tasks") or {})
    if (data.get("transition") or {}).get("milestone") != MILESTONE:
        errors.append(f"transition.milestone must be {MILESTONE}")
    missing_tasks = [name for name in REQUIRED_TASKS if name not in tasks]
    if missing_tasks:
        errors.append("transition.tasks missing: " + ", ".join(missing_tasks))
    for needle in PLAN_NEEDLES:
        if needle not in plan:
            errors.append(f"TRACKING_PLAN.md must mention {needle}")
    return errors


def _catalog_errors(root: Path, data: dict) -> list[str]:
    catalog_path = root / "docs" / "analytics" / "event_catalog.json"
    if not catalog_path.is_file():
        return []
    catalog = _load(catalog_path)
    listed = listed_catalog_events(catalog)
    ignore = set(data.get("ignore") or [])
    events = data.get("events") or {}
    inventory_names = set(events) | ignore
    extra = sorted(listed - inventory_names)
    extra = [name for name in extra if not name.startswith("vision_provider_")]
    missing_from_catalog = sorted(
        name for name, spec in events.items()
        if spec.get("status") in {"core", "keep", "legacy", "deprecated"} and name not in listed
    )
    errors: list[str] = []
    if extra:
        errors.append("catalog has events not in inventory: " + ", ".join(extra[:20]))
    if missing_from_catalog:
        errors.append("inventory events missing from catalog: " + ", ".join(missing_from_catalog[:20]))
    return errors


def check(root: Path = ROOT, version: str | None = None) -> list[str]:
    inventory_path = root / "docs" / "analytics" / "event_inventory.json"
    plan_path = root / "docs" / "analytics" / "TRACKING_PLAN.md"
    data = _load(inventory_path)
    plan = plan_path.read_text(encoding="utf-8")
    errors = _document_errors(root, data, plan)
    errors.extend(_catalog_errors(root, data))
    resolved = version if version is not None else app_version(root)
    if transition_due(resolved):
        errors.extend(producer_transition_errors(root))
    return errors


def main() -> int:
    errors = check()
    if errors:
        print("tracking inventory check failed:", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    catalog_note = "catalog present" if CATALOG.is_file() else "catalog absent (docs-only branch ok)"
    due = "producer gates on" if transition_due(app_version(ROOT)) else f"producer gates deferred until {MILESTONE}"
    print(f"tracking inventory ok ({len(_load(INVENTORY)['events'])} events, {catalog_note}, {due})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
