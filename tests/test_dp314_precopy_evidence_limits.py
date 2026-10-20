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


    def test_sequence_rejects_evidence_overflow_without_capturing_fields(self):
        from dichiarazioni_pubbliche.verification_requirements_v1 import (
            compare_private_event_sequence,
        )
        requirement = claim()
        first, _ = sources()
        poison = replace(first, locator_ref=GuardedField("locator:sequence-excess"))
        rows = (first,) * 128 + (poison,)
        with patch(
            "dichiarazioni_pubbliche.verification_requirements_v1._snap",
            side_effect=AssertionError("SEQUENCE_EXCESS_EVIDENCE_SNAPSHOT"),
        ) as snapshot:
            with self.assertRaisesRegex(ValueError, "^SEQUENCE_OBSERVATIONS_INVALID$"):
                compare_private_event_sequence(
                    requirement, rows, (), left_event_ref="event:left",
                    right_event_ref="event:right", claimed_order="BEFORE",
                )
            snapshot.assert_not_called()


    def test_limit_precedes_validation_of_excess_row_types(self):
        base_claim = claim()
        first, _ = sources()
        with self.assertRaisesRegex(ValueError, "^BATCH_TOO_LARGE$"):
            build_research_batch(
                (base_claim,), {base_claim.claim_id: (first,) * 128 + (object(),)}
            )
        requirements = tuple(
            replace(base_claim, claim_id=f"claim:type-cap:{n}") for n in range(5)
        )
        grouped = {record.claim_id: (first,) * 128 for record in requirements[:-1]}
        grouped[requirements[-1].claim_id] = (object(),)
        with self.assertRaisesRegex(ValueError, "^BATCH_TOO_LARGE$"):
            build_research_batch(requirements, grouped)


if __name__ == "__main__":
    unittest.main()
