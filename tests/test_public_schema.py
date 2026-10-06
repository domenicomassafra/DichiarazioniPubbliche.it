from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    ClaimType,
    FindingPublicationStatus,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    DOSSIER_REQUIRED_KEYS,
    PUBLIC_SCHEMA_VERSION,
    PUBLISHABLE_ASSESSMENTS,
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_content,
    validate_dossier,
    validate_public_bundle,
)


def valid_dossier() -> dict:
    return {
        "finding_id": "finding:100",
        "claim_id": "claim:200",
        "claim": "L'aliquota media è pari al 15%.",
        "claim_type": ClaimType.NUMERIC_STATISTIC.value,
        "claim_contract": {
            "version": 1,
            "temporal_scope": {"statement_date": "2026-09-20"},
            "check_worthy": True,
            "speaker_approval_required": True,
            "source_segment_ids": ["segment:s1"],
        },
        "speaker": {
            "id": "person:p1",
            "name": "Nome Cognome",
            "public_role": "Senatore",
            "public_roles": [
                {
                    "organization_id": "org:senato",
                    "organization_name": "Senato della Repubblica",
                    "role": "Senatore",
                    "start_date": "2022-10-13",
                    "end_date": None,
                    "review_event_ids": ["review:role1"],
                }
            ],
            "provenance": [
                {
                    "candidate_id": "speaker-candidate:c1",
                    "review_event_ids": ["review:sp1"],
                }
            ],
        },
        "source": {
            "content_id": "content:c1",
            "url": "https://example.test/source",
            "title": "Intervista TV",
            "published_at": "2026-09-20T10:00:00+00:00",
            "segments": [
                {
                    "segment_id": "segment:s1",
                    "segment_index": 0,
                    "start_ms": 1000,
                    "end_ms": 5000,
                    "transcript_candidates": [
                        {
                            "segment_id": "seg:raw1",
                            "variant_id": "var:v1",
                            "provider_id": "local",
                            "source_kind": "OFFICIAL",
                            "transcript_sha256": "0" * 64,
                        }
                    ],
                }
            ],
        },
        "finding": {
            "assessment": VerificationAssessment.SUPPORTED.value,
            "publication_status": FindingPublicationStatus.PUBLISH.value,
            "rationale": "Dati confermati dai documenti ufficiali del MEF.",
            "policy_version": "policy-v1",
            "verification_run_id": "run:vr1",
            "created_at": "2026-09-21T09:00:00+00:00",
            "published_at": "2026-09-21T09:30:00+00:00",
            "publication_review_ids": ["review:pub1"],
            "supersedes_id": None,
        },
        "evidence": [
            {
                "id": "evidence:e1",
                "url": "https://example.test/mef-report",
                "publisher": "Ministero dell'Economia e delle Finanze",
                "source_type": "PRIMARY_OFFICIAL",
                "publication_date": "2026-09-15",
                "observed_at": "2026-09-21T08:00:00+00:00",
                "content_sha256": "1" * 64,
                "reference_period": "2026",
                "rights_status": "PUBLIC_DOMAIN",
                "relation": "SUPPORTING",
                "verification_observation_ids": ["obs:o1"],
                "evidence_review_ids": ["review:ev1"],
                "observation_review_ids": ["review:obs1"],
            }
        ],
        "corrections": [],
        "rights_of_reply": [],
    }


def valid_bundle() -> dict:
    dossier = valid_dossier()
    return {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "generated_at": "2026-09-26T12:00:00+00:00",
        "dataset_sha256": "2" * 64,
        "methodology": {
            "claim_level_only": True,
            "aggregate_person_score": False,
            "requires_publication_gate": True,
            "requires_approved_evidence": True,
            "requires_resolved_transcript": True,
        },
        "dossier_count": 1,
        "omitted_count": 0,
        "dossiers": [dossier],
    }


