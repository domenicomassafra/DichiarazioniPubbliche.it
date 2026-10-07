"""Regression tests for independent repository ticket filename/H1 identities."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
