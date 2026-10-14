"""The tracking-plan inventory is well-formed and mentions the 1.5.8 close."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_tracking_inventory as check  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]


class TrackingInventoryTests(unittest.TestCase):
    def test_inventory_passes_on_this_tree(self) -> None:
        errors = check.check(ROOT)
        self.assertEqual(errors, [])

    def test_feedback_submitted_allows_user_text(self) -> None:
        data = check._load(ROOT / "docs" / "analytics" / "event_inventory.json")
        row = data["events"]["feedback_submitted"]
        self.assertEqual(row.get("kind"), "user_submitted")
        self.assertTrue(row.get("user_initiated"))
        self.assertIn("text", row.get("allow") or [])
        self.assertIn("contact", row.get("allow") or [])
        self.assertNotIn("text", row.get("forbid") or [])
        self.assertEqual(data["privacy"]["user_submitted_events"], ["feedback_submitted"])
        self.assertEqual(check.user_content_errors(data), [])

    def test_auto_events_must_not_allow_user_content(self) -> None:
        data = check._load(ROOT / "docs" / "analytics" / "event_inventory.json")
        for name, spec in data["events"].items():
            if name == "feedback_submitted":
                continue
            allow = set((spec or {}).get("allow") or [])
            self.assertFalse(allow & {"text", "contact"}, name)
            self.assertNotEqual((spec or {}).get("kind"), "user_submitted", name)

    def test_checker_rejects_auto_event_user_content(self) -> None:
        data = check._load(ROOT / "docs" / "analytics" / "event_inventory.json")
        data["events"]["studio_import_requested"] = {
            **data["events"]["studio_import_requested"],
            "allow": ["text"],
        }
        errors = check.user_content_errors(data)
        self.assertTrue(any("studio_import_requested" in item for item in errors))

    def test_checker_rejects_feedback_without_allow(self) -> None:
        data = check._load(ROOT / "docs" / "analytics" / "event_inventory.json")
        data["events"]["feedback_submitted"] = {
            "status": "keep",
            "domain": "feedback",
            "path": "capture",
            "forbid": ["text", "contact"],
        }
        errors = check.user_content_errors(data)
        self.assertTrue(any("feedback_submitted" in item for item in errors))
        self.assertTrue(any("allow" in item for item in errors))

    def test_publish_export_is_legacy_with_merge(self) -> None:
        data = check._load(ROOT / "docs" / "analytics" / "event_inventory.json")
        row = data["events"]["publish_export_finished"]
        self.assertEqual(row["status"], "legacy")
        self.assertEqual(row["merge"], "studio_export_finished")
        self.assertEqual(row["stop"], "1.5.8")

    def test_transition_milestone_is_1_5_8(self) -> None:
        data = check._load(ROOT / "docs" / "analytics" / "event_inventory.json")
        self.assertEqual(data["dates"]["close_transition"], "1.5.8")
        self.assertEqual(data["dates"]["stop_legacy_emit"], "1.5.8")
        self.assertEqual(data["dates"]["delete_wrappers"], "1.5.8")
        self.assertEqual(data["transition"]["milestone"], "1.5.8")
        self.assertEqual(set(data["transition"]["tasks"]), set(check.REQUIRED_TASKS))
        self.assertTrue(data["transition"]["keep_query_maps"])

    def test_plan_has_no_2027_calendar_close(self) -> None:
        plan = (ROOT / "docs" / "analytics" / "TRACKING_PLAN.md").read_text(encoding="utf-8")
        self.assertNotIn("2027-01-12", plan)
        self.assertNotIn("2027-02-09", plan)
        self.assertIn("§12.1", plan)
        self.assertIn("single_os_enum", plan)

    def test_current_version_defers_producer_gates(self) -> None:
        version = check.app_version(ROOT)
        self.assertEqual(version, "1.5.7")
        self.assertFalse(check.transition_due(version))
        gaps = check.producer_transition_errors(ROOT)
        self.assertTrue(gaps)
        self.assertTrue(any(item.startswith("T1 ") for item in gaps))
        self.assertTrue(any(item.startswith("T2 ") for item in gaps))
        self.assertTrue(any(item.startswith("T3 ") for item in gaps))
        self.assertTrue(any(item.startswith("T4 ") for item in gaps))
        self.assertTrue(any(item.startswith("T5 ") for item in gaps))

    def test_1_5_8_enforces_producer_acceptance(self) -> None:
        errors = check.check(ROOT, version="1.5.8")
        joined = "\n".join(errors)
        self.assertTrue(errors)
        for prefix in ("T1 ", "T2 ", "T3 ", "T4 ", "T5 "):
            self.assertIn(prefix, joined)
        self.assertIn("feedback path missing envelope fields", joined)
        self.assertIn("publish_export_*", joined)


if __name__ == "__main__":
    unittest.main()
