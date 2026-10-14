"""Offline owner-only DP314 research reconciliation work queue."""

from __future__ import annotations

import sys
import unittest
from dataclasses import fields, replace
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "poc"),
    str(Path(__file__).resolve().parent),
]

from test_dp314_requirement_research_delta_20261014 import batch  # noqa: E402
from test_dp314_verification_requirements import claim, record, sources  # noqa: E402


class PrivateResearchWaveTests(unittest.TestCase):
    def wave(self, old=None, new=None, **kw):
        from dichiarazioni_pubbliche.requirement_research_wave_v1 import (
            plan_research_wave,
        )

        old = old if old is not None else batch()
        new = new if new is not None else old
        args = dict(
            previous=old,
            current=new,
            expected_previous_sha256=old.snapshot_sha256,
            expected_current_sha256=new.snapshot_sha256,
        )
        args.update(kw)
        return plan_research_wave(**args)

    def test_unchanged_is_idle_not_source_approval_or_work_completion(self):
        result = self.wave()
        self.assertEqual(result.status, "IDLE_NO_AUTO_APPROVAL")
        self.assertEqual(result.queue, ())
        self.assertFalse(result.publication_authority)
        self.assertFalse(result.source_approval_authority)
        self.assertFalse(result.finding_authority)
        self.assertTrue(result.private_only)
        self.assertIsNone(result.verdict)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result.source_body_count, 0)
        self.assertEqual(result, self.wave())

    def test_real_revoked_evidence_raises_eligibility_review_first(self):
        old = batch()
        changed = replace(sources()[0], source_use_status="REVOKED")
        new = batch(observations={"claim:synthetic": (changed, sources()[1])})
        result = self.wave(old, new)
        self.assertEqual(result.status, "MANUAL_RECHECK_REQUIRED")
        self.assertEqual(result.queue[0].reason, "EVIDENCE_ELIGIBILITY_LOSS")
        self.assertEqual(result.queue[0].claim_ids, ("claim:synthetic",))
        self.assertEqual(result.queue[0].evidence_ids, (changed.evidence_id,))
        self.assertEqual(result.queue[0].priority, 0)
        self.assertEqual(
            result.queue[0].change_direction, "LOST_ELIGIBILITY_NOT_PROVEN_REVOKE"
        )
        self.assertNotIn("REVOKED_AT_PROVIDER", repr(result))

    def test_added_removed_and_changed_work_are_all_visible(self):
        a, b, c = (
            claim(claim_id="claim:a"),
            claim("NUMERIC", claim_id="claim:b"),
            claim("NUMERIC", claim_id="claim:c"),
        )
        num = (record("gamma", "PRIMARY_STATISTICS", "root:z", sha="1" * 64),)
        old = batch((a, b), {"claim:a": sources(), "claim:b": num})
        changed_source = replace(sources()[0], evidence_sha256="b" * 64)
        new = batch((a, c), {"claim:a": (changed_source, sources()[1]), "claim:c": num})
        result = self.wave(old, new)
        self.assertEqual(result.recheck_claim_ids, ("claim:a", "claim:b", "claim:c"))
        self.assertEqual(
            {step.reason for step in result.queue},
            {"REMOVED_CLAIM_NOT_RESOLVED", "CHANGED_INPUT_RECHECK", "NEW_CLAIM_REVIEW"},
        )
        self.assertTrue(all(step.claim_ids for step in result.queue))
        self.assertNotIn("source_url", repr(result))

    def test_shared_evidence_ids_are_not_independent_corroboration(self):
        a, b = claim(claim_id="claim:a"), claim(claim_id="claim:b")
        same = sources()
        old = batch((a,), {"claim:a": same})
        new = batch((a, b), {"claim:a": same, "claim:b": same})
        result = self.wave(old, new)
        self.assertEqual(
            result.reused_evidence_ids, tuple(sorted(s.evidence_id for s in same))
        )
        self.assertEqual(result.status, "MANUAL_RECHECK_REQUIRED")
        self.assertFalse(result.independent_corroboration_established)
        self.assertEqual(result.claim_count, 2)

    def test_stale_and_forged_source_pins_fail_closed(self):
        old = batch()
        with self.assertRaisesRegex(ValueError, "DELTA_PIN_MISMATCH"):
            self.wave(old, old, expected_previous_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.wave(old, replace(old, source_body_count=1))
        with self.assertRaisesRegex(ValueError, "DELTA_BATCH_INVALID"):
            self.wave(old, replace(old, publication_authority=True))

    def test_current_worklist_source_hash_changed_without_state_change(self):
        old = batch()
        new = batch(
            observations={
                "claim:synthetic": (
                    replace(sources()[0], evidence_sha256="2" * 64),
                    sources()[1],
                )
            }
        )
        result = self.wave(old, new)
        self.assertEqual(result.queue[0].reason, "CHANGED_INPUT_RECHECK")
        self.assertEqual(result.queue[0].claim_ids, ("claim:synthetic",))
        self.assertEqual(result.queue[0].priority, 4)
        self.assertNotEqual(result.snapshot_sha256, self.wave(old).snapshot_sha256)

    def test_simultaneous_profile_change_and_eligibility_loss_are_both_visible(self):
        old = batch()
        changed_claim = claim("NUMERIC")
        changed_source = replace(sources()[0], source_use_status="REVOKED")
        current = batch(
            (changed_claim,), {changed_claim.claim_id: (changed_source, sources()[1])}
        )
        plan = self.wave(old, current)
        self.assertEqual(plan.queue[0].reason, "EVIDENCE_ELIGIBILITY_LOSS")
        self.assertIn(
            "CHANGED_REQUIREMENT_PROFILE", tuple(step.reason for step in plan.queue)
        )
        self.assertIn(changed_claim.claim_id, plan.recheck_claim_ids)

    def test_simultaneous_eligibility_loss_and_gain_both_surface_exact_evidence(self):
        old = batch()
        old_evidence = sources()
        replacement = record("gamma", "PRIMARY_RECORD", "root:c", sha="3" * 64)
        new = batch(observations={"claim:synthetic": (replacement, old_evidence[1])})
        planned = self.wave(old, new)
        by_reason = {step.reason: step for step in planned.queue}
        self.assertIn("EVIDENCE_ELIGIBILITY_LOSS", by_reason)
        self.assertIn("NEW_EVIDENCE_ELIGIBILITY", by_reason)
        self.assertEqual(
            by_reason["EVIDENCE_ELIGIBILITY_LOSS"].evidence_ids,
            (old_evidence[0].evidence_id,),
        )
        self.assertEqual(
            by_reason["NEW_EVIDENCE_ELIGIBILITY"].evidence_ids,
            (replacement.evidence_id,),
        )
        self.assertEqual(planned.status, "MANUAL_RECHECK_REQUIRED")

    def test_mutable_batch_subclass_swaps_private_action_after_validation_denied(self):
        # Independent worker-9 P2: canonical delta validation accepts a
        # PrivateResearchBatch subclass that changes `items` AFTER the SHA
        # validation, before this queue reads its next_steps again.
        from dichiarazioni_pubbliche.requirement_research_batch_v1 import (
            PrivateResearchBatch,
        )

        old = batch()
        current = batch(
            observations={
                "claim:synthetic": (
                    replace(sources()[0], source_use_status="REVOKED"),
                    sources()[1],
                )
            }
        )

        class SwappingBatch(PrivateResearchBatch):
            def __getattribute__(self, name):
                if name == "items":
                    accesses = object.__getattribute__(self, "accesses") + 1
                    object.__setattr__(self, "accesses", accesses)
                    rows = super().__getattribute__("items")
                    if accesses >= 7:
                        return (
                            replace(
                                rows[0], next_steps=("PRIVATE_RAW_TRANSCRIPT_SENTINEL",)
                            ),
                        )
                    return rows
                return super().__getattribute__(name)

        shaped = {item.name: getattr(current, item.name) for item in fields(current)}
        evil = SwappingBatch(**shaped)
        object.__setattr__(evil, "accesses", 0)
        with self.assertRaisesRegex(ValueError, "WAVE_BATCH_INVALID"):
            self.wave(old, evil)


if __name__ == "__main__":
    unittest.main()
