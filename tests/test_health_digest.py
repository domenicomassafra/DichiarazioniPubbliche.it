import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.health_digest import (  # noqa: E402
    build_health_digest,
    error_category,
    write_private_json,
)


class FakeDb:
    receipt_rows = ()
    undated_count = 0
    billing_timezone = "UTC"
    billing_window_override = None

    def run(self, sql, **variables):
        if "WITH bound AS" in sql and "current_setting('TimeZone')" in sql:
            if self.billing_window_override is not None:
                return self.billing_window_override
            current = datetime.fromisoformat(variables["current"])
            try:
                zone = ZoneInfo(self.billing_timezone)
            except ZoneInfoNotFoundError:
                return json.dumps({
                    "timezone": self.billing_timezone,
                    "local_day": current.date().isoformat(),
                    "window_start": None, "window_end": None,
                })
            start = current.astimezone(zone).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            # FakeDB only models unambiguous UTC days; the real PG tests
            # exercise DST midnight folds and skipped local midnight.
            return json.dumps({
                "timezone": self.billing_timezone,
                "local_day": current.astimezone(zone).date().isoformat(),
                "window_start": start.isoformat(),
                "window_end": (start + timedelta(days=1)).isoformat(),
            })
        if "FROM processing_job" in sql and "GROUP BY job_type" in sql:
            return '[{"job_type":"CLAIM_EXTRACT","state":"BLOCKED","count":2}]'
        if "'oldest_queued_seconds'" in sql:
            return '{"queued":0,"oldest_queued_seconds":0}'
        if "state IN ('BLOCKED', 'DEAD_LETTER')" in sql:
            return (
                '[{"last_error":"OMNIROUTE_TIERED_OFFICIAL_RUNTIME_BLOCKED: detail",'
                '"count":2}]'
            )
        if "FROM source_health" in sql:
            return (
                '[{"source_id":"s","status":"HEALTHY","consecutive_failures":0,'
                '"checked_at":"2026-09-22","last_success_at":"2026-09-22"}]'
            )
        if "FROM content_item" in sql and "GROUP BY processing_status" in sql:
            return '[{"processing_status":"CLAIM_EXTRACTION_BLOCKED","count":2}]'
        if "count(*)" in sql and "FROM provider_receipt" in sql:
            return str(self.undated_count)
        if "FROM worker_budget_reservation" in sql:
            return '{"daily_amount":0,"daily_count":0,"prior_count":0}'
        if "FROM provider_receipt" in sql:
            self.receipt_window = variables
            return json.dumps(self.receipt_rows)
        if "'variants'" in sql:
            return (
                '{"variants":2,"raw_segments":10,"canonical_segments":10,'
                '"publication_blocked_segments":3}'
            )
        if "'atomic_claims'" in sql:
            return (
                '{"atomic_claims":4,"check_worthy_claims":3,'
                '"claim_types":{"CURRENT_POLICY":2,"VALUE_JUDGMENT":2}}'
            )
        if "'evidence_records'" in sql:
            return (
                '{"evidence_records":5,"claim_candidates":7,'
                '"approved_candidates":2,'
                '"candidate_statuses":{"APPROVED":2,"RETRIEVED":5},'
                '"source_types":{"PRIMARY_OFFICIAL":5}}'
            )
        if "'evidence_observations'" in sql:
            return (
                '{"evidence_observations":3,'
                '"observation_statuses":{"APPROVED":2,"CANDIDATE":1},'
                '"verification_runs":2,'
                '"verification_assessments":{"SUPPORTED":1,"UNRESOLVED":1},'
                '"findings":2,'
                '"finding_publication_statuses":{"POLICY_HOLD":1,"UNRESOLVED":1},'
                '"relation_candidates":1,'
                '"relation_candidate_statuses":{"CANDIDATE":1},'
                '"reanalysis_triggers":1,'
                '"reanalysis_statuses":{"ENQUEUED":1},'
                '"review_events":2,'
                '"review_actions":{"APPROVED":2}}'
            )
        if "'public_people'" in sql:
            return (
                '{"public_people":2,"speaker_candidates":3,'
                '"speaker_candidate_statuses":{"APPROVED":2,"CANDIDATE":1},'
                '"speaker_assigned_segments":8,"speaker_assigned_claims":3}'
            )
        raise AssertionError(sql)


