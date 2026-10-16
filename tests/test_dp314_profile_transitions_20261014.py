"""DP-314 private profile transitions: source-bound snapshots, manual gates only."""

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "poc"),
    str(Path(__file__).resolve().parent),
]

from dichiarazioni_pubbliche.private_requirement_profile_transitions_v1 import (  # noqa: E402
    build_profile_snapshot,
    compare_profile_snapshots,
)
from dichiarazioni_pubbliche.requirement_research_batch_v1 import (  # noqa: E402
    build_research_batch,
)
from test_dp314_verification_requirements import claim, record, sources  # noqa: E402


class ProfileTransitionTests(unittest.TestCase):
    def snapshot(self, claims=None, observations=None):
        claims = (claim(),) if claims is None else claims
        observations = (
            {"claim:synthetic": sources()} if observations is None else observations
        )
        return build_profile_snapshot(claims, observations)

    def compare(self, old, new, **overrides):
        pins = {
            "expected_previous_sha256": old.snapshot_sha256,
            "expected_current_sha256": new.snapshot_sha256,
        }
        pins.update(overrides)
        return compare_profile_snapshots(old, new, **pins)

    def test_real_canonical_preflight_and_research_batch_fixture(self):
        snapshot = self.snapshot()
        batch = build_research_batch((claim(),), {"claim:synthetic": sources()})
        self.assertEqual(snapshot.records[0].preflight.state, batch.items[0].state)
        self.assertEqual(
            snapshot.records[0].preflight.eligible_evidence_ids,
            batch.items[0].eligible_evidence_ids,
        )
        self.assertEqual(
            snapshot.records[0].preflight.snapshot_sha256,
            batch.items[0].preflight_sha256,
        )
        self.assertEqual(
            snapshot.records[0].profile.required_roles,
            ("PRIMARY_RECORD", "INDEPENDENT_RECORD"),
        )
        self.assertEqual(snapshot.claim_count, 1)
        self.assertEqual(snapshot.evidence_count, 2)

    def test_replay_is_order_independent_private_without_implicit_authority(self):
        first = self.snapshot()
        second = self.snapshot(observations={"claim:synthetic": sources()[::-1]})
        self.assertEqual(first, second)
        result = self.compare(first, second)
        self.assertEqual(result.status, "UNCHANGED_NO_AUTHORITY")
        self.assertEqual(result.steps, ())
        self.assertEqual(result.recheck_claim_ids, ())
        self.assertIsNone(result.verdict)
        self.assertTrue(result.private_only)
        self.assertFalse(result.source_rights_attested)
        self.assertFalse(result.reviewer_attested)
        self.assertFalse(result.fact_authority)
        self.assertFalse(result.source_approval_authority)
        self.assertFalse(result.publication_authority)
        self.assertEqual(result.source_body_count, 0)
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result, self.compare(first, second))

    def test_declared_rights_revoke_loses_eligibility_without_provider_claim(self):
        old = self.snapshot()
        revoked = replace(sources()[0], source_use_status="REVOKED")
        new = self.snapshot(observations={"claim:synthetic": (revoked, sources()[1])})
        result = self.compare(old, new)
        step = result.steps[0]
        self.assertEqual(step.lost_eligible_ids, (revoked.evidence_id,))
        self.assertEqual(step.gained_eligible_ids, ())
        self.assertEqual(step.rights_declared_changed_ids, (revoked.evidence_id,))
        self.assertIn("RIGHTS_DECLARATION_CHANGED", step.change_codes)
        self.assertIn("REVIEW_ELIGIBILITY_LOSS", step.manual_actions)
        self.assertIn("SOURCE_RIGHTS_EXTERNAL_ATTESTATION_REQUIRED", step.gates)
        self.assertFalse(step.source_approval_authority)
        self.assertNotIn("PROVIDER_REVOKED", repr(result))

    def test_review_pending_to_approved_gain_stays_manual(self):
        held = replace(sources()[0], evidence_review_status="PENDING")
        before = self.snapshot(observations={"claim:synthetic": (held, sources()[1])})
        after = self.snapshot()
        step = self.compare(before, after).steps[0]
        self.assertEqual(step.gained_eligible_ids, (held.evidence_id,))
        self.assertEqual(step.review_declared_changed_ids, (held.evidence_id,))
        self.assertIn("REVIEW_NEW_ELIGIBILITY", step.manual_actions)
        self.assertIn("EVIDENCE_REVIEW_EXTERNAL_ATTESTATION_REQUIRED", step.gates)
        self.assertFalse(step.finding_authority)

    def test_simultaneous_profile_change_eligibility_loss_and_gain(self):
        old = self.snapshot()
        replacement = record("gamma", "PRIMARY_STATISTICS", "root:c", sha="3" * 64)
        current_claim = claim("NUMERIC")
        new = self.snapshot(
            (current_claim,),
            {"claim:synthetic": (replacement, sources()[1])},
        )
        step = self.compare(old, new).steps[0]
        self.assertEqual(step.kind, "CHANGED")
        self.assertEqual(
            step.lost_eligible_ids,
            tuple(sorted((sources()[0].evidence_id, sources()[1].evidence_id))),
        )
        self.assertEqual(step.gained_eligible_ids, (replacement.evidence_id,))
        self.assertIn("REQUIREMENT_PROFILE_CHANGED", step.change_codes)
        self.assertIn("REVIEW_CHANGED_REQUIREMENT_PROFILE", step.manual_actions)
        self.assertIn("REVIEW_ELIGIBILITY_LOSS", step.manual_actions)
        self.assertIn("REVIEW_NEW_ELIGIBILITY", step.manual_actions)
        self.assertEqual(
            step.before_required_roles, ("PRIMARY_RECORD", "INDEPENDENT_RECORD")
        )
        self.assertEqual(step.after_required_roles, ("PRIMARY_STATISTICS",))
        self.assertEqual(len(step.gates), 4)

    def test_unchanged_preflight_state_can_hide_source_bytes_or_policy_drift(self):
        old = self.snapshot()
        source_drift = replace(sources()[0], evidence_sha256="e" * 64)
        current = self.snapshot(
            observations={"claim:synthetic": (source_drift, sources()[1])}
        )
        self.assertEqual(
            old.records[0].preflight.state, current.records[0].preflight.state
        )
        step = self.compare(old, current).steps[0]
        self.assertIn("EVIDENCE_METADATA_CHANGED", step.change_codes)
        self.assertEqual(step.changed_evidence_ids, (source_drift.evidence_id,))
        self.assertIn("REVIEW_CHANGED_EVIDENCE_PROVENANCE", step.manual_actions)
        changed_policy = self.snapshot(
            (claim(policy_version="policy:test:v2"),), {"claim:synthetic": sources()}
        )
        policy_step = self.compare(old, changed_policy).steps[0]
        self.assertIn("CLAIM_INPUT_CHANGED", policy_step.change_codes)
        self.assertIn("REVIEW_CHANGED_CLAIM_INPUT", policy_step.manual_actions)
        self.assertNotEqual(old.snapshot_sha256, changed_policy.snapshot_sha256)

    def test_added_removed_claims_and_unaffected_siblings(self):
        a, b = claim(claim_id="claim:a"), claim("NUMERIC", claim_id="claim:b")
        numeric = (record("gamma", "PRIMARY_STATISTICS", "root:c", sha="3" * 64),)
        old = self.snapshot((a,), {"claim:a": sources()})
        new = self.snapshot((a, b), {"claim:a": sources(), "claim:b": numeric})
        addition = self.compare(old, new)
        self.assertEqual(addition.added_claim_ids, ("claim:b",))
        self.assertEqual(addition.recheck_claim_ids, ("claim:b",))
        self.assertEqual(tuple(s.claim_id for s in addition.steps), ("claim:b",))
        self.assertEqual(addition.steps[0].gained_eligible_ids, ("evidence:gamma",))
        self.assertIn("ADDED_CLAIM_MANUAL_REVIEW", addition.steps[0].manual_actions)
        removal = self.compare(new, old)
        self.assertEqual(removal.removed_claim_ids, ("claim:b",))
        self.assertIn("REMOVED_CLAIM_NOT_RESOLVED", removal.steps[0].manual_actions)

    def test_same_evidence_id_changed_root_or_role_requires_manual_recheck(self):
        replacement = replace(
            sources()[0],
            primary_root_ref="root:z",
            source_family_ref="source:root:z",
            evidence_role="PRIMARY_TEXT",
        )
        current = self.snapshot(
            observations={"claim:synthetic": (replacement, sources()[1])}
        )
        step = self.compare(self.snapshot(), current).steps[0]
        self.assertEqual(step.changed_evidence_ids, (replacement.evidence_id,))
        self.assertEqual(step.lost_eligible_ids, (replacement.evidence_id,))
        self.assertIn("REVIEW_CHANGED_EVIDENCE_PROVENANCE", step.manual_actions)

    def test_stale_pin_and_self_rehashed_tampering_fail_closed(self):
        old = self.snapshot()
        with self.assertRaisesRegex(ValueError, "PROFILE_PIN_MISMATCH"):
            self.compare(old, old, expected_previous_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "PROFILE_SNAPSHOT_INVALID"):
            self.compare(old, replace(old, publication_authority=True))
        with self.assertRaisesRegex(ValueError, "PROFILE_SNAPSHOT_INVALID"):
            self.compare(old, replace(old, claim_count=999))
        forged = replace(
            old.records[0],
            preflight=replace(
                old.records[0].preflight,
                eligible_evidence_ids=(),
            ),
        )
        with self.assertRaisesRegex(ValueError, "PROFILE_SNAPSHOT_INVALID"):
            self.compare(old, replace(old, records=(forged,)))

    def test_mutation_after_snapshot_has_no_effect_on_original_fingerprint(self):
        original_claim = claim()
        original_evidence = sources()
        snap = self.snapshot((original_claim,), {"claim:synthetic": original_evidence})
        original_digest = snap.snapshot_sha256
        object.__setattr__(original_claim, "policy_version", "policy:test:rewritten")
        object.__setattr__(original_evidence[0], "source_use_status", "REVOKED")
        self.assertEqual(snap.snapshot_sha256, original_digest)
        self.assertEqual(snap.records[0].claim.policy_version, "policy:test:v1")
        self.assertEqual(snap.records[0].evidence[0].source_use_status, "APPROVED")
        self.assertEqual(self.compare(snap, snap).steps, ())
        different = self.snapshot(
            (original_claim,), {"claim:synthetic": original_evidence}
        )
        self.assertNotEqual(snap.snapshot_sha256, different.snapshot_sha256)
        self.assertEqual(
            self.compare(snap, different).steps[0].lost_eligible_ids,
            ("evidence:alpha",),
        )

    def test_rehashed_forged_eligibility_is_still_rejected(self):
        from dichiarazioni_pubbliche.private_requirement_profile_transitions_v1 import (  # noqa: PLC0415
            _record_material,
            _snapshot_material,
        )
        from dichiarazioni_pubbliche.requirement_research_batch_v1 import (  # noqa: PLC0415
            _digest,
        )

        initial = self.snapshot()
        row = initial.records[0]
        forged_preflight = replace(row.preflight, eligible_evidence_ids=())
        forged_row = replace(
            row,
            preflight=forged_preflight,
            snapshot_sha256=_digest(
                _record_material(row.claim, row.evidence, row.profile, forged_preflight)
            ),
        )
        forged = replace(
            initial,
            records=(forged_row,),
            snapshot_sha256=_digest(_snapshot_material((forged_row,))),
        )
        with self.assertRaisesRegex(ValueError, "PROFILE_SNAPSHOT_INVALID"):
            self.compare(forged, forged)

    def test_inert_unsupported_and_nonfactual_profiles_never_become_findings(self):
        unknown = claim("UNSUPPORTED_RESEARCH_CLASS")
        expressive = claim("NON_FACTUAL", claim_id="claim:expression")
        snap = self.snapshot(
            (unknown, expressive),
            {"claim:synthetic": sources(), "claim:expression": ()},
        )
        by_id = {row.claim.claim_id: row for row in snap.records}
        self.assertEqual(
            by_id["claim:synthetic"].preflight.state,
            "NOT_CHECKABLE_PROFILE_UNAVAILABLE",
        )
        self.assertEqual(by_id["claim:synthetic"].profile, None)
        self.assertEqual(by_id["claim:expression"].preflight.state, "NON_FACTUAL")
        plan = self.compare(self.snapshot((), {}), snap)
        self.assertEqual(plan.added_claim_ids, ("claim:expression", "claim:synthetic"))
        self.assertTrue(all(not step.finding_authority for step in plan.steps))
        self.assertTrue(all(not step.publication_authority for step in plan.steps))

    def test_subclasses_and_malformed_raw_inputs_denied_before_snapshot(self):
        from dichiarazioni_pubbliche.verification_requirements_v1 import (  # noqa: PLC0415
            RequirementClaim,
            RequirementEvidence,
        )

        class EvilClaim(RequirementClaim):
            pass

        class EvilEvidence(RequirementEvidence):
            pass

        with self.assertRaisesRegex(ValueError, "PROFILE_INPUT_INVALID"):
            self.snapshot((EvilClaim(**vars(claim())),), {"claim:synthetic": sources()})
        with self.assertRaisesRegex(ValueError, "PROFILE_INPUT_INVALID"):
            self.snapshot(
                observations={"claim:synthetic": (EvilEvidence(**vars(sources()[0])),)}
            )
        with self.assertRaisesRegex(ValueError, "PROFILE_INPUT_INVALID"):
            self.snapshot(observations={"claim:synthetic": list(sources())})
        with self.assertRaisesRegex(ValueError, "PROFILE_INPUT_INVALID"):
            self.snapshot(observations={"claim:unrelated": sources()})
        with self.assertRaisesRegex(ValueError, "PROFILE_INPUT_INVALID"):
            self.snapshot((claim(), claim()), {"claim:synthetic": sources()})
        with self.assertRaisesRegex(ValueError, "PROFILE_INPUT_INVALID"):
            self.snapshot(observations={"claim:synthetic": sources() * 65})
        with self.assertRaisesRegex(ValueError, "PROFILE_INPUT_INVALID"):
            self.snapshot(
                (claim(claim_kind="Private source body / URL"),),
                {"claim:synthetic": sources()},
            )


if __name__ == "__main__":
    unittest.main()
