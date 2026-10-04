import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    RELATION_VERSION,
    RelationCandidateType,
)
from dichiarazioni_pubbliche.relation_repository import (  # noqa: E402
    FORBIDDEN_PUBLISHED_STATUSES,
    INSERT_RELATION_CANDIDATE_SQL_V1,
    RelationCandidateRecord,
    normalize_relation_candidate_record,
    relation_candidate_to_sql_parameters,
)


class RelationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_record = RelationCandidateRecord(
            id="relation-candidate:test-1",
            subject_claim_id="claim:prior-1",
            object_claim_id="claim:later-1",
            relation_type=RelationCandidateType.CONTRADICTION_CANDIDATE.value,
            relation_version=RELATION_VERSION,
            status="CANDIDATE",
            confidence=0.85,
            rationale_codes=(
                "SAME_PROPOSITION_OPPOSITE_STANCE",
                "OVERLAPPING_TEMPORAL_SCOPE",
            ),
            metadata={"source_job_id": "job:test-1"},
        )

    def test_normalizer_round_trip_from_record(self):
        normalized = normalize_relation_candidate_record(self.valid_record)
        self.assertEqual(normalized, self.valid_record)

    def test_normalizer_round_trip_from_dict(self):
        data = self.valid_record.to_dict()
        normalized = normalize_relation_candidate_record(data)
        self.assertEqual(normalized, self.valid_record)
        self.assertEqual(normalized.to_dict(), data)

    def test_normalizer_applies_defaults(self):
        minimal_dict = {
            "id": "relation-candidate:min-1",
            "subject_claim_id": "claim:a",
            "object_claim_id": "claim:b",
            "relation_type": RelationCandidateType.SAME_PROPOSITION.value,
        }
        record = normalize_relation_candidate_record(minimal_dict)
        self.assertEqual(record.relation_version, RELATION_VERSION)
        self.assertEqual(record.status, "CANDIDATE")
        self.assertIsNone(record.confidence)
        self.assertEqual(record.rationale_codes, ())
        self.assertEqual(record.metadata, {})

    def test_rejection_of_unknown_fields(self):
        data = self.valid_record.to_dict()
        data["published_by"] = "editor-1"
        data["editorial_verdict"] = "TRUE"
        with self.assertRaises(ValueError) as ctx:
            normalize_relation_candidate_record(data)
        self.assertIn("RELATION_RECORD_UNKNOWN_FIELDS", str(ctx.exception))
        self.assertIn("published_by", str(ctx.exception))
        self.assertIn("editorial_verdict", str(ctx.exception))

    def test_rejection_of_invalid_input_type(self):
        for invalid in (None, "relation:1", 123, ["list"]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError) as ctx:
                    normalize_relation_candidate_record(invalid)
                self.assertIn(
                    "RELATION_RECORD_INVALID_TYPE", str(ctx.exception)
                )

    def test_rejection_of_missing_required_fields(self):
        for field in ("id", "subject_claim_id", "object_claim_id", "relation_type"):
            data = self.valid_record.to_dict()
            del data[field]
            with self.subTest(missing_field=field):
                with self.assertRaises(ValueError) as ctx:
                    normalize_relation_candidate_record(data)
                self.assertIn(
                    "RELATION_RECORD_MISSING_FIELDS", str(ctx.exception)
                )
                self.assertIn(field, str(ctx.exception))

    def test_rejection_of_non_canonical_relation_type(self):
        data = self.valid_record.to_dict()
        data["relation_type"] = "DIRECT_LIE"
        with self.assertRaises(ValueError) as ctx:
            normalize_relation_candidate_record(data)
        self.assertIn("RELATION_TYPE_INVALID", str(ctx.exception))

    def test_rejection_of_mismatched_relation_version(self):
        data = self.valid_record.to_dict()
        data["relation_version"] = "claim-relation-v999"
        with self.assertRaises(ValueError) as ctx:
            normalize_relation_candidate_record(data)
        self.assertIn("RELATION_VERSION_MISMATCH", str(ctx.exception))

    def test_rejection_of_self_relation(self):
        data = self.valid_record.to_dict()
        data["object_claim_id"] = data["subject_claim_id"]
        with self.assertRaises(ValueError) as ctx:
            normalize_relation_candidate_record(data)
        self.assertIn("RELATION_SELF_REFUSED", str(ctx.exception))

    def test_rejection_of_out_of_range_confidence(self):
        for bad_conf in (-0.1, 1.01, 2.5):
            data = self.valid_record.to_dict()
            data["confidence"] = bad_conf
            with self.subTest(bad_confidence=bad_conf):
                with self.assertRaises(ValueError) as ctx:
                    normalize_relation_candidate_record(data)
                self.assertIn(
                    "RELATION_CONFIDENCE_OUT_OF_RANGE", str(ctx.exception)
                )

    def test_relation_persistence_cannot_set_published_state(self):
        # 1. Normalizer rejects published statuses in dict input
        for forbidden in (
            "PUBLISH",
            "PUBLISHED",
            "APPROVED",
            "VERIFIED",
            "ACTIVE",
        ):
            data = self.valid_record.to_dict()
            data["status"] = forbidden
            with self.subTest(forbidden_status=forbidden):
                with self.assertRaises(ValueError) as ctx:
                    normalize_relation_candidate_record(data)
                self.assertIn("RELATION_STATUS_INVALID", str(ctx.exception))

        # 2. Record dataclass rejects published status on direct initialization
        for forbidden in FORBIDDEN_PUBLISHED_STATUSES:
            with self.subTest(forbidden_status=forbidden):
                with self.assertRaises(ValueError) as ctx:
                    RelationCandidateRecord(
                        id="candidate:1",
                        subject_claim_id="claim:1",
                        object_claim_id="claim:2",
                        relation_type=RelationCandidateType.RELATED_TOPIC.value,
                        status=forbidden,
                    )
                self.assertIn("RELATION_STATUS_INVALID", str(ctx.exception))

        # 3. Parameters helper rejects published status and outputs strictly CANDIDATE
        data_published = self.valid_record.to_dict()
        data_published["status"] = "PUBLISHED"
        with self.assertRaises(ValueError):
            relation_candidate_to_sql_parameters(data_published)

        params = relation_candidate_to_sql_parameters(self.valid_record)
        self.assertEqual(params["status"], "CANDIDATE")

    def test_relation_candidate_insert_sql(self):
        sql = INSERT_RELATION_CANDIDATE_SQL_V1

        # Target must be claim_relation_candidate, never published claim_relation
        self.assertIn("INSERT INTO claim_relation_candidate", sql)
        self.assertNotIn("INSERT INTO claim_relation (", sql)

        # Must bind required columns
        self.assertIn(":'subject_claim_id'", sql)
        self.assertIn(":'object_claim_id'", sql)
        self.assertIn(":'relation_type'", sql)
        self.assertIn(":'relation_version'", sql)
        self.assertIn(":'status'", sql)
        self.assertIn("NULLIF(:'confidence','')::numeric", sql)
        self.assertIn(":'rationale_codes'::jsonb", sql)
        self.assertIn(":'metadata'::jsonb", sql)

        # Idempotent insert returning boolean existence
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)
        self.assertIn("SELECT EXISTS(SELECT 1 FROM inserted)::text;", sql)


if __name__ == "__main__":
    unittest.main()
