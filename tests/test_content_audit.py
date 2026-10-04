import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.content_audit import load_audit, summarize_audit, validate_audit


AUDIT = ROOT / "poc" / "content" / "raffagiulians-bollo-2026" / "content-audit.json"


class ContentAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = load_audit(AUDIT)

    def test_audit_contract(self):
        self.assertEqual(validate_audit(self.audit), [])

    def test_all_84_transcript_segments_are_classified(self):
        summary = summarize_audit(self.audit)
        self.assertEqual(summary["segment_count"], 84)

    def test_inserted_meloni_clip_is_not_attributed_to_creator(self):
        inserted = [
            row
            for row in self.audit["segment_coverage"]
            if 414 <= row["start_seconds"] <= 434
        ]
        self.assertTrue(inserted)
        self.assertTrue(
            all(row["speaker"] == "Giorgia Meloni (inserted clip)" for row in inserted)
        )

    def test_numeric_bollo_claims_have_secondary_asr(self):
        numeric_ids = {"C07", "C08", "C09"}
        rows = {row["id"]: row for row in self.audit["claims"]}
        for cid in numeric_ids:
            self.assertEqual(rows[cid]["asr_verification"]["status"], "CONFIRMED")

    def test_no_aggregate_creator_score(self):
        forbidden = {
            "accuracy_score",
            "truth_score",
            "person_score",
            "creator_score",
            "overall_verdict",
        }
        self.assertFalse(forbidden.intersection(self.audit))


if __name__ == "__main__":
    unittest.main()
