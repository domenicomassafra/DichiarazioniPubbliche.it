import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.knowledge_repository import (  # noqa: E402
    EntityIdentifierRecord,
    make_resolution_candidate,
)
from dichiarazioni_pubbliche.public_attribution import (  # noqa: E402
    PUBLIC_ATTRIBUTION_VERSION,
    RoleInterval,
    evaluate_public_attribution,
)
from dichiarazioni_pubbliche.speaker_runtime import make_speaker_candidate  # noqa: E402


def approved_resolution(person_id="person:a", *, contradictions=(), identifier_ids=()):
    support = [{"code": "IDENTIFIER_ID", "value": value} for value in identifier_ids]
    row = make_resolution_candidate(
        content_id="content:a",
        passage_id="passage:a",
        mention_text="Mario Rossi",
        entity_type="PERSON",
        target_id=person_id,
        resolution_method="MANUAL_REVIEW",
        supporting_features=support,
        contradicting_features=contradictions,
    )
    return row.__class__(**{**row.__dict__, "status": "APPROVED"})


def speaker(person_id="person:a", *, method="MANUAL_REVIEW", source_ref=None):
    return make_speaker_candidate(
        content_id="content:a",
        person_id=person_id,
        start_ms=0,
        end_ms=5000,
        attribution_method=method,
        source_ref=source_ref,
    )


def active_role(*, end_date=None, interval_id="role:a", person_id="person:a"):
    return RoleInterval(
        interval_id=interval_id,
        person_id=person_id,
        organization_id="org:camera",
        role="Deputato",
        start_date=date(2025, 1, 1),
        end_date=end_date,
        status="ACTIVE",
        review_event_ids=("review:role",),
        source_ref={"url": "https://example.test/role"},
    )


def decision(**overrides):
    kwargs = dict(
        person_id="person:a",
        content_id="content:a",
        occurrence_start_ms=1000,
        occurrence_end_ms=2000,
        statement_date=date(2026, 5, 1),
        speaker_candidate=speaker(),
        resolution_candidates=(approved_resolution(),),
        identifiers=(),
        role_intervals=(active_role(),),
        requested_role_interval_id="role:a",
    )
    kwargs.update(overrides)
    return evaluate_public_attribution(**kwargs)


