"""The tracking-plan inventory is well-formed and mentions the global-plan contract."""
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
        self.assertEqual(row["stop"], "2027-01-12")


if __name__ == "__main__":
    unittest.main()