class HealthDigestTests(unittest.TestCase):
    @staticmethod
    def receipt(key, basis, *, estimate=None, measured=None, **extra):
        return {
            "receipt_id": f"receipt:{key}", "operation_key": f"operation:{key}",
            "attempt": 1, "provider_id": "provider:fixture",
            "operation": "CAPTION_PROBE", "status": "SUCCESS",
            "billing_basis": basis, "estimated_cost_usd": estimate,
            "measured_cost_usd": measured, **extra,
        }

    def digest(self, rows, **kwargs):
        db = FakeDb()
        db.receipt_rows = rows
        with tempfile.TemporaryDirectory() as tmp:
            return build_health_digest(
                db, private_root=Path(tmp),
                now=datetime(2026, 10, 15, tzinfo=timezone.utc), **kwargs,
            )

    def test_billing_separates_unverified_measured_estimates_unknown_plan_energy(self):
        paid = self.receipt("paid", "MEASURED_PROVIDER_COST", measured="0.1")
        digest = self.digest([
            paid, paid,
            self.receipt("estimate", "ESTIMATED_ONLY", estimate="0.2"),
            self.receipt("unknown", "UNKNOWN", estimate="0"),
            self.receipt("plan", "EXTERNAL_PLAN"),
            self.receipt("local", "ZERO_COST", local_energy_basis="UNKNOWN"),
        ])
        billing = digest["billing_today"]
        self.assertEqual(billing["recorded_measured_usd"], 0.1)
        self.assertEqual(billing["provisional_estimated_usd"], 0.2)
        self.assertEqual(digest["estimated_cost_usd_today"], 0.2)
        self.assertEqual(billing["attempt_count"], 5)
        self.assertEqual(billing["duplicate_receipt_replays"], 1)
        self.assertEqual(billing["unknown_cash_attempts"], 1)
        self.assertEqual(billing["external_plan_attempts"], 1)
        self.assertEqual(billing["unknown_energy_attempts"], 5)
        self.assertIsNone(billing["authoritative_billed_usd"])
        self.assertIsNone(billing["plan_quota_consumed"])
        self.assertIsNone(billing["measured_energy_wh"])
        self.assertFalse(billing["invoice_attested"])
        self.assertFalse(billing["authorizes_dispatch"])
        self.assertNotIn("receipt:paid", json.dumps(digest))
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "UNKNOWN")
        self.assertEqual(statuses["SLO-COST-SOURCE-DAILY"], "UNKNOWN")

    def test_provider_digest_never_blends_recorded_cost_with_unverified_estimates(self):
        # Both attempts share provider, operation and status. Their different
        # origins must remain visible in every private provider group.
        digest = self.digest([
            self.receipt("observed", "MEASURED_PROVIDER_COST", measured="0.15"),
            self.receipt("estimated", "ESTIMATED_ONLY", estimate="0.20"),
            self.receipt("unknown", "UNKNOWN"),
        ])
        groups = digest["provider_receipts_today"]
        self.assertEqual(len(groups), 3)
        by_basis = {row["billing_basis"]: row for row in groups}
        self.assertEqual(by_basis["MEASURED_PROVIDER_COST"]["cost_usd"], 0.15)
        self.assertEqual(
            by_basis["MEASURED_PROVIDER_COST"]["cost_basis"],
            "RECORDED_MEASURED_UNVERIFIED",
        )
        self.assertEqual(by_basis["ESTIMATED_ONLY"]["cost_usd"], 0.2)
        self.assertEqual(
            by_basis["ESTIMATED_ONLY"]["cost_basis"],
            "PROVISIONAL_ESTIMATE_UNVERIFIED",
        )
        self.assertTrue(by_basis["UNKNOWN"]["cash_uncertain"])
        self.assertEqual(by_basis["UNKNOWN"]["cost_basis"], "NO_AUTHENTICATED_PRICE")
        billing = digest["billing_today"]
        self.assertEqual(billing["recorded_measured_usd"], 0.15)
        self.assertEqual(billing["provisional_estimated_usd"], 0.2)
        self.assertEqual(billing["budget_exposure_upper_bound_usd_today"], 0.35)
        self.assertIsNone(billing["authoritative_billed_usd"])

    def test_unavailable_postgres_timezone_marks_billing_unknown(self):
        db = FakeDb()
        db.billing_timezone = "Invalid/UnknownSessionZone"
        db.receipt_rows = [
            self.receipt("unallocated", "MEASURED_PROVIDER_COST", measured="0.2")
        ]
        with tempfile.TemporaryDirectory() as tmp:
            digest = build_health_digest(
                db, private_root=Path(tmp),
                now=datetime(2026, 10, 25, 12, tzinfo=timezone.utc),
            )
        billing = digest["billing_today"]
        self.assertEqual(billing["window_timezone_status"], "UNKNOWN")
        self.assertIsNone(billing["window_start"])
        self.assertIsNone(billing["window_end"])
        self.assertIsNone(billing["attempt_count"])
        self.assertIsNone(billing["budget_exposure_upper_bound_usd_today"])
        self.assertIsNone(digest["estimated_cost_usd_today"])
        self.assertFalse(billing["invoice_attested"])
        self.assertFalse(billing["authorizes_dispatch"])
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "UNKNOWN")

    def test_malformed_or_drifted_pg_window_fails_closed_without_billable_rows(self):
        valid = {
            "timezone": "UTC", "local_day": "2026-10-25",
            "window_start": "2026-10-25T00:00:00+00:00",
            "window_end": "2026-10-26T00:00:00+00:00",
        }
        for response in (
            "not json",
            json.dumps({**valid, "window_start": "2026-10-25T00:00:00"}),
            json.dumps({**valid, "local_day": "2026-10-24"}),
            json.dumps({**valid, "window_end": "2026-10-24T00:00:00+00:00"}),
            json.dumps({**valid, "window_start": "2026-10-25T00:00:00+01:00"}),
            json.dumps({**valid, "timezone": "Invalid/UnknownSessionZone"}),
        ):
            with self.subTest(response=response):
                db = FakeDb()
                db.billing_window_override = response
                with tempfile.TemporaryDirectory() as tmp:
                    digest = build_health_digest(
                        db, private_root=Path(tmp),
                        now=datetime(2026, 10, 25, 12, tzinfo=timezone.utc),
                    )
                self.assertEqual(digest["billing_today"]["window_timezone_status"], "UNKNOWN")
                self.assertIsNone(digest["billing_today"]["window_start"])
                self.assertIsNone(digest["billing_today"]["attempt_count"])
                self.assertIsNone(digest["estimated_cost_usd_today"])
                self.assertFalse(digest["billing_today"]["invoice_attested"])
                self.assertFalse(digest["billing_today"]["authorizes_dispatch"])
                self.assertFalse(hasattr(db, "receipt_window"))

    def test_known_breach_is_not_hidden_by_an_unknown_attempt(self):
        digest = self.digest([
            self.receipt("known", "ESTIMATED_ONLY", estimate="0.7"),
            self.receipt("unknown", "UNKNOWN"),
        ], max_cost_usd_per_day=1, max_cost_usd_per_source_day=1)
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "BREACH")
        # Provider/operation aggregation has no authenticated source binding.
        self.assertEqual(statuses["SLO-COST-SOURCE-DAILY"], "UNKNOWN")

    def test_per_source_slo_never_uses_provider_group_as_source_identity(self):
        digest = self.digest([
            self.receipt("a", "MEASURED_PROVIDER_COST", measured="0.4"),
            self.receipt("b", "MEASURED_PROVIDER_COST", measured="0.4",
                         status="FAILED"),
        ], max_cost_usd_per_day=1, max_cost_usd_per_source_day=1)
        self.assertFalse(digest["billing_today"]["provider_grouping_is_source_attribution"])
        self.assertEqual(digest["billing_today"]["recorded_measured_usd"], 0.8)
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "BREACH")
        # Two grouped receipt rows are NOT two approved source ledgers.
        self.assertEqual(statuses["SLO-COST-SOURCE-DAILY"], "UNKNOWN")

    def test_unknown_zero_ceiling_is_not_healthy_zero_cost(self):
        digest = self.digest([self.receipt("unknown", "UNKNOWN", estimate="0")])
        self.assertEqual(digest["billing_today"]["unknown_cash_attempts"], 1)
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "UNKNOWN")

    def test_unverified_zero_cost_cannot_make_cash_slo_healthy(self):
        # Legacy receipts can infer ZERO_COST from a zero estimate without
        # independent provider evidence of free usage.
        digest = self.digest([self.receipt("zero", "ZERO_COST", estimate="0")])
        self.assertEqual(digest["billing_today"]["zero_cost_attempts"], 1)
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "UNKNOWN")

    def test_zero_upper_bound_estimate_without_provider_proof_is_not_free(self):
        # The real provider candidate batch may record a zero provisional
        # bound with ESTIMATED_ONLY, which is not verified free service.
        digest = self.digest([self.receipt("zero-bound", "ESTIMATED_ONLY", estimate="0")])
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "UNKNOWN")

    def test_zero_recorded_measured_without_independent_proof_is_not_free(self):
        digest = self.digest([self.receipt("measured-zero", "MEASURED_PROVIDER_COST", measured="0")])
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "UNKNOWN")

    def test_decimal_boundary_cost_ratio_does_not_false_breach(self):
        digest = self.digest([
            self.receipt("first", "ESTIMATED_ONLY", estimate="0.1"),
            self.receipt("second", "ESTIMATED_ONLY", estimate="0.2"),
        ], max_cost_usd_per_day=0.5)
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        # Equality at the warning boundary is AT_RISK, not a >target BREACH.
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "AT_RISK")

    def test_decimal_breach_just_above_ratio_survives_json_float_rounding(self):
        digest = self.digest([
            self.receipt("amount", "ESTIMATED_ONLY", estimate="0.1"),
        ], max_cost_usd_per_day=0.16666666666666666)
        statuses = {row["id"]: row["status"] for row in digest["slo"]["objectives"]}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "BREACH")

    def test_receipt_reader_uses_explicit_half_open_utc_day(self):
        from datetime import timedelta
        db = FakeDb()
        build_health_digest(
            db, private_root=Path("/nonexistent-dp512-fixture"),
            now=datetime(2026, 11, 1, 0, 30, tzinfo=timezone(timedelta(hours=2))),
        )
        self.assertEqual(db.receipt_window["since"], "2026-10-31T00:00:00+00:00")
        self.assertEqual(db.receipt_window["until"], "2026-11-01T00:00:00+00:00")

    def test_conflicting_attempt_does_not_generate_a_healthy_digest(self):
        first = self.receipt("one", "ESTIMATED_ONLY", estimate="0.1")
        with self.assertRaisesRegex(ValueError, "OPERATION_ATTEMPT_ID_CONFLICT"):
            self.digest([first, {**first, "receipt_id": "receipt:other"}])

    def test_error_category_never_emits_raw_detail(self):
        self.assertEqual(
            error_category("OMNIROUTE_TIERED_OFFICIAL_RUNTIME_BLOCKED: private detail"),
            "OMNIROUTE_TIERED_OFFICIAL_RUNTIME_BLOCKED",
        )
        self.assertEqual(error_category("some arbitrary text"), "OTHER")

    def test_digest_is_aggregate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            digest = build_health_digest(
                FakeDb(),
                private_root=Path(tmp),
                now=datetime(2026, 9, 22, tzinfo=timezone.utc),
            )
        self.assertEqual(digest["estimated_cost_usd_today"], 0.0)
        self.assertEqual(
            digest["blockers"][0]["category"],
            "OMNIROUTE_TIERED_OFFICIAL_RUNTIME_BLOCKED",
        )
        self.assertFalse(digest["privacy"]["contains_transcript_text"])
        self.assertEqual(digest["claims"]["atomic_claims"], 4)
        self.assertEqual(digest["evidence"]["claim_candidates"], 7)
        self.assertEqual(digest["verification"]["verification_runs"], 2)
        self.assertEqual(
            digest["verification"]["finding_publication_statuses"]["POLICY_HOLD"],
            1,
        )
        self.assertEqual(digest["verification"]["review_events"], 2)
        self.assertEqual(digest["identity"]["speaker_assigned_claims"], 3)

    def test_health_file_is_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "health.json"
            write_private_json(path, {"ok": True})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(path.parent).st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
