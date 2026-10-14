"""DP314: compare source-bound private research plans without authority transfer."""
import sys
import unittest
from dataclasses import asdict, replace
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "poc"),
                str(Path(__file__).resolve().parent)]

from dichiarazioni_pubbliche.requirement_research_batch_v1 import build_research_batch  # noqa: E402
from test_dp314_verification_requirements import claim, record, sources  # noqa: E402


def batch(claims=None, observations=None):
    claims = claims if claims is not None else (claim(),)
    observations = observations if observations is not None else {claims[0].claim_id: sources()}
    return build_research_batch(claims, observations)


class RequirementResearchDeltaTests(unittest.TestCase):
    def compare(self, before, after, **kw):
        from dichiarazioni_pubbliche.requirement_research_delta_v1 import compare_research_batches
        return compare_research_batches(before, after, before.snapshot_sha256,
                                        after.snapshot_sha256, **kw)

    def test_unchanged_deterministic_and_no_publish_authority(self):
        before = batch()
        delta = self.compare(before, before)
        self.assertEqual(delta.status, "UNCHANGED")
        self.assertEqual(delta.changed_claims, ())
        self.assertEqual(delta.added_claim_ids, ())
        self.assertEqual(delta.removed_claim_ids, ())
        self.assertEqual(delta.recheck_claim_ids, ())
        self.assertFalse(delta.publication_authority)
        self.assertFalse(delta.finding_authority)
        self.assertFalse(delta.authoritative_source_approval)
        self.assertTrue(delta.private_only)
        self.assertIsNone(delta.verdict)
        self.assertEqual(delta.provider_calls, 0)
        self.assertEqual(delta.source_body_count, 0)
        self.assertEqual(delta, self.compare(before, before))

    def test_revocation_is_recheck_without_inventing_reasons_or_verdict(self):
        before = batch()
        revoked = replace(sources()[0], source_use_status="REVOKED")
        after = batch(observations={"claim:synthetic": (revoked, sources()[1])})
        delta = self.compare(before, after)
        self.assertEqual(delta.status, "RECHECK_REQUIRED")
        self.assertEqual(len(delta.changed_claims), 1)
        change = delta.changed_claims[0]
        self.assertEqual(change.claim_id, "claim:synthetic")
        self.assertEqual(change.before_state, "CHECKABLE_PENDING")
        self.assertEqual(change.after_state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertEqual(change.lost_eligible_ids, (revoked.evidence_id,))
        self.assertIn("REVIEW_EVIDENCE_ELIGIBILITY_LOSS", change.actions)
        self.assertIn("REVALIDATE_CHANGED_INPUT", change.actions)
        self.assertIn("RESOLVE_SOURCE_USE_OR_REVIEW_HOLD", change.current_next_steps)
        self.assertNotIn("REVOKED_AT_PROVIDER", change.actions)
        self.assertIsNone(change.verdict)
        self.assertFalse(change.publication_authority)

    def test_same_state_changed_provenance_still_invalidates_release(self):
        before = batch()
        changed = replace(sources()[0], evidence_sha256="3" * 64)
        after = batch(observations={"claim:synthetic": (changed, sources()[1])})
        self.assertEqual(before.items[0].state, after.items[0].state)
        delta = self.compare(before, after)
        self.assertEqual(delta.status, "RECHECK_REQUIRED")
        self.assertIn("REVALIDATE_CHANGED_INPUT", delta.changed_claims[0].actions)
        self.assertNotEqual(delta.before_sha256, delta.after_sha256)
        self.assertFalse(delta.publication_authority)

    def test_added_or_removed_claims_are_never_assumed_complete(self):
        a, b = claim(claim_id="claim:a"), claim("NUMERIC", claim_id="claim:b")
        nums = (record("gamma", "PRIMARY_STATISTICS", "root:c", sha="1" * 64),)
        before = batch((a,), {"claim:a": sources()})
        after = batch((a, b), {"claim:a": sources(), "claim:b": nums})
        gain = self.compare(before, after)
        self.assertEqual(gain.added_claim_ids, ("claim:b",))
        self.assertEqual(gain.recheck_claim_ids, ("claim:b",))
        self.assertEqual(gain.status, "RECHECK_REQUIRED")
        self.assertEqual(gain, self.compare(before, after))
        loss = self.compare(after, before)
        self.assertEqual(loss.removed_claim_ids, ("claim:b",))
        self.assertIn("claim:b", loss.recheck_claim_ids)
        self.assertEqual(loss.status, "RECHECK_REQUIRED")
        self.assertFalse(loss.finding_authority)

    def test_independent_claim_delta_does_not_taint_unchanged_sibling(self):
        a, b = claim(claim_id="claim:a"), claim("NUMERIC", claim_id="claim:b")
        nums = (record("gamma", "PRIMARY_STATISTICS", "root:c", sha="1" * 64),)
        before = batch((a, b), {"claim:a": sources(), "claim:b": nums})
        after = batch((b, a), {"claim:b": (replace(nums[0], evidence_review_status="REVOKED"),),
                               "claim:a": tuple(reversed(sources()))})
        delta = self.compare(before, after)
        self.assertEqual(delta.recheck_claim_ids, ("claim:b",))
        self.assertEqual([row.claim_id for row in delta.changed_claims], ["claim:b"])
        self.assertIn("REVIEW_EVIDENCE_ELIGIBILITY_LOSS", delta.changed_claims[0].actions)

    def test_fail_closed_mismatched_pins_and_tampered_private_batch(self):
        before, after = batch(), batch()
        with self.assertRaisesRegex(ValueError, "DELTA_PIN_MISMATCH"):
            from dichiarazioni_pubbliche.requirement_research_delta_v1 import compare_research_batches
            compare_research_batches(before, after, "0" * 64, after.snapshot_sha256)
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(before, replace(after, source_body_count=1))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(before, replace(after, publication_authority=True))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(before, replace(after, claim_count=99))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(before, replace(after, items=(replace(after.items[0],
                          next_steps=("UNREVIEWED_CONCLUSION",)),)))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(before, replace(after, items=({"raw_transcript":"PRIVATE"},)))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(before, replace(after, items=(replace(after.items[0],
                          state="PRIVATE RAW TRANSCRIPT"),)))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(before, replace(after, items=(replace(after.items[0],
                          state={"raw_transcript":"PRIVATE"}),)))

    def test_batch_limits_and_private_only_scope(self):
        b = batch()
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(b, replace(b, items=b.items * 33))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(b, replace(b, items=(b.items[0], b.items[0])))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(b, replace(b, private_only=False))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.compare(b, replace(b, source_body_count=False))

    def test_rehashed_untrusted_status_and_action_cannot_be_echoed(self):
        from dichiarazioni_pubbliche.requirement_research_batch_v1 import _digest, VERSION
        original = batch()
        for corrupted in (
            {"state": "PRIVATE_UNREVIEWED_SOURCE_BODY_IN_STATE"},
            {"next_steps": ("PRIVATE_UNREVIEWED_SOURCE_BODY",)},
            {"claim_kind": "PRIVATE\nRAW\nTRANSCRIPT"},
        ):
            with self.subTest(corrupted=corrupted):
                bad = replace(original.items[0], **corrupted)
                forged = replace(original, items=(bad,), snapshot_sha256=_digest({
                    "version": VERSION, "items": [asdict(bad)],
                }))
                with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
                    self.compare(original, forged)


if __name__ == "__main__":
    unittest.main()
