import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tools"))

from dichiarazioni_pubbliche.daily_pipeline_health import (  # noqa: E402
    COUNTER_NAMES, DAILY_PIPELINE_COUNTS_SQL, classify_daily_pipeline,
)
import check_daily_pipeline_health as cli  # noqa: E402


TODAY = date(2026, 10, 10)


def snapshot(**overrides):
    result = {name: 0 for name in COUNTER_NAMES}
    result.update({
        "daily_runs_completed": 1, "latest_daily_run_date": TODAY.isoformat(),
    })
    result.update(overrides)
    return result


class DailyPipelineHealthTests(unittest.TestCase):
    def test_daily_timer_success_without_material_is_not_a_working_pipeline(self):
        status = classify_daily_pipeline(snapshot(), today=TODAY)
        self.assertEqual(status.state, "NEEDS_OPERATOR_ACTION")
        self.assertIn("NO_ACTUAL_DISCOVERY_RESULTS", status.reasons)
        self.assertIs(status.publication_authority, False)
        self.assertIs(status.paid_calls_authorized, False)
        self.assertIs(status.private_only, True)

    def test_each_real_stage_gap_is_classified_without_fake_promotion(self):
        cases = (
            (dict(daily_items_discovered=3), "POLLED_METADATA_NOT_CAPTURED"),
            (dict(discovery_hits=4), "DISCOVERY_NOT_CAPTURED"),
            (dict(discovery_hits=4, captures=4), "CAPTURE_NOT_PARSED"),
            (dict(discovery_hits=4, captures=4, passages=4),
             "PASSAGES_NOT_PROMOTED_TO_PRIVATE_CANDIDATES"),
            (dict(discovery_hits=4, captures=4, passages=4, statement_candidates=3),
             "PRIVATE_REVIEW_STILL_REQUIRED"),
            (dict(jobs_queued=2), "UNPROCESSED_QUEUE_PRESENT"),
            (dict(jobs_blocked=2), "BLOCKED_JOBS_PRESENT"),
        )
        for values, reason in cases:
            with self.subTest(reason=reason):
                report = classify_daily_pipeline(snapshot(**values), today=TODAY)
                self.assertIn(reason, report.reasons)
                self.assertFalse(report.publication_authority)
        self.assertIn(
            "NO_PRIVATE_CAPTURES",
            classify_daily_pipeline(snapshot(daily_items_discovered=3), today=TODAY).reasons,
        )

    def test_not_yet_daily_or_stale_run_is_not_passed(self):
        self.assertIn(
            "NO_COMPLETED_DAILY_RUN",
            classify_daily_pipeline(
                snapshot(daily_runs_completed=0, latest_daily_run_date=None),
                today=TODAY,
            ).reasons,
        )
        self.assertIn(
            "DAILY_RUN_NOT_CURRENT",
            classify_daily_pipeline(
                snapshot(latest_daily_run_date=(TODAY - timedelta(days=1)).isoformat()),
                today=TODAY,
            ).reasons,
        )

    def test_invalid_types_forged_success_or_future_run_fails_closed(self):
        for values in (
            dict(captures=True),
            dict(captures="0"),
            dict(jobs_blocked=-1),
            dict(latest_daily_run_date="tomorrow"),
            dict(latest_daily_run_date="2026-10-11"),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                classify_daily_pipeline(snapshot(**values), today=TODAY)
        with self.assertRaisesRegex(ValueError, "SCHEMA_DRIFT"):
            classify_daily_pipeline({**snapshot(), "raw_transcript": "private"}, today=TODAY)

    def test_query_is_read_only_and_does_not_project_any_private_body(self):
        sql = DAILY_PIPELINE_COUNTS_SQL.lower()
        self.assertIn("begin transaction read only", sql)
        self.assertNotIn("insert into", sql)
        self.assertNotIn("update ", sql)
        self.assertNotIn("delete from", sql)
        self.assertNotIn("raw_text", sql)
        self.assertNotIn("canonical_url", sql)
        self.assertIn("row_to_json", sql)

    def test_cli_displays_aggregate_only_and_exits_failclosed(self):
        with patch.object(cli.PsqlRuntime, "run", return_value=json.dumps(snapshot())):
            from contextlib import redirect_stdout
            from io import StringIO
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main(["--database-url", "postgresql:///fixture"]), 0)
            body = json.loads(out.getvalue())
            self.assertFalse(body["publication_authority"])
            self.assertTrue(body["reasons"])
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main(["--expect-populated"]), 1)
        with patch.object(cli.PsqlRuntime, "run", side_effect=RuntimeError("secret private-id")):
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main([]), 2)
            self.assertNotIn("secret", out.getvalue())


if __name__ == "__main__":
    unittest.main()
