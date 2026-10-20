"""DP-314 rejects evidence overflow before inspecting row metadata."""
import unittest
from dataclasses import replace
from unittest.mock import patch

from dichiarazioni_pubbliche.requirement_research_batch_v1 import build_research_batch
from tests.test_dp314_verification_requirements import claim, sources


class GuardedField(str):
    def __deepcopy__(self, memo):
        raise AssertionError("EXCESS_EVIDENCE_FIELD_COPIED")


class PrecopyEvidenceLimitTests(unittest.TestCase):
    def test_oversize_per_claim_and_global_fail_before_metadata_snapshot(self):
        requirement = claim()
        first, _ = sources()
        poison = replace(first, locator_ref=GuardedField("locator:overflow"))
        for count in (129, 513):
            with self.subTest(count=count):
                rows = (first,) * (count - 1) + (poison,)
                with patch(
                    "dichiarazioni_pubbliche.requirement_research_batch_v1._snap",
                    side_effect=AssertionError("EXCESS_EVIDENCE_SNAPSHOT"),
                ) as snapshot:
                    with self.assertRaisesRegex(ValueError, "^BATCH_TOO_LARGE$"):
                        build_research_batch((requirement,), {requirement.claim_id: rows})
                    snapshot.assert_not_called()
                self.assertEqual(str(poison.locator_ref), "locator:overflow")


    def test_global_cap_across_valid_per_claim_sizes(self):
        sample_claim = claim()
        sample_evidence, _ = sources()
        requirements = tuple(
            replace(sample_claim, claim_id=f"claim:overflow:{n}")
            for n in range(5)
        )
        evidence_by_claim = {
            requirement.claim_id: (sample_evidence,) * 128
            for requirement in requirements[:-1]
        }
        poison = replace(sample_evidence, locator_ref=GuardedField("locator:last"))
        evidence_by_claim[requirements[-1].claim_id] = (poison,)
        self.assertEqual(sum(map(len, evidence_by_claim.values())), 513)
        self.assertTrue(all(len(rows) <= 128 for rows in evidence_by_claim.values()))
        with patch(
            "dichiarazioni_pubbliche.requirement_research_batch_v1._snap",
            side_effect=AssertionError("EXCESS_EVIDENCE_SNAPSHOT"),
        ) as snapshot:
            with self.assertRaisesRegex(ValueError, "^BATCH_TOO_LARGE$"):
                build_research_batch(requirements, evidence_by_claim)
            snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
