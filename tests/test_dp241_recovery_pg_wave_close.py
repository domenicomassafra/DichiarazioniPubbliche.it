"""DP-241 next wave: PostgreSQL-proven source provenance and rights epoch fencing.

Inherits the existing self-contained disposable PostgreSQL fixture (never
production); the base class' original concurrency/replay tests also re-run.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from tests import test_dp241_recovery_pg_next as baseline
from tests.test_dp241_original_source_investigation import receipt


class Dp241RecoveryWaveCloseTests(baseline.OriginalSourceRecoveryPgTests):
    def test_capture_final_url_changed_without_hash_change_fences_old_plan(self):
        """Capture URL is part of provenance, not mere cosmetic metadata."""
        self.register()
        self.sql("""
            UPDATE content_capture
              SET final_url='https://foreign.invalid/rewritten-original'
              WHERE id='capture:content:clip';
        """)
        self.assertEqual(
            self.sql("SELECT content_sha256 FROM content_capture "
                     "WHERE id='capture:content:clip';"),
            self.t.capture.content_sha256,
        )
        with self.assertRaisesRegex(ValueError, "PROVENANCE_STALE"):
            self.store.reserve(self.p, self.t, source_id="source:clip",
                               key="attempt:rewritten-url", expected_revision=0)
        self.assertEqual(self.store.history(self.p.plan_id).revision, 0)

    def test_content_canonical_url_mutation_fences_restart_and_replay(self):
        self.register()
        pending = self.store.reserve(self.p, self.t, source_id="source:clip",
                                     key="attempt:pinned", expected_revision=0)
        self.sql("""
            UPDATE content_item
              SET canonical_url='https://unapproved.invalid/reparented'
              WHERE id='content:clip';
        """)
        resumed = type(self.store)(self.dsn, allow_disposable_postgres=True)
        with self.assertRaisesRegex(ValueError, "PROVENANCE_STALE"):
            resumed.read(self.p, self.t, source_id="source:clip")
        with self.assertRaisesRegex(ValueError, "PROVENANCE_STALE"):
            resumed.reserve(self.p, self.t, source_id="source:clip",
                            key="attempt:pinned", expected_revision=0)
        self.assertEqual(resumed.history(self.p.plan_id).pending_attempt_id,
                         pending.pending_attempt_id)

    def test_new_cleared_rights_successor_invalidates_old_rights_epoch(self):
        """Even a newly CLEARED review is not the approval bound to old plan."""
        self.register()
        pending = self.store.reserve(self.p, self.t, source_id="source:clip",
                                     key="attempt:rights-old", expected_revision=0)
        self.sql("""
          INSERT INTO private_source_rights_record(
            id,subject_fingerprint,source_family,locator_kind,locator_value,
            content_id,passage_id,rights_status,rights_receipt_ref,
            permitted_uses,reviewed_at,reviewer_ref,policy_version,supersedes_id)
          SELECT 'rights:renewed',subject_fingerprint,source_family,
            locator_kind,locator_value,content_id,passage_id,
            'CLEARED','synthetic-new-review',
            ARRAY['DISCOVER_METADATA','FETCH']::text[],
            now(),'synthetic-reviewer-new','synthetic-policy-v2',id
          FROM private_source_rights_record WHERE id='rights:clip';
        """)
        self.assertEqual(self.sql(
            "SELECT rights_status FROM private_source_rights_record "
            "WHERE id='rights:renewed';"), "CLEARED")
        with self.assertRaisesRegex(ValueError, "PROVENANCE_STALE"):
            self.store.complete(self.p, self.t, source_id="source:clip",
                                key="attempt:rights-old",
                                expected_revision=pending.revision,
                                observed=receipt(self.p, 0, "NOT_FOUND"))
        self.assertEqual(self.store.history(self.p.plan_id).revision, 1)

    def test_capture_observed_at_mutation_cannot_retimestamp_existing_capture(self):
        self.register()
        self.sql("""
            UPDATE content_capture SET observed_at='2026-10-12T00:00:00Z'
              WHERE id='capture:content:clip';
        """)
        with self.assertRaisesRegex(ValueError, "PROVENANCE_STALE"):
            self.store.read(self.p, self.t, source_id="source:clip")

    def test_backdated_new_capture_in_source_lineage_invalidates_old_plan(self):
        """A new older-observed capture can bring missing original context."""
        self.register()
        self.sql("""
            INSERT INTO content_capture(
              id,content_id,observed_at,final_url,content_sha256,
              retrieval_method,retrieval_version,rights_status)
            VALUES (
              'capture:backdated', 'content:clip', '2026-09-01T00:00:00Z',
              'https://fixture.invalid/newly-discovered-original',
              repeat('f',64),'FIXTURE','v2','CLEARED');
        """)
        self.assertEqual(self.sql(
            "SELECT id FROM content_capture WHERE content_id='content:clip' "
            "ORDER BY observed_at DESC LIMIT 1;"), "capture:content:clip")
        with self.assertRaisesRegex(ValueError, "PROVENANCE_STALE"):
            self.store.reserve(self.p, self.t, source_id="source:clip",
                               key="attempt:new-source-epoch", expected_revision=0)
        self.assertEqual(self.store.history(self.p.plan_id).revision, 0)

    def test_pinned_provenance_digest_is_immutable_after_registration(self):
        self.register()
        with self.assertRaisesRegex(RuntimeError, "DP241_PG_PLAN_PROVENANCE_IMMUTABLE"):
            self.sql("""
                UPDATE dp241_pg_plan
                   SET source_provenance_sha=repeat('a',64)
                 WHERE plan_id='""" + self.p.plan_id + """';
            """)
        self.assertEqual(self.store.read(self.p, self.t, source_id="source:clip").revision, 0)

    def test_restart_from_legacy_schema_with_existing_reservation_requires_new_plan(self):
        """Never backfill an original rights/provenance digest retroactively."""
        self.register()
        pending = self.store.reserve(self.p, self.t, source_id="source:clip",
                                     key="attempt:old-ledger", expected_revision=0)
        self.sql("ALTER TABLE dp241_pg_plan DROP COLUMN source_provenance_sha;")
        try:
            reopened = type(self.store)(self.dsn, allow_disposable_postgres=True)
            with self.assertRaisesRegex(ValueError, "DP241_PG_LEGACY_PLAN_UNPINNED"):
                reopened.install_fixture_schema()
            with self.assertRaisesRegex(ValueError, "DP241_PG_LEGACY_PLAN_UNPINNED"):
                reopened.read(self.p, self.t, source_id="source:clip")
            self.assertEqual(reopened.history(self.p.plan_id).pending_attempt_id,
                             pending.pending_attempt_id)
        finally:
            # Restore only the test's ephemeral cluster for inherited cases.
            # Never backfill/re-authorize the historical plan.
            self.sql("SET session_replication_role=replica; "
                     "TRUNCATE dp241_pg_event, dp241_pg_plan; "
                     "SET session_replication_role=origin;")
            self.sql("ALTER TABLE dp241_pg_plan ADD COLUMN source_provenance_sha "
                     "text NOT NULL CHECK(source_provenance_sha ~ '^[0-9a-f]{64}$');")

    def test_empty_legacy_schema_migrates_without_backfilling_a_rights_decision(self):
        """Safe additive upgrade is possible before any plan was registered."""
        self.sql("ALTER TABLE dp241_pg_plan DROP COLUMN source_provenance_sha;")
        resumed = type(self.store)(self.dsn, allow_disposable_postgres=True)
        resumed.install_fixture_schema()
        self.assertEqual(self.sql(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='dp241_pg_plan' AND column_name='source_provenance_sha';"),
            "1",
        )
        self.assertEqual(resumed.register(self.p, self.t, source_id="source:clip").revision, 0)


if __name__ == "__main__":
    unittest.main()
