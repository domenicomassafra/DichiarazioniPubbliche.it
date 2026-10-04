import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.correction_runtime import (  # noqa: E402
    deterministic_correction_id,
    deterministic_right_of_reply_id,
    normalize_evidence_urls,
)


class CorrectionRuntimeTests(unittest.TestCase):
    def test_reply_id_is_deterministic(self):
        kwargs = dict(
            finding_id="finding:a",
            body="Replica documentata.",
            submitter_name="Persona",
            submitter_role="Ruolo",
            evidence_urls=["https://example.test/evidence"],
        )
        self.assertEqual(
            deterministic_right_of_reply_id(**kwargs),
            deterministic_right_of_reply_id(**kwargs),
        )

    def test_reply_urls_are_http_only(self):
        with self.assertRaises(ValueError):
            normalize_evidence_urls(["javascript:alert(1)"])

    def test_reply_inputs_are_bounded(self):
        with self.assertRaises(ValueError):
            normalize_evidence_urls(["https://example.test/x"] * 33)
        with self.assertRaises(ValueError):
            deterministic_right_of_reply_id(
                finding_id="finding:a",
                body="ok",
                submitter_name="x" * 301,
                submitter_role=None,
                evidence_urls=[],
            )

    def test_correction_requires_distinct_finding(self):
        with self.assertRaises(ValueError):
            deterministic_correction_id(
                finding_id="finding:a",
                previous_finding_id="finding:a",
                reason="Changed evidence.",
                changed_fields={"assessment": ["A", "B"]},
            )

    def test_correction_changed_fields_are_bounded(self):
        with self.assertRaises(ValueError):
            deterministic_correction_id(
                finding_id="finding:new",
                previous_finding_id="finding:old",
                reason="Changed evidence.",
                changed_fields={"blob": "x" * 40_000},
            )


if __name__ == "__main__":
    unittest.main()
