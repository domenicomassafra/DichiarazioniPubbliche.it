from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claimreview_interop import (  # noqa: E402
    ClaimReviewInteropError,
    build_claimreview_interop,
)
from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    FINDING_PUBLICATION_STATUS_VERSION,
    VERIFICATION_ASSESSMENT_VERSION,
    VerificationAssessment,
)


def validated_public_dossier() -> dict:
    return {
        "finding_id": "finding:100",
        "claim_id": "claim:200",
        "claim": "L'aliquota media è pari al 15%.",
        "claim_type": "NUMERIC_STATISTIC",
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
            "public_roles": [],
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
            "segments": [],
        },
        "finding": {
            "assessment": "SUPPORTED",
            "publication_status": "PUBLISH",
            "rationale": "Dati confermati dai documenti ufficiali.",
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
                "url": "https://example.test/report",
                "publisher": "Ministero dell'Economia",
                "publication_date": "2026-09-15",
                "evidence_review_ids": ["review:ev1"],
                "observation_review_ids": ["review:obs1"],
            }
        ],
        "corrections": [],
        "rights_of_reply": [],
    }


class ClaimReviewInteropTests(unittest.TestCase):
    def test_public_dossier_maps_to_claimreview_without_changing_vocabulary(self):
        dossier = validated_public_dossier()
        original = copy.deepcopy(dossier)
        record = build_claimreview_interop(dossier)

        self.assertEqual(dossier, original)
        self.assertEqual(record.finding_id, "finding:100")
        self.assertEqual(record.claim_id, "claim:200")
        self.assertEqual(record.assessment, "SUPPORTED")
        self.assertEqual(record.assessment_version, VERIFICATION_ASSESSMENT_VERSION)
        self.assertEqual(record.publication_status, "PUBLISH")
        self.assertEqual(
            record.publication_status_version,
            FINDING_PUBLICATION_STATUS_VERSION,
        )
        self.assertEqual(record.claimreview["@type"], "ClaimReview")
        self.assertEqual(record.claimreview["identifier"], "finding:100")
        self.assertEqual(record.claimreview["claimReviewed"], dossier["claim"])
        self.assertEqual(
            record.claimreview["reviewRating"],
            {"@type": "Rating", "alternateName": "SUPPORTED"},
        )
        properties = {
            row["name"]: row["value"]
            for row in record.claimreview["additionalProperty"]
        }
        self.assertEqual(properties["findingId"], "finding:100")
        self.assertEqual(properties["assessment"], "SUPPORTED")
        self.assertEqual(
            properties["assessmentVocabularyVersion"],
            VERIFICATION_ASSESSMENT_VERSION,
        )
        self.assertEqual(
            properties["publicationStatusVocabularyVersion"],
            FINDING_PUBLICATION_STATUS_VERSION,
        )
        self.assertFalse(record.publication_authority)

    def test_every_publishable_assessment_is_preserved_exactly_not_remapped(self):
        for assessment in (
            VerificationAssessment.SUPPORTED.value,
            VerificationAssessment.FACTUALLY_FALSE.value,
            VerificationAssessment.OUTDATED_DATA.value,
        ):
            with self.subTest(assessment=assessment):
                dossier = validated_public_dossier()
                dossier["finding"]["assessment"] = assessment
                record = build_claimreview_interop(dossier)
                self.assertEqual(record.assessment, assessment)
                self.assertEqual(
                    record.claimreview["reviewRating"]["alternateName"],
                    assessment,
                )

    def test_finding_version_lineage_is_preserved_exactly(self):
        dossier = validated_public_dossier()
        dossier["finding_id"] = "finding:version:2"
        dossier["finding"]["supersedes_id"] = "finding:version:1"
        dossier["finding"]["policy_version"] = "policy-v9"
        dossier["finding"]["verification_run_id"] = "verification:exact:9"
        record = build_claimreview_interop(dossier)

        self.assertEqual(record.finding_id, "finding:version:2")
        self.assertEqual(record.supersedes_id, "finding:version:1")
        self.assertEqual(record.policy_version, "policy-v9")
        self.assertEqual(record.verification_run_id, "verification:exact:9")
        properties = {
            row["name"]: row["value"]
            for row in record.claimreview["additionalProperty"]
        }
        self.assertEqual(properties["findingId"], "finding:version:2")
        self.assertEqual(properties["supersedesFindingId"], "finding:version:1")
        self.assertEqual(properties["policyVersion"], "policy-v9")
        self.assertEqual(properties["verificationRunId"], "verification:exact:9")

    def test_held_private_or_unapproved_inputs_fail_closed(self):
        for status in (
            "POLICY_HOLD",
            "INTERNAL_CANDIDATE",
            "NEEDS_MORE_EVIDENCE",
            "DISPUTED",
            "RETRACTED",
        ):
            with self.subTest(status=status):
                dossier = validated_public_dossier()
                dossier["finding"]["publication_status"] = status
                with self.assertRaisesRegex(
                    ClaimReviewInteropError,
                    "FINDING_NOT_PUBLISHED",
                ):
                    build_claimreview_interop(dossier)

        unreviewed = validated_public_dossier()
        unreviewed["finding"]["publication_review_ids"] = []
        with self.assertRaisesRegex(
            ClaimReviewInteropError,
            "PUBLICATION_REVIEW_REQUIRED",
        ):
            build_claimreview_interop(unreviewed)

        private = validated_public_dossier()
        private["raw_text"] = "private transcript body"
        with self.assertRaisesRegex(ClaimReviewInteropError, "PRIVATE_FIELD_PRESENT"):
            build_claimreview_interop(private)

        private_evidence = validated_public_dossier()
        private_evidence["evidence"][0]["excerpt"] = "private evidence body"
        private_evidence["evidence"][0]["evidence_body"] = "raw"
        with self.assertRaisesRegex(ClaimReviewInteropError, "PRIVATE_FIELD_PRESENT"):
            build_claimreview_interop(private_evidence)

    def test_unresolved_or_noncanonical_assessment_cannot_be_exported(self):
        unresolved = validated_public_dossier()
        unresolved["finding"]["assessment"] = "UNRESOLVED"
        with self.assertRaisesRegex(
            ClaimReviewInteropError,
            "ASSESSMENT_NOT_PUBLISHABLE",
        ):
            build_claimreview_interop(unresolved)

        invented = validated_public_dossier()
        invented["finding"]["assessment"] = "MOSTLY_TRUE"
        with self.assertRaisesRegex(
            ClaimReviewInteropError,
            "ASSESSMENT_NON_CANONICAL",
        ):
            build_claimreview_interop(invented)

    def test_no_person_score_numeric_rating_or_intent_is_created(self):
        record = build_claimreview_interop(validated_public_dossier())
        payload = record.claimreview
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        for forbidden in (
            "ratingValue",
            "bestRating",
            "worstRating",
            "trust_score",
            "reliability_score",
            "credibility_score",
            "intent",
            "lied",
            "liar",
            "bugiardo",
        ):
            self.assertNotIn(forbidden, encoded)
        person = payload["itemReviewed"]["author"]
        self.assertEqual(person["@type"], "Person")
        self.assertEqual(set(person), {"@type", "identifier", "name"})
        self.assertEqual(
            set(payload["reviewRating"]),
            {"@type", "alternateName"},
        )

    def test_unapproved_evidence_or_reply_is_rejected(self):
        unreviewed_evidence = validated_public_dossier()
        unreviewed_evidence["evidence"][0]["evidence_review_ids"] = []
        with self.assertRaisesRegex(
            ClaimReviewInteropError,
            "EVIDENCE_REVIEW_REQUIRED",
        ):
            build_claimreview_interop(unreviewed_evidence)

        private_reply = validated_public_dossier()
        private_reply["rights_of_reply"] = [
            {"id": "reply:1", "status": "PENDING", "body": "private"}
        ]
        with self.assertRaises(ClaimReviewInteropError):
            build_claimreview_interop(private_reply)


if __name__ == "__main__":
    unittest.main()
