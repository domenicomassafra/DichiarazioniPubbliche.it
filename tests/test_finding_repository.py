import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    FINDING_PUBLICATION_STATUS_VERSION,
    VERIFICATION_ASSESSMENT_VERSION,
    FindingPublicationStatus,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.finding_repository import (  # noqa: E402
    INSERT_FINDING_DRAFT_SQL_V1,
    FindingRecord,
    finding_record_to_sql_parameters,
    normalize_finding_record,
)
from dichiarazioni_pubbliche.finding_runtime import (  # noqa: E402
    FindingDraft,
)


class FindingRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_record = FindingRecord(
            finding_id="finding:test-1",
            claim_id="claim:test-1",
            verification_run_id="verification:test-1",
            assessment=VerificationAssessment.FACTUALLY_FALSE.value,
            assessment_version=VERIFICATION_ASSESSMENT_VERSION,
            rationale="NUMERIC_MISMATCH",
            publication_status=FindingPublicationStatus.POLICY_HOLD.value,
            publication_status_version=FINDING_PUBLICATION_STATUS_VERSION,
            policy_version="finding-policy-v1",
            evidence_ids=("evidence:1", "evidence:2"),
            model_bundle={
                "verification_version": VERIFICATION_ASSESSMENT_VERSION,
                "deterministic": True,
            },
            supersedes_id="finding:prior-1",
        )

    def test_normalizer_round_trip_from_record(self):
        normalized = normalize_finding_record(self.valid_record)
        self.assertEqual(normalized, self.valid_record)

    def test_normalizer_round_trip_from_dict(self):
        data = self.valid_record.to_dict()
        normalized = normalize_finding_record(data)
        self.assertEqual(normalized, self.valid_record)
        self.assertEqual(normalized.to_dict(), data)

    def test_normalizer_round_trip_from_finding_draft(self):
        draft = FindingDraft(
            finding_id="finding:draft-1",
            claim_id="claim:draft-1",
            verification_run_id="verification:draft-1",
            assessment=VerificationAssessment.SUPPORTED.value,
            assessment_version=VERIFICATION_ASSESSMENT_VERSION,
            rationale="OFFICIAL_STATISTICS_MATCH",
            publication_status=FindingPublicationStatus.POLICY_HOLD.value,
            publication_status_version=FINDING_PUBLICATION_STATUS_VERSION,
            policy_version="finding-policy-v1",
            evidence_ids=("evidence:alpha",),
            model_bundle={"deterministic": True},
            supersedes_id=None,
        )
        record = normalize_finding_record(draft)
        self.assertEqual(record.finding_id, "finding:draft-1")
        self.assertEqual(record.claim_id, "claim:draft-1")
        self.assertEqual(record.assessment, "SUPPORTED")
        self.assertEqual(record.supersedes_id, None)
        # Round trip back through dict
        roundtripped = normalize_finding_record(record.to_dict())
        self.assertEqual(record, roundtripped)

    def test_normalizer_applies_defaults_for_canonical_versions(self):
        minimal_dict = {
            "finding_id": "finding:min-1",
            "claim_id": "claim:min-1",
            "verification_run_id": "verification:min-1",
            "assessment": "SUPPORTED",
            "rationale": "ok",
            "publication_status": "POLICY_HOLD",
            "policy_version": "v1",
        }
        record = normalize_finding_record(minimal_dict)
        self.assertEqual(
            record.assessment_version, VERIFICATION_ASSESSMENT_VERSION
        )
        self.assertEqual(
            record.publication_status_version,
            FINDING_PUBLICATION_STATUS_VERSION,
        )
        self.assertEqual(record.evidence_ids, ())
        self.assertEqual(record.model_bundle, {})
        self.assertIsNone(record.supersedes_id)

    def test_rejection_of_unknown_fields(self):
        data = self.valid_record.to_dict()
        data["unexpected_score"] = 0.99
        data["extra_metadata"] = "bad"
        with self.assertRaises(ValueError) as ctx:
            normalize_finding_record(data)
        self.assertIn("FINDING_RECORD_UNKNOWN_FIELDS", str(ctx.exception))
        self.assertIn("unexpected_score", str(ctx.exception))
        self.assertIn("extra_metadata", str(ctx.exception))

    def test_rejection_of_invalid_input_type(self):
        for invalid in (None, "finding:1", 42, ["list"], True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError) as ctx:
                    normalize_finding_record(invalid)
                self.assertIn(
                    "FINDING_RECORD_INVALID_TYPE", str(ctx.exception)
                )

    def test_rejection_of_missing_required_fields(self):
        for field in (
            "finding_id",
            "claim_id",
            "verification_run_id",
            "assessment",
            "rationale",
            "publication_status",
            "policy_version",
        ):
            data = self.valid_record.to_dict()
            del data[field]
            with self.subTest(missing_field=field):
                with self.assertRaises(ValueError) as ctx:
                    normalize_finding_record(data)
                self.assertIn(
                    "FINDING_RECORD_MISSING_FIELDS", str(ctx.exception)
                )
                self.assertIn(field, str(ctx.exception))

    def test_rejection_of_non_canonical_assessment(self):
        data = self.valid_record.to_dict()
        data["assessment"] = "MOSTLY_TRUE"
        with self.assertRaises(ValueError) as ctx:
            normalize_finding_record(data)
        self.assertIn("FINDING_ASSESSMENT_INVALID", str(ctx.exception))

    def test_rejection_of_mismatched_assessment_version(self):
        data = self.valid_record.to_dict()
        data["assessment_version"] = "deterministic-verification-v999"
        with self.assertRaises(ValueError) as ctx:
            normalize_finding_record(data)
        self.assertIn(
            "FINDING_ASSESSMENT_VERSION_MISMATCH", str(ctx.exception)
        )

    def test_rejection_of_non_canonical_publication_status(self):
        data = self.valid_record.to_dict()
        data["publication_status"] = "APPROVED_BY_ADMIN"
        with self.assertRaises(ValueError) as ctx:
            normalize_finding_record(data)
        self.assertIn(
            "FINDING_PUBLICATION_STATUS_INVALID", str(ctx.exception)
        )

    def test_rejection_of_mismatched_publication_status_version(self):
        data = self.valid_record.to_dict()
        data["publication_status_version"] = "finding-publication-v999"
        with self.assertRaises(ValueError) as ctx:
            normalize_finding_record(data)
        self.assertIn(
            "FINDING_PUBLICATION_STATUS_VERSION_MISMATCH", str(ctx.exception)
        )

    def test_finding_sql_requires_verification_provenance_equality(self):
        sql = INSERT_FINDING_DRAFT_SQL_V1

        # Must verify verification_run identity
        self.assertIn("verification.id = :'verification_run_id'", sql)

        # Must verify claim_id matches verification run
        self.assertIn("verification.claim_id = :'claim_id'", sql)

        # Must verify assessment matches verification run
        self.assertIn("verification.assessment = :'assessment'", sql)

        # Must verify exact set equality of evidence_ids in both directions
        self.assertIn(
            "verification.evidence_ids @> :'evidence_ids'::jsonb", sql
        )
        self.assertIn(
            ":'evidence_ids'::jsonb @> verification.evidence_ids", sql
        )

        # Must embed canonical versions from domain_vocabulary
        self.assertIn(f"'{VERIFICATION_ASSESSMENT_VERSION}'", sql)
        self.assertIn(f"'{FINDING_PUBLICATION_STATUS_VERSION}'", sql)

        # Atomic insertion and linking structure
        self.assertIn("WITH eligible AS (", sql)
        self.assertIn("inserted AS (", sql)
        self.assertIn("linked AS (", sql)
        self.assertIn("FROM eligible", sql)
        self.assertIn("FROM inserted", sql)
        self.assertIn(
            "INSERT INTO finding_evidence (finding_id, evidence_id, relation)",
            sql,
        )
        self.assertIn("'VERIFICATION_INPUT'", sql)
        self.assertIn("SELECT EXISTS(SELECT 1 FROM inserted)::text;", sql)

    def test_sql_parameter_generation(self):
        params = finding_record_to_sql_parameters(self.valid_record)
        self.assertEqual(params["finding_id"], "finding:test-1")
        self.assertEqual(params["claim_id"], "claim:test-1")
        self.assertEqual(
            params["verification_run_id"], "verification:test-1"
        )
        self.assertEqual(params["assessment"], "FACTUALLY_FALSE")
        self.assertEqual(params["publication_status"], "POLICY_HOLD")
        self.assertEqual(params["policy_version"], "finding-policy-v1")
        self.assertEqual(params["supersedes_id"], "finding:prior-1")
        self.assertEqual(
            params["evidence_ids"], '["evidence:1","evidence:2"]'
        )


if __name__ == "__main__":
    unittest.main()