def valid_wording(*, source_type: str = "VERBATIM_ORIGINAL") -> dict:
    claim = valid_dossier()["claim"]
    assert isinstance(claim, str)
    return {
        "version": "wording-contract-v1",
        "source_occurrence": {
            "occurrence_id": "statement:s1",
            "wording_type": source_type,
            "text_sha256": "a" * 64,
            "language": "it",
            "direct_quote_eligible": source_type == "VERBATIM_ORIGINAL",
            "representation_role": "SOURCE_OCCURRENCE",
        },
        "normalized_claim": {
            "wording_type": "PARAPHRASE",
            "text_sha256": hashlib.sha256(claim.encode("utf-8")).hexdigest(),
            "source_occurrence_id": "statement:s1",
            "source_wording_type": source_type,
            "language": "it",
            "derivation_method": "CLAIM_NORMALIZATION",
            "derivation_version": "test-v1",
            "direct_quote_eligible": False,
            "representation_role": "DERIVED_REPRESENTATION",
        },
        "representations": [
            {
                "wording_type": "TRANSLATION",
                "text_sha256": "b" * 64,
                "source_occurrence_id": "statement:s1",
                "source_wording_type": source_type,
                "language": "en",
                "source_language": "it",
                "derivation_method": "TRANSLATION_HUMAN",
                "derivation_version": "test-v1",
                "review_state": "HUMAN_REVIEWED",
                "signal_codes": [],
                "direct_quote_eligible": False,
                "representation_role": "DERIVED_REPRESENTATION",
            }
        ],
        "public_provenance": {
            "segment_ids": ["segment:s1"],
            "text_provenance_ids": [],
        },
    }


def valid_content() -> dict:
    return {
        "content_id": "content:c1",
        "slug": "content-c1",
        "url": "https://example.test/source",
        "title": "Intervista TV",
        "published_at": "2026-09-20T10:00:00+00:00",
        "content_kind": "VIDEO",
        "duration_ms": 120000,
        "public_media_url": None,
        "media_policy_version": None,
        "publication_version": "public-content-v1",
        "review_event_ids": ["review:content-c1"],
        "finding_ids": ["finding:100"],
    }


