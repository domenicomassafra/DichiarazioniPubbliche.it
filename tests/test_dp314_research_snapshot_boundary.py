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


if __name__ == "__main__":
    unittest.main()
