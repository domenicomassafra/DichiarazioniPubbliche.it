"""DP518: canonical, disposable PostgreSQL private release-currentness tests."""

from __future__ import annotations

import json
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor

from tests import test_dp320_revocation_pg_next as pg
from tests.test_claim_evidence_retrieval_replay import _bin
from dichiarazioni_pubbliche.ops.release_currentness_pg_v1 import (
    DisposableReleaseCurrentnessPg,
)
from dichiarazioni_pubbliche.revocation_epoch_fence import RevocationFenceHeld


PROJECTION = "1" * 64
INDEX = "2" * 64
GENERATION = "3" * 64
ALTERNATE = "4" * 64
TIME = "2026-10-12T07:00:00Z"


class ReleaseCurrentnessPgTests(unittest.TestCase):
    _interactive = pg.IsolatedPostgresRevocationTests._interactive
    _at_barrier = pg.IsolatedPostgresRevocationTests._at_barrier
    _waiting = pg.IsolatedPostgresRevocationTests._waiting
    _release = pg.IsolatedPostgresRevocationTests._release
    @classmethod
    def setUpClass(cls):
        pg.IsolatedPostgresRevocationTests.setUpClass.__func__(cls)
        cls.reader = DisposableReleaseCurrentnessPg(cls.dsn)
        cls.reader.install_disposable_schema()

    @classmethod
    def tearDownClass(cls):
        pg.IsolatedPostgresRevocationTests.tearDownClass.__func__(cls)

    @classmethod
    def sql(cls, query):
        return pg.IsolatedPostgresRevocationTests.sql.__func__(cls, query)

    def setUp(self):
        self.sql(
            "TRUNCATE dp518_pg_selection, dp518_pg_current, dp518_pg_release, "
            "dp320_pg_ack, dp320_pg_outbox, dp320_pg_revocation, "
            "dp320_pg_publication, dp320_pg_source CASCADE;"
        )
        self.sql("INSERT INTO dp518_pg_current(singleton,revision,release_id)"
                 " VALUES(true,0,NULL);")
        self.store.register_fixture_source("rights:1", pg.RIGHTS)
        self.store.register_fixture_source("source:1", pg.SOURCE)

    def _ticket(self, release="release:one"):
        ticket = self.store.mint(
            release_id=release, dependency_ids=("source:1", "rights:1")
        )
        self.store.publish_reference(ticket=ticket, artifact_sha256=pg.ARTIFACT)
        return ticket

    def _select(self, ticket, *, event="selection:one", expected=0, index=INDEX):
        return self.reader.select_private_reference(
            ticket=ticket, artifact_sha256=pg.ARTIFACT,
            projection_sha256=PROJECTION, index_sha256=index,
            generation_sha256=GENERATION, event_id=event,
            expected_revision=expected,
        )

    def _read(self, *, release="release:one", index=INDEX,
              generation=GENERATION, epoch=1):
        return self.reader.read_private_reference(
            release_id=release, index_sha256=index,
            projection_sha256=PROJECTION, generation_sha256=generation,
            expected_revision=epoch,
        )

    def test_no_reference_never_promotes_empty_source_to_public_current(self):
        result = self._read(epoch=0)
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason, "NO_REFERENCE")
        self.assertFalse(result.publication_authorized)
        self.assertFalse(result.host_ack_verified)
        self.assertFalse(result.cdn_ack_verified)
        self.assertRegex(result.opaque_version, r"^[0-9a-f]{64}$")

    def test_exact_dp320_release_selected_then_private_readback_restart(self):
        ticket = self._ticket()
        receipt = self._select(ticket)
        self.assertEqual(receipt["revision"], 1)
        restarted = DisposableReleaseCurrentnessPg(self.dsn)
        current = restarted.read_private_reference(
            release_id=ticket.release_id, index_sha256=INDEX,
            projection_sha256=PROJECTION, generation_sha256=GENERATION,
            expected_revision=1,
        )
        self.assertEqual(current.status, "COHERENT_PRIVATE_REFERENCE")
        self.assertEqual(current.reason, "PRIVATE_ONLY_NOT_DEPLOYED")
        self.assertFalse(current.publication_authorized)
        self.assertEqual(current.pending_invalidations, 0)
        self.assertRegex(current.opaque_version, r"^[0-9a-f]{64}$")
        self.assertNotIn("rights:1", repr(current))
        self.assertNotIn("source:1", repr(current))
        self.assertEqual(self.sql("SELECT count(*) FROM dp518_pg_selection"), "1")

    def test_generation_drift_held_after_pointer_selection(self):
        self._select(self._ticket())
        current = self._read()
        self.assertEqual(current.status, "COHERENT_PRIVATE_REFERENCE")
        stale = self._read(generation="f" * 64)
        self.assertEqual(stale.status, "HELD")
        self.assertEqual(stale.reason, "RELEASE_VERSION_MISMATCH")
        self.assertFalse(stale.publication_authorized)

    def test_revocation_precedes_currentness_even_after_synthetic_ack(self):
        ticket = self._ticket()
        self._select(ticket)
        original = self._read()
        self.assertEqual(
            self.store.revoke(source_id="rights:1", event_id="revoke:rights",
                              reason="RIGHTS_WITHDRAWN", occurred_at=TIME), 1
        )
        pending = self._read()
        self.assertEqual(pending.status, "HELD")
        self.assertGreaterEqual(pending.pending_invalidations, 1)
        self.assertNotEqual(pending.opaque_version, original.opaque_version)
        self.store.acknowledge(event_id="revoke:rights", epoch=1)
        again = self._read()
        self.assertEqual(again.status, "HELD")
        self.assertEqual(again.pending_invalidations, 0)
        self.assertEqual(again.acknowledgements, 1)
        self.assertFalse(again.cdn_ack_verified)
        self.assertNotEqual(again.opaque_version, original.opaque_version)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self._select(ticket, event="selection:reuse", expected=1)

    def test_correction_changes_epoch_and_old_pinned_search_denied(self):
        ticket = self._ticket()
        self._select(ticket)
        self.store.revoke(source_id="source:1", event_id="revoke:correction",
                          reason="CORRECTION", occurred_at=TIME)
        result = self._read()
        self.assertEqual(result.status, "HELD")
        self.assertFalse(result.publication_authorized)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp320_pg_revocation"), "1")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp320_pg_outbox"), "1")

    def test_partial_replay_and_release_id_conflict_fail_closed(self):
        ticket = self._ticket()
        first = self._select(ticket)
        other = DisposableReleaseCurrentnessPg(self.dsn)
        self.assertEqual(other.select_private_reference(
            ticket=ticket, artifact_sha256=pg.ARTIFACT,
            projection_sha256=PROJECTION, index_sha256=INDEX,
            generation_sha256=GENERATION, event_id="selection:one",
            expected_revision=0,
        ), first)
        self.assertEqual(self._select(ticket), first)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp518_pg_selection"), "1")
        with self.assertRaisesRegex(RevocationFenceHeld, "DP518_RELEASE_ID_CONFLICT"):
            self._select(ticket, index=ALTERNATE)
        with self.assertRaisesRegex(RevocationFenceHeld, "DP518_REVISION_CONFLICT"):
            self._select(ticket, event="selection:second", expected=0)
        self.assertEqual(self._read(index=ALTERNATE).status, "HELD")

    def test_switch_pointer_rejects_old_release_and_rollback_pointer_version(self):
        first = self._ticket()
        self._select(first)
        second = self._ticket("release:two")
        self._select(second, event="selection:two", expected=1, index=ALTERNATE)
        old = self._read()
        self.assertEqual(old.status, "HELD")
        self.assertEqual(old.reason, "RELEASE_VERSION_MISMATCH")
        self.assertEqual(self._read(release="release:two", index=ALTERNATE, epoch=2).status,
                         "COHERENT_PRIVATE_REFERENCE")
        with self.assertRaisesRegex(RevocationFenceHeld, "DP518_REVISION_CONFLICT"):
            self._select(first, event="selection:rollback", expected=1)
        with self.assertRaisesRegex(RevocationFenceHeld, "DP518_SELECTION_REPLAY_STALE"):
            self._select(first)
        self.assertEqual(self.sql("SELECT count(*) FROM dp518_pg_selection"), "2")

    def test_direct_pointer_rollback_cannot_resurrect_old_release(self):
        first = self._ticket()
        self._select(first)
        second = self._ticket("release:two")
        self._select(second, event="selection:two", expected=1, index=ALTERNATE)
        self.sql("UPDATE dp518_pg_current SET revision=1,"
                 "release_id='release:one' WHERE singleton=true;")
        stale = self._read(release="release:one", index=INDEX, epoch=1)
        self.assertEqual(stale.status, "HELD")
        self.assertEqual(stale.reason, "SELECTION_INTEGRITY_FAILURE")
        with self.assertRaisesRegex(RevocationFenceHeld, "DP518_POINTER_HISTORY_DRIFT"):
            self._select(first, event="selection:rollback-forged", expected=1)

    def test_unacked_unrelated_event_holds_all_selection_until_local_ack(self):
        ticket = self._ticket()
        self._select(ticket)
        self.store.register_fixture_source("rights:unrelated", pg.RIGHTS)
        self.store.revoke(source_id="rights:unrelated", event_id="revoke:elsewhere",
                          reason="PRIVACY_HOLD", occurred_at=TIME)
        self.assertEqual(self._read().status, "HELD")
        self.store.acknowledge(event_id="revoke:elsewhere", epoch=1)
        self.assertEqual(self._read().status, "COHERENT_PRIVATE_REFERENCE")
        self.assertFalse(self._read().cdn_ack_verified)

    def test_missing_outbox_for_immutable_revocation_fails_even_after_ack(self):
        ticket = self._ticket()
        self._select(ticket)
        self.store.revoke(source_id="rights:1", event_id="revoke:missing-outbox",
                          reason="RIGHTS_EXPIRED", occurred_at=TIME)
        # Simulate a corrupt source DB by disabling only the fixture's append-only
        # trigger, never a production path.
        self.sql("ALTER TABLE dp320_pg_outbox DISABLE TRIGGER dp320_outbox_immutable;"
                 "DELETE FROM dp320_pg_outbox;"
                 "ALTER TABLE dp320_pg_outbox ENABLE TRIGGER dp320_outbox_immutable;")
        stale = self._read()
        self.assertEqual(stale.status, "HELD")
        self.assertEqual(stale.reason, "OUTBOX_INTEGRITY_FAILURE")
        self.assertEqual(stale.revocation_events, 1)
        self.assertFalse(stale.publication_authorized)

    def test_material_hash_change_without_revocation_fails_closed(self):
        ticket = self._ticket()
        self._select(ticket)
        self.sql("UPDATE dp320_pg_source SET material_sha256=repeat('c',64)"
                 " WHERE source_id='source:1';")
        self.assertEqual(self._read().status, "HELD")
        self.assertNotEqual(self._read().reason, "PRIVATE_ONLY_NOT_DEPLOYED")

    def test_concurrent_revoke_first_blocks_local_currentness(self):
        ticket = self._ticket()
        self._select(ticket)
        holder = self._at_barrier(
            "BEGIN; SELECT dp320_pg_revoke('rights:1','revoke:race',"
            "'PRIVACY_HOLD','2026-10-12T07:00:00Z'::timestamptz);")
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._read)
                self._waiting("dp518_pg_probe")
                self._release(holder)
                result = future.result(timeout=12)
            self.assertEqual(result.status, "HELD")
            self.assertEqual(result.pending_invalidations, 1)
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.communicate(timeout=5)

    def test_uncommitted_selection_first_serializes_later_revoke(self):
        ticket = self._ticket()
        dependencies = json.dumps([vars(dep) for dep in ticket.dependencies])
        holder = self._at_barrier(
            "BEGIN; SELECT dp518_pg_select('release:one','" + pg.ARTIFACT +
            "','" + ticket.fingerprint + "','" + dependencies + "'::jsonb,'" +
            PROJECTION + "','" + INDEX + "','" + GENERATION +
            "','selection:held',0);")
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                revoked = pool.submit(
                    self.store.revoke, source_id="rights:1",
                    event_id="revoke:queued", reason="CORRECTION", occurred_at=TIME)
                self._waiting("dp320_pg_revoke")
                self.assertEqual(self.sql("SELECT count(*) FROM dp518_pg_selection"), "0")
                self.assertEqual(self.sql("SELECT epoch FROM dp320_pg_source "
                                          "WHERE source_id='rights:1'"), "0")
                self._release(holder)
                self.assertEqual(revoked.result(timeout=12), 1)
            self.assertEqual(self.sql("SELECT count(*) FROM dp518_pg_selection"), "1")
            self.assertEqual(self._read().status, "HELD")
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.communicate(timeout=5)

    def test_two_different_release_selections_cannot_commit_same_revision(self):
        first = self._ticket()
        second = self._ticket("release:two")

        def compete(ticket, event):
            try:
                return self._select(ticket, event=event)["revision"]
            except RevocationFenceHeld as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            attempts = [
                pool.submit(compete, first, "selection:race:first"),
                pool.submit(compete, second, "selection:race:second"),
            ]
            self.assertEqual(
                {entry.result(timeout=12) for entry in attempts},
                {1, "DP518_REVISION_CONFLICT"},
            )
        self.assertEqual(self.sql("SELECT count(*) FROM dp518_pg_selection"), "1")

    def test_conflicting_event_or_missing_dp320_publication_never_selects(self):
        ticket = self._ticket()
        self._select(ticket)
        alternate = self._ticket("release:two")
        with self.assertRaisesRegex(RevocationFenceHeld, "DP518_SELECTION_REPLAY_CONFLICT"):
            self._select(alternate, event="selection:one", expected=1)
        self.sql("DELETE FROM dp320_pg_publication WHERE release_id='release:two';")
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_PUBLIC_ARTIFACT_UNMATCHED"):
            self._select(alternate, event="selection:three", expected=1)

    def test_append_only_selection_and_atomic_rollback_after_event(self):
        ticket = self._ticket()
        self.sql("""CREATE OR REPLACE FUNCTION dp518_test_abort() RETURNS trigger
          LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'DP518_TEST_ABORT'; END $$;
          CREATE TRIGGER dp518_abort_select BEFORE UPDATE ON dp518_pg_current
          FOR EACH ROW EXECUTE FUNCTION dp518_test_abort();""")
        try:
            with self.assertRaisesRegex(RevocationFenceHeld, "DP518_TEST_ABORT"):
                self._select(ticket)
        finally:
            self.sql("DROP TRIGGER dp518_abort_select ON dp518_pg_current;")
        self.assertEqual(self.sql("SELECT count(*) FROM dp518_pg_selection"), "0")
        self.assertEqual(self.sql("SELECT revision FROM dp518_pg_current"), "0")
        self._select(ticket)
        proc = subprocess.run(
            [_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", self.dsn],
            input="UPDATE dp518_pg_selection SET revision=3;",
            text=True, capture_output=True, timeout=10,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("append-only", proc.stderr)


if __name__ == "__main__":
    unittest.main()
