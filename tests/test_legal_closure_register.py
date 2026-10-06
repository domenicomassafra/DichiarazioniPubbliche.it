"""DP-306 documentation-contract tests.

These checks validate the closure register as a control surface. They deliberately do
not interpret law or turn retrieved sources into legal conclusions.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "policy" / "legal-closure-register.md"
SOURCE_TICKETS = tuple(
    ROOT / "docs" / "tickets" / name
    for name in (
        "DP-301-intentionality-lie-policy.md",
        "DP-302-right-of-reply-intake-threat-model.md",
        "DP-303-correction-takedown-appeal-workflow.md",
        "DP-304-privacy-minimization-sensitive-person-policy.md",
        "DP-305-copyright-transcript-excerpt-policy.md",
    )
)

SOURCE_Q_RE = re.compile(r"^\|\s*(Q-30[1-5]-\d{2})\s*\|", re.MULTILINE)
CROSSWALK_RE = re.compile(
    r"^\|\s*(Q-30[1-5]-\d{2})\s*\|\s*(Q-306-\d{2})\s*\|\s*$",
    re.MULTILINE,
)
CLOSURE_ROW_RE = re.compile(
    r"^\|\s*(Q-306-\d{2})\s*\([^)]*\)\s*\|(.+?)\|\s*$",
    re.MULTILINE,
)
METADATA_ROW_RE = re.compile(
    r"^\|\s*(Q-306-\d{2})\s*\|(.+?)\|\s*$",
    re.MULTILINE,
)


def _section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading) + len(heading)
    end = text.index(next_heading, start)
    return text[start:end]


class LegalClosureRegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.register = REGISTER.read_text(encoding="utf-8")

    def test_every_dp301_to_dp305_question_has_exactly_one_crosswalk_row(self):
        source_ids: list[str] = []
        for ticket in SOURCE_TICKETS:
            source_ids.extend(SOURCE_Q_RE.findall(ticket.read_text(encoding="utf-8")))

        mappings = CROSSWALK_RE.findall(self.register)
        mapped_source_ids = [source_id for source_id, _ in mappings]
        mapped_targets = [target for _, target in mappings]

        self.assertEqual(len(source_ids), len(set(source_ids)))
        self.assertEqual(len(mapped_source_ids), len(set(mapped_source_ids)))
        self.assertEqual(set(mapped_source_ids), set(source_ids))
        self.assertTrue(
            all(re.fullmatch(r"Q-306-\d{2}", target) for target in mapped_targets)
        )

    def test_all_closure_rows_have_one_decision_control_metadata_row(self):
        closure = _section(
            self.register,
            "## Closure table",
            "## Source-question crosswalk",
        )
        metadata = _section(
            self.register,
            "## Decision-control metadata",
            "## Explicitly NOT verified",
        )

        closure_rows = CLOSURE_ROW_RE.findall(closure)
        metadata_rows = METADATA_ROW_RE.findall(metadata)
        closure_ids = [question_id for question_id, _ in closure_rows]
        metadata_ids = [question_id for question_id, _ in metadata_rows]

        self.assertEqual(closure_ids, [f"Q-306-{index:02d}" for index in range(1, 17)])
        self.assertEqual(len(metadata_ids), len(set(metadata_ids)))
        self.assertEqual(set(metadata_ids), set(closure_ids))

        for question_id, payload in metadata_rows:
            cells = [cell.strip() for cell in payload.split("|")]
            self.assertEqual(len(cells), 6, question_id)
            self.assertTrue(all(cells), question_id)
            self.assertIn("UNASSIGNED", cells[2], question_id)
            self.assertIn("DP-", cells[3], question_id)
            self.assertIn("review", cells[4].lower(), question_id)
            self.assertTrue(
                "UNSCHEDULED" in cells[5]
                or re.search(r"\d{4}-\d{2}-\d{2}", cells[5]),
                question_id,
            )

    def test_status_vocabulary_is_bounded_and_no_legal_decision_is_claimed(self):
        closure = _section(
            self.register,
            "## Closure table",
            "## Source-question crosswalk",
        )
        rows = CLOSURE_ROW_RE.findall(closure)
        statuses: list[str] = []
        for question_id, payload in rows:
            cells = [cell.strip() for cell in payload.split("|")]
            self.assertEqual(len(cells), 7, question_id)
            status = cells[2].strip("`")
            self.assertIn(
                status,
                {"OPEN", "EVIDENCE_COLLECTED", "DECIDED", "DEFERRED", "BLOCKED"},
                question_id,
            )
            statuses.append(status)

        self.assertEqual(statuses.count("BLOCKED"), 2)
        self.assertEqual(statuses.count("OPEN"), 14)
        self.assertNotIn("DECIDED", statuses)
        self.assertIn("0 `DECIDED`", self.register)
        self.assertIn("external DP-307 inputs", self.register)

    def test_every_closure_row_names_surface_safe_default_and_launch_impact(self):
        closure = _section(
            self.register,
            "## Closure table",
            "## Source-question crosswalk",
        )
        for question_id, payload in CLOSURE_ROW_RE.findall(closure):
            cells = [cell.strip() for cell in payload.split("|")]
            self.assertEqual(len(cells), 7, question_id)
            affected_surface = cells[4]
            safe_default = cells[5]
            launch_impact = cells[6]
            self.assertTrue(affected_surface, question_id)
            self.assertTrue(safe_default, question_id)
            self.assertIn("`BLOCKER`", launch_impact, question_id)


if __name__ == "__main__":
    unittest.main()
