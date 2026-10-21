"""Adversarial DP-314 research planning input boundary, synthetic metadata only."""
import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.requirement_research_batch_v1 import build_research_batch
from tests.test_dp314_verification_requirements import claim, sources


class SwappingRightsMap(dict):
    """Shows revoked rights during validation, approved rights on lookup."""

    def __init__(self, key, revoked, approved):
        super().__init__({key: revoked})
        self.approved = approved

    def __getitem__(self, key):
        return self.approved


class ResearchSnapshotBoundaryTests(unittest.TestCase):
    def test_research_plan_rejects_source_rights_swap_between_validation_and_read(self):
        requirement = claim()
        approved = sources()
        revoked = (replace(approved[0], source_use_status="REVOKED"), approved[1])
        current = {requirement.claim_id: revoked}
        actual = build_research_batch((requirement,), current)
        self.assertEqual(actual.items[0].state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("RESOLVE_SOURCE_USE_OR_REVIEW_HOLD", actual.items[0].next_steps)

        # A caller-defined Mapping can return a different tuple at lookup;
        # approving that view silently hides the revocation in the input map.
        malicious = SwappingRightsMap(requirement.claim_id, revoked, approved)
        with self.assertRaisesRegex(ValueError, "BATCH_INPUT_UNSAFE"):
            build_research_batch((requirement,), malicious)
        self.assertEqual(malicious.get(requirement.claim_id), revoked)

    def test_plain_mapping_replay_and_immutable_boundary_remain_deterministic(self):
        requirement = claim(run_state="NOT_STARTED")
        entries = sources()
        batch = build_research_batch((requirement,), {requirement.claim_id: entries})
        replay = build_research_batch(
            (requirement,), {requirement.claim_id: tuple(reversed(entries))}
        )
        self.assertEqual(batch, replay)
        self.assertEqual(batch.items[0].state, "NOT_CHECKED")
        self.assertIsNone(batch.items[0].verdict)
        self.assertFalse(batch.publication_authority)


class SwapsDuringCopy(str):
    """An exact dataclass can still carry a hostile field-value subclass."""

    calls = 0

    def __new__(cls, original, replacement):
        value = super().__new__(cls, original)
        value.replacement = replacement
        return value

    def __deepcopy__(self, memo):
        type(self).calls += 1
        return self.replacement


class CopyHookBoundaryTests(unittest.TestCase):
    def setUp(self):
        SwapsDuringCopy.calls = 0

    def test_batch_rejects_revoked_rights_before_copying_nested_field(self):
        requirement = claim()
        originals = sources()
        revoked = SwapsDuringCopy("REVOKED", "APPROVED")
        evidence = (replace(originals[0], source_use_status=revoked), originals[1])
        preimage = {requirement.claim_id: evidence}
        with self.assertRaisesRegex(ValueError, "BATCH_(INVALID_EVIDENCE|INPUT_UNSAFE)"):
            build_research_batch((requirement,), preimage)
        self.assertEqual(SwapsDuringCopy.calls, 0)
        self.assertIs(preimage[requirement.claim_id][0].source_use_status, revoked)
        self.assertEqual(str(revoked), "REVOKED")
        self.assertEqual(
            build_research_batch(
                (requirement,),
                {requirement.claim_id: (replace(originals[0], source_use_status="REVOKED"), originals[1])},
            ).items[0].state,
            "CHECKED_INSUFFICIENT_EVIDENCE",
        )

    def test_batch_rejects_nested_identity_dates_and_claim_fields_before_copy(self):
        base_claim = claim()
        originals = sources()
        cases = (
            (base_claim, (replace(originals[0],
                source_family_ref=SwapsDuringCopy("source:root:b", "source:root:a")), originals[1])),
            (base_claim, (replace(originals[0],
                published_date=SwapsDuringCopy("2026-01-01", "2025-05-25")), originals[1])),
            (replace(base_claim, review_cutoff_date=SwapsDuringCopy("2025-07-01", "2030-01-01")), originals),
        )
        for changed_claim, rows in cases:
            with self.subTest(field=rows[0].published_date, claim=changed_claim.review_cutoff_date):
                with self.assertRaisesRegex(ValueError, "BATCH_(INVALID_CLAIM|INVALID_EVIDENCE|INPUT_UNSAFE)"):
                    build_research_batch((changed_claim,), {changed_claim.claim_id: rows})
                self.assertEqual(SwapsDuringCopy.calls, 0)

    def test_direct_preflight_and_sequence_reject_deepcopy_hooks(self):
        from dichiarazioni_pubbliche.verification_requirements_v1 import (
            compare_private_event_sequence, preflight_verification_requirements,
        )
        from tests.test_dp314_verification_requirements import sequence_sources
        originals = sources()
        revoked = SwapsDuringCopy("REVOKED", "APPROVED")
        evidence = (replace(originals[0], source_use_status=revoked), originals[1])
        with self.assertRaisesRegex(ValueError, "REQUIREMENT_.*INVALID"):
            preflight_verification_requirements(claim(), evidence)
        self.assertEqual(SwapsDuringCopy.calls, 0)
        sequence_evidence, observations = sequence_sources()
        changed = (replace(sequence_evidence[0], source_use_status=revoked), *sequence_evidence[1:])
        with self.assertRaisesRegex(ValueError, "REQUIREMENT_.*INVALID"):
            compare_private_event_sequence(
                claim(), changed, observations, left_event_ref="event:left",
                right_event_ref="event:right", claimed_order="BEFORE",
            )
        self.assertEqual(SwapsDuringCopy.calls, 0)
        self.assertEqual(str(changed[0].source_use_status), "REVOKED")
        forged_date = replace(observations[0],
            occurred_on=SwapsDuringCopy("2030-01-01", "2025-05-10"))
        with self.assertRaisesRegex(ValueError, "SEQUENCE_.*INVALID"):
            compare_private_event_sequence(
                claim(), sequence_evidence, (forged_date, *observations[1:]),
                left_event_ref="event:left", right_event_ref="event:right",
                claimed_order="BEFORE",
            )
        self.assertEqual(SwapsDuringCopy.calls, 0)

    def test_every_nested_text_field_rejects_subclasses_without_side_effects(self):
        from dataclasses import fields
        requirement, records = claim(), sources()
        for sample in (requirement, records[0]):
            for field in fields(sample):
                value = getattr(sample, field.name)
                if value is None:
                    continue
                hostile = SwapsDuringCopy(value, value)
                changed = replace(sample, **{field.name: hostile})
                with self.subTest(class_name=type(sample).__name__, field=field.name):
                    if sample is requirement:
                        payload_claim, payload_rows = changed, records
                        expected = "BATCH_(INVALID_CLAIM|UNEXPECTED_CLAIM)"
                    else:
                        payload_claim, payload_rows = requirement, (changed, records[1])
                        expected = "BATCH_INVALID_EVIDENCE"
                    with self.assertRaisesRegex(ValueError, expected):
                        build_research_batch(
                            (payload_claim,), {payload_claim.claim_id: payload_rows}
                        )
                    self.assertEqual(SwapsDuringCopy.calls, 0)
                    self.assertIs(getattr(changed, field.name), hostile)


if __name__ == "__main__":
    unittest.main()
