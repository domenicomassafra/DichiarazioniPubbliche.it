"""The archived PLAN and ticket headers can still be inspected as history."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.report_ticket_status import ticket_snapshot


class TicketStatusTests(unittest.TestCase):
    def test_archived_ticket_snapshot_is_explicitly_historical(self):
        result = ticket_snapshot()
        self.assertEqual(result["authority"], "historical-only")
        self.assertEqual(result["snapshot_as_of"], "2026-10-17")
        # The post-grilling 2026-10-10 implementation roadmap added 37
        # explicitly specced FUTURE tickets (125 -> 162). Future additions or
        # genuine GitHub issue closures must not alter the frozen archive.
        # Check archival consistency without treating these counts as open work.
        self.assertGreaterEqual(result["total"], 162)
        self.assertGreaterEqual(result["done"], 90)
        self.assertEqual(result["done"] + result["not_done"], result["total"])
        self.assertEqual(
            sum(result[key] for key in ("done", "in_progress", "blocked", "future", "ready")),
            result["total"],
        )
        self.assertEqual(len(result["not_done_ticket_ids"]), result["not_done"])
        self.assertEqual(len(set(result["not_done_ticket_ids"])), result["not_done"])
        self.assertNotIn("DP-607", result["not_done_ticket_ids"])
        self.assertIn("DP-705", result["not_done_ticket_ids"])
        self.assertTrue((ROOT / "docs/tickets/DP-443-first-integrated-source-reader-pilot.md").is_file())
        self.assertTrue(result["files_agree_with_plan"])

    def test_duplicate_and_missing_ticket_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs/tickets").mkdir(parents=True)
            (root / "PLAN.md").write_text("| DP-001 | DONE | First | - |\n")
            (root / "docs/tickets/DP-001-first.md").write_text("# DP-001\nStatus: DONE\n")
            self.assertEqual(ticket_snapshot(root)["not_done"], 0)
            (root / "docs/tickets/DP-001-duplicate.md").write_text("# DP-001\nStatus: DONE\n")
            with self.assertRaisesRegex(ValueError, "DUPLICATE"):
                ticket_snapshot(root)
            (root / "docs/tickets/DP-001-duplicate.md").unlink()
            (root / "docs/tickets/DP-001-first.md").unlink()
            with self.assertRaisesRegex(ValueError, "SET_DRIFT"):
                ticket_snapshot(root)

    def test_status_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs/tickets").mkdir(parents=True)
            (root / "PLAN.md").write_text("| DP-001 | DONE | First | - |\n")
            (root / "docs/tickets/DP-001-first.md").write_text("# DP-001\nStatus: BLOCKED\n")
            with self.assertRaisesRegex(ValueError, "STATUS_DRIFT"):
                ticket_snapshot(root)


if __name__ == "__main__":
    unittest.main()
