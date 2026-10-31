"""DP-512: actual health consumer over isolated canonical PostgreSQL receipts."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests import test_dp512_billing_pg_fence_next as pg_fixture
from dichiarazioni_pubbliche.health_digest import build_health_digest
from dichiarazioni_pubbliche.ops.budget_exposure_v1 import read_billing_day_window
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


def _host_agrees_with_pg_boundary_offsets(response):
    """Identify real host/PostgreSQL tzdata drift at the two DB day boundaries."""
    zone = ZoneInfo(response["timezone"])
    for key in ("window_start", "window_end"):
        postgres = datetime.fromisoformat(response[key])
        if postgres.utcoffset() != postgres.astimezone(zone).utcoffset():
            return False
    return True


class HealthDigestPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg = pg_fixture.BillingPgFenceTests
        cls.pg.setUpClass()
        cls.db = PsqlRuntime(cls.pg.dsn)

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    def setUp(self):
        self.pg.sql('TRUNCATE dp512_pg_event, dp512_pg_state, provider_receipt CASCADE;')

    def receipt(self, key, **changes):
        self.pg.receipt(self.pg(), key, operation_key=f'operation:{key}', **changes)

    def digest(self, now):
        with tempfile.TemporaryDirectory() as private_root:
            return build_health_digest(self.db, now=now, private_root=Path(private_root))

    def test_half_open_utc_month_boundary_and_unchanged_canonical_rows(self):
        for key, when in (
            ('before', '2026-10-31 23:59:59.999999+00'),
            ('start', '2026-11-01 00:00:00+00'),
            ('last', '2026-11-01 23:59:59.999999+00'),
            ('after', '2026-11-02 00:00:00+00'),
        ):
            self.receipt(key, basis='ESTIMATED_ONLY', estimate='0.1')
            self.pg.sql(f"UPDATE provider_receipt SET started_at='{when}', completed_at='{when}' WHERE id='receipt:{key}';")
        before = self.pg.sql('SELECT md5(json_agg(r ORDER BY id)::text) FROM provider_receipt r;')
        with patch.dict(os.environ, PGTZ="UTC"):
            digest = self.digest(datetime(2026, 11, 2, 0, 30, tzinfo=timezone(timedelta(hours=2))))
        billing = digest['billing_today']
        self.assertEqual(billing['attempt_count'], 2)
        self.assertEqual(billing['provisional_estimated_usd'], 0.2)
        self.assertEqual(billing['window_start'], '2026-11-01T00:00:00+00:00')
        self.assertEqual(billing['window_end'], '2026-11-02T00:00:00+00:00')
        self.assertEqual(before, self.pg.sql('SELECT md5(json_agg(r ORDER BY id)::text) FROM provider_receipt r;'))

    def test_unknown_and_recorded_charge_are_distinct_and_private(self):
        self.receipt('unknown', estimate='0', status='private-status@example.invalid')
        self.receipt('paid', basis='MEASURED_PROVIDER_COST', measured='0.12', receipt_body="'{\"secret\":\"private-token-fixture\"}'::jsonb")
        digest = self.digest(datetime(2026, 10, 12, 12, tzinfo=timezone.utc))
        billing = digest['billing_today']
        self.assertEqual(billing['unknown_cash_attempts'], 1)
        self.assertEqual(billing['recorded_measured_usd'], 0.12)
        self.assertIsNone(billing['authoritative_billed_usd'])
        self.assertFalse(billing['invoice_attested'])
        statuses = {row['id']: row['status'] for row in digest['slo']['objectives']}
        self.assertEqual(statuses['SLO-COST-GLOBAL-DAILY'], 'UNKNOWN')
        encoded = json.dumps(digest)
        for forbidden in ('private-status@', 'private-token-fixture', 'receipt:unknown', 'operation:paid'):
            self.assertNotIn(forbidden, encoded)
        self.assertIn('UNRECOGNIZED_STATUS', encoded)

    def test_legacy_receipt_without_both_timestamps_is_not_silently_dropped(self):
        self.receipt('undated', basis='ZERO_COST', estimate='0')
        self.pg.sql("UPDATE provider_receipt SET started_at=NULL, completed_at=NULL "
                    "WHERE id='receipt:undated';")
        digest = self.digest(datetime.now(timezone.utc))
        # A timestamp-free historical receipt cannot be dated to the present
        # UTC window: show unallocated liability, do not rewrite its history.
        self.assertEqual(digest['billing_today']['attempt_count'], 0)
        self.assertEqual(digest['billing_today']['undated_unallocated_receipts'], 1)
        statuses = {row['id']: row['status'] for row in digest['slo']['objectives']}
        self.assertEqual(statuses['SLO-COST-GLOBAL-DAILY'], 'UNKNOWN')

    def test_rome_dst_billing_day_matches_postgresql_session_timezone(self):
        for today, utc_start, utc_end in (
            ("2026-03-29T12:00:00+00:00", "2026-03-28T23:00:00+00:00",
             "2026-03-29T22:00:00+00:00"),
            ("2026-10-25T12:00:00+00:00", "2026-10-24T22:00:00+00:00",
             "2026-10-25T23:00:00+00:00"),
        ):
            with self.subTest(today=today):
                self.pg.sql(
                    "TRUNCATE dp512_pg_event, dp512_pg_state, provider_receipt CASCADE;"
                )
                start = datetime.fromisoformat(utc_start)
                end = datetime.fromisoformat(utc_end)
                for key, when in (
                    ("before", start - timedelta(microseconds=1)),
                    ("start", start),
                    ("last", end - timedelta(microseconds=1)),
                    ("after", end),
                ):
                    self.receipt(key, basis="ESTIMATED_ONLY", estimate="0.1")
                    self.pg.sql(
                        "UPDATE provider_receipt SET started_at="
                        f"'{when.isoformat()}',completed_at='{when.isoformat()}' "
                        f"WHERE id='receipt:{key}';"
                    )
                with patch.dict(os.environ, PGTZ="Europe/Rome"):
                    self.assertEqual(self.db.run("SHOW TIME ZONE;"), "Europe/Rome")
                    digest = self.digest(datetime.fromisoformat(today))
                self.assertEqual(digest["billing_today"]["window_start"], utc_start)
                self.assertEqual(digest["billing_today"]["window_end"], utc_end)
                self.assertEqual(digest["billing_today"]["attempt_count"], 2)
                self.assertEqual(digest["billing_today"]["provisional_estimated_usd"], 0.2)

    def test_db_boundaries_handle_utc_rome_and_havana_midnight_fold(self):
        cases = (
            ("UTC", "2026-11-01T04:30:00+00:00",
             "2026-11-01T00:00:00+00:00", "2026-11-02T00:00:00+00:00"),
            ("Europe/Rome", "2026-03-29T12:00:00+00:00",
             "2026-03-28T23:00:00+00:00", "2026-03-29T22:00:00+00:00"),
            ("Europe/Rome", "2026-10-25T12:00:00+00:00",
             "2026-10-24T22:00:00+00:00", "2026-10-25T23:00:00+00:00"),
            ("America/Havana", "2026-11-01T04:30:00+00:00",
             "2026-11-01T05:00:00+00:00", "2026-11-02T05:00:00+00:00"),
            ("America/Havana", "2026-11-01T05:30:00+00:00",
             "2026-11-01T05:00:00+00:00", "2026-11-02T05:00:00+00:00"),
            ("America/Santiago", "2026-09-06T14:00:00+00:00",
             "2026-09-06T04:00:00+00:00", "2026-09-07T03:00:00+00:00"),
        )
        for zone, when, start, end in cases:
            with self.subTest(zone=zone, when=when):
                observed = {}

                def captured_query(sql, **params):
                    raw = self.db.run(sql, **params)
                    observed.update(json.loads(raw))
                    return raw

                with patch.dict(os.environ, PGTZ=zone):
                    self.assertEqual(self.db.run("SHOW TIME ZONE;"), zone)
                    window = read_billing_day_window(
                        captured_query, current=datetime.fromisoformat(when)
                    )
                if not _host_agrees_with_pg_boundary_offsets(observed):
                    # A PostgreSQL/OS timezone database mismatch is a real
                    # budget-admission hold, not a test failure or an excuse
                    # to accept contradictory billing windows.
                    self.assertEqual(window.timezone_status, "UNKNOWN")
                    self.assertIsNone(window.start_utc)
                    self.assertIsNone(window.end_utc)
                    continue
                self.assertEqual(window.timezone_status, "KNOWN")
                self.assertEqual(window.start_utc.isoformat(), start)
                self.assertEqual(window.end_utc.isoformat(), end)

    def test_midnight_dst_digest_uses_exact_pg_receipt_window(self):
        for zone, current, start, end in (
            ("America/Havana", "2026-11-01T05:30:00+00:00",
             "2026-11-01T05:00:00+00:00", "2026-11-02T05:00:00+00:00"),
            ("America/Santiago", "2026-09-06T14:00:00+00:00",
             "2026-09-06T04:00:00+00:00", "2026-09-07T03:00:00+00:00"),
        ):
            with self.subTest(zone=zone):
                self.pg.sql(
                    "TRUNCATE dp512_pg_event, dp512_pg_state, provider_receipt CASCADE;"
                )
                first = datetime.fromisoformat(start)
                last = datetime.fromisoformat(end)
                for key, instant in (
                    ("before", first - timedelta(microseconds=1)),
                    ("start", first),
                    ("last", last - timedelta(microseconds=1)),
                    ("after", last),
                ):
                    self.receipt(key, basis="ESTIMATED_ONLY", estimate="0.1")
                    self.pg.sql(
                        "UPDATE provider_receipt SET started_at="
                        f"'{instant.isoformat()}',completed_at='{instant.isoformat()}' "
                        f"WHERE id='receipt:{key}';"
                    )
                with patch.dict(os.environ, PGTZ=zone):
                    observed = {}

                    def captured_query(sql, **params):
                        raw = self.db.run(sql, **params)
                        observed.update(json.loads(raw))
                        return raw

                    read_billing_day_window(
                        captured_query, current=datetime.fromisoformat(current)
                    )
                    digest = self.digest(datetime.fromisoformat(current))
                if not _host_agrees_with_pg_boundary_offsets(observed):
                    billing = digest["billing_today"]
                    self.assertEqual(billing["window_timezone_status"], "UNKNOWN")
                    self.assertIsNone(billing["window_start"])
                    self.assertIsNone(billing["window_end"])
                    self.assertFalse(billing["authorizes_dispatch"])
                    continue
                self.assertEqual(digest["billing_today"]["window_timezone_status"], "KNOWN")
                self.assertEqual(digest["billing_today"]["window_start"], start)
                self.assertEqual(digest["billing_today"]["window_end"], end)
                self.assertEqual(digest["billing_today"]["attempt_count"], 2)
                self.assertEqual(digest["billing_today"]["provisional_estimated_usd"], 0.2)
                self.assertFalse(digest["billing_today"]["authorizes_dispatch"])


if __name__ == '__main__':
    unittest.main()
