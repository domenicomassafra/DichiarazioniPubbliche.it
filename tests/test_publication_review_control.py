import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    evaluate_high_risk_candidate,
)
from dichiarazioni_pubbliche.publication_review_control import (  # noqa: E402
    ReviewRiskClass,
    ReviewRole,
    ReviewStage,
    build_review_event,
    evaluate_attested_review_separation,
    evaluate_publication_review,
)
from dichiarazioni_pubbliche.publication_safety import (  # noqa: E402
    ProofState,
    PublicationSafetyInput,
    WordingMode,
    evaluate_publication_safety,
)


def safety(**ref_overrides):
    refs = {
        "source_sha256": "a" * 64,
        "quote_version": "quote:v1",
        "speaker_version": "speaker:v1",
        "context_version": "context:v1",
        "evidence_version": "evidence:v1",
        "finding_version": "finding:v1",
        "finding_review": "review:finding:1",
        "policy_version": "policy-v1",
    }
    refs.update(ref_overrides)
    value = PublicationSafetyInput(
        wording_mode=WordingMode.PARAPHRASE,
        media_quote=False,
        source_identity=ProofState.PASSED,
        exact_wording=ProofState.NOT_APPLICABLE,
        transcript_verbatim=ProofState.NOT_APPLICABLE,
        speaker_span=ProofState.PASSED,
        speech_origin=ProofState.PASSED,
        context_integrity=ProofState.PASSED,
        wording_integrity=ProofState.PASSED,
        identity_integrity=ProofState.PASSED,
        translation_review=ProofState.NOT_APPLICABLE,
        evidence_suitability=ProofState.PASSED,
        citation_assurance=ProofState.PASSED,
        privacy=ProofState.PASSED,
        rights=ProofState.PASSED,
        verification_review=ProofState.PASSED,
        finding_review=ProofState.PASSED,
        challenge_hold=ProofState.PASSED,
        load_bearing_refs=refs,
    )
    result = evaluate_publication_safety(value)
    assert result.eligible
    return result


def high_risk(kind="LEGAL", **overrides):
    if kind == "STANDARD":
        values = dict(
            source_text="Il bilancio è stato pubblicato.",
            normalized_text="Il bilancio è stato pubblicato.",
            legal_status_claim=False,
            identity_resolved=True,
            privacy_allows=True,
            official_record_approved=False,
            jurisdiction_match=False,
            effective_time_match=False,
            human_review_approved=False,
            dual_control_approved=False,
            qualified_policy_accepted=False,
        )
    elif kind == "HIGH":
        values = dict(
            source_text="Secondo la procura, Rossi avrebbe commesso una frode.",
            normalized_text="Secondo la procura, Rossi avrebbe commesso una frode.",
            legal_status_claim=False,
            identity_resolved=True,
            privacy_allows=True,
            official_record_approved=False,
            jurisdiction_match=False,
            effective_time_match=False,
            human_review_approved=True,
            dual_control_approved=False,
            qualified_policy_accepted=True,
            policy_decision_ref="decision:dp307:high-risk-v1",
        )
    else:
        values = dict(
            source_text="La procura comunica che Mario Rossi è indagato.",
            normalized_text="Mario Rossi è indagato.",
            legal_status_claim=True,
            identity_resolved=True,
            privacy_allows=True,
            official_record_approved=True,
            jurisdiction_match=True,
            effective_time_match=True,
            human_review_approved=True,
            dual_control_approved=False,
            qualified_policy_accepted=True,
            policy_decision_ref="decision:dp307:legal-status-v1",
        )
    values.update(overrides)
    return evaluate_high_risk_candidate(**values)


def event(
    *,
    safety_result,
    risk_result,
    input_binding="b" * 64,
    stage=ReviewStage.PRIMARY,
    role=ReviewRole.DECISION_REVIEWER,
    actor="reviewer:1",
    credential="1" * 64,
    previous=None,
    version="finding:v1",
    action="APPROVED",
    exception=None,
):
    return build_review_event(
        record_id="finding:1",
        record_version=version,
        stage=stage,
        role=role,
        action=action,
        actor_ref=actor,
        credential_fingerprint=credential,
        reviewed_at=(
            "2026-10-05T21:00:00+02:00"
            if previous is None
            else "2026-10-05T21:05:00+02:00"
        ),
        publication_safety=safety_result,
        high_risk=risk_result,
        high_risk_input_binding_sha256=input_binding,
        previous_event=previous,
        separation_exception_ref=exception,
    )


def evaluate(
    events,
    *,
    safety_result,
    risk_result,
    input_binding="b" * 64,
    version="finding:v1",
    upstream_actors=(),
    upstream_credentials=(),
):
    return evaluate_publication_review(
        record_id="finding:1",
        record_version=version,
        publication_safety=safety_result,
        high_risk=risk_result,
        high_risk_input_binding_sha256=input_binding,
        events=events,
        upstream_actor_refs=upstream_actors,
        upstream_credential_fingerprints=upstream_credentials,
    )


