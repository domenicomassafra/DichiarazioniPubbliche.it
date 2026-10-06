import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    evaluate_high_risk_candidate,
)
from dichiarazioni_pubbliche.publication_eligibility import (  # noqa: E402
    _evaluate_publication_eligibility_from_events,
)
from dichiarazioni_pubbliche.publication_review_control import (  # noqa: E402
    ReviewRole,
    ReviewStage,
    build_review_event,
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
    return evaluate_publication_safety(
        PublicationSafetyInput(
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
    )


def risk(kind: str):
    if kind == "STANDARD":
        return evaluate_high_risk_candidate(
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
    if kind == "HIGH":
        return evaluate_high_risk_candidate(
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
    return evaluate_high_risk_candidate(
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


def review_event(
    *,
    safety_result,
    risk_result,
    stage=ReviewStage.PRIMARY,
    role=ReviewRole.DECISION_REVIEWER,
    actor="reviewer:1",
    credential="1" * 64,
    previous=None,
):
    return build_review_event(
        record_id="finding:1",
        record_version="finding:v1",
        stage=stage,
        role=role,
        action="APPROVED",
        actor_ref=actor,
        credential_fingerprint=credential,
        reviewed_at=(
            "2026-10-05T21:00:00+02:00"
            if previous is None
            else "2026-10-05T21:05:00+02:00"
        ),
        publication_safety=safety_result,
        high_risk=risk_result,
        high_risk_input_binding_sha256="b" * 64,
        previous_event=previous,
    )


def compose(safety_result, risk_result, events, **kwargs):
    return _evaluate_publication_eligibility_from_events(
        record_id="finding:1",
        record_version="finding:v1",
        publication_safety=safety_result,
        high_risk=risk_result,
        high_risk_input_binding_sha256=kwargs.pop("input_binding", "b" * 64),
        review_events=events,
        **kwargs,
    )


class PublicationEligibilityTests(unittest.TestCase):
    def test_standard_candidate_requires_primary_review(self):
        safety_result = safety()
        risk_result = risk("STANDARD")
        held = compose(safety_result, risk_result, ())
        self.assertEqual(held.disposition, "HOLD_FOR_PUBLICATION_REVIEW")
        self.assertIn("PRIMARY_REVIEW_REQUIRED", held.blockers)

        primary = review_event(safety_result=safety_result, risk_result=risk_result)
        ready = compose(safety_result, risk_result, (primary,))
        self.assertEqual(ready.disposition, "ELIGIBLE_FOR_PROJECTION_REVALIDATION")
        self.assertEqual(ready.counted_review_event_ids, (primary.event_id,))

    def test_high_and_legal_require_completed_review_separation(self):
        for kind in ("HIGH", "LEGAL"):
            with self.subTest(kind=kind):
                safety_result = safety()
                risk_result = risk(kind)
                primary = review_event(
                    safety_result=safety_result,
                    risk_result=risk_result,
                )
                held = compose(safety_result, risk_result, (primary,))
                self.assertEqual(held.disposition, "HOLD_FOR_PUBLICATION_REVIEW")
                self.assertIn("REVIEW_SEPARATION_UNAVAILABLE", held.blockers)
                self.assertIn("REVIEW_SEPARATION_REQUIRED", held.blockers)

                independent = review_event(
                    safety_result=safety_result,
                    risk_result=risk_result,
                    stage=ReviewStage.INDEPENDENT,
                    role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
                    actor="reviewer:2",
                    credential="2" * 64,
                    previous=primary,
                )
                ready = compose(safety_result, risk_result, (primary, independent))
                self.assertEqual(
                    ready.disposition,
                    "ELIGIBLE_FOR_PROJECTION_REVALIDATION",
                )
                self.assertEqual(
                    ready.counted_review_event_ids,
                    (primary.event_id, independent.event_id),
                )

    def test_same_actor_or_credential_cannot_satisfy_composer(self):
        safety_result = safety()
        risk_result = risk("LEGAL")
        primary = review_event(safety_result=safety_result, risk_result=risk_result)
        same_actor = review_event(
            safety_result=safety_result,
            risk_result=risk_result,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:1",
            credential="2" * 64,
            previous=primary,
        )
        result = compose(safety_result, risk_result, (primary, same_actor))
        self.assertIn("DUPLICATE_REVIEWER_IDENTITY", result.blockers)
        self.assertEqual(result.disposition, "HOLD_FOR_PUBLICATION_REVIEW")

    def test_stale_safety_binding_forces_rereview(self):
        safety_result = safety()
        risk_result = risk("LEGAL")
        primary = review_event(safety_result=safety_result, risk_result=risk_result)
        independent = review_event(
            safety_result=safety_result,
            risk_result=risk_result,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        changed_safety = safety(source_sha256="c" * 64)
        result = compose(changed_safety, risk_result, (primary, independent))
        self.assertIn("STALE_PUBLICATION_SAFETY_BINDING", result.blockers)
        self.assertEqual(result.disposition, "HOLD_FOR_PUBLICATION_REVIEW")

    def test_high_risk_input_binding_change_forces_rereview(self):
        safety_result = safety()
        risk_result = risk("HIGH")
        primary = review_event(safety_result=safety_result, risk_result=risk_result)
        independent = review_event(
            safety_result=safety_result,
            risk_result=risk_result,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        result = compose(
            safety_result,
            risk_result,
            (primary, independent),
            input_binding="d" * 64,
        )
        self.assertIn("STALE_HIGH_RISK_BINDING", result.blockers)
        self.assertEqual(result.disposition, "HOLD_FOR_PUBLICATION_REVIEW")

    def test_review_event_tamper_cannot_be_hidden_by_composer(self):
        safety_result = safety()
        risk_result = risk("STANDARD")
        primary = review_event(safety_result=safety_result, risk_result=risk_result)
        tampered = replace(primary, actor_ref="reviewer:tampered")
        result = compose(safety_result, risk_result, (tampered,))
        self.assertIn("REVIEW_EVENT_TAMPERED", result.blockers)
        self.assertEqual(result.disposition, "HOLD_FOR_PUBLICATION_REVIEW")

    def test_binding_is_deterministic_and_load_bearing(self):
        safety_result = safety()
        risk_result = risk("LEGAL")
        primary = review_event(safety_result=safety_result, risk_result=risk_result)
        independent = review_event(
            safety_result=safety_result,
            risk_result=risk_result,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:2",
            credential="2" * 64,
            previous=primary,
        )
        first = compose(safety_result, risk_result, (primary, independent))
        second = compose(safety_result, risk_result, (primary, independent))
        self.assertEqual(first, second)

        alternate = review_event(
            safety_result=safety_result,
            risk_result=risk_result,
            stage=ReviewStage.INDEPENDENT,
            role=ReviewRole.INDEPENDENT_PUBLICATION_REVIEWER,
            actor="reviewer:3",
            credential="3" * 64,
            previous=primary,
        )
        changed = compose(safety_result, risk_result, (primary, alternate))
        self.assertNotEqual(first.binding_sha256, changed.binding_sha256)
        self.assertFalse(hasattr(first, "publication_allowed"))
        self.assertFalse(hasattr(first, "actor_ref"))
        self.assertFalse(hasattr(first, "credential_fingerprint"))


if __name__ == "__main__":
    unittest.main()
