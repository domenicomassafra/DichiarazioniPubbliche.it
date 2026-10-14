"""DP-319 opt-in private source research attempt planning, no execution."""

import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.investigation_attempts_v1 import (  # noqa: E402
    InvestigationObservation,
    InvestigationSpec,
    propose_investigation,
)
from dichiarazioni_pubbliche.research_plan import ResearchAssignment  # noqa: E402


def spec(**changes):
    return replace(InvestigationSpec(
        need_id="need:original", material_fingerprint="source-version-sha:a",
        question_kind="ORIGINAL_SOURCE", question="Locate unedited original clip",
        source_family="approved-test-family", max_attempts=2,
        cost_cap_usd=Decimal("0.10"), rights_status="CLEARED",
    ), **changes)


def assignment(lane="ORIGINAL_MEDIA", **changes):
    return replace(ResearchAssignment(
        assignment_id=f"assignment:{lane}", coverage_need_id="need:original",
        lane=lane, question="Find exact original", adapter_ids=("approved:test",),
        max_queries=1, max_results=3, max_results_per_host=2,
        cost_cap_usd=Decimal("0.03"), temporal_constraints={},
        authority_scope={}, stop_conditions=("REVIEWED_SOURCE_FOUND",),
    ), **changes)


def decision(rows=(), *, s=None, assignments=None, ready=True):
    return propose_investigation(
        spec=s or spec(),
        assignments=(assignment(), assignment("PRIMARY_SOURCE")) if assignments is None else assignments,
        observations=rows, budget_ready=ready, capability_ready=ready,
    )


def receipt(proposal, *, result="NO_MATCH", lane="ORIGINAL_MEDIA", **changes):
    base = dict(
        attempt_id=proposal.proposed_attempt_id,
        material_fingerprint=spec().material_fingerprint,
        assignment_id=proposal.assignment_id,
        lane=lane,
        result=result, lineage_id=None, source_version=None,
        source_sha256=None, review_event_id=None,
        spent_usd=Decimal("0.01"),
    )
    base.update(changes)
    return InvestigationObservation(**base)


