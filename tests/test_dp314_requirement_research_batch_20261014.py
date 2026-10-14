"""DP314: bounded research worklist from verified private preflight, never a verdict."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_dp314_verification_requirements import claim, record, sources


class RequirementResearchBatchTests(unittest.TestCase):
    def _run(self, claims=None, evidence=None, **kwargs):
        from dichiarazioni_pubbliche.requirement_research_batch_v1 import build_research_batch
        return build_research_batch(
            claims if claims is not None else (claim(),),
            evidence if evidence is not None else {"claim:synthetic": sources()},
            **kwargs,
        )

    def test_evidence_complete_still_requires_real_deterministic_verifier(self):
        report = self._run()
        self.assertEqual(report.items[0].state, "CHECKABLE_PENDING")
        self.assertEqual(report.items[0].next_steps, ("DETERMINISTIC_VERIFICATION_REQUIRED",))
        self.assertIsNone(report.items[0].verdict)
        self.assertFalse(report.publication_authority)
        self.assertFalse(report.finding_authority)
        self.assertTrue(report.private_only)
        self.assertFalse(report.authoritative_source_approval)
        self.assertEqual(report.source_body_count, 0)
        self.assertEqual(report.provider_calls, 0)

    def test_empty_or_held_evidence_has_specific_role_and_rights_gaps(self):
        no_rows = self._run(evidence={"claim:synthetic": ()}).items[0]
        self.assertEqual(no_rows.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("REVIEW_PRIMARY_RECORD", no_rows.next_steps)
        self.assertIn("REVIEW_INDEPENDENT_RECORD", no_rows.next_steps)
        self.assertIn("ESTABLISH_INDEPENDENT_PROVENANCE", no_rows.next_steps)
        held = self._run(evidence={"claim:synthetic": (
            replace(sources()[0], source_use_status="REVOKED"), sources()[1],
        )}).items[0]
        self.assertIn("RESOLVE_SOURCE_USE_OR_REVIEW_HOLD", held.next_steps)
        self.assertIn("REVIEW_PRIMARY_RECORD", held.next_steps)
        self.assertNotIn(sources()[0].evidence_id, held.eligible_evidence_ids)

    def test_not_started_does_not_hide_existing_rights_and_role_blocks(self):
        pending = claim(run_state="NOT_STARTED")
        revoked = replace(sources()[0], source_use_status="REVOKED")
        item = self._run(claims=(pending,), evidence={pending.claim_id: (revoked, sources()[1])}).items[0]
        self.assertEqual(item.state, "NOT_CHECKED")
        self.assertIn("START_RESEARCH_RUN", item.next_steps)
        self.assertIn("RESOLVE_SOURCE_USE_OR_REVIEW_HOLD", item.next_steps)
        self.assertIn("REVIEW_PRIMARY_RECORD", item.next_steps)
        self.assertIn("ESTABLISH_INDEPENDENT_PROVENANCE", item.next_steps)
        self.assertIsNone(item.verdict)

    def test_duplicated_wire_family_and_roots_not_independent(self):
        aliased = replace(sources()[1], source_family_ref=sources()[0].source_family_ref)
        item = self._run(evidence={"claim:synthetic": (sources()[0], aliased)}).items[0]
        self.assertIn("ESTABLISH_INDEPENDENT_PROVENANCE", item.next_steps)
        self.assertNotEqual(item.state, "CHECKABLE_PENDING")
        same_bytes = replace(sources()[1], evidence_sha256=sources()[0].evidence_sha256)
        item = self._run(evidence={"claim:synthetic": (sources()[0], same_bytes)}).items[0]
        self.assertIn("ESTABLISH_INDEPENDENT_PROVENANCE", item.next_steps)

    def test_nonfactual_not_started_and_unknown_profile_never_schedule_verdict(self):
        batch = self._run(claims=(
            claim("NON_FACTUAL", claim_id="claim:a"),
            claim("UNSUPPORTED_UNKNOWN", claim_id="claim:b"),
            claim(run_state="NOT_STARTED", claim_id="claim:c"),
        ), evidence={"claim:a": (), "claim:b": (), "claim:c": ()})
        self.assertEqual([item.state for item in batch.items], [
            "NON_FACTUAL", "NOT_CHECKABLE_PROFILE_UNAVAILABLE", "NOT_CHECKED",
        ])
        self.assertEqual(batch.items[0].next_steps, ("NO_FACTUAL_VERIFICATION",))
        self.assertEqual(batch.items[1].next_steps, ("PROFILE_AUTHORITY_REQUIRED",))
        self.assertIn("START_RESEARCH_RUN", batch.items[2].next_steps)
        self.assertIn("REVIEW_PRIMARY_RECORD", batch.items[2].next_steps)
        self.assertIn("REVIEW_INDEPENDENT_RECORD", batch.items[2].next_steps)
        self.assertTrue(all(item.verdict is None for item in batch.items))

    def test_contradiction_is_hold_not_falsehood_or_public_ranking(self):
        opposing = replace(sources()[1], stance="REFUTE")
        item = self._run(evidence={"claim:synthetic": (sources()[0], opposing)}).items[0]
        self.assertEqual(item.state, "UNRESOLVED_CONFLICT")
        self.assertEqual(item.next_steps, ("REVIEW_CONFLICT_WITH_CHALLENGER",))
        self.assertIsNone(item.verdict)

    def test_multi_claim_deterministic_replay_and_isolated_rights_revocation(self):
        a = claim(claim_id="claim:a")
        b = claim("NUMERIC", claim_id="claim:b")
        nums = (record("gamma", "PRIMARY_STATISTICS", "root:c", sha="1" * 64),)
        before = self._run(claims=(b, a), evidence={"claim:b": nums, "claim:a": sources()})
        replay = self._run(claims=(a, b), evidence={"claim:a": tuple(reversed(sources())), "claim:b": nums})
        self.assertEqual(before, replay)
        revoked = self._run(claims=(a, b), evidence={
            "claim:b": (replace(nums[0], evidence_review_status="REVOKED"),),
            "claim:a": sources(),
        })
        self.assertNotEqual(before.snapshot_sha256, revoked.snapshot_sha256)
        self.assertEqual(before.items[0], revoked.items[0])
        self.assertIn("RESOLVE_SOURCE_USE_OR_REVIEW_HOLD", revoked.items[1].next_steps)

    def test_invalid_cross_tenant_scope_extra_claim_untrusted_body_and_bounds(self):
        with self.assertRaisesRegex(ValueError, "BATCH_UNEXPECTED_CLAIM"):
            self._run(evidence={"claim:synthetic": (), "claim:foreign": sources()})
        with self.assertRaisesRegex(ValueError, "BATCH_DUPLICATE_CLAIM"):
            self._run(claims=(claim(), claim()))
        with self.assertRaisesRegex(ValueError, "BATCH_INVALID_EVIDENCE"):
            self._run(evidence={"claim:synthetic": [*sources()]})
        with self.assertRaisesRegex(ValueError, "BATCH_TOO_LARGE"):
            self._run(max_claims=0)
        with self.assertRaisesRegex(ValueError, "BATCH_TOO_LARGE"):
            self._run(claims=tuple(replace(claim(),claim_id=f"claim:{i}") for i in range(33)))
        with self.assertRaisesRegex(ValueError, "BATCH_INVALID_CLAIM"):
            self._run(claims=({"private_body": "do not read"},))


if __name__ == "__main__":
    unittest.main()
