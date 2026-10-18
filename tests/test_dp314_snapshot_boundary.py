"""DP-314 detached-input and private evidence-audit regressions."""

import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.verification_requirements_v1 import (
    RequirementClaim, RequirementEvidence, SequenceEventObservation,
    compare_private_event_sequence, preflight_verification_requirements,
)
from tests.test_dp314_verification_requirements import claim, sources, sequence_sources


class DetachedEvidenceSnapshotTests(unittest.TestCase):
    def test_mutable_subclasses_cannot_change_approval_after_snapshot(self):
        class MutableEvidence(RequirementEvidence):
            def __getattribute__(self, name):
                if name == "evidence_review_status":
                    data = object.__getattribute__(self, "__dict__")
                    count = data.setdefault("_review_reads", 0)
                    data["_review_reads"] = count + 1
                    return "APPROVED" if count == 0 else "REVOKED"
                return super().__getattribute__(name)

        class MutableClaim(RequirementClaim):
            pass

        class MutableObservation(SequenceEventObservation):
            pass

        first, second = sources()
        with self.assertRaisesRegex(ValueError, "REQUIREMENT_INPUT_INVALID"):
            preflight_verification_requirements(
                MutableClaim(**vars(claim())), (first, second)
            )
        with self.assertRaisesRegex(ValueError, "REQUIREMENT_EVIDENCE_INPUT_INVALID"):
            preflight_verification_requirements(
                claim(), (first, MutableEvidence(**vars(second)))
            )
        evidence, observations = sequence_sources()
        with self.assertRaisesRegex(ValueError, "SEQUENCE_OBSERVATION_INPUT_INVALID"):
            compare_private_event_sequence(
                claim(), evidence,
                (MutableObservation(**vars(observations[0])), *observations[1:]),
                left_event_ref="event:left", right_event_ref="event:right",
                claimed_order="BEFORE",
            )

    def test_private_sequence_uses_same_detached_evidence_as_preflight(self):
        evidence, observations = sequence_sources()
        result = compare_private_event_sequence(
            claim(), evidence, observations,
            left_event_ref="event:left", right_event_ref="event:right",
            claimed_order="BEFORE",
        )
        self.assertEqual(result.comparison_status, "OBSERVATIONS_AGREE")
        self.assertFalse(result.publication_authority)
        modified = tuple(replace(row, evidence_review_status="REVOKED")
                         if row.evidence_id == evidence[1].evidence_id else row
                         for row in evidence)
        held = compare_private_event_sequence(
            claim(), modified, observations,
            left_event_ref="event:left", right_event_ref="event:right",
            claimed_order="BEFORE",
        )
        self.assertEqual(held.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertNotEqual(held.snapshot_sha256, result.snapshot_sha256)

