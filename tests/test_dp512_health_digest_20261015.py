"""DP-512: actual health consumer over isolated canonical PostgreSQL receipts."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests import test_dp512_billing_pg_fence_next as pg_fixture
from dichiarazioni_pubbliche.health_digest import build_health_digest
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


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


if __name__ == '__main__':
    unittest.main()
