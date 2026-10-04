from __future__ import annotations

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


class PublicSchemaContractTests(unittest.TestCase):
    def test_schema_version_is_unchanged(self):
        self.assertEqual(PUBLIC_SCHEMA_VERSION, "dichiarazioni-pubbliche-public-v2")

    def test_valid_dossier_passes(self):
        dossier = valid_dossier()
        result = validate_dossier(dossier)
        self.assertIs(result, dossier)

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
