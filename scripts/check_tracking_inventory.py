#!/usr/bin/env python3
"""Validate docs/analytics/event_inventory.json and, when present, event_catalog.json.

The tracking plan inventory is the source of truth. The emit-PR catalog must
list the same business events (status may be more specific). Missing catalog
is allowed on the docs-only branch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "analytics" / "event_inventory.json"
CATALOG = ROOT / "docs" / "analytics" / "event_catalog.json"
PLAN = ROOT / "docs" / "analytics" / "TRACKING_PLAN.md"
ALLOWED_STATUS = {"core", "keep", "legacy", "deprecated", "reserved"}
REQUIRED_DATES = ("plan_effective", "stop_legacy_emit", "delete_wrappers")


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


def check(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    inventory_path = root / "docs" / "analytics" / "event_inventory.json"
    catalog_path = root / "docs" / "analytics" / "event_catalog.json"
    plan_path = root / "docs" / "analytics" / "TRACKING_PLAN.md"
    data = _load(inventory_path)
    if not data.get("source_of_truth"):
        errors.append("event_inventory.json must set source_of_truth true")
    dates = data.get("dates") or {}
    for key in REQUIRED_DATES:
        if not dates.get(key):
            errors.append(f"dates.{key} is required")
    if dates.get("stop_legacy_emit") != "2027-01-12":
        errors.append("stop_legacy_emit must be 2027-01-12")
    if dates.get("delete_wrappers") != "2027-02-09":
        errors.append("delete_wrappers must be 2027-02-09")
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
    plan = plan_path.read_text(encoding="utf-8")
    for needle in (
        "2027-01-12", "publish_export", "legacy=true", "outcome_canon", "os_canon",
        "ANALYTICS_V2.md", "event_inventory.json", "captureBusinessEvent",
    ):
        if needle not in plan:
            errors.append(f"TRACKING_PLAN.md must mention {needle}")
    if catalog_path.is_file():
        catalog = _load(catalog_path)
        listed = listed_catalog_events(catalog)
        ignore = set(data.get("ignore") or [])
        inventory_names = set(events) | ignore
        extra = sorted(listed - inventory_names)
        # Catalog may expand reserved typed prefixes that have no call site.
        extra = [name for name in extra if not name.startswith("vision_provider_")]
        missing_from_catalog = sorted(
            name for name, spec in events.items()
            if spec.get("status") in {"core", "keep", "legacy", "deprecated"} and name not in listed
        )
        if extra:
            errors.append("catalog has events not in inventory: " + ", ".join(extra[:20]))
        if missing_from_catalog:
            errors.append("inventory events missing from catalog: " + ", ".join(missing_from_catalog[:20]))
    return errors


def main() -> int:
    errors = check()
    if errors:
        print("tracking inventory check failed:", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    catalog_note = "catalog present" if CATALOG.is_file() else "catalog absent (docs-only branch ok)"
    print(f"tracking inventory ok ({len(_load(INVENTORY)['events'])} events, {catalog_note})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
