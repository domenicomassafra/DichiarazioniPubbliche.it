import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_contract import (  # noqa: E402
    ClaimType,
    validate_atomic_claim,
)
from dichiarazioni_pubbliche.claim_repository import (  # noqa: E402
    AtomicClaimRecord,
    CLAIM_CONTEXT_SQL_V1,
    CLAIM_COUNT_SQL_V1,
    CLAIM_TYPE_VERSION,
    INSERT_ATOMIC_CLAIMS_SQL_V1,
    NON_FACTUAL_CLAIM_TYPES,
    claims_to_json_payload,
    normalize_atomic_claim_record,
    render_insert_atomic_claims_sql,
)


class ClaimRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_record = AtomicClaimRecord(
            id="claim:v1:test-1",
            content_id="content:test-1",
            normalized_claim="Il tasso di disoccupazione è al 7 percento.",
            claim_type=ClaimType.NUMERIC_STATISTIC.value,
            segment_ids=("segment:1", "segment:2"),
            claim_type_version=CLAIM_TYPE_VERSION,
            temporal_scope={
                "statement_date": "2026-09-24",
                "valid_from": "2026-01-01",
                "valid_until": "2026-12-31",
            },
            check_worthy=True,
            extraction_model="test-extractor-v1",
            extraction_version="prompt-v1",
            metadata={"batch_id": "b1"},
        )

    def test_normalizer_round_trip_from_record(self):
        normalized = normalize_atomic_claim_record(self.valid_record)
        self.assertEqual(normalized, self.valid_record)
        self.assertEqual(normalize_atomic_claim_record(self.valid_record), self.valid_record)

    def test_normalizer_round_trip_from_dict(self):
        data = self.valid_record.to_dict()
        normalized = normalize_atomic_claim_record(data)
        self.assertEqual(normalized, self.valid_record)
        self.assertEqual(normalized.to_dict(), data)

    def test_normalizer_round_trip_from_claim_contract_dataclass(self):
        contract = validate_atomic_claim(
            claim_id="claim:v1:contract-1",
            content_id="content:c1",
            normalized_claim="La spesa sanitaria è aumentata.",
            claim_type=ClaimType.FISCAL_INFERENCE,
            statement_date="2026-09-20",
            check_worthy=True,
            source_segment_ids=("segment:10",),
            metadata={"source": "interview"},
        )
        record = normalize_atomic_claim_record(contract)
        self.assertEqual(record.id, "claim:v1:contract-1")
        self.assertEqual(record.claim_id, "claim:v1:contract-1")
        self.assertEqual(record.content_id, "content:c1")
        self.assertEqual(record.claim_type, "FISCAL_INFERENCE")
        self.assertEqual(record.segment_ids, ("segment:10",))
        self.assertEqual(record.source_segment_ids, ("segment:10",))
        self.assertEqual(record.temporal_scope["statement_date"], "2026-09-20")

    def test_normalizer_applies_defaults(self):
        minimal_dict = {
            "id": "claim:v1:min-1",
            "content_id": "content:min-1",
            "normalized_claim": "Il debito pubblico ammonta a 2800 miliardi.",
            "claim_type": ClaimType.NUMERIC_STATISTIC.value,
            "segment_ids": ["segment:min"],
        }
        record = normalize_atomic_claim_record(minimal_dict)
        self.assertEqual(record.claim_type_version, CLAIM_TYPE_VERSION)
        self.assertTrue(record.check_worthy)
        self.assertEqual(record.temporal_scope, {})
        self.assertIsNone(record.extraction_model)
        self.assertIsNone(record.extraction_version)
        self.assertEqual(record.metadata, {})

    def test_rejection_of_unknown_fields(self):
        data = self.valid_record.to_dict()
        data["unrecognized_field"] = "malicious"
        data["political_score"] = 99
        with self.assertRaises(ValueError) as ctx:
            normalize_atomic_claim_record(data)
        self.assertIn("ATOMIC_CLAIM_RECORD_UNKNOWN_FIELDS", str(ctx.exception))
        self.assertIn("unrecognized_field", str(ctx.exception))
        self.assertIn("political_score", str(ctx.exception))

    def test_rejection_of_invalid_input_type(self):
        for invalid in (None, 12345, "claim:string", ["not", "a", "record"]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError) as ctx:
                    normalize_atomic_claim_record(invalid)
                self.assertIn("ATOMIC_CLAIM_RECORD_INVALID_TYPE", str(ctx.exception))

    def test_rejection_of_missing_required_fields(self):
        for field in ("id", "content_id", "normalized_claim", "claim_type", "segment_ids"):
            data = self.valid_record.to_dict()
            del data[field]
            with self.subTest(missing_field=field):
                with self.assertRaises(ValueError) as ctx:
                    normalize_atomic_claim_record(data)
                self.assertIn("ATOMIC_CLAIM_RECORD_MISSING_FIELDS", str(ctx.exception))
                self.assertIn(field, str(ctx.exception))

    def test_rejection_of_non_canonical_claim_type(self):
        data = self.valid_record.to_dict()
        data["claim_type"] = "FABRICATED_CLAIM_TYPE"
        with self.assertRaises(ValueError) as ctx:
            normalize_atomic_claim_record(data)
        self.assertIn("ATOMIC_CLAIM_TYPE_INVALID", str(ctx.exception))

    def test_rejection_of_mismatched_claim_type_version(self):
        data = self.valid_record.to_dict()
        data["claim_type_version"] = "atomic-claim-v999"
        with self.assertRaises(ValueError) as ctx:
            normalize_atomic_claim_record(data)
        self.assertIn("ATOMIC_CLAIM_TYPE_VERSION_MISMATCH", str(ctx.exception))

    def test_rejection_of_non_factual_type_as_check_worthy(self):
        for non_factual in NON_FACTUAL_CLAIM_TYPES:
            data = self.valid_record.to_dict()
            data["claim_type"] = non_factual
            data["check_worthy"] = True
            with self.subTest(claim_type=non_factual):
                with self.assertRaises(ValueError) as ctx:
                    normalize_atomic_claim_record(data)
                self.assertIn("ATOMIC_CLAIM_NON_FACTUAL_NOT_CHECK_WORTHY", str(ctx.exception))

            # When check_worthy=False, non-factual claim types are allowed
            data["check_worthy"] = False
            rec = normalize_atomic_claim_record(data)
            self.assertEqual(rec.claim_type, non_factual)
            self.assertFalse(rec.check_worthy)

    def test_rejection_of_empty_or_invalid_segment_provenance(self):
        for bad_segments in ([], (), [" "], ["", "segment:1"], [123]):
            data = self.valid_record.to_dict()
            data["segment_ids"] = bad_segments
            with self.subTest(bad_segments=bad_segments):
                with self.assertRaises(ValueError):
                    normalize_atomic_claim_record(data)

    def test_sql_constants_contain_canonical_version_literals(self):
        sql = INSERT_ATOMIC_CLAIMS_SQL_V1
        self.assertIn(CLAIM_TYPE_VERSION, sql)
        self.assertIn(f"'{CLAIM_TYPE_VERSION}'", sql)

    def test_sql_semantics_preserve_idempotent_replay(self):
        sql = INSERT_ATOMIC_CLAIMS_SQL_V1
        self.assertIn("INSERT INTO atomic_claim (", sql)
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)
        self.assertIn("replayed AS (", sql)
        self.assertIn("SELECT claim.id", sql)
        self.assertIn("FROM atomic_claim claim", sql)
        self.assertIn("WHERE claim.content_id = input.content_id", sql)
        self.assertIn("AND claim.normalized_claim = input.normalized_claim", sql)
        self.assertIn("AND claim.claim_type = input.claim_type", sql)
        self.assertIn(f"AND claim.claim_type_version = '{CLAIM_TYPE_VERSION}'", sql)
        self.assertIn("replayed_only AS (", sql)
        self.assertIn("rejected AS (", sql)
        self.assertIn("blocked AS (", sql)
        self.assertIn("linked AS (", sql)
        self.assertIn("INSERT INTO claim_segment (claim_id, segment_id)", sql)
        self.assertIn("JOIN canonical_transcript_segment canonical", sql)
        self.assertIn("WHEN (SELECT has_rejected FROM blocked) = 1 THEN 0", sql)

    def test_claim_count_and_context_sql(self):
        self.assertIn("FROM atomic_claim", CLAIM_COUNT_SQL_V1)
        self.assertIn("WHERE content_id = :'content_id'", CLAIM_COUNT_SQL_V1)
        self.assertIn("FROM atomic_claim claim", CLAIM_CONTEXT_SQL_V1)
        self.assertIn("JOIN content_item content", CLAIM_CONTEXT_SQL_V1)
        self.assertIn("WHERE claim.id = :'claim_id'", CLAIM_CONTEXT_SQL_V1)

    def test_render_and_json_payload_helpers(self):
        rendered = render_insert_atomic_claims_sql("'$payload$'")
        self.assertIn("FROM jsonb_to_recordset('$payload$'::jsonb)", rendered)
        self.assertIn(CLAIM_TYPE_VERSION, rendered)

        payload = claims_to_json_payload([self.valid_record])
        self.assertIn(self.valid_record.id, payload)
        self.assertIn(self.valid_record.normalized_claim, payload)


if __name__ == "__main__":
    unittest.main()
