"""Canonical backlog counts must agree between the master plan and ticket files."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.report_ticket_status import ticket_snapshot


class TicketStatusTests(unittest.TestCase):
    def test_real_backlog_has_one_canonical_status_for_each_ticket(self):
        result = ticket_snapshot()
        self.assertEqual(result["total"], 125)
        self.assertEqual(result["done"], 86)
        self.assertEqual(result["not_done"], 39)
        self.assertEqual(len(result["not_done_ticket_ids"]), 39)
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
