"""DP-320 PostgreSQL-only reference: adversarial transaction and restart proof."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests.test_claim_evidence_retrieval_replay import _bin, _cmd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.revocation_epoch_fence import RevocationFenceHeld  # noqa: E402
from dichiarazioni_pubbliche.revocation_pg_fence_v1 import (  # noqa: E402
    IsolatedPostgresRevocationFence,
)


NOW = "2026-10-12T00:00:00+00:00"
RIGHTS = "a" * 64
SOURCE = "b" * 64
ARTIFACT = "f" * 64


class IsolatedPostgresRevocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary in ("initdb", "pg_ctl", "psql"):
            _bin(binary)
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp320-fence-pg-")
        cls.pgdata = Path(cls.tmp.name) / "pg"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.pgctl = _bin("pg_ctl")
        cls.started = False
        try:
            _cmd([_bin("initdb"), "-D", str(cls.pgdata), "--username=postgres",
                  "--auth=trust", "--no-locale", "--encoding=UTF8"])
            _cmd([cls.pgctl, "-D", str(cls.pgdata), "-l", str(Path(cls.tmp.name) / "pg.log"),
                  "-o", f"-F -p {cls.port} -h 127.0.0.1 -k {cls.tmp.name}", "-w", "start"])
            cls.started = True
            admin_dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
            _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", admin_dsn],
                 stdin="CREATE DATABASE dp320_test_fence;")
            cls.dsn = f"postgresql://postgres@127.0.0.1:{cls.port}/dp320_test_fence"
            _cmd([_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", cls.dsn],
                 stdin=(ROOT / "db" / "schema.v1.sql").read_text(encoding="utf-8"))
            cls.store = IsolatedPostgresRevocationFence(cls.dsn)
            cls.store.install_fixture_schema()
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            _cmd([cls.pgctl, "-D", str(cls.pgdata), "-m", "immediate", "-w", "stop"])
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @classmethod
    def sql(cls, query):
        return _cmd([_bin("psql"), "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                     "-d", cls.dsn], stdin=query)

    def setUp(self):
        self.sql("TRUNCATE dp320_pg_ack, dp320_pg_outbox, dp320_pg_revocation, "
                 "dp320_pg_publication, dp320_pg_source CASCADE;")
        self.store.register_fixture_source("rights:1", RIGHTS)
        self.store.register_fixture_source("source:1", SOURCE)

    def ticket(self):
        return self.store.mint(release_id="release:one", dependency_ids=("source:1", "rights:1"))

    def test_canonical_pg_and_stale_publish_or_read_after_revocation(self):
        self.assertEqual(self.sql("SELECT COUNT(*) FROM content_item;"), "0")
        issued = self.ticket()
        self.store.publish_reference(ticket=issued, artifact_sha256=ARTIFACT)
        self.assertTrue(self.store.check_served(ticket=issued, artifact_sha256=ARTIFACT))
        self.assertEqual(self.store.revoke(source_id="rights:1", event_id="revocation:first",
                                           reason="RIGHTS_WITHDRAWN", occurred_at=NOW), 1)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self.store.publish_reference(ticket=issued, artifact_sha256=ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self.store.check_served(ticket=issued, artifact_sha256=ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self.ticket()
        self.assertEqual(self.store.pending_invalidations(), (("revocation:first", "rights:1", 1),))
        self.store.acknowledge(event_id="revocation:first", epoch=1)
        self.assertEqual(self.store.pending_invalidations(), ())
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self.store.check_served(ticket=issued, artifact_sha256=ARTIFACT)

    def test_restart_replay_conflicts_and_outbox_durability(self):
        self.assertEqual(self.store.revoke(source_id="rights:1", event_id="revocation:retry",
                                           reason="PRIVACY_HOLD", occurred_at=NOW), 1)
        restarted = IsolatedPostgresRevocationFence(self.dsn)
        self.assertEqual(restarted.revoke(source_id="rights:1", event_id="revocation:retry",
                                          reason="PRIVACY_HOLD", occurred_at=NOW), 1)
        self.assertEqual(restarted.pending_invalidations(), (("revocation:retry", "rights:1", 1),))
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_REPLAY_CONFLICT"):
            restarted.revoke(source_id="source:1", event_id="revocation:retry",
                             reason="PRIVACY_HOLD", occurred_at=NOW)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_REPLAY_CONFLICT"):
            restarted.revoke(source_id="rights:1", event_id="revocation:retry",
                             reason="CORRECTION", occurred_at=NOW)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_REPLAY_CONFLICT"):
            restarted.revoke(source_id="rights:1", event_id="revocation:retry",
                             reason="PRIVACY_HOLD", occurred_at="2026-10-13T00:00:00Z")
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_OUTBOX_ACK_STALE"):
            restarted.acknowledge(event_id="revocation:retry", epoch=2)
        restarted.acknowledge(event_id="revocation:retry", epoch=1)
        restarted.acknowledge(event_id="revocation:retry", epoch=1)
        self.assertEqual(restarted.pending_invalidations(), ())
        self.assertEqual(restarted.revoke(source_id="rights:1", event_id="revocation:next",
                                          reason="RIGHTS_EXPIRED", occurred_at=NOW), 2)
        self.assertEqual(restarted.pending_invalidations(), (("revocation:next", "rights:1", 2),))
        self.assertEqual(self.sql("SELECT epoch||':'||status FROM dp320_pg_source "
                                  "WHERE source_id='rights:1';"), "2:HELD")

    def _interactive(self):
        return subprocess.Popen([_bin("psql"), "-X", "-q", "-A", "-t", "-v",
                                 "ON_ERROR_STOP=1", "-d", self.dsn],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1)

    def _at_barrier(self, sql):
        process = self._interactive()
        process.stdin.write("SET statement_timeout='5000ms'; "
                            "SET lock_timeout='5000ms'; "
                            "SET idle_in_transaction_session_timeout='8000ms';\n"
                            + sql + "\n\\echo DP320_BARRIER\n")
        process.stdin.flush()
        try:
            for _ in range(5):
                if process.stdout.readline().strip() == "DP320_BARRIER":
                    break
            else:
                self.fail("interactive PostgreSQL transaction did not reach barrier")
        except BaseException:
            process.kill()
            process.communicate(timeout=5)
            raise
        return process

    def _release(self, process, *, commit=True):
        process.stdin.write(("COMMIT;" if commit else "ROLLBACK;") + "\n")
        process.stdin.close()
        process.wait(timeout=8)
        self.assertEqual(process.returncode, 0, process.stderr.read())
        process.stdout.close()
        process.stderr.close()

    def _waiting(self, contains):
        # Observe a *separate* PostgreSQL backend blocked on the record lock.
        for _ in range(100):
            state = self.sql("SELECT COUNT(*) FROM pg_stat_activity WHERE "
                             "wait_event_type='Lock' AND state='active' "
                             "AND pid<>pg_backend_pid() "
                             "AND query NOT LIKE '%pg_stat_activity%' "
                             f"AND query LIKE '%{contains}%';")
            if state and int(state) > 0:
                return
            time.sleep(0.025)
        self.fail("expected concurrent PostgreSQL transaction waiting for row lock")

    def test_revoke_commits_before_waiting_publish_and_read(self):
        old = self.ticket()
        self.store.publish_reference(ticket=old, artifact_sha256=ARTIFACT)
        # Transaction A locks rights. Transaction B queues the revoke behind A.
        holder = self._at_barrier("BEGIN; SELECT source_id FROM dp320_pg_source "
                                  "WHERE source_id='rights:1' FOR UPDATE;")
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                revoked = pool.submit(self.store.revoke, source_id="rights:1",
                                      event_id="revocation:raced", reason="RIGHTS_WITHDRAWN",
                                      occurred_at=NOW)
                self._waiting("dp320_pg_revoke")
                published = pool.submit(self.store.publish_reference, ticket=old,
                                        artifact_sha256=ARTIFACT)
                served = pool.submit(self.store.check_served, ticket=old,
                                     artifact_sha256=ARTIFACT)
                self._release(holder)
                self.assertEqual(revoked.result(timeout=10), 1)
                for candidate in (published, served):
                    with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
                        candidate.result(timeout=10)
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.communicate(timeout=5)

    def test_publish_commits_first_then_revocation_invalidates_prior_reference(self):
        ticket = self.ticket()
        # Publish holds the same PostgreSQL row lock until commit; revoke cannot
        # increment epoch in the gap between validation and reference insert.
        dependencies = json.dumps([vars(dep) for dep in ticket.dependencies])
        holder = self._at_barrier(
            "BEGIN; SELECT dp320_pg_publish('release:one', '" + ARTIFACT +
            "', '" + ticket.fingerprint + "', '" + dependencies + "'::jsonb);"
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                revoke = pool.submit(self.store.revoke, source_id="rights:1",
                                     event_id="revocation:after-publish", reason="CORRECTION",
                                     occurred_at=NOW)
                self._waiting("dp320_pg_revoke")
                # The durable publication reference is still uncommitted and
                # revocation cannot advance its epoch before this commit.
                self.assertEqual(self.sql("SELECT COUNT(*) FROM dp320_pg_publication;"), "0")
                self.assertEqual(self.sql("SELECT epoch FROM dp320_pg_source "
                                          "WHERE source_id='rights:1';"), "0")
                self._release(holder)
                self.assertEqual(revoke.result(timeout=10), 1)
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.communicate(timeout=5)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dp320_pg_publication;"), "1")
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self.store.check_served(ticket=ticket, artifact_sha256=ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self.store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)

    def test_material_version_mutation_denies_ticket_and_no_registration_restore(self):
        old = self.ticket()
        self.sql("UPDATE dp320_pg_source SET material_sha256=repeat('c',64) "
                 "WHERE source_id='source:1';")
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self.store.publish_reference(ticket=old, artifact_sha256=ARTIFACT)
        updated = self.ticket()
        self.assertNotEqual(old.fingerprint, updated.fingerprint)
        self.store.revoke(source_id="source:1", event_id="revocation:version",
                          reason="SOURCE_SUPERSEDED", occurred_at=NOW)
        self.store.register_fixture_source("source:1", SOURCE)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_STALE_OR_HELD"):
            self.store.publish_reference(ticket=updated, artifact_sha256=ARTIFACT)
        self.assertEqual(self.sql("SELECT epoch||':'||status FROM dp320_pg_source "
                                  "WHERE source_id='source:1';"), "1:HELD")

    def test_crashed_transaction_cannot_commit_revocation_without_outbox(self):
        aborted = self._at_barrier("BEGIN; SELECT dp320_pg_revoke("
                                    "'rights:1','revocation:crashed','PRIVACY_HOLD',"
                                    "'2026-10-12T00:00:00Z'::timestamptz);")
        aborted.kill()
        aborted.communicate(timeout=5)
        self.assertEqual(self.sql("SELECT epoch||':'||status FROM dp320_pg_source "
                                  "WHERE source_id='rights:1';"), "0:ACTIVE")
        self.assertEqual(self.store.pending_invalidations(), ())
        self.assertEqual(self.store.revoke(source_id="rights:1", event_id="revocation:crashed",
                                           reason="PRIVACY_HOLD", occurred_at=NOW), 1)
        self.assertEqual(self.store.pending_invalidations(), (("revocation:crashed", "rights:1", 1),))

    def test_immutable_revocation_event_and_release_conflict(self):
        ticket = self.ticket()
        self.store.publish_reference(ticket=ticket, artifact_sha256=ARTIFACT)
        with self.assertRaisesRegex(RevocationFenceHeld, "FENCE_RELEASE_ID_CONFLICT"):
            self.store.publish_reference(ticket=ticket, artifact_sha256="c" * 64)
        self.store.revoke(source_id="rights:1", event_id="revocation:immutable",
                          reason="RIGHTS_WITHDRAWN", occurred_at=NOW)
        for table in ("dp320_pg_revocation", "dp320_pg_outbox"):
            proc = subprocess.run([_bin("psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1",
                                   "-d", self.dsn], input=f"UPDATE {table} SET epoch=99;",
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("append-only", proc.stderr)
        self.assertEqual(self.store.pending_invalidations(),
                         (("revocation:immutable", "rights:1", 1),))


if __name__ == "__main__":
    unittest.main()
