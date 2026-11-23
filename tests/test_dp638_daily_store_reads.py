import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.daily_store import DailyStore  # noqa: E402


class DailyStoreReadTests(unittest.TestCase):
    def test_statement_reads_are_explicit_and_exclude_capture_body(self):
        expected = [{"id": "statement-1", "quote": "Una frase", "status": "CANDIDATE"}]
        with patch.object(DailyStore, "run", return_value=json.dumps(expected)) as run:
            result = DailyStore().read_statements(since="2026-11-23", status="CANDIDATE")

        self.assertEqual(result, expected)
        sql = run.call_args.args[0].lower()
        self.assertIn("statement.quote", sql)
        self.assertIn("verdict.explanation", sql)
        self.assertNotIn("daily_capture.body", sql)
        self.assertNotIn("select body", sql)

    def test_statement_read_rejects_invalid_status_and_unbounded_limit(self):
        with self.assertRaisesRegex(ValueError, "STATUS_INVALID"):
            DailyStore().read_statements(since="2026-11-23", status="PUBLISHED")
        with self.assertRaisesRegex(ValueError, "READ_LIMIT_INVALID"):
            DailyStore().read_statements(since="2026-11-23", limit=1001)

    def test_today_read_contract_returns_content_ids(self):
        with patch.object(DailyStore, "run", return_value='["content-1"]') as run:
            result = DailyStore().captured_content_ids_today("2026-11-23")

        self.assertEqual(result, {"content-1"})
        self.assertIn("jsonb_agg(content_id)", run.call_args.args[0])
        self.assertIn(
            "(fetched_at AT TIME ZONE 'Europe/Rome')::date",
            run.call_args.args[0],
        )


if __name__ == "__main__":
    unittest.main()
