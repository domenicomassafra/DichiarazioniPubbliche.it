"""DP-320 isolated transaction reference, not a live public/purge claim."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.revocation_epoch_fence import (  # noqa: E402
    IsolatedPublicationEpochStore,
    RevocationFenceHeld,
)

NOW = datetime(2026, 10, 11, 10, tzinfo=timezone.utc)
SHA = "a" * 64
ARTIFACT = "b" * 64


class RevocationEpochFenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "private-reference.sqlite"
        self.conn = sqlite3.connect(self.database, timeout=5)
        self.addCleanup(self.conn.close)
        self.store = IsolatedPublicationEpochStore(self.conn)
        self.store.init_fixture_schema()
        self.store.register_fixture_source("source:1", SHA)
        self.store.register_fixture_source("rights:1", "c" * 64)

    def ticket(self, *deps: str):
        return self.store.mint(release_id="public:1", dependency_ids=tuple(deps or ("source:1",)))

    def test_empty_or_unbound_sources_never_grant_public_ticket(self):
        with self.assertRaisesRegex(RevocationFenceHeld, "SCOPE"):
            self.store.mint(release_id="public:1", dependency_ids=())
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.ticket("source:unknown")
        with self.assertRaisesRegex(RevocationFenceHeld, "DUPLICATE"):
            self.ticket("source:1", "source:1")

    def test_exact_multi_source_barrier_revocation_blocks_artifact_and_reader(self):
        ticket = self.ticket("rights:1", "source:1")
        self.store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)
        self.assertTrue(self.store.check_served(ticket, ARTIFACT))
        epoch = self.store.revoke(source_id="rights:1", event_id="event:withdrawal:1", reason="RIGHTS_WITHDRAWN", now=NOW)
        self.assertEqual(epoch, 1)
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.store.check_served(ticket, ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.ticket("source:1", "rights:1")
        self.assertEqual(self.store.pending_invalidations(), (("event:withdrawal:1", "rights:1", 1),))

    def test_revocation_remains_held_even_after_outbox_ack_and_restart(self):
        ticket = self.ticket("source:1")
        self.store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)
        self.assertEqual(self.store.revoke(source_id="source:1", event_id="event:correction", reason="CORRECTION", now=NOW), 1)
        self.store.acknowledge(event_id="event:correction", epoch=1)
        self.assertEqual(self.store.pending_invalidations(), ())
        restarted = IsolatedPublicationEpochStore(sqlite3.connect(self.database))
        try:
            with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
                restarted.check_served(ticket, ARTIFACT)
            with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
                restarted.mint(release_id="public:2", dependency_ids=("source:1",))
        finally:
            restarted.conn.close()

    def test_repeat_event_is_idempotent_and_conflicting_replay_denied(self):
        self.assertEqual(self.store.revoke(source_id="source:1", event_id="event:1", reason="PRIVACY_HOLD", now=NOW), 1)
        self.assertEqual(self.store.revoke(source_id="source:1", event_id="event:1", reason="PRIVACY_HOLD", now=NOW), 1)
        self.assertEqual(len(self.store.pending_invalidations()), 1)
        for source, reason in (("rights:1", "PRIVACY_HOLD"), ("source:1", "CORRECTION")):
            with self.subTest(source=source, reason=reason), self.assertRaisesRegex(RevocationFenceHeld, "REPLAY_CONFLICT"):
                self.store.revoke(source_id=source, event_id="event:1", reason=reason, now=NOW)
        self.assertEqual(self.store.revoke(source_id="source:1", event_id="event:2", reason="SOURCE_SUPERSEDED", now=NOW), 2)

    def test_forged_token_epoch_or_material_hash_is_denied(self):
        ticket = self.ticket("source:1")
        item = ticket.dependencies[0]
        forged = replace(ticket, dependencies=(replace(item, material_sha256="0" * 64),))
        with self.assertRaisesRegex(RevocationFenceHeld, "TAMPERED"):
            self.store.publish_reference(ticket=forged, artifact_sha256=ARTIFACT)
        forged_epoch = replace(ticket, dependencies=(replace(item, epoch=1),))
        with self.assertRaisesRegex(RevocationFenceHeld, "TAMPERED"):
            self.store.publish_reference(ticket=forged_epoch, artifact_sha256=ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "HASH_INVALID"):
            self.store.publish_reference(ticket=ticket, artifact_sha256="private payload")
        self.store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "RELEASE_ID_CONFLICT"):
            self.store.publish_reference(ticket=ticket, artifact_sha256="f" * 64)

    def test_unapproved_restore_is_not_possible_by_reseeding(self):
        self.store.revoke(source_id="source:1", event_id="event:1", reason="REVIEW_REVOKED", now=NOW)
        self.store.register_fixture_source("source:1", "d" * 64)
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.ticket("source:1")

    def test_revocation_and_release_transactions_serialize(self):
        ticket = self.ticket("source:1")
        barrier = threading.Barrier(2)
        results: list[str] = []

        def perform(action: str):
            connection = sqlite3.connect(self.database, timeout=5)
            try:
                store = IsolatedPublicationEpochStore(connection)
                barrier.wait(timeout=5)
                if action == "publish":
                    try:
                        store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)
                        results.append("PUBLISHED_BEFORE_REVOKE")
                    except RevocationFenceHeld:
                        results.append("PUBLISH_HELD")
                else:
                    store.revoke(source_id="source:1", event_id="event:race", reason="SOURCE_SUPERSEDED", now=NOW)
                    results.append("REVOKED")
            finally:
                connection.close()

        writers = [threading.Thread(target=perform, args=(what,)) for what in ("publish", "revoke")]
        for thread in writers:
            thread.start()
        for thread in writers:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive(), "SQLite isolated transaction race deadlocked")
        self.assertIn("REVOKED", results)
        self.assertTrue("PUBLISH_HELD" in results or "PUBLISHED_BEFORE_REVOKE" in results)
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.store.check_served(ticket, ARTIFACT)
        self.assertEqual(self.store.pending_invalidations(), (("event:race", "source:1", 1),))

    def test_read_fence_keeps_revocation_from_committing_mid_read(self):
        """A public read cannot accept an artifact after revoke commits."""
        ticket = self.ticket("source:1")
        self.store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)
        reading_publication = threading.Event()
        release_read = threading.Event()
        outcomes: list[object] = []

        def read():
            connection = sqlite3.connect(self.database, timeout=5)

            def pause_before_publication(sql: str):
                if sql.startswith("SELECT artifact_sha256,fence_sha256 FROM epoch_publication"):
                    reading_publication.set()
                    release_read.wait(timeout=5)

            connection.set_trace_callback(pause_before_publication)
            try:
                store = IsolatedPublicationEpochStore(connection)
                outcomes.append(store.check_served(ticket, ARTIFACT))
            except BaseException as error:
                outcomes.append(error)
            finally:
                connection.close()

        reader = threading.Thread(target=read)
        reader.start()
        try:
            self.assertTrue(reading_publication.wait(timeout=3))
            # The second writer either acquires BEGIN IMMEDIATE at once (bug)
            # or is refused by the in-flight read transaction (safe).
            writer_conn = sqlite3.connect(self.database, timeout=0)
            try:
                writer = IsolatedPublicationEpochStore(writer_conn)
                with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                    writer.revoke(
                        source_id="source:1", event_id="event:read-race",
                        reason="RIGHTS_WITHDRAWN", now=NOW,
                    )
            finally:
                writer_conn.close()
        finally:
            release_read.set()
            reader.join(timeout=8)
        self.assertFalse(reader.is_alive())
        self.assertEqual(outcomes, [True])
        self.assertEqual(
            self.store.revoke(
                source_id="source:1", event_id="event:read-race",
                reason="RIGHTS_WITHDRAWN", now=NOW,
            ),
            1,
        )
        with self.assertRaisesRegex(RevocationFenceHeld, "STALE_OR_HELD"):
            self.store.check_served(ticket, ARTIFACT)

    def test_rejected_read_releases_transaction_for_subsequent_revocation(self):
        ticket = self.ticket("source:1")
        self.store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "ARTIFACT_UNMATCHED"):
            self.store.check_served(ticket, "e" * 64)
        self.assertEqual(
            self.store.revoke(
                source_id="source:1", event_id="event:after-bad-read",
                reason="RIGHTS_WITHDRAWN", now=NOW,
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