class PublicSchemaContractTests(unittest.TestCase):
    def test_schema_version_is_unchanged(self):
        self.assertEqual(PUBLIC_SCHEMA_VERSION, "dichiarazioni-pubbliche-public-v2")

    def test_valid_dossier_passes(self):
        dossier = valid_dossier()
        result = validate_dossier(dossier)
        self.assertIs(result, dossier)

    def test_additive_wording_metadata_preserves_legacy_public_v2(self):
        legacy = valid_dossier()
        self.assertIs(validate_dossier(legacy), legacy)

        current = valid_dossier()
        current["wording"] = valid_wording()
        self.assertIs(validate_dossier(current), current)
        self.assertEqual(PUBLIC_SCHEMA_VERSION, "dichiarazioni-pubbliche-public-v2")

    def test_reported_source_is_distinct_and_never_direct_quote_eligible(self):
        dossier = valid_dossier()
        dossier["wording"] = valid_wording(source_type="REPORTED_QUOTE")
        self.assertIs(validate_dossier(dossier), dossier)
        dossier["wording"]["source_occurrence"]["direct_quote_eligible"] = True
        with self.assertRaisesRegex(
            PublicSchemaValidationError,
            "direct-quote authority",
        ):
            validate_dossier(dossier)

    def test_derived_representation_cannot_become_direct_quote(self):
        dossier = valid_dossier()
        dossier["wording"] = valid_wording()
        dossier["wording"]["representations"][0]["direct_quote_eligible"] = True
        with self.assertRaisesRegex(
            PublicSchemaValidationError,
            "derived wording cannot be direct-quote eligible",
        ):
            validate_dossier(dossier)

    def test_translation_requires_original_language_and_review_state(self):
        for key, value in (
            ("source_language", "fr"),
            ("review_state", None),
        ):
            with self.subTest(key=key):
                dossier = valid_dossier()
                dossier["wording"] = valid_wording()
                dossier["wording"]["representations"][0][key] = value
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(dossier)

    def test_wording_contract_rejects_raw_or_private_text_fields(self):
        dossier = valid_dossier()
        dossier["wording"] = valid_wording()
        dossier["wording"]["representations"][0]["text"] = "private translation"
        with self.assertRaisesRegex(PublicSchemaValidationError, "unknown wording"):
            validate_dossier(dossier)

    def test_wording_public_provenance_must_match_source(self):
        dossier = valid_dossier()
        dossier["wording"] = valid_wording()
        dossier["wording"]["public_provenance"]["segment_ids"] = ["segment:other"]
        with self.assertRaisesRegex(
            PublicSchemaValidationError,
            "does not match public source provenance",
        ):
            validate_dossier(dossier)

    def test_claim_field_may_be_none_or_absent(self):
        dossier_none = valid_dossier()
        dossier_none["claim"] = None
        self.assertIs(validate_dossier(dossier_none), dossier_none)

        dossier_absent = valid_dossier()
        del dossier_absent["claim"]
        self.assertIs(validate_dossier(dossier_absent), dossier_absent)

    def test_empty_lists_for_public_roles_corrections_and_replies_pass(self):
        dossier = valid_dossier()
        dossier["speaker"]["public_roles"] = []
        dossier["corrections"] = []
        dossier["rights_of_reply"] = []
        self.assertIs(validate_dossier(dossier), dossier)

    def test_missing_required_key_fails(self):
        for key in DOSSIER_REQUIRED_KEYS:
            with self.subTest(key=key):
                d = valid_dossier()
                del d[key]
                with self.assertRaises(PublicSchemaValidationError) as ctx:
                    validate_dossier(d)
                self.assertIn("missing required key", str(ctx.exception))

            with self.subTest(key_none=key):
                d = valid_dossier()
                d[key] = None
                with self.assertRaises(PublicSchemaValidationError) as ctx:
                    validate_dossier(d)
                self.assertIn("missing required key", str(ctx.exception))

    def test_unknown_top_level_key_fails(self):
        d = valid_dossier()
        d["unexpected_key"] = "forbidden"
        with self.assertRaises(PublicSchemaValidationError) as ctx:
            validate_dossier(d)
        self.assertIn("unknown top-level key", str(ctx.exception))
        self.assertIn("unexpected_key", str(ctx.exception))

    def test_numeric_rating_fields_rejected(self):
        forbidden_fields = [
            "ratingValue",
            "bestRating",
            "worstRating",
            "reviewRating",
            "numericRating",
            "rating_value",
            "best_rating",
            "worst_rating",
        ]
        for field in forbidden_fields:
            with self.subTest(field_in_finding=field):
                d = valid_dossier()
                d["finding"][field] = 5
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(d)

            with self.subTest(field_in_changed_fields=field):
                d = valid_dossier()
                d["corrections"].append(
                    {
                        "id": "c1",
                        "finding_id": "f1",
                        "previous_finding_id": "f0",
                        "reason": "Update",
                        "changed_fields": {field: 5},
                        "created_at": "2026-09-21T10:00:00+00:00",
                    }
                )
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(d)

    def test_person_aggregate_and_scoring_rejected(self):
        forbidden_scoring = [
            ("reliability_score", 85),
            ("person_score", 90),
            ("aggregate_score", 70),
            ("truth_score", 60),
            ("political_score", 50),
            ("person_ranking", 1),
            ("leaderboard", ["p1", "p2"]),
            ("score", 100),
            ("ranking", 3),
        ]
        for key, val in forbidden_scoring:
            with self.subTest(speaker_key=key):
                d = valid_dossier()
                d["speaker"][key] = val
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(d)

            with self.subTest(nested_changed_fields=key):
                d = valid_dossier()
                d["corrections"].append(
                    {
                        "id": "c1",
                        "finding_id": "f1",
                        "previous_finding_id": "f0",
                        "reason": "Update",
                        "changed_fields": {key: val},
                        "created_at": "2026-09-21T10:00:00+00:00",
                    }
                )
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(d)

    def test_private_identity_resolution_material_is_rejected(self):
        forbidden_identity = [
            ("public_attribution_input", {"private": True}),
            ("retrieval_score", 0.99),
            ("supporting_features", [{"code": "KNOWN_ALIAS", "value": "private"}]),
            ("contradicting_features", [{"code": "DATE_CONFLICT"}]),
            ("speaker_label", "PRIVATE_ALIAS"),
            ("identifier_value", "PRIVATE-ID"),
            ("mention_text", "Private mention"),
            ("resolution_method", "MANUAL_REVIEW"),
            ("resolution_version", "entity-resolution-v1"),
            ("confidence", 0.99),
            ("aliases", ["private alias"]),
        ]
        for key, value in forbidden_identity:
            with self.subTest(speaker_key=key):
                dossier = valid_dossier()
                dossier["speaker"][key] = value
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(dossier)

            with self.subTest(nested_changed_fields=key):
                dossier = valid_dossier()
                dossier["corrections"].append(
                    {
                        "id": "c-private-identity",
                        "finding_id": "f1",
                        "previous_finding_id": "f0",
                        "reason": "Update",
                        "changed_fields": {key: value},
                        "created_at": "2026-09-21T10:00:00+00:00",
                    }
                )
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(dossier)

    def test_non_publishable_assessment_rejected(self):
        non_publishable = [
            VerificationAssessment.INSUFFICIENT_EVIDENCE.value,
            VerificationAssessment.UNRESOLVED.value,
            "RANDOM_ASSESSMENT",
        ]
        for assessment in non_publishable:
            with self.subTest(assessment=assessment):
                d = valid_dossier()
                d["finding"]["assessment"] = assessment
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(d)

    def test_publishable_assessments_pass(self):
        for assessment in PUBLISHABLE_ASSESSMENTS:
            with self.subTest(assessment=assessment):
                d = valid_dossier()
                d["finding"]["assessment"] = assessment.value
                self.assertIs(validate_dossier(d), d)

    def test_unknown_claim_type_rejected(self):
        d = valid_dossier()
        d["claim_type"] = "INVENTED_CLAIM_TYPE"
        with self.assertRaises(PublicSchemaValidationError) as ctx:
            validate_dossier(d)
        self.assertIn("claim_type", str(ctx.exception))

    def test_non_public_finding_publication_status_rejected(self):
        non_public_statuses = [
            FindingPublicationStatus.INTERNAL_CANDIDATE.value,
            FindingPublicationStatus.POLICY_HOLD.value,
            FindingPublicationStatus.NO_FINDING.value,
            FindingPublicationStatus.NEEDS_MORE_EVIDENCE.value,
            "DRAFT",
        ]
        for status in non_public_statuses:
            with self.subTest(status=status):
                d = valid_dossier()
                d["finding"]["publication_status"] = status
                with self.assertRaises(PublicSchemaValidationError):
                    validate_dossier(d)

    def test_validate_public_bundle_passes(self):
        bundle = valid_bundle()
        result = validate_public_bundle(bundle)
        self.assertIs(result, bundle)

    def test_public_content_can_have_zero_findings(self):
        content = valid_content()
        content["finding_ids"] = []
        self.assertIs(validate_content(content), content)

    def test_public_content_media_metadata_is_fail_closed(self):
        content = valid_content()
        content["public_media_url"] = "https://media.example.test/embed/1"
        with self.assertRaises(PublicSchemaValidationError):
            validate_content(content)

        content["media_policy_version"] = "public-media-v1"
        self.assertIs(validate_content(content), content)

        written = valid_content()
        written["content_kind"] = "WRITTEN"
        written["duration_ms"] = None
        written["public_media_url"] = "https://media.example.test/embed/1"
        written["media_policy_version"] = "public-media-v1"
        with self.assertRaises(PublicSchemaValidationError):
            validate_content(written)

    def test_bundle_accepts_legacy_without_contents_and_validates_new_contents(self):
        legacy = valid_bundle()
        self.assertIs(validate_public_bundle(legacy), legacy)

        current = valid_bundle()
        current["contents"] = [valid_content()]
        current["dataset_sha256"] = projection_dataset_sha256(current)
        self.assertIs(validate_public_bundle(current), current)

    def test_content_cannot_reference_private_or_other_content_finding(self):
        bundle = valid_bundle()
        content = valid_content()
        content["finding_ids"] = ["finding:private"]
        bundle["contents"] = [content]
        with self.assertRaisesRegex(PublicSchemaValidationError, "non-public finding"):
            validate_public_bundle(bundle)

        other = valid_dossier()
        other["finding_id"] = "finding:other"
        other["claim_id"] = "claim:other"
        other["source"]["content_id"] = "content:other"
        bundle = valid_bundle()
        bundle["dossiers"].append(other)
        bundle["dossier_count"] = 2
        content = valid_content()
        content["finding_ids"] = ["finding:other"]
        bundle["contents"] = [content]
        with self.assertRaisesRegex(PublicSchemaValidationError, "different source content_id"):
            validate_public_bundle(bundle)

    def test_content_bundle_fingerprint_detects_tampering(self):
        bundle = valid_bundle()
        bundle["contents"] = [valid_content()]
        bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
        self.assertIs(validate_public_bundle(bundle), bundle)
        bundle["contents"][0]["title"] = "Titolo alterato dopo la proiezione"
        with self.assertRaisesRegex(PublicSchemaValidationError, "dataset_sha256"):
            validate_public_bundle(bundle)

    def test_validate_public_bundle_rejects_person_aggregate(self):
        bundle = valid_bundle()
        bundle["methodology"]["aggregate_person_score"] = True
        with self.assertRaises(PublicSchemaValidationError):
            validate_public_bundle(bundle)

    def test_validate_public_bundle_rejects_unknown_bundle_key(self):
        bundle = valid_bundle()
        bundle["unexpected"] = "payload"
        with self.assertRaises(PublicSchemaValidationError):
            validate_public_bundle(bundle)

    def test_validate_public_bundle_rejects_count_mismatch(self):
        bundle = valid_bundle()
        bundle["dossier_count"] = 5
        with self.assertRaises(PublicSchemaValidationError):
            validate_public_bundle(bundle)

    def test_validate_public_bundle_rejects_wrong_schema_version(self):
        bundle = valid_bundle()
        bundle["schema_version"] = "dichiarazioni-pubbliche-public-v999"
        with self.assertRaises(PublicSchemaValidationError):
            validate_public_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
