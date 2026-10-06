"""Operator-runbook contract tests for DP-505.

The runtime taxonomy owns page/no-page policy.  The runbook must stay a faithful,
fail-closed operator rendering of that policy and must name an internal incident owner
and private contact route without pretending that launch-facing contacts are complete.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.taxonomy import get  # noqa: E402


RUNBOOK = ROOT / "docs" / "ops" / "operator-runbook.md"
SECURITY = ROOT / "SECURITY.md"


def _decision_matrix(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(
            r"^\| `([^`]+)` \| `(PAGE|NO_PAGE)` \| .+ \|$",
            line,
        )
        if match:
            rows[match.group(1)] = match.group(2)
    return rows


class OperatorRunbookContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runbook = RUNBOOK.read_text(encoding="utf-8")
        self.security = SECURITY.read_text(encoding="utf-8")

    def test_representative_matrix_matches_taxonomy_page_policy(self) -> None:
        matrix = _decision_matrix(self.runbook)
        expected_states = {
            "DEAD_LETTER",
            "FAILED",
            "OMNIROUTE_HTTP",
            "CLAIM_EXTRACTION_CANARY_FAILED",
            "SLO_BREACH",
            "OMNIROUTE_API_KEY_MISSING",
            "GROQ_API_KEY_MISSING",
            "DEFERRED",
            "COST",
            "SLO_AT_RISK",
            "SLO_UNKNOWN",
        }
        self.assertEqual(set(matrix), expected_states)
        for state, decision in matrix.items():
            with self.subTest(state=state):
                self.assertEqual(decision == "PAGE", get(state).page)

    def test_runbook_assigns_operational_owner_and_private_contact_path(self) -> None:
        self.assertIn(
            "primary operational incident owner is the repository owner",
            self.runbook.lower(),
        )
        self.assertIn("[`SECURITY.md`](../../SECURITY.md)", self.runbook)
        self.assertIn(
            "report security issues privately to the\nrepository owner",
            self.security,
        )

    def test_runbook_does_not_claim_public_contact_closure(self) -> None:
        self.assertIn("public security email", self.runbook)
        self.assertIn("still pre-launch decisions", self.runbook)
        self.assertIn("must not be misrepresented", self.runbook)

    def test_forbidden_remedies_remain_explicit(self) -> None:
        forbidden = (
            "never switch model/provider",
            "never lower validation/publication gates",
            "never hand-edit canonical transcript/evidence/finding state",
            "never treat `UNKNOWN` as healthy",
        )
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.runbook)


if __name__ == "__main__":
    unittest.main()
