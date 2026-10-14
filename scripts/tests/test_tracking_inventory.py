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
        self.assertTrue(errors)
        self.assertTrue(any("T1 " in item or "T4 " in item or "T5 " in item for item in errors))


if __name__ == "__main__":
    unittest.main()
