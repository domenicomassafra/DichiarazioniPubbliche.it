"""Regression tests for independent repository ticket filename/H1 identities."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_repository_contract as contract


class TicketIdentityContractTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tickets_dir = Path(temporary.name)

    def ticket(self, filename: str, title_id: str | None) -> None:
        heading = f"# {title_id} — Example\n" if title_id else "# Missing ticket ID\n"
        (self.tickets_dir / filename).write_text(
            heading + "Status: FUTURE\n## Acceptance criteria\n",
            encoding="utf-8",
        )

    def problems(self) -> list[str]:
        with patch.object(contract, "TICKETS_DIR", self.tickets_dir):
            return contract.check_tickets()

    def test_matching_filename_and_h1_ids_pass(self) -> None:
        self.ticket("DP-101-first.md", "DP-101")
        self.ticket("DP-102-second.md", "DP-102")
        self.assertEqual(self.problems(), [])

    def test_filename_h1_mismatch_fails(self) -> None:
        self.ticket("DP-101-first.md", "DP-102")
        self.assertIn(
            "DP-101-first.md: filename id DP-101 does not match H1 id DP-102",
            self.problems(),
        )

    def test_duplicate_filename_ids_with_distinct_h1s_fail(self) -> None:
        self.ticket("DP-101-first.md", "DP-101")
        self.ticket("DP-101-second.md", "DP-102")
        self.assertTrue(
            any(problem.startswith("duplicate filename id DP-101 ") for problem in self.problems())
        )
        self.assertFalse(any(problem.startswith("duplicate ticket id ") for problem in self.problems()))

    def test_duplicate_h1_ids_with_distinct_filenames_fail(self) -> None:
        self.ticket("DP-101-first.md", "DP-101")
        self.ticket("DP-102-second.md", "DP-101")
        self.assertTrue(
            any(problem.startswith("duplicate ticket id DP-101 ") for problem in self.problems())
        )
        self.assertFalse(any(problem.startswith("duplicate filename id ") for problem in self.problems()))

    def test_filename_duplicate_still_fails_when_h1_missing(self) -> None:
        self.ticket("DP-101-first.md", None)
        self.ticket("DP-101-second.md", "DP-101")
        problems = self.problems()
        self.assertTrue(any(problem.startswith("duplicate filename id DP-101 ") for problem in problems))
        self.assertTrue(any("no 'DP-###' ticket id in the H1 title" in problem for problem in problems))

    def test_malformed_filename_id_fails_independently_of_valid_h1(self) -> None:
        self.ticket("DP-1234-invalid.md", "DP-101")
        self.assertIn(
            "DP-1234-invalid.md: no 'DP-###' ticket id in filename",
            self.problems(),
        )


class TicketArchiveContractTests(unittest.TestCase):
    def test_repository_contract_does_not_enforce_a_live_plan_status_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tickets = root / "docs/tickets"
            tickets.mkdir(parents=True)
            (root / "PLAN.md").write_text(
                "| DP-235 | FUTURE | Private source pilot | DP-209 |\n", encoding="utf-8"
            )
            (tickets / "DP-235-private-source-pilot.md").write_text(
                "# DP-235 — Private source pilot\nStatus: IN PROGRESS\n## Acceptance criteria\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with (
                patch.object(contract, "ROOT", root),
                patch.object(contract, "TICKETS_DIR", tickets),
                patch.object(sys, "argv", ["check_repository_contract.py", "--only", "tickets"]),
                contextlib.redirect_stdout(output),
            ):
                result = contract.main()
            self.assertEqual(result, 0, output.getvalue())
            self.assertNotIn("TICKET_STATUS_DRIFT", output.getvalue())


class LiveDocumentationAuthorityTests(unittest.TestCase):
    def test_github_is_the_only_live_status_reader(self) -> None:
        plan = (contract.ROOT / "PLAN.md").read_text(encoding="utf-8")
        readme = (contract.ROOT / "README.md").read_text(encoding="utf-8")
        tracker = (contract.ROOT / "docs/agents/issue-tracker.md").read_text(encoding="utf-8")
        self.assertIn("gh issue list", readme[:2500])
        self.assertNotIn("Read the live backlog with `python3 tools/report_ticket_status.py", readme)
        self.assertIn("GitHub Issues", plan[:1500])
        self.assertIn("historical", plan[:1500].lower())
        self.assertIn("GitHub Issues", tracker)
        self.assertNotIn("for current", tracker)
        self.assertIn("## Historical frozen checkpoint", plan)
        self.assertNotIn("## Current frozen checkpoint", plan)
        self.assertNotIn("Preserve the canonical 125 statuses", plan)


if __name__ == "__main__":
    unittest.main()
