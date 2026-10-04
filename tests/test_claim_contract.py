import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_contract import (  # noqa: E402
    ClaimType,
    validate_atomic_claim,
)


class ClaimContractTests(unittest.TestCase):
    def claim(self, **overrides):
        values = {
            "claim_id": "claim:v1:test",
            "content_id": "content:a",
            "normalized_claim": "The rate is 10 percent.",
            "claim_type": ClaimType.NUMERIC_STATISTIC,
            "statement_date": "2026-09-24",
            "check_worthy": True,
            "source_segment_ids": ("segment:1",),
        }
        values.update(overrides)
        return validate_atomic_claim(**values)

    def test_identity_is_deterministic_and_provenance_preserved(self):
        left = self.claim()
        right = self.claim(source_segment_ids=("segment:1", "segment:1"))
        self.assertEqual(left.claim_id, right.claim_id)
        self.assertEqual(left.source_segment_ids, ("segment:1",))
        self.assertEqual(
            self.claim(claim_id="claim:other").claim_id,
            "claim:other",
        )

    def test_non_factual_type_cannot_be_check_worthy(self):
        with self.assertRaisesRegex(ValueError, "NON_FACTUAL"):
            self.claim(claim_type=ClaimType.VALUE_JUDGMENT, check_worthy=True)

    def test_unknown_type_and_missing_segments_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "TYPE_UNKNOWN"):
            self.claim(claim_type="NOT_A_TYPE")
        with self.assertRaisesRegex(ValueError, "PROVENANCE_REQUIRED"):
            self.claim(source_segment_ids=())

    def test_text_provenance_is_valid_alternative_to_timed_segments(self):
        claim = self.claim(
            source_segment_ids=(),
            source_text_provenance_ids=("text-provenance:abc",),
        )
        self.assertEqual(claim.source_segment_ids, ())
        self.assertEqual(
            claim.source_text_provenance_ids,
            ("text-provenance:abc",),
        )

    def test_temporal_scope_is_bounded(self):
        claim = self.claim(valid_from="2026-01-01", valid_until="2026-12-31")
        self.assertEqual(claim.temporal_scope.valid_from, "2026-01-01")
        with self.assertRaisesRegex(ValueError, "VALID_FROM_AFTER_STATEMENT"):
            self.claim(valid_from="2026-09-25")
        with self.assertRaisesRegex(ValueError, "TEMPORAL_SCOPE_INVALID"):
            self.claim(valid_from="2026-10-01", valid_until="2026-09-24")

    def test_statement_date_may_remain_unresolved(self):
        claim = self.claim(statement_date=None)
        self.assertIsNone(claim.temporal_scope.statement_date)


if __name__ == "__main__":
    unittest.main()
