import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tools"))

from dichiarazioni_pubbliche.daily_pipeline_health import (  # noqa: E402
    COUNTER_NAMES, DAILY_PIPELINE_COUNTS_SQL, classify_daily_pipeline,
)
import check_daily_pipeline_health as cli  # noqa: E402

TODAY = date(2026, 11, 12)


def snapshot(**overrides):
    result = {name: 0 for name in COUNTER_NAMES}
    result.update({"daily_runs_completed": 1, "latest_daily_run_date": TODAY.isoformat()})
    result.update(overrides)
    return result


class DailyPipelineHealthTests(unittest.TestCase):
    def test_complete_day_is_healthy(self):
        report = classify_daily_pipeline(
            snapshot(
                daily_items_discovered=20,
                captures=18,
                statements=12,
                verdicts=12,
                published=9,
                provider_receipts=40,
            ),
            today=TODAY,
        )
        self.assertEqual(report.state, "HEALTHY")
        self.assertEqual(report.reasons, ())
        self.assertFalse(report.publication_authority)
        self.assertTrue(report.private_only)

    def test_each_stage_gap_is_named(self):
        cases = (
            (dict(daily_items_discovered=3), "ITEMS_NOT_CAPTURED"),
            (dict(daily_items_discovered=3, captures=3), "CAPTURES_WITHOUT_STATEMENTS"),
            (dict(daily_items_discovered=3, captures=3, statements=2), "STATEMENTS_WITHOUT_VERDICTS"),
            (dict(daily_items_discovered=3, captures=3, statements=2, verdicts=2), "NOTHING_PUBLISHED"),
            (dict(daily_items_discovered=3, jobs_blocked=1), "BLOCKED_JOBS_PRESENT"),
            (dict(daily_runs_failed=2), "FAILED_DAILY_RUN_PRESENT"),
        )
        for values, reason in cases:
            with self.subTest(reason=reason):
                report = classify_daily_pipeline(snapshot(**values), today=TODAY)
                self.assertIn(reason, report.reasons)
                self.assertEqual(report.state, "NEEDS_OPERATOR_ACTION")

    def test_missing_run_and_no_discovery_are_reported(self):
        report = classify_daily_pipeline(
            snapshot(daily_runs_completed=0, latest_daily_run_date=None), today=TODAY
        )
        self.assertIn("NO_COMPLETED_DAILY_RUN", report.reasons)
        self.assertIn(
            "NO_DISCOVERED_ITEMS",
            classify_daily_pipeline(snapshot(), today=TODAY).reasons,
        )

    def test_old_rows_are_not_counted_by_the_query(self):
        sql = DAILY_PIPELINE_COUNTS_SQL.lower()
        self.assertIn("begin transaction read only", sql)
        self.assertNotIn("insert into", sql)
        self.assertNotIn("update ", sql)
        self.assertNotIn("delete from", sql)
        self.assertNotIn("canonical_url", sql)
        self.assertNotIn("body", sql)
        self.assertIn("interval '24 hours'", sql)
        self.assertIn("row_to_json", sql)

    def test_invalid_types_and_forged_dates_fail_closed(self):
        for values in (
            dict(captures=True),
            dict(captures="0"),
            dict(jobs_blocked=-1),
            dict(latest_daily_run_date="tomorrow"),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                classify_daily_pipeline(snapshot(**values), today=TODAY)
        with self.assertRaisesRegex(ValueError, "SCHEMA_DRIFT"):
            classify_daily_pipeline({**snapshot(), "raw_transcript": "private"}, today=TODAY)

    def test_cli_aggregate_only_and_fail_closed(self):
        from contextlib import redirect_stdout
        from io import StringIO

        with patch.object(cli.PsqlRuntime, "run", return_value=json.dumps(snapshot())):
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main(["--database-url", "postgresql:///fixture"]), 0)
            body = json.loads(out.getvalue())
            self.assertFalse(body["publication_authority"])
            self.assertTrue(body["reasons"])
        with patch.object(cli.PsqlRuntime, "run", side_effect=RuntimeError("secret private-id")):
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main([]), 2)
            self.assertNotIn("secret", out.getvalue())


if __name__ == "__main__":
    unittest.main()
