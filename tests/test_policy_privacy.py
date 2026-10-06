"""DP-304 — privacy, minimization, and sensitive-person policy tests.

The deny-by-default surface: classification, public-interest relevance,
sensitive/high-risk quarantine without trait inference, retention interaction,
and the rights-request rule that a public historical version is never silently
erased.
"""

import sys
import unittest
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.privacy_policy import (  # noqa: E402
    PRIVACY_POLICY_VERSION,
    RETENTION_PERIODS_APPROVED,
    DataClass,
    PrivateAccessMode,
    PrivateAccessOutcome,
    PrivateAccessPurpose,
    PrivateAccessRequest,
    PrivateAccessRole,
    ProjectionInput,
    PublicationDecision,
    RetentionDecision,
    RightsRequestKind,
    RightsRequestOutcome,
    assert_no_trait_inference,
    build_private_access_audit,
    contains_high_risk_marker,
    contains_pii_shape,
    contains_sensitive_marker,
    decide_private_access,
    decide_projection,
    minimize_public_fieldset,
    retention_decision,
    rights_request_outcome,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import ChallengeRole  # noqa: E402


def _core(**overrides) -> ProjectionInput:
    base = {
        "field_name": "finding_id",
        "data_class": DataClass.PUBLIC_CORE,
        "relevance_reason": "PUBLIC_ROLE",
    }
    base.update(overrides)
    return ProjectionInput(**base)


class ClassificationTests(unittest.TestCase):
    def test_policy_version_is_pinned(self):
        self.assertEqual(PRIVACY_POLICY_VERSION, "privacy-minimization-v1")

    def test_operational_private_is_never_projectable(self):
        for field in ("raw_text", "canonical_text", "excerpt", "operator_note"):
            with self.subTest(field=field):
                result = decide_projection(
                    _core(field_name=field, data_class=DataClass.OPERATIONAL_PRIVATE)
                )
                self.assertEqual(result.decision, PublicationDecision.PROHIBIT)

    def test_sensitive_and_high_risk_classes_are_never_projectable(self):
        for data_class in (
            DataClass.SENSITIVE_CANDIDATE,
            DataClass.HIGH_RISK_IDENTITY,
            DataClass.EPHEMERAL,
        ):
            with self.subTest(data_class=data_class):
                result = decide_projection(_core(data_class=data_class))
                self.assertEqual(result.decision, PublicationDecision.PROHIBIT)

    def test_unknown_class_fails_closed(self):
        result = decide_projection(_core(data_class="SOMETHING_ELSE"))
        self.assertEqual(result.decision, PublicationDecision.PROHIBIT)

    def test_operational_private_field_name_is_refused_even_if_classified_public(self):
        # A serializer bug that labels a private field PUBLIC_CORE still loses.
        for field in ("transcript_text", "raw_text", "evidence_excerpt", "api_key"):
            with self.subTest(field=field):
                result = decide_projection(
                    _core(field_name=field, data_class=DataClass.PUBLIC_CORE)
                )
                self.assertEqual(result.decision, PublicationDecision.PROHIBIT)

    def test_sensitive_schema_field_name_is_refused_even_if_classified_public(self):
        # This is schema-name minimization, not inference about a person's value.
        for field in ("religion", "criminal_history", "victim_status", "mental_health"):
            with self.subTest(field=field):
                result = decide_projection(
                    _core(field_name=field, data_class=DataClass.PUBLIC_CORE)
                )
                self.assertEqual(result.decision, PublicationDecision.PROHIBIT)
                self.assertIn("SENSITIVE_OR_HIGH_RISK_FIELD_NAME", result.reasons)

    def test_public_core_with_relevance_is_allowed(self):
        self.assertEqual(decide_projection(_core()).decision, PublicationDecision.ALLOW)


class RelevanceGateTests(unittest.TestCase):
    def test_missing_relevance_holds(self):
        result = decide_projection(_core(relevance_reason=None))
        self.assertEqual(result.decision, PublicationDecision.HOLD_FOR_REVIEW)

    def test_weak_relevance_string_holds(self):
        result = decide_projection(_core(relevance_reason="because"))
        self.assertEqual(result.decision, PublicationDecision.HOLD_FOR_REVIEW)

    def test_public_figure_status_alone_is_insufficient(self):
        # P-304-01: being a public figure is not a relevance reason.
        result = decide_projection(_core(relevance_reason="IS_PUBLIC_FIGURE"))
        self.assertEqual(result.decision, PublicationDecision.HOLD_FOR_REVIEW)

    def test_every_accepted_relevance_reason_allows_projection(self):
        for reason in (
            "PUBLIC_ROLE",
            "PUBLIC_INTEREST_FUNCTION",
            "OFFICIAL_RECORD",
            "DOCUMENTED_PUBLIC_ACTIVITY",
        ):
            with self.subTest(reason=reason):
                self.assertEqual(
                    decide_projection(_core(relevance_reason=reason)).decision,
                    PublicationDecision.ALLOW,
                )


class SafeTextApprovalTests(unittest.TestCase):
    def test_public_safe_text_requires_explicit_approval(self):
        result = decide_projection(
            _core(
                field_name="claim",
                data_class=DataClass.PUBLIC_SAFE_TEXT,
                explicitly_approved=False,
            )
        )
        self.assertEqual(result.decision, PublicationDecision.HOLD_FOR_REVIEW)

    def test_approved_public_safe_text_is_allowed(self):
        result = decide_projection(
            _core(
                field_name="claim",
                data_class=DataClass.PUBLIC_SAFE_TEXT,
                explicitly_approved=True,
                text_value="the budget was 12,000 euro",
            )
        )
        self.assertEqual(result.decision, PublicationDecision.ALLOW)


class NoTraitInferenceTests(unittest.TestCase):
    """C-304-02 is the invariant: markers hold, they never become traits."""

    def test_markers_are_quarantine_signals_only(self):
        assert_no_trait_inference()
        for text in (
            "the witness statement",
            "un minore",
            "il paziente",
            "la vittima",
        ):
            with self.subTest(text=text):
                self.assertTrue(contains_high_risk_marker(text))

    def test_sensitive_markers_are_detected(self):
        for text in (
            "a health diagnosis was referenced",
            "problemi di salute",
            "religione",
            "orientamento sessuale",
        ):
            with self.subTest(text=text):
                self.assertTrue(contains_sensitive_marker(text))

    def test_marker_text_is_held_never_published(self):
        result = decide_projection(
            _core(
                field_name="claim",
                data_class=DataClass.PUBLIC_SAFE_TEXT,
                explicitly_approved=True,
                text_value="the witness was a minor at the time",
            )
        )
        self.assertEqual(result.decision, PublicationDecision.HOLD_FOR_REVIEW)

    def test_sensitive_text_is_held_never_published(self):
        result = decide_projection(
            _core(
                field_name="claim",
                data_class=DataClass.PUBLIC_SAFE_TEXT,
                explicitly_approved=True,
                text_value="a health diagnosis was discussed",
            )
        )
        self.assertEqual(result.decision, PublicationDecision.HOLD_FOR_REVIEW)

    def test_plain_neutral_text_is_not_held(self):
        result = decide_projection(
            _core(
                field_name="claim",
                data_class=DataClass.PUBLIC_SAFE_TEXT,
                explicitly_approved=True,
                text_value="the fund was 12,000 euro in 2025",
            )
        )
        self.assertEqual(result.decision, PublicationDecision.ALLOW)


class PiiShapeTests(unittest.TestCase):
    def test_pii_shapes_are_prohibited_not_merely_held(self):
        for text in (
            "contact person@example.org",
            "call 06 1234567",
            "id 123456789",
        ):
            with self.subTest(text=text):
                self.assertTrue(contains_pii_shape(text))
                result = decide_projection(
                    _core(
                        field_name="claim",
                        data_class=DataClass.PUBLIC_SAFE_TEXT,
                        explicitly_approved=True,
                        text_value=text,
                    )
                )
                self.assertEqual(result.decision, PublicationDecision.PROHIBIT)

    def test_numbers_in_a_normal_claim_are_not_pii(self):
        self.assertFalse(contains_pii_shape("the budget was 12,000 euro"))
        self.assertFalse(contains_pii_shape("in 2019 the rate was 1.5 percent"))


class IntentVocabularyLeakTests(unittest.TestCase):
    """DP-301's hard rule applies to privacy-safe public fields too."""

    def test_intent_language_in_a_safe_text_field_is_prohibited(self):
        result = decide_projection(
            _core(
                field_name="claim",
                data_class=DataClass.PUBLIC_SAFE_TEXT,
                explicitly_approved=True,
                text_value="the official deliberately lied",
            )
        )
        self.assertEqual(result.decision, PublicationDecision.PROHIBIT)

    def test_intent_language_in_a_field_name_is_prohibited(self):
        result = decide_projection(_core(field_name="lie_type"))
        self.assertEqual(result.decision, PublicationDecision.PROHIBIT)


class MinimizationTests(unittest.TestCase):
    def test_minimization_drops_private_fields(self):
        kept = minimize_public_fieldset(
            ["finding_id", "claim_id", "raw_text", "excerpt", "speaker_id"]
        )
        self.assertEqual(kept, ("claim_id", "finding_id", "speaker_id"))

    def test_minimization_drops_person_score_fields(self):
        kept = minimize_public_fieldset(["finding_id", "trust_score", "person_rank"])
        self.assertEqual(kept, ("finding_id",))

    def test_minimization_drops_sensitive_or_high_risk_schema_fields(self):
        kept = minimize_public_fieldset(
            ["finding_id", "religion", "victim_status", "criminal_history"]
        )
        self.assertEqual(kept, ("finding_id",))

    def test_minimization_is_sorted_and_deduplicated(self):
        kept = minimize_public_fieldset(["b", "a", "b"])
        self.assertEqual(kept, ("a", "b"))


class RetentionInteractionTests(unittest.TestCase):
    def test_no_retention_period_is_invented(self):
        # P-304-06: periods are an owner/counsel decision.
        self.assertFalse(RETENTION_PERIODS_APPROVED)
        for data_class in (
            DataClass.PUBLIC_CORE,
            DataClass.OPERATIONAL_PRIVATE,
            DataClass.SENSITIVE_CANDIDATE,
        ):
            with self.subTest(data_class=data_class):
                self.assertEqual(
                    retention_decision(data_class),
                    RetentionDecision.AWAITING_APPROVED_PERIOD,
                )

    def test_ephemeral_is_purge_eligible(self):
        self.assertEqual(
            retention_decision(DataClass.EPHEMERAL),
            RetentionDecision.EPHEMERAL_PURGE_ELIGIBLE,
        )

    def test_legal_hold_overrides_ordinary_retention(self):
        self.assertEqual(
            retention_decision(DataClass.EPHEMERAL, legal_hold_active=True),
            RetentionDecision.LEGAL_HOLD,
        )
        self.assertEqual(
            retention_decision(DataClass.OPERATIONAL_PRIVATE, legal_hold_active=True),
            RetentionDecision.LEGAL_HOLD,
        )

    def test_unknown_class_awaits_a_period_rather_than_deleting(self):
        self.assertEqual(
            retention_decision("SOMETHING_ELSE"),
            RetentionDecision.AWAITING_APPROVED_PERIOD,
        )


class RightsRequestTests(unittest.TestCase):
    def test_unreviewed_request_stays_open_and_private(self):
        for kind in RightsRequestKind:
            with self.subTest(kind=kind):
                self.assertEqual(
                    rights_request_outcome(
                        kind, affects_published_version=False, reviewed=False
                    ),
                    RightsRequestOutcome.OPEN_PRIVATE,
                )

    def test_deletion_affecting_a_published_version_becomes_a_public_hold(self):
        # E-304-09: never a silent erase of public history.
        self.assertEqual(
            rights_request_outcome(
                RightsRequestKind.DELETION, affects_published_version=True, reviewed=True
            ),
            RightsRequestOutcome.REVIEWED_PUBLIC_HOLD,
        )

    def test_correction_affecting_a_published_version_becomes_a_reviewed_correction(self):
        self.assertEqual(
            rights_request_outcome(
                RightsRequestKind.CORRECTION, affects_published_version=True, reviewed=True
            ),
            RightsRequestOutcome.REVIEWED_CORRECTION,
        )

    def test_unknown_request_kind_stays_open(self):
        self.assertEqual(
            rights_request_outcome(
                "SOMETHING_ELSE", affects_published_version=False, reviewed=True
            ),
            RightsRequestOutcome.OPEN_PRIVATE,
        )


class PrivateAccessTests(unittest.TestCase):
    def _request(self, **overrides) -> PrivateAccessRequest:
        base = {
            "actor_ref": "reviewer-1",
            "role": PrivateAccessRole.DECISION_REVIEWER,
            "purpose": PrivateAccessPurpose.EDITORIAL_REVIEW,
            "data_class": DataClass.OPERATIONAL_PRIVATE,
            "requested_fields": ("raw_text", "evidence_excerpt"),
        }
        base.update(overrides)
        return PrivateAccessRequest(**base)

    def test_authorized_private_inspection_is_read_only(self):
        decision = decide_private_access(self._request())
        self.assertEqual(decision.outcome, PrivateAccessOutcome.ALLOW_READ_ONLY)
        self.assertTrue(decision.allowed)

    def test_private_access_roles_reuse_existing_dp303_runtime_role_names(self):
        challenge_roles = {role.value for role in ChallengeRole}
        self.assertTrue(
            {role.value for role in PrivateAccessRole}.issubset(challenge_roles)
        )
        for untrusted_role in (
            ChallengeRole.PUBLIC_SUBMITTER,
            ChallengeRole.INTAKE_ADAPTER,
        ):
            with self.subTest(role=untrusted_role):
                self.assertFalse(
                    decide_private_access(self._request(role=untrusted_role.value)).allowed
                )

    def test_unknown_role_purpose_mode_and_class_fail_closed(self):
        cases = (
            {"role": "PUBLIC_USER"},
            {"purpose": "CURIOSITY"},
            {"mode": "SOMETHING_ELSE"},
            {"data_class": "SOMETHING_ELSE"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertFalse(decide_private_access(self._request(**overrides)).allowed)

    def test_public_class_is_not_routed_through_private_access(self):
        decision = decide_private_access(
            self._request(data_class=DataClass.PUBLIC_CORE)
        )
        self.assertEqual(decision.outcome, PrivateAccessOutcome.DENY)
        self.assertIn("NOT_A_PRIVATE_DATA_CLASS", decision.reasons)

    def test_non_read_modes_are_never_authorized(self):
        for mode in (
            PrivateAccessMode.LOG,
            PrivateAccessMode.EXPORT,
            PrivateAccessMode.MUTATE,
            PrivateAccessMode.DELETE,
        ):
            with self.subTest(mode=mode):
                decision = decide_private_access(self._request(mode=mode))
                self.assertEqual(decision.outcome, PrivateAccessOutcome.DENY)
                self.assertIn("PRIVATE_ACCESS_IS_READ_ONLY", decision.reasons)

    def test_sensitive_classes_require_bounded_review_or_incident_purpose(self):
        denied = decide_private_access(
            self._request(
                actor_ref="operator-1",
                role=PrivateAccessRole.OPERATOR,
                purpose=PrivateAccessPurpose.OPERATIONS,
                data_class=DataClass.SENSITIVE_CANDIDATE,
            )
        )
        self.assertEqual(denied.outcome, PrivateAccessOutcome.DENY)
        self.assertIn("SENSITIVE_REVIEW_PURPOSE_REQUIRED", denied.reasons)

        allowed = decide_private_access(
            self._request(
                data_class=DataClass.HIGH_RISK_IDENTITY,
                purpose=PrivateAccessPurpose.RIGHTS_REQUEST,
            )
        )
        self.assertTrue(allowed.allowed)
        self.assertNotIn("minor", " ".join(allowed.reasons).lower())
        self.assertNotIn("victim", " ".join(allowed.reasons).lower())

    def test_legal_hold_never_relaxes_read_only_boundary(self):
        read = decide_private_access(self._request(legal_hold_active=True))
        self.assertTrue(read.allowed)
        self.assertIn("LEGAL_HOLD_PRESERVED_READ_ONLY", read.reasons)

        delete = decide_private_access(
            self._request(
                legal_hold_active=True,
                mode=PrivateAccessMode.DELETE,
            )
        )
        self.assertFalse(delete.allowed)
        self.assertIn("PRIVATE_ACCESS_IS_READ_ONLY", delete.reasons)

    def test_audit_receipt_contains_identifiers_and_counts_never_private_fields(self):
        request = self._request(
            requested_fields=("PRIVATE_BODY_SENTINEL", "raw_text", "email_address"),
            legal_hold_active=True,
        )
        decision = decide_private_access(request)
        receipt = build_private_access_audit(
            request,
            decision,
            record_ref="capture:123",
            occurred_at="2026-10-05T23:10:00+02:00",
        )
        payload = asdict(receipt)
        rendered = repr(payload)
        self.assertEqual(
            set(payload),
            {
                "policy_version",
                "actor_ref",
                "record_ref",
                "purpose",
                "outcome",
                "occurred_at",
                "requested_field_count",
                "legal_hold_active",
            },
        )
        self.assertEqual(payload["requested_field_count"], 3)
        for private_value in request.requested_fields:
            self.assertNotIn(private_value, rendered)

    def test_audit_redacts_identifier_shaped_private_contact(self):
        request = self._request(actor_ref="private@example.test")
        decision = decide_private_access(request)
        receipt = build_private_access_audit(
            request,
            decision,
            record_ref="private@example.test",
            occurred_at="2026-10-05T23:10:00+02:00",
        )
        self.assertEqual(receipt.actor_ref, "REDACTED_IDENTIFIER")
        self.assertEqual(receipt.record_ref, "REDACTED_IDENTIFIER")
        self.assertEqual(decision.outcome, PrivateAccessOutcome.DENY)

    def test_audit_rejects_non_timestamp_text_in_timestamp_slot(self):
        request = self._request()
        receipt = build_private_access_audit(
            request,
            decide_private_access(request),
            record_ref="capture:123",
            occurred_at="PRIVATE_BODY_SENTINEL",
        )
        self.assertEqual(receipt.occurred_at, "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