class PrivateInvestigationAttemptTests(unittest.TestCase):
    def test_private_bounded_proposal_only_with_preexisting_real_adapter(self):
        first = decision()
        self.assertEqual(first.status, "READY_PRIVATE_PROPOSAL")
        self.assertFalse(first.publication_authority)
        self.assertEqual(first.remaining_attempts, 2)
        self.assertEqual(first, decision())
        self.assertTrue(first.proposed_attempt_id.startswith("investigation-attempt:"))

    def test_bad_rights_budget_and_capability_hold_without_attempt(self):
        for status in ("UNKNOWN", "REVOKED", "EXPIRED", "DENIED"):
            with self.subTest(status=status):
                result = decision(s=spec(rights_status=status))
                self.assertEqual(result.status, "WAIT_EXTERNAL")
                self.assertIsNone(result.proposed_attempt_id)
        self.assertEqual(decision(ready=False).status, "WAIT_EXTERNAL")

    def test_string_false_readiness_cannot_authorize_an_investigation_attempt(self):
        for field in ("budget_ready", "capability_ready"):
            with self.subTest(field=field):
                arguments = {
                    "spec": spec(), "assignments": (assignment(),),
                    "observations": (), "budget_ready": True,
                    "capability_ready": True,
                }
                arguments[field] = "false"
                with self.assertRaisesRegex(ValueError, "INVESTIGATION_READINESS_INVALID"):
                    propose_investigation(**arguments)

    def test_changed_question_and_attempt_ceiling_invalidate_prior_plan(self):
        first = decision()
        for changed in (
            spec(question="Locate a different exact original scene"),
            spec(max_attempts=3),
            spec(cost_cap_usd=Decimal("0.09")),
        ):
            with self.subTest(changed=changed):
                new = decision(s=changed)
                self.assertNotEqual(new.plan_fingerprint, first.plan_fingerprint)
                self.assertNotEqual(new.proposed_attempt_id, first.proposed_attempt_id)

    def test_changed_assignment_question_scope_or_gate_invalidates_prior_attempt(self):
        first = decision(assignments=(assignment(),))
        a = assignment()
        changes = (
            {"question": "Another approved research question"},
            {"max_results_per_host": 1},
            {"temporal_constraints": {"start": "2026-10-01"}},
            {"authority_scope": {"jurisdiction": "IT"}},
            {"status": "BLOCKED", "blockers": ("RIGHTS_WITHDRAWN",)},
        )
        for change in changes:
            with self.subTest(change=change):
                current = decision(assignments=(replace(a, **change),))
                self.assertNotEqual(current.plan_fingerprint, first.plan_fingerprint)
                self.assertNotEqual(current.proposed_attempt_id, first.proposed_attempt_id)
                old = receipt(first, lane=a.lane)
                with self.assertRaisesRegex(ValueError, "UNBOUND_ATTEMPT"):
                    decision((old,), assignments=(replace(a, **change),))

    def test_rights_status_change_never_reuses_old_authorized_attempt_id(self):
        active = spec(rights_status="CLEARED")
        prior = decision(s=active, assignments=(assignment(),))
        blocked = spec(rights_status="REVOKED")
        current = decision(s=blocked, assignments=(assignment(),))
        self.assertEqual(current.status, "WAIT_EXTERNAL")
        self.assertIsNone(current.proposed_attempt_id)
        self.assertNotEqual(current.plan_fingerprint, prior.plan_fingerprint)
        with self.assertRaisesRegex(ValueError, "UNBOUND_ATTEMPT"):
            decision((receipt(prior, lane="ORIGINAL_MEDIA"),),
                     s=blocked, assignments=(assignment(),))

    def test_empty_plan_and_unreviewed_adapter_never_execute(self):
        self.assertEqual(decision(assignments=()).status, "WAIT_EXTERNAL")
        self.assertEqual(decision(assignments=(assignment(status="BLOCKED", blockers=("NO_SOURCE_PERMIT",)),)).status, "WAIT_EXTERNAL")
        self.assertEqual(decision(assignments=(assignment(stop_conditions=()),)).status, "WAIT_EXTERNAL")

    def test_no_match_then_second_distinct_strategy_then_checked_insufficient(self):
        first = decision()
        a = receipt(first, lane="ORIGINAL_MEDIA" if first.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE")
        second = decision((a,))
        self.assertEqual(second.status, "READY_PRIVATE_PROPOSAL")
        self.assertNotEqual(second.assignment_id, first.assignment_id)
        b = receipt(second, lane="ORIGINAL_MEDIA" if second.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE")
        final = decision((a, b))
        self.assertEqual(final.status, "EXHAUSTED")
        self.assertEqual(final.independent_reviewed_lineages, 0)
        self.assertNotIn("SUPPORTED", final.reason_code)

    def test_all_allowed_strategies_checked_below_attempt_cap_is_insufficient_not_support(self):
        first = decision(s=spec(max_attempts=3))
        lane1 = "ORIGINAL_MEDIA" if first.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE"
        a = receipt(first, lane=lane1)
        second = decision((a,), s=spec(max_attempts=3))
        lane2 = "ORIGINAL_MEDIA" if second.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE"
        b = receipt(second, lane=lane2)
        final = decision((a, b), s=spec(max_attempts=3))
        self.assertEqual(final.status, "CHECKED_INSUFFICIENT")
        self.assertEqual(final.remaining_attempts, 1)
        self.assertFalse(final.publication_authority)

    def test_reviewed_locator_only_yields_private_candidate_not_truth_or_rights(self):
        first = decision()
        row = receipt(first,
            lane="ORIGINAL_MEDIA" if first.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE",
            result="REVIEWED_SOURCE_CANDIDATE", lineage_id="lineage:one",
            source_version="version:one", source_sha256="a" * 64,
            review_event_id="review:source:1",
        )
        done = decision((row,))
        self.assertEqual(done.status, "RESOLVED_PRIVATE_CANDIDATE")
        self.assertFalse(done.publication_authority)
        self.assertEqual(done.independent_reviewed_lineages, 1)
        self.assertNotIn("FACTUALLY", str(done))

    def test_duplicate_receipt_idempotent_and_conflicts_rejected(self):
        first = decision()
        row = receipt(first, lane="ORIGINAL_MEDIA" if first.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE")
        self.assertEqual(decision((row, row)), decision((row,)))
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            decision((row, replace(row, spent_usd=Decimal("0.02"))))
        with self.assertRaisesRegex(ValueError, "UNBOUND_ATTEMPT"):
            decision((replace(row, attempt_id="invented:job"),))
        with self.assertRaisesRegex(ValueError, "FOREIGN_ASSIGNMENT"):
            decision((replace(row, lane="CHALLENGER"),))

    def test_over_budget_assignment_receipt_cannot_count_as_checked(self):
        # One attempt cannot claim a spend above its *own* assignment ceiling,
        # even when the overall investigation envelope still has room.
        first = decision()
        lane = "ORIGINAL_MEDIA" if first.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE"
        excessive = receipt(first, lane=lane, result="NO_MATCH", spent_usd=Decimal("0.04"))
        self.assertLess(excessive.spent_usd, spec().cost_cap_usd)
        self.assertGreater(excessive.spent_usd, assignment(lane).cost_cap_usd)
        with self.assertRaisesRegex(ValueError, "INVESTIGATION_ASSIGNMENT_COST_EXCEEDED"):
            decision((excessive,))
        # The same upper bound applies to a purportedly reviewed source.
        claimed_review = replace(excessive, result="REVIEWED_SOURCE_CANDIDATE",
                                 lineage_id="lineage:one", source_version="source:one",
                                 source_sha256="a" * 64, review_event_id="review:event")
        with self.assertRaisesRegex(ValueError, "INVESTIGATION_ASSIGNMENT_COST_EXCEEDED"):
            decision((claimed_review,))
        self.assertEqual(decision((replace(excessive, spent_usd=Decimal("0.03")),)).status,
                         "READY_PRIVATE_PROPOSAL")

    def test_new_material_reopens_under_new_version_and_preserves_history(self):
        first = decision()
        record = receipt(first, lane="ORIGINAL_MEDIA" if first.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE")
        new = decision((record,), s=spec(material_fingerprint="source-version-sha:b"))
        self.assertEqual(new.status, "READY_PRIVATE_PROPOSAL")
        self.assertNotEqual(new.proposed_attempt_id, first.proposed_attempt_id)
        self.assertEqual(new.prior_attempt_count, 0)

    def test_outage_and_external_block_not_confused_with_negative_search(self):
        first = decision()
        lane = "ORIGINAL_MEDIA" if first.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE"
        self.assertEqual(decision((receipt(first, lane=lane, result="OUTAGE"),)).status, "WAIT_EXTERNAL")
        self.assertEqual(decision((receipt(first, lane=lane, result="RIGHTS_BLOCKED"),)).status, "WAIT_EXTERNAL")

    def test_invalid_source_hash_and_self_certified_fake_review_rejected(self):
        first = decision()
        lane = "ORIGINAL_MEDIA" if first.assignment_id.endswith("ORIGINAL_MEDIA") else "PRIMARY_SOURCE"
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_INVALID"):
            receipt(first, lane=lane, result="REVIEWED_SOURCE_CANDIDATE",
                    lineage_id="lineage:1", source_version="v:1", source_sha256="invalid", review_event_id="review:1")
        with self.assertRaisesRegex(ValueError, "UNREVIEWED_RECEIPT"):
            receipt(first, lane=lane, result="NO_MATCH", review_event_id="fake-review")

    def test_overlarge_or_duplicate_plan_is_rejected(self):
        a = assignment()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ASSIGNMENTS"):
            decision(assignments=(a, a))
        with self.assertRaisesRegex(ValueError, "INPUT_UNBOUNDED"):
            decision(assignments=(a,) * 17)


if __name__ == "__main__":
    unittest.main()