class PublicationReviewControlTests(unittest.TestCase):
    def setUp(self):
        self.safety = safety()

    def test_standard_requires_explicit_primary_review_without_implicit_dual_control(self):
        risk = high_risk("STANDARD")
        primary = event(safety_result=self.safety, risk_result=risk)
        self.assertEqual(primary.review_risk_class, ReviewRiskClass.STANDARD)
        result = evaluate([primary], safety_result=self.safety, risk_result=risk)
        self.assertEqual(result.risk_class, ReviewRiskClass.STANDARD)
        self.assertTrue(result.review_complete)
        self.assertFalse(result.dual_control_required)
        self.assertFalse(result.dual_control_satisfied)
        self.assertEqual(result.disposition, "STANDARD_REVIEW_COMPLETE")
        self.assertFalse(hasattr(result, "publication_allowed"))

    def test_event_risk_class_is_hash_bound_and_must_match_current_high_risk_decision(self):
        risk = high_risk("LEGAL")
        primary = event(safety_result=self.safety, risk_result=risk)
        self.assertEqual(primary.review_risk_class, ReviewRiskClass.LEGAL)
        tampered = replace(primary, review_risk_class=ReviewRiskClass.STANDARD)
        result = evaluate([tampered], safety_result=self.safety, risk_result=risk)
        self.assertIn("REVIEW_EVENT_TAMPERED", result.blockers)

    def test_attested_separation_gate_requires_second_reviewer_for_hash_bound_legal_class(self):
        risk = high_risk("LEGAL")
        primary = event(safety_result=self.safety, risk_result=risk)
        held = evaluate_attested_review_separation(
            record_id="finding:1",
            record_version="finding:v1",
            events=(primary,),
        )
        self.assertEqual(held.risk_class, ReviewRiskClass.LEGAL)
        self.assertFalse(held.review_complete)
        self.assertIn("REVIEW_SEPARATION_UNAVAILABLE", held.blockers)

        independent = event(
            safety_result=self.safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        ready = evaluate_attested_review_separation(
            record_id="finding:1",
            record_version="finding:v1",
            events=(primary, independent),
        )
        self.assertTrue(ready.review_complete)
        self.assertTrue(ready.dual_control_satisfied)

    def test_attested_separation_gate_rejects_diverged_safety_binding(self):
        risk = high_risk("HIGH")
        primary = event(safety_result=self.safety, risk_result=risk)
        changed_safety = safety(source_sha256="c" * 64)
        independent = event(
            safety_result=changed_safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        held = evaluate_attested_review_separation(
            record_id="finding:1",
            record_version="finding:v1",
            events=(primary, independent),
        )
        self.assertFalse(held.review_complete)
        self.assertIn("REVIEW_SAFETY_BINDING_DIVERGED", held.blockers)

    def test_high_and_legal_require_two_distinct_reviewers(self):
        for kind, expected in (
            ("HIGH", ReviewRiskClass.HIGH),
            ("LEGAL", ReviewRiskClass.LEGAL),
        ):
            with self.subTest(kind=kind):
                risk = high_risk(kind)
                primary = event(safety_result=self.safety, risk_result=risk)
                one = evaluate([primary], safety_result=self.safety, risk_result=risk)
                self.assertEqual(one.risk_class, expected)
                self.assertFalse(one.review_complete)
                self.assertIn("REVIEW_SEPARATION_UNAVAILABLE", one.blockers)
                self.assertIn(
                    "OBTAIN_INDEPENDENT_PUBLICATION_REVIEW", one.next_actions
                )
                independent = event(
                    safety_result=self.safety,
                    risk_result=risk,
                    stage=ReviewStage.INDEPENDENT,
                    role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
                    actor="reviewer:2",
                    credential="2" * 64,
                    previous=primary,
                )
                two = evaluate(
                    [primary, independent],
                    safety_result=self.safety,
                    risk_result=risk,
                )
                self.assertTrue(two.review_complete)
                self.assertTrue(two.dual_control_satisfied)
                self.assertEqual(two.disposition, "DUAL_CONTROL_COMPLETE")

    def test_same_person_cannot_count_twice_even_with_explicit_exception(self):
        risk = high_risk("LEGAL")
        primary = event(safety_result=self.safety, risk_result=risk)
        independent = event(
            safety_result=self.safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:1",
            credential="2" * 64,
            previous=primary,
            exception="exception:staffing:1",
        )
        result = evaluate(
            [primary, independent], safety_result=self.safety, risk_result=risk
        )
        self.assertFalse(result.review_complete)
        self.assertIn("DUPLICATE_REVIEWER_IDENTITY", result.blockers)
        self.assertIn("SEPARATION_EXCEPTION_NOT_DUAL_CONTROL", result.blockers)

    def test_same_credential_cannot_count_for_different_actor(self):
        risk = high_risk("HIGH")
        primary = event(safety_result=self.safety, risk_result=risk)
        independent = event(
            safety_result=self.safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="1" * 64,
            previous=primary,
        )
        result = evaluate(
            [primary, independent], safety_result=self.safety, risk_result=risk
        )
        self.assertFalse(result.review_complete)
        self.assertIn("DUPLICATE_REVIEWER_CREDENTIAL", result.blockers)

    def test_independent_reviewer_must_be_separate_from_upstream_decision_actor(self):
        risk = high_risk("LEGAL")
        primary = event(safety_result=self.safety, risk_result=risk)
        independent = event(
            safety_result=self.safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="verification-author:1",
            credential="2" * 64,
            previous=primary,
        )
        result = evaluate(
            [primary, independent],
            safety_result=self.safety,
            risk_result=risk,
            upstream_actors=("verification-author:1",),
        )
        self.assertFalse(result.review_complete)
        self.assertIn(
            "INDEPENDENT_REVIEWER_NOT_SEPARATE_FROM_UPSTREAM", result.blockers
        )

    def test_wrong_role_does_not_satisfy_independent_stage(self):
        risk = high_risk("LEGAL")
        primary = event(safety_result=self.safety, risk_result=risk)
        independent = event(
            safety_result=self.safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.DECISION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        result = evaluate(
            [primary, independent], safety_result=self.safety, risk_result=risk
        )
        self.assertFalse(result.review_complete)
        self.assertIn("INDEPENDENT_REVIEW_ROLE_INVALID", result.blockers)

    def test_safety_binding_change_stales_existing_approvals(self):
        risk = high_risk("LEGAL")
        primary = event(safety_result=self.safety, risk_result=risk)
        independent = event(
            safety_result=self.safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        for key, changed in (
            ("source_sha256", "c" * 64),
            ("quote_version", "quote:v2"),
            ("speaker_version", "speaker:v2"),
            ("context_version", "context:v2"),
            ("evidence_version", "evidence:v2"),
            ("finding_version", "finding:v2"),
        ):
            with self.subTest(key=key):
                changed_safety = safety(**{key: changed})
                result = evaluate(
                    [primary, independent],
                    safety_result=changed_safety,
                    risk_result=risk,
                )
                self.assertFalse(result.review_complete)
                self.assertIn("STALE_PUBLICATION_SAFETY_BINDING", result.blockers)

    def test_high_risk_input_binding_change_stales_existing_approvals(self):
        risk = high_risk("LEGAL")
        primary = event(safety_result=self.safety, risk_result=risk)
        independent = event(
            safety_result=self.safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        result = evaluate(
            [primary, independent],
            safety_result=self.safety,
            risk_result=risk,
            input_binding="d" * 64,
        )
        self.assertFalse(result.review_complete)
        self.assertIn("STALE_HIGH_RISK_BINDING", result.blockers)

    def test_material_record_version_change_requires_new_review(self):
        risk = high_risk("LEGAL")
        old_primary = event(safety_result=self.safety, risk_result=risk)
        result = evaluate(
            [old_primary],
            safety_result=self.safety,
            risk_result=risk,
            version="finding:v2",
        )
        self.assertFalse(result.review_complete)
        self.assertIn("PRIMARY_REVIEW_REQUIRED", result.blockers)

    def test_event_tamper_is_detected(self):
        risk = high_risk("LEGAL")
        primary = event(safety_result=self.safety, risk_result=risk)
        tampered = replace(primary, actor_ref="reviewer:other")
        result = evaluate(
            [tampered], safety_result=self.safety, risk_result=risk
        )
        self.assertFalse(result.review_complete)
        self.assertIn("REVIEW_EVENT_TAMPERED", result.blockers)

    def test_exact_event_replay_is_detected(self):
        risk = high_risk("STANDARD")
        primary = event(safety_result=self.safety, risk_result=risk)
        result = evaluate(
            [primary, primary], safety_result=self.safety, risk_result=risk
        )
        self.assertFalse(result.review_complete)
        self.assertIn("REVIEW_REPLAY_DETECTED", result.blockers)

    def test_append_only_later_rejection_invalidates_prior_stage_approval(self):
        risk = high_risk("STANDARD")
        approved = event(safety_result=self.safety, risk_result=risk)
        rejected = event(
            safety_result=self.safety,
            risk_result=risk,
            actor="reviewer:2",
            credential="2" * 64,
            previous=approved,
            action="REJECTED",
        )
        result = evaluate(
            [approved, rejected], safety_result=self.safety, risk_result=risk
        )
        self.assertFalse(result.review_complete)
        self.assertIn("PRIMARY_REVIEW_NOT_APPROVED", result.blockers)
        self.assertEqual(approved.action, "APPROVED")

    def test_upstream_high_risk_hold_cannot_be_overridden_by_two_reviews(self):
        risk = high_risk("LEGAL", privacy_allows=False)
        primary = event(safety_result=self.safety, risk_result=risk)
        independent = event(
            safety_result=self.safety,
            risk_result=risk,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        result = evaluate(
            [primary, independent], safety_result=self.safety, risk_result=risk
        )
        self.assertFalse(result.review_complete)
        self.assertIn("UPSTREAM_HIGH_RISK_GATE_NOT_READY", result.blockers)


if __name__ == "__main__":
    unittest.main()
