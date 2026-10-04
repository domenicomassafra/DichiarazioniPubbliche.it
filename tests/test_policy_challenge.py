"""DP-303 — correction / takedown / appeal workflow tests.

Covers the append-only state machine, the actor-authority table, the
"publication is never implicit" rule, chain validation, and appeal separation.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.correction_runtime import (  # noqa: E402
    deterministic_correction_id,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import (  # noqa: E402
    CHALLENGE_WORKFLOW_VERSION,
    NO_INTENT_DERIVATION,
    ChallengeContext,
    ChallengeKind,
    ChallengeRole,
    ChallengeState,
    TransitionBlocker,
    build_correction_record_id,
    build_reply_record_id,
    evaluate_transition,
    is_private_state,
    public_omission_required,
    publication_authorized,
)


def _correction(**overrides) -> ChallengeContext:
    base = {
        "kind": ChallengeKind.CORRECTION,
        "current_state": ChallengeState.PRIVATE_RECEIVED,
        "actor_role": ChallengeRole.PUBLIC_SUBMITTER,
        "actor_id": "submitter-1",
        "reason": "the register value differs",
        "superseding_finding_id": "finding-2",
        "supersedes_chain_valid": True,
    }
    base.update(overrides)
    return ChallengeContext(**base)


class WorkflowContractTests(unittest.TestCase):
    def test_version_is_pinned(self):
        self.assertEqual(CHALLENGE_WORKFLOW_VERSION, "challenge-workflow-v1")

    def test_no_intent_derivation_is_stated_as_a_constant(self):
        # C-303-04 must be visible in code, not just in prose.
        self.assertIn("never establishes intent", NO_INTENT_DERIVATION)

    def test_every_terminal_public_state_has_no_forward_transition(self):
        # Append-only history: a public correction is a new record, never a
        # mutation of the prior one.
        from dichiarazioni_pubbliche.policy.challenge_workflow import ALLOWED_TRANSITIONS

        self.assertEqual(ALLOWED_TRANSITIONS[ChallengeKind.CORRECTION][
            ChallengeState.PUBLIC_VERSIONED], frozenset()
        )


class ActorAuthorityTests(unittest.TestCase):
    def test_public_submitter_cannot_publish_a_correction_directly(self):
        ctx = _correction(
            current_state=ChallengeState.REVIEW_REQUIRED,
            actor_role=ChallengeRole.PUBLIC_SUBMITTER,
            challenge_review_approved=True,
            target_finding_review_approved=True,
            reanalysis_trigger_processed=True,
        )
        decision = evaluate_transition(ctx)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, TransitionBlocker.ROLE_NOT_AUTHORIZED.value)

    def test_intake_adapter_cannot_reach_a_decision_state(self):
        ctx = _correction(
            current_state=ChallengeState.REVIEW_REQUIRED,
            actor_role=ChallengeRole.INTAKE_ADAPTER,
            challenge_review_approved=True,
            target_finding_review_approved=True,
            reanalysis_trigger_processed=True,
        )
        self.assertFalse(evaluate_transition(ctx).allowed)

    def test_unknown_role_is_refused(self):
        ctx = _correction(actor_role="ROOT")
        self.assertFalse(evaluate_transition(ctx).allowed)

    def test_public_submitter_may_initiate_a_takedown_request(self):
        ctx = ChallengeContext(
            kind=ChallengeKind.TAKEDOWN,
            current_state=ChallengeState.PRIVATE_RECEIVED,
            actor_role=ChallengeRole.PUBLIC_SUBMITTER,
            actor_id="submitter-1",
            reason="please review",
        )
        decision = evaluate_transition(ctx)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, ChallengeState.TRIAGE_PENDING)


class CorrectionFlowTests(unittest.TestCase):
    def test_correction_with_invalid_chain_is_rejected_not_advanced(self):
        ctx = _correction(supersedes_chain_valid=False)
        decision = evaluate_transition(ctx)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, ChallengeState.REJECTED)
        self.assertFalse(publication_authorized(ctx, decision))

    def test_correction_advances_to_reanalysis_with_a_valid_chain(self):
        decision = evaluate_transition(_correction())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, ChallengeState.REANALYSIS_PENDING)

    def test_reanalysis_pending_cannot_advance_before_the_trigger_processes(self):
        ctx = _correction(
            current_state=ChallengeState.REANALYSIS_PENDING,
            actor_role=ChallengeRole.OPERATOR,
            reanalysis_trigger_processed=False,
        )
        self.assertFalse(evaluate_transition(ctx).allowed)

    def test_full_correction_path_reaches_public_versioned(self):
        ctx = _correction(
            current_state=ChallengeState.REVIEW_REQUIRED,
            actor_role=ChallengeRole.DECISION_REVIEWER,
            actor_id="reviewer-1",
            challenge_review_approved=True,
            target_finding_review_approved=True,
            reanalysis_trigger_processed=True,
        )
        decision = evaluate_transition(ctx)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, ChallengeState.PUBLIC_VERSIONED)
        self.assertTrue(publication_authorized(ctx, decision))

    def test_stale_review_cannot_authorize_publication(self):
        ctx = _correction(
            current_state=ChallengeState.REVIEW_REQUIRED,
            actor_role=ChallengeRole.DECISION_REVIEWER,
            actor_id="reviewer-1",
            challenge_review_approved=True,
            target_finding_review_approved=True,
            reanalysis_trigger_processed=True,
            review_is_stale=True,
        )
        decision = evaluate_transition(ctx)
        self.assertFalse(decision.allowed)
        self.assertIn(TransitionBlocker.STALE_REVIEW, decision.blockers)
        self.assertFalse(publication_authorized(ctx, decision))

    def test_missing_correction_review_never_publishes(self):
        ctx = _correction(
            current_state=ChallengeState.REVIEW_REQUIRED,
            actor_role=ChallengeRole.DECISION_REVIEWER,
            actor_id="reviewer-1",
            challenge_review_approved=False,
            target_finding_review_approved=True,
            reanalysis_trigger_processed=True,
        )
        decision = evaluate_transition(ctx)
        self.assertFalse(publication_authorized(ctx, decision))

    def test_non_leaf_target_blocks_the_correction(self):
        ctx = _correction(
            current_state=ChallengeState.REVIEW_REQUIRED,
            actor_role=ChallengeRole.DECISION_REVIEWER,
            actor_id="reviewer-1",
            challenge_review_approved=True,
            target_finding_review_approved=True,
            reanalysis_trigger_processed=True,
            target_is_leaf=False,
        )
        decision = evaluate_transition(ctx)
        self.assertFalse(decision.allowed)
        self.assertIn(TransitionBlocker.CHAIN_NOT_LEAF, decision.blockers)


class PublicationIsNeverImplicitTests(unittest.TestCase):
    def test_status_alone_never_authorizes_publication(self):
        # C-303-03: a bare status value cannot substitute for the gates.
        bare = _correction(current_state=ChallengeState.PUBLIC_VERSIONED)
        decision = evaluate_transition(bare)
        self.assertFalse(publication_authorized(bare, decision))

    def test_disallowed_transition_never_authorizes_publication(self):
        ctx = _correction(
            current_state=ChallengeState.REVIEW_REQUIRED,
            actor_role=ChallengeRole.PUBLIC_SUBMITTER,
        )
        self.assertFalse(publication_authorized(ctx, evaluate_transition(ctx)))

    def test_takedown_and_appeal_never_authorize_publication(self):
        for kind in (ChallengeKind.TAKEDOWN, ChallengeKind.APPEAL):
            ctx = ChallengeContext(
                kind=kind,
                current_state=ChallengeState.PRIVATE_RECEIVED,
                actor_role=ChallengeRole.PUBLIC_SUBMITTER,
                actor_id="s",
                reason="r",
            )
            self.assertFalse(publication_authorized(ctx, evaluate_transition(ctx)))


class TakedownFlowTests(unittest.TestCase):
    def test_approved_hold_requires_a_review_event(self):
        ctx = ChallengeContext(
            kind=ChallengeKind.TAKEDOWN,
            current_state=ChallengeState.TRIAGE_PENDING,
            actor_role=ChallengeRole.TRIAGE_REVIEWER,
            actor_id="triage-1",
            reason="rights complaint",
            challenge_review_approved=True,
        )
        decision = evaluate_transition(ctx)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, ChallengeState.PUBLIC_HOLD_APPROVED)

    def test_unapproved_takedown_is_referred_not_held(self):
        ctx = ChallengeContext(
            kind=ChallengeKind.TAKEDOWN,
            current_state=ChallengeState.TRIAGE_PENDING,
            actor_role=ChallengeRole.TRIAGE_REVIEWER,
            actor_id="triage-1",
            reason="no evidence",
        )
        decision = evaluate_transition(ctx)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, ChallengeState.REFERRED)

    def test_hold_requires_public_omission_not_deletion(self):
        ctx = ChallengeContext(
            kind=ChallengeKind.TAKEDOWN,
            current_state=ChallengeState.PUBLIC_HOLD_APPROVED,
            actor_role=ChallengeRole.TRIAGE_REVIEWER,
            actor_id="triage-1",
            reason="rights complaint",
            challenge_review_approved=True,
        )
        self.assertTrue(public_omission_required(ctx))

    def test_a_pending_takedown_does_not_omit_public_output(self):
        ctx = ChallengeContext(
            kind=ChallengeKind.TAKEDOWN,
            current_state=ChallengeState.TRIAGE_PENDING,
            actor_role=ChallengeRole.TRIAGE_REVIEWER,
            actor_id="triage-1",
            reason="pending",
        )
        self.assertFalse(public_omission_required(ctx))


class AppealFlowTests(unittest.TestCase):
    def _appeal(self, **overrides) -> ChallengeContext:
        base = {
            "kind": ChallengeKind.APPEAL,
            "current_state": ChallengeState.PRIVATE_RECEIVED,
            "actor_role": ChallengeRole.PUBLIC_SUBMITTER,
            "actor_id": "submitter-1",
            "reason": "please reconsider",
            "original_reviewer_id": "reviewer-1",
        }
        base.update(overrides)
        return ChallengeContext(**base)

    def test_appeal_by_the_original_reviewer_is_refused(self):
        ctx = self._appeal(actor_id="reviewer-1")
        self.assertFalse(evaluate_transition(ctx).allowed)

    def test_appeal_by_the_original_reviewer_is_allowed_with_a_recorded_exception(self):
        ctx = self._appeal(actor_id="reviewer-1", separation_exception_recorded=True)
        self.assertTrue(evaluate_transition(ctx).allowed)

    def test_independent_reviewer_may_uphold(self):
        ctx = self._appeal(
            current_state=ChallengeState.INDEPENDENT_REVIEW_PENDING,
            actor_role=ChallengeRole.APPEAL_REVIEWER,
            actor_id="reviewer-2",
            challenge_review_approved=True,
            reanalysis_trigger_processed=True,
            target_finding_review_approved=True,
        )
        decision = evaluate_transition(ctx)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, ChallengeState.UPHELD)

    def test_appeal_without_a_review_decision_needs_info(self):
        ctx = self._appeal(
            current_state=ChallengeState.INDEPENDENT_REVIEW_PENDING,
            actor_role=ChallengeRole.APPEAL_REVIEWER,
            actor_id="reviewer-2",
            challenge_review_approved=False,
        )
        decision = evaluate_transition(ctx)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.next_state, ChallengeState.NEEDS_INFO)

    def test_appeal_outcome_never_does_not_edit_the_original_decision(self):
        # The workflow only ever returns a new state; it has no mutation API.
        ctx = self._appeal(
            current_state=ChallengeState.INDEPENDENT_REVIEW_PENDING,
            actor_role=ChallengeRole.APPEAL_REVIEWER,
            actor_id="reviewer-2",
            challenge_review_approved=True,
        )
        before = ctx.current_state
        evaluate_transition(ctx)
        self.assertEqual(ctx.current_state, before)


class FailClosedTests(unittest.TestCase):
    def test_retention_hold_freezes_every_transition(self):
        ctx = _correction(retention_hold_active=True)
        decision = evaluate_transition(ctx)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, TransitionBlocker.RETENTION_HOLD_ACTIVE.value)

    def test_unknown_target_blocks(self):
        ctx = _correction(target_record_exists=False)
        self.assertFalse(evaluate_transition(ctx).allowed)

    def test_oversized_reason_blocks(self):
        ctx = _correction(reason="x" * 8001)
        self.assertFalse(evaluate_transition(ctx).allowed)

    def test_intent_language_in_public_copy_is_refused(self):
        # C-303-04 + DP-301 hard rule applied to a public notice.
        ctx = _correction(public_notice_text="the official lied and was removed")
        decision = evaluate_transition(ctx)
        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.reason, TransitionBlocker.INTENT_LANGUAGE_IN_PUBLIC_COPY.value
        )

    def test_unknown_kind_is_refused(self):
        ctx = _correction(kind="SOMETHING_ELSE")
        self.assertFalse(evaluate_transition(ctx).allowed)

    def test_private_states_are_private(self):
        for state in (
            ChallengeState.PRIVATE_RECEIVED,
            ChallengeState.REANALYSIS_PENDING,
            ChallengeState.REVIEW_REQUIRED,
            ChallengeState.INDEPENDENT_REVIEW_PENDING,
        ):
            self.assertTrue(is_private_state(state))

    def test_public_state_is_not_private(self):
        self.assertFalse(is_private_state(ChallengeState.PUBLIC_VERSIONED))


class ReuseOfExistingRuntimeTests(unittest.TestCase):
    """DP-303 says extend correction_runtime, do not fork it."""

    def test_correction_id_is_delegated_to_the_existing_runtime(self):
        produced = build_correction_record_id(
            finding_id="finding-2",
            previous_finding_id="finding-1",
            reason="corrected value",
            changed_fields={"finding": {"assessment": "SUPPORTED"}},
        )
        expected = deterministic_correction_id(
            finding_id="finding-2",
            previous_finding_id="finding-1",
            reason="corrected value",
            changed_fields={"finding": {"assessment": "SUPPORTED"}},
        )
        self.assertEqual(produced, expected)

    def test_reply_id_is_delegated_to_the_existing_runtime(self):
        produced = build_reply_record_id(
            finding_id="finding-1",
            body="a reply body",
            submitter_name=None,
            submitter_role=None,
            evidence_urls=[],
        )
        self.assertTrue(produced.startswith("reply:"))

    def test_identical_correction_assets_produce_an_identical_id(self):
        kwargs = dict(
            finding_id="f2",
            previous_finding_id="f1",
            reason="r",
            changed_fields={"a": 1},
        )
        self.assertEqual(
            build_correction_record_id(**kwargs), build_correction_record_id(**kwargs)
        )


if __name__ == "__main__":
    unittest.main()