class PublicAttributionTests(unittest.TestCase):
    def test_identity_and_role_at_time_are_independently_approved(self):
        result = decision()
        self.assertTrue(result.publication_allowed)
        self.assertEqual(result.version, PUBLIC_ATTRIBUTION_VERSION)
        self.assertEqual(result.person_id, "person:a")
        self.assertEqual(result.public_role, "Deputato")
        self.assertEqual(result.attribution_scope, "SPEAKER_WITH_ROLE")

    def test_stale_role_is_omitted_without_changing_stable_person(self):
        result = decision(
            role_intervals=(active_role(end_date=date(2026, 1, 1)),),
        )
        self.assertTrue(result.publication_allowed)
        self.assertEqual(result.person_id, "person:a")
        self.assertIsNone(result.public_role)
        self.assertIn("ROLE_AT_STATEMENT_TIME_UNPROVEN", result.reason_codes)

    def test_same_name_different_people_never_share_public_occurrence_proof(self):
        result = decision(
            resolution_candidates=(
                approved_resolution("person:a"),
                approved_resolution("person:b"),
            )
        )
        self.assertFalse(result.publication_allowed)
        self.assertIn("IDENTITY_RESOLUTION_AMBIGUOUS", result.reason_codes)

    def test_direct_person_link_tamper_fails_matching_provenance(self):
        result = decision(person_id="person:b")
        self.assertFalse(result.publication_allowed)
        self.assertIn("SPEAKER_PERSON_MISMATCH", result.reason_codes)

    def test_contradicting_identity_features_hold_instead_of_highest_score_selection(self):
        result = decision(
            resolution_candidates=(
                approved_resolution(
                    contradictions=({"code": "DATE_ROLE_CONFLICT", "value": "2024"},)
                ),
            )
        )
        self.assertFalse(result.publication_allowed)
        self.assertIn(
            "IDENTITY_CONTRADICTING_FEATURES_REQUIRE_REVIEW",
            result.reason_codes,
        )

    def test_superseded_identifier_invalidates_resolution_link(self):
        identifier = EntityIdentifierRecord(
            id="identifier:person-a",
            entity_type="PERSON",
            entity_id="person:a",
            identifier_kind="OFFICIAL_PERSON_ID",
            identifier_value="A-1",
            authority="OFFICIAL_REGISTER",
            source_ref={"url": "https://example.test/person/a"},
            status="SUPERSEDED",
        )
        result = decision(
            resolution_candidates=(
                approved_resolution(identifier_ids=(identifier.id,)),
            ),
            identifiers=(identifier,),
        )
        self.assertFalse(result.publication_allowed)
        self.assertIn("IDENTITY_IDENTIFIER_SUPERSEDED", result.reason_codes)

    def test_account_ownership_is_authorship_only_and_never_embedded_speaker_identity(self):
        platform = speaker(
            method="PLATFORM_CREDIT",
            source_ref={
                "account_owner_person_id": "person:a",
                "account_content_id": "content:a",
                "authorship_scope": "SOURCE_AUTHORSHIP",
            },
        )
        authorship = decision(
            speaker_candidate=platform,
            resolution_candidates=(),
            role_intervals=(),
            requested_role_interval_id=None,
            occurrence_kind="AUTHORSHIP",
        )
        self.assertTrue(authorship.publication_allowed)
        self.assertEqual(authorship.attribution_scope, "AUTHORSHIP_ONLY")

        embedded = decision(
            speaker_candidate=platform,
            resolution_candidates=(),
            role_intervals=(),
            requested_role_interval_id=None,
            occurrence_kind="EMBEDDED_THIRD_PARTY",
        )
        self.assertFalse(embedded.publication_allowed)
        self.assertIn("ACCOUNT_CREDIT_NOT_SPEAKER_IDENTITY", embedded.reason_codes)

    def test_weak_metadata_method_cannot_publish_speaker_identity(self):
        result = decision(speaker_candidate=speaker(method="SOURCE_METADATA"))
        self.assertFalse(result.publication_allowed)
        self.assertIn("SPEAKER_METHOD_NOT_PUBLICATION_CAPABLE", result.reason_codes)

    def test_speaker_proof_must_cover_exact_occurrence(self):
        short = make_speaker_candidate(
            content_id="content:a",
            person_id="person:a",
            start_ms=1200,
            end_ms=1800,
            attribution_method="MANUAL_REVIEW",
        )
        result = decision(speaker_candidate=short)
        self.assertFalse(result.publication_allowed)
        self.assertIn("SPEAKER_PROOF_DOES_NOT_COVER_OCCURRENCE", result.reason_codes)

    def test_multi_speaker_boundaries_do_not_inherit_guest_identity(self):
        guest = make_speaker_candidate(
            content_id="content:a",
            person_id="person:a",
            start_ms=1000,
            end_ms=2000,
            attribution_method="MANUAL_REVIEW",
        )
        allowed = decision(
            occurrence_start_ms=1200,
            occurrence_end_ms=1800,
            speaker_candidate=guest,
        )
        self.assertTrue(allowed.publication_allowed)

        host_turn = decision(
            occurrence_start_ms=2000,
            occurrence_end_ms=2600,
            speaker_candidate=guest,
        )
        self.assertFalse(host_turn.publication_allowed)
        self.assertIn("SPEAKER_PROOF_DOES_NOT_COVER_OCCURRENCE", host_turn.reason_codes)

        voice_over = decision(
            occurrence_start_ms=500,
            occurrence_end_ms=1300,
            speaker_candidate=guest,
        )
        self.assertFalse(voice_over.publication_allowed)
        self.assertIn("SPEAKER_PROOF_DOES_NOT_COVER_OCCURRENCE", voice_over.reason_codes)

    def test_embedded_clip_requires_its_own_content_and_person_proof(self):
        surrounding_guest = speaker("person:a")
        embedded_wrong_content = decision(
            content_id="content:embedded",
            person_id="person:b",
            occurrence_start_ms=1000,
            occurrence_end_ms=2000,
            speaker_candidate=surrounding_guest,
            resolution_candidates=(),
            role_intervals=(),
            requested_role_interval_id=None,
        )
        self.assertFalse(embedded_wrong_content.publication_allowed)
        self.assertIn("SPEAKER_CONTENT_MISMATCH", embedded_wrong_content.reason_codes)

        embedded_clip = make_speaker_candidate(
            content_id="content:embedded",
            person_id="person:b",
            start_ms=900,
            end_ms=2100,
            attribution_method="MANUAL_REVIEW",
        )
        embedded_resolution = make_resolution_candidate(
            content_id="content:embedded",
            passage_id="passage:embedded",
            mention_text="Mario Rossi",
            entity_type="PERSON",
            target_id="person:b",
            resolution_method="MANUAL_REVIEW",
            supporting_features=(),
            contradicting_features=(),
        )
        embedded_resolution = embedded_resolution.__class__(
            **{**embedded_resolution.__dict__, "status": "APPROVED"}
        )
        allowed = evaluate_public_attribution(
            person_id="person:b",
            content_id="content:embedded",
            occurrence_start_ms=1000,
            occurrence_end_ms=2000,
            statement_date=date(2026, 5, 1),
            speaker_candidate=embedded_clip,
            resolution_candidates=(embedded_resolution,),
            role_intervals=(),
        )
        self.assertTrue(allowed.publication_allowed)
        self.assertEqual(allowed.person_id, "person:b")


if __name__ == "__main__":
    unittest.main()
