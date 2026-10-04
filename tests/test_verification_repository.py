import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    VERIFICATION_ASSESSMENT_VERSION,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.verification_repository import (  # noqa: E402
    INSERT_VERIFICATION_RUN_SQL_V1,
    LATEST_VERIFICATION_TEMPLATE_SQL_V1,
    VerificationRunRecord,
    normalize_verification_run_record,
    verification_run_to_sql_parameters,
)


class VerificationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_record = VerificationRunRecord(
            run_id="verification:test-run-1",
            claim_id="claim:test-1",
            verification_kind="numeric_statistic",
            verification_rule={
                "metric": "employment_rate_pct",
                "reference_period": "2026-07",
                "expected_value": 63.2,
            },
            input_fingerprint="sha256:fingerprint-1",
            statement_cutoff="2026-09-24",
            assessment=VerificationAssessment.SUPPORTED.value,
            verification_version=VERIFICATION_ASSESSMENT_VERSION,
            evidence_ids=("evidence:1", "evidence:2"),
            observation_ids=("obs:1", "obs:2"),
            blockers=(),
            rationale_codes=("OFFICIAL_DATA_MATCH",),
            result={"diff": 0.0, "tolerance": 0.1},
        )

    def test_normalizer_round_trip_from_record(self):
        normalized = normalize_verification_run_record(self.valid_record)
        self.assertEqual(normalized, self.valid_record)
        self.assertEqual(normalize_verification_run_record(self.valid_record), self.valid_record)

    def test_normalizer_round_trip_from_dict(self):
        data = self.valid_record.to_dict()
        normalized = normalize_verification_run_record(data)
        self.assertEqual(normalized, self.valid_record)
        self.assertEqual(normalized.to_dict(), data)

    def test_normalizer_accepts_id_alias(self):
        data = self.valid_record.to_dict()
        del data["run_id"]
        data["id"] = "verification:aliased-id"
        normalized = normalize_verification_run_record(data)
        self.assertEqual(normalized.run_id, "verification:aliased-id")
        self.assertEqual(normalized.id, "verification:aliased-id")

    def test_normalizer_applies_defaults(self):
        minimal_dict = {
            "run_id": "verification:min-1",
            "claim_id": "claim:min-1",
            "verification_kind": "numeric_statistic",
            "verification_rule": {"metric": "gdp_pct"},
            "input_fingerprint": "sha256:min-fp",
            "statement_cutoff": "2026-09-01",
            "assessment": VerificationAssessment.UNRESOLVED.value,
        }
        record = normalize_verification_run_record(minimal_dict)
        self.assertEqual(record.verification_version, VERIFICATION_ASSESSMENT_VERSION)
        self.assertEqual(record.evidence_ids, ())
        self.assertEqual(record.observation_ids, ())
        self.assertEqual(record.blockers, ())
        self.assertEqual(record.rationale_codes, ())
        self.assertEqual(record.result, {})

    def test_rejection_of_unknown_fields(self):
        data = self.valid_record.to_dict()
        data["unauthorized_override"] = True
        data["score"] = 100
        with self.assertRaises(ValueError) as ctx:
            normalize_verification_run_record(data)
        self.assertIn("VERIFICATION_RECORD_UNKNOWN_FIELDS", str(ctx.exception))
        self.assertIn("unauthorized_override", str(ctx.exception))
        self.assertIn("score", str(ctx.exception))

    def test_rejection_of_invalid_input_type(self):
        for invalid in (None, 987, "verification:string", [1, 2, 3]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError) as ctx:
                    normalize_verification_run_record(invalid)
                self.assertIn("VERIFICATION_RECORD_INVALID_TYPE", str(ctx.exception))

    def test_rejection_of_missing_required_fields(self):
        required_fields = (
            "run_id",
            "claim_id",
            "verification_kind",
            "verification_rule",
            "input_fingerprint",
            "statement_cutoff",
            "assessment",
        )
        for field in required_fields:
            data = self.valid_record.to_dict()
            del data[field]
            with self.subTest(missing_field=field):
                with self.assertRaises(ValueError) as ctx:
                    normalize_verification_run_record(data)
                self.assertTrue(
                    "VERIFICATION_RECORD_MISSING_FIELDS" in str(ctx.exception)
                    or "VERIFICATION_RUN_ID_REQUIRED" in str(ctx.exception)
                )

    def test_rejection_of_non_canonical_assessment(self):
        data = self.valid_record.to_dict()
        data["assessment"] = "ARBITRARY_TRUTH_VERDICT"
        with self.assertRaises(ValueError) as ctx:
            normalize_verification_run_record(data)
        self.assertIn("VERIFICATION_ASSESSMENT_INVALID", str(ctx.exception))

    def test_rejection_of_mismatched_verification_version(self):
        data = self.valid_record.to_dict()
        data["verification_version"] = "verification-v999"
        with self.assertRaises(ValueError) as ctx:
            normalize_verification_run_record(data)
        self.assertIn("VERIFICATION_VERSION_MISMATCH", str(ctx.exception))

    def test_rejection_of_invalid_statement_cutoff_date(self):
        for bad_date in ("invalid-date", "2026/09/24", "2026-9-24", "26-09-2026", ""):
            data = self.valid_record.to_dict()
            data["statement_cutoff"] = bad_date
            with self.subTest(bad_date=bad_date):
                with self.assertRaises(ValueError) as ctx:
                    normalize_verification_run_record(data)
                self.assertTrue(
                    "VERIFICATION_STATEMENT_CUTOFF_INVALID_DATE" in str(ctx.exception)
                    or "VERIFICATION_STATEMENT_CUTOFF_REQUIRED" in str(ctx.exception)
                )

    def test_rejection_of_invalid_mappings_and_lists(self):
        bad_rule_data = self.valid_record.to_dict()
        bad_rule_data["verification_rule"] = "not_a_mapping"
        with self.assertRaises(ValueError) as ctx:
            normalize_verification_run_record(bad_rule_data)
        self.assertIn("VERIFICATION_RULE_INVALID", str(ctx.exception))

        bad_ev_data = self.valid_record.to_dict()
        bad_ev_data["evidence_ids"] = "not_a_list"
        with self.assertRaises(ValueError) as ctx:
            normalize_verification_run_record(bad_ev_data)
        self.assertIn("VERIFICATION_EVIDENCE_IDS_INVALID", str(ctx.exception))

    def test_sql_constants_contain_canonical_version_literals(self):
        sql = INSERT_VERIFICATION_RUN_SQL_V1
        self.assertIn(VERIFICATION_ASSESSMENT_VERSION, sql)
        self.assertIn(f"'{VERIFICATION_ASSESSMENT_VERSION}'", sql)

    def test_sql_semantics_preserve_idempotent_replay(self):
        sql = INSERT_VERIFICATION_RUN_SQL_V1
        self.assertIn("INSERT INTO verification_run (", sql)
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)
        self.assertIn("RETURNING id", sql)
        self.assertIn("SELECT EXISTS(SELECT 1 FROM inserted)::text;", sql)

    def test_latest_verification_template_sql(self):
        sql = LATEST_VERIFICATION_TEMPLATE_SQL_V1
        self.assertIn("FROM verification_run", sql)
        self.assertIn("WHERE claim_id = :'claim_id'", sql)
        self.assertIn("ORDER BY created_at DESC, id DESC", sql)
        self.assertIn("LIMIT 1", sql)

    def test_verification_run_to_sql_parameters(self):
        params = verification_run_to_sql_parameters(self.valid_record)
        self.assertEqual(params["run_id"], "verification:test-run-1")
        self.assertEqual(params["claim_id"], "claim:test-1")
        self.assertEqual(params["verification_kind"], "numeric_statistic")
        self.assertEqual(params["verification_version"], VERIFICATION_ASSESSMENT_VERSION)
        self.assertEqual(params["statement_cutoff"], "2026-09-24")
        self.assertEqual(params["assessment"], "SUPPORTED")
        self.assertEqual(json.loads(params["evidence_ids"]), ["evidence:1", "evidence:2"])
        self.assertEqual(json.loads(params["observation_ids"]), ["obs:1", "obs:2"])
        self.assertEqual(json.loads(params["blockers"]), [])
        self.assertEqual(json.loads(params["rationale_codes"]), ["OFFICIAL_DATA_MATCH"])
        self.assertEqual(json.loads(params["result"]), {"diff": 0.0, "tolerance": 0.1})


if __name__ == "__main__":
    unittest.main()
