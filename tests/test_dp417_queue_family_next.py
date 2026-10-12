"""DP-417: actually persisted Collection-scoped changed/blocked Capture inbox.

The only writes below are synthetic fixture rows in a disposable local PG;
the reader itself executes a single bounded SELECT and cannot approve actions.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime  # noqa: E402
from dichiarazioni_pubbliche.studio_discovery_triage_reader import (  # noqa: E402
    _CAPTURE_QUEUE_SQL, read_capture_triage_queue,
)


def capture_row(**updates):
    return {
        "id": "capture:new", "content_id": "content:one",
        "previous_capture_id": "capture:old", "capture_status": "CAPTURED",
        "hold_status": "NONE", "archive_status": "NOT_REQUESTED",
        "rights_status": "UNKNOWN", "source_changed": True,
        "lifecycle_event_id": "event:one",
    } | updates


def packet(**updates):
    return {
        "collection_id": "collection:one", "collection_status": "ACTIVE",
        "cursor_valid": True, "rows": [capture_row()],
        "snapshot_sha256": "a" * 64, "snapshot_valid": True,
    } | updates


class FakeReadStore:
    def __init__(self, row=None, error=None):
        self.row, self.error, self.calls = row, error, []

    def run(self, sql, **variables):
        self.calls.append((sql, variables))
        if self.error:
            raise self.error
        return "" if self.row is None else json.dumps(self.row)


class CaptureQueueContractTests(unittest.TestCase):
    def test_new_changed_capture_is_real_inspection_queue_not_approval(self):
        store = FakeReadStore(packet(rows=[
            capture_row(),
            capture_row(id="capture:next", content_id="content:two",
                        previous_capture_id="capture:older"),
        ]))
        value = read_capture_triage_queue(
            store, collection_id="collection:one", limit=1,
        )
        self.assertEqual(value["results"], [{
            "queue_family": "CHANGED_CAPTURE", "collection_id": "collection:one",
            "content_id": "content:one", "capture_id": "capture:new",
            "previous_capture_id": "capture:old", "lifecycle_event_id": "event:one",
            "source_changed": True, "state": "NEEDS_REVIEW",
            "blockers": ["CAPTURE_CHANGE_REVIEW_REQUIRED",
                         "PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED",
                         "CAPTURE_REVIEW_AUTHORITY_NOT_EVALUATED"],
            "retry_condition": "AFTER_PRIVATE_CAPTURE_REVIEW",
        }])
        self.assertEqual(value["next_after_capture_id"], "capture:new")
        self.assertFalse(value["triage_action_authorized"])
        self.assertFalse(value["publication_authority"])
        self.assertFalse(value["rights_clearance"])
        self.assertTrue(value["private_only"])
        self.assertTrue(value["read_only"])
        sql, args = store.calls[0]
        self.assertEqual(sql, _CAPTURE_QUEUE_SQL)
        self.assertEqual(args, {"collection_id": "collection:one", "after_id": "", "limit": 1,
                          "expected_snapshot_sha256": ""})
        for relation in ("research_collection_content", "content_capture",
                         "capture_lifecycle_event", "member.status='INCLUDED'"):
            self.assertIn(relation, sql)
        self.assertIn("REPEATABLE READ READ ONLY", sql)
        self.assertNotIn("canonical_url", sql)
        self.assertNotIn("body_ref", sql)
        self.assertNotIn("normalized_statement", sql)
        self.assertNotIn("source_text", json.dumps(value))

    def test_blocked_quarantine_purge_hold_and_archive_retry_are_reasoned(self):
        cases = (
            ({"capture_status": "QUARANTINED", "source_changed": False, "previous_capture_id": None},
             "CAPTURE_QUARANTINED", "AFTER_QUARANTINE_REVIEW"),
            ({"capture_status": "PURGE_PENDING"},
             "CAPTURE_PURGE_PENDING", "AFTER_PURGE_LIFECYCLE_RESOLUTION"),
            ({"capture_status": "PURGED_BODY"},
             "CAPTURE_BODY_PURGED", "RECAPTURE_ONLY_AFTER_RIGHTS_REVIEW"),
            ({"hold_status": "RIGHTS_HOLD"},
             "CAPTURE_HOLD_ACTIVE", "AFTER_HOLD_RELEASE_AND_RIGHTS_REVIEW"),
            ({"archive_status": "FAILED"},
             "CAPTURE_ARCHIVE_FAILED", "AFTER_ARCHIVE_RETRY_REVIEW"),
        )
        for change, reason, retry in cases:
            with self.subTest(change=change):
                answer = read_capture_triage_queue(
                    FakeReadStore(packet(rows=[capture_row(**change)])),
                    collection_id="collection:one",
                )
                result = answer["results"][0]
                self.assertEqual(result["queue_family"], "BLOCKED_CAPTURE")
                self.assertEqual(result["state"], "BLOCKED")
                self.assertIn(reason, result["blockers"])
                self.assertEqual(result["retry_condition"], retry)
                self.assertNotIn("source_url", json.dumps(result))

    def test_deny_invalid_scope_cursors_forged_parents_extra_rows_and_store_secrets(self):
        bad_packets = (
            packet(collection_id="collection:private"),
            packet(cursor_valid=False),
            packet(rows=[capture_row(previous_capture_id=None, source_changed=False)]),
            packet(rows=[capture_row(capture_status="APPROVED")]),
            packet(rows=[capture_row(hold_status="UNSAFE")]),
            packet(rows=[capture_row(id="capture:two"), capture_row(id="capture:one")]),
            packet(rows=[capture_row(id="capture:new")] * 2),
            packet(rows=[capture_row(content_id="content:private", id="capture:secret",
                                     source_changed="yes")]),
        )
        for sample in bad_packets:
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                read_capture_triage_queue(FakeReadStore(sample), collection_id="collection:one")
        for invalid in ({"limit": 0}, {"limit": 31}, {"limit": True},
                        {"after_capture_id": "x\nPRIVATE"}, {"after_capture_id": True},
                        {"collection_id": "collection:../../private"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                read_capture_triage_queue(FakeReadStore(packet()), **(
                    {"collection_id": "collection:one"} | invalid
                ))
        with self.assertRaisesRegex(RuntimeError, "^STUDIO_CAPTURE_QUEUE_STORE_UNAVAILABLE$") as caught:
            read_capture_triage_queue(
                FakeReadStore(error=RuntimeError("PASSWORD=SECRET")), collection_id="collection:one",
            )
        self.assertNotIn("SECRET", str(caught.exception))


class PersistedCaptureQueueTests(unittest.TestCase):
    """True PostgreSQL SELECT, real canonical schema, never a production DB."""

    @classmethod
    def setUpClass(cls):
        if any(not shutil.which(binname) for binname in ("initdb", "pg_ctl", "psql")):
            raise unittest.SkipTest("PostgreSQL initdb/pg_ctl/psql unavailable")
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp417-queue-family-next-")
        cls.pgdata = Path(cls.tmp.name) / "data"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        cls.started = False
        try:
            init = subprocess.run(["initdb", "-D", str(cls.pgdata), "--username=postgres",
                                   "--auth=trust", "--no-locale"],
                                  capture_output=True, text=True)
            if init.returncode:
                raise AssertionError(init.stderr)
            start = subprocess.run(["pg_ctl", "-D", str(cls.pgdata), "-l",
                                    str(Path(cls.tmp.name) / "postgres.log"), "-o",
                                    f"-F -p {port} -h 127.0.0.1 -k {cls.tmp.name}",
                                    "-w", "start"], capture_output=True, text=True)
            if start.returncode:
                raise AssertionError(start.stderr)
            cls.started = True
            cls.store = PsqlRuntime(database_url=cls.url)
            cls.store.run((ROOT / "db/schema.v1.sql").read_text())
            cls.store.run("""
                INSERT INTO research_collection
                  (id, slug, name, scope_text, policy_version, status)
                VALUES ('collection:one', 'one', 'SECRET A', 'PRIVATE', 'v1', 'ACTIVE'),
                       ('collection:other', 'other', 'SECRET B', 'PRIVATE', 'v1', 'ACTIVE');
                INSERT INTO content_item (id, canonical_url, title, rights_status) VALUES
                  ('content:one', 'https://private.example/one', 'SECRET SOURCE', 'UNKNOWN'),
                  ('content:other', 'https://private.example/other', 'SECRET OTHER', 'UNKNOWN'),
                  ('content:removed', 'https://private.example/removed', 'SECRET REMOVED', 'UNKNOWN'),
                  ('content:unchanged', 'https://private.example/unchanged', 'SECRET UNCHANGED', 'UNKNOWN');
                INSERT INTO research_collection_content
                  (collection_id, content_id, inclusion_method, inclusion_version, status)
                VALUES ('collection:one','content:one','MANUAL','v1','INCLUDED'),
                       ('collection:other','content:other','MANUAL','v1','INCLUDED'),
                       ('collection:one','content:removed','MANUAL','v1','REMOVED'),
                       ('collection:one','content:unchanged','MANUAL','v1','INCLUDED');
                INSERT INTO content_capture
                  (id, content_id, observed_at, final_url, content_sha256,
                   retrieval_method, retrieval_version, status, rights_status)
                VALUES
                  ('capture:one-old','content:one','2026-10-01T09:00:00Z','https://private.example/one',
                   repeat('a',64),'HTTP','v1','CAPTURED','UNKNOWN'),
                  ('capture:one-new','content:one','2026-10-02T09:00:00Z','https://private.example/one',
                   repeat('b',64),'HTTP','v1','CAPTURED','UNKNOWN'),
                  ('capture:other','content:other','2026-10-02T09:00:00Z','https://private.example/other',
                   repeat('c',64),'HTTP','v1','QUARANTINED','UNKNOWN'),
                  ('capture:removed','content:removed','2026-10-02T09:00:00Z','https://private.example/removed',
                   repeat('d',64),'HTTP','v1','QUARANTINED','UNKNOWN'),
                  ('capture:unchanged','content:unchanged','2026-10-02T09:00:00Z','https://private.example/unchanged',
                   repeat('e',64),'HTTP','v1','CAPTURED','UNKNOWN');
                INSERT INTO capture_lifecycle_event
                  (id, capture_id, event_type, receipt) VALUES
                  ('event:old','capture:one-old','CAPTURE_REOBSERVED','{}'),
                  ('event:new','capture:one-new','PARSE_SUCCEEDED','{}');
                CREATE ROLE dp417_reader LOGIN;
                GRANT USAGE ON SCHEMA public TO dp417_reader;
                GRANT SELECT ON research_collection, research_collection_content,
                  content_capture, capture_lifecycle_event TO dp417_reader;
            """)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            if getattr(cls, "started", False):
                subprocess.run(["pg_ctl", "-D", str(cls.pgdata), "-m", "fast", "-w", "stop"],
                               capture_output=True, text=True)
        finally:
            if hasattr(cls, "tmp"):
                cls.tmp.cleanup()

    def setUp(self):
        # Each PostgreSQL test observes an isolated logical fixture state,
        # regardless of alphabetical execution order.
        self.store.run("""
            UPDATE research_collection_content SET status='INCLUDED'
            WHERE collection_id='collection:one' AND content_id='content:one';
            UPDATE content_capture SET hold_status='NONE'
            WHERE id='capture:one-new';
        """)

    def test_exact_collection_snapshot_provenance_and_exclusion(self):
        results = read_capture_triage_queue(self.store, collection_id="collection:one")
        self.assertEqual([row["capture_id"] for row in results["results"]], ["capture:one-new"])
        self.assertEqual(results["results"][0]["previous_capture_id"], "capture:one-old")
        self.assertEqual(results["results"][0]["lifecycle_event_id"], "event:new")
        self.assertNotIn("capture:other", json.dumps(results))
        self.assertNotIn("capture:removed", json.dumps(results))
        self.assertNotIn("capture:unchanged", json.dumps(results))
        for secret in ("private.example", "SECRET SOURCE", "repeat(", "content_sha256", "body_ref"):
            self.assertNotIn(secret, json.dumps(results))
        self.assertIsNone(results["next_after_capture_id"])
        self.assertTrue(results["read_only"])

    def test_revoked_single_capture_is_a_blocked_review_queue(self):
        # A rights-revoked Capture can be the only observed version. The
        # absence of a second Capture must not hide the operator exception.
        self.store.run("""
            UPDATE content_capture SET rights_status='REVOKED'
            WHERE id='capture:unchanged';
        """)
        try:
            observed = read_capture_triage_queue(
                self.store, collection_id="collection:one",
            )
            blocked = next((row for row in observed["results"]
                            if row["capture_id"] == "capture:unchanged"), None)
            self.assertIsNotNone(blocked)
            self.assertEqual(blocked["queue_family"], "BLOCKED_CAPTURE")
            self.assertIn("CAPTURE_RIGHTS_REVOKED", blocked["blockers"])
            self.assertIsNone(observed["next_after_capture_id"])
        finally:
            self.store.run("""
                UPDATE content_capture SET rights_status='UNKNOWN'
                WHERE id='capture:unchanged';
            """)

    def test_changed_to_hold_then_excluded_and_cursor_cannot_cross_parent(self):
        original = read_capture_triage_queue(self.store, collection_id="collection:one")
        self.assertEqual(original["results"][0]["queue_family"], "CHANGED_CAPTURE")
        self.store.run("UPDATE content_capture SET hold_status='RIGHTS_HOLD' WHERE id='capture:one-new'")
        blocked = read_capture_triage_queue(self.store, collection_id="collection:one")
        self.assertEqual(blocked["results"][0]["queue_family"], "BLOCKED_CAPTURE")
        self.assertIn("CAPTURE_HOLD_ACTIVE", blocked["results"][0]["blockers"])
        with self.assertRaises(ValueError):
            read_capture_triage_queue(self.store, collection_id="collection:other",
                                      after_capture_id="capture:one-new")
        self.store.run("UPDATE research_collection_content SET status='REMOVED'"
                       " WHERE collection_id='collection:one' AND content_id='content:one'")
        self.assertEqual(
            read_capture_triage_queue(self.store, collection_id="collection:one")["results"], [],
        )
        with self.assertRaises(ValueError):
            read_capture_triage_queue(self.store, collection_id="collection:one",
                                      after_capture_id="capture:one-new")

    def test_readonly_postgres_role_and_live_cursor_pagination(self):
        # The query runs with a database role that cannot write a single
        # capture/member/lifecycle row; it is not a production user.
        reader = PsqlRuntime(database_url=self.url.replace("postgres@", "dp417_reader@"))
        observed = read_capture_triage_queue(reader, collection_id="collection:other")
        self.assertEqual([r["capture_id"] for r in observed["results"]], ["capture:other"])
        self.assertEqual(observed["results"][0]["state"], "BLOCKED")
        with self.assertRaises(RuntimeError):
            reader.run("UPDATE content_capture SET status='CAPTURED' WHERE id='capture:other'")
        with self.assertRaises(ValueError):
            read_capture_triage_queue(reader, collection_id="collection:one",
                                      after_capture_id="capture:one-old")
        self.store.run("""
            INSERT INTO content_item (id, canonical_url) VALUES
                ('content:two', 'https://private.example/two');
            INSERT INTO research_collection_content
                (collection_id, content_id, inclusion_method, inclusion_version)
            VALUES ('collection:one','content:two','MANUAL','v1');
            INSERT INTO content_capture
                (id, content_id, observed_at, final_url, content_sha256,
                 retrieval_method, retrieval_version)
            VALUES
                ('capture:two-old','content:two','2026-10-01T00:00:00Z',
                 'https://private.example/two',repeat('f',64),'HTTP','v1'),
                ('capture:two-new','content:two','2026-10-02T00:00:00Z',
                 'https://private.example/two',repeat('0',64),'HTTP','v1');
        """)
        try:
            first = read_capture_triage_queue(
                reader, collection_id="collection:one", limit=1,
            )
            self.assertEqual([r["capture_id"] for r in first["results"]], ["capture:one-new"])
            self.assertEqual(first["next_after_capture_id"], "capture:one-new")
            second = read_capture_triage_queue(
                reader, collection_id="collection:one", limit=1,
                after_capture_id=first["next_after_capture_id"],
                expected_snapshot_sha256=first["snapshot_sha256"],
            )
            self.assertEqual([r["capture_id"] for r in second["results"]], ["capture:two-new"])
            self.assertIsNone(second["next_after_capture_id"])
            self.store.run(
                "UPDATE research_collection SET status='PAUSED' WHERE id='collection:one'"
            )
            paused = read_capture_triage_queue(reader, collection_id="collection:one")
            self.assertEqual([r["state"] for r in paused["results"]], ["BLOCKED", "BLOCKED"])
            self.assertTrue(all(
                "COLLECTION_NOT_ACTIVE" in r["blockers"] for r in paused["results"]
            ))
            self.assertTrue(all(
                r["retry_condition"] == "AFTER_COLLECTION_SCOPE_REVIEW"
                for r in paused["results"]
            ))
        finally:
            self.store.run("""
                UPDATE research_collection SET status='ACTIVE' WHERE id='collection:one';
                DELETE FROM content_item WHERE id='content:two';
            """)


if __name__ == "__main__":
    unittest.main()
