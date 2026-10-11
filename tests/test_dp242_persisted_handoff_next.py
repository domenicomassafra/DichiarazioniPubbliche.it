"""DP-242: real disposable SQLite transactions, never B authority or publication."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from dichiarazioni_pubbliche.studio_machine_candidate_handoff_v1 import (
    LocalPersistedBatchMachineHandoff,
)
from tests import test_dp242_studio_machine_handoff as dp242_fixture

CAPTURE_SHA = "c" * 64


class PersistedBatchHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "private-handoff.sqlite"
        self.conn = sqlite3.connect(self.db, isolation_level=None, timeout=2)
        self.addCleanup(self.conn.close)
        self.store = LocalPersistedBatchMachineHandoff(self.conn)
        self.store.init_isolated_fixture_schema()
        self.plan, self.index, self.currents = (
            dp242_fixture.DP240BatchMachineHandoffTests.fixture()
        )
        self.item = self.plan.items[0]
        self.current = self.currents[self.item.passage_id]
        self.conn.execute(
            "INSERT INTO dp242_source (id, collection_id, source_sha256, revision) "
            "VALUES (?, ?, ?, ?)",
            (
                "source:fixture",
                self.plan.collection_id,
                self.current.source_sha256,
                self.current.source_revision,
            ),
        )
        self.conn.execute(
            "INSERT INTO dp242_capture "
            "(id, source_id, content_id, capture_sha256, capture_status, hold_status, revision) "
            "VALUES (?, ?, ?, ?, 'CAPTURED', 'NONE', 3)",
            (self.item.capture_id, "source:fixture", self.item.content_id, CAPTURE_SHA),
        )
        self.conn.execute(
            "INSERT INTO dp242_passage "
            "(id, capture_id, content_id, passage_sha256, selector_fingerprint, "
            "speaker_candidate_id, identity_review_status, speech_role, speech_act, "
            "context_version, context_review_id, identity_revision, revision) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 4)",
            (
                self.item.passage_id,
                self.item.capture_id,
                self.item.content_id,
                self.item.passage_sha256,
                self.item.selector_fingerprint,
                self.item.speaker_candidate_id,
                self.item.identity_review_status,
                self.item.speech_role,
                self.item.speech_act,
                self.item.context_version,
                self.item.context_review_id,
                self.current.identity_revision,
            ),
        )
        self.conn.execute(
            "INSERT INTO dp242_rights (capture_id, status, evidence_sha256, revision) "
            "VALUES (?, 'CLEARED', ?, ?)",
            (
                self.item.capture_id,
                self.current.rights_evidence_sha256,
                self.current.rights_revision,
            ),
        )
        self.snapshot_pin = self.store.read_snapshot_binding_sha256(
            self.item.passage_id
        )

    def submit(self, **overrides):
        options = dict(
            plan=self.plan,
            index=self.index,
            passage_id=self.item.passage_id,
            expected_receipt_sha256=self.index.receipt_sha256,
            expected_capture_sha256=CAPTURE_SHA,
            expected_snapshot_sha256=self.snapshot_pin,
            expected_handoff_revision=0,
            request_key="operator:request:1",
        )
        return self.store.persist_held_batch_handoff(**(options | overrides))

    def test_persisted_transactional_handoff_crash_after_commit_replays_identically(
        self,
    ):
        first = self.submit()
        self.assertEqual(first["status"], "HELD_MACHINE_AUTHORITY_UNAVAILABLE")
        self.assertEqual(first["source"]["content_id"], self.item.content_id)
        self.assertEqual(first["source"]["capture_id"], self.item.capture_id)
        self.assertEqual(first["source"]["passage_id"], self.item.passage_id)
        self.assertEqual(first["source"]["source_id"], "source:fixture")
        self.assertEqual(first["source"]["collection_id"], self.plan.collection_id)
        self.assertEqual(first["source"]["capture_sha256"], CAPTURE_SHA)
        self.assertEqual(first["source"]["source_sha256"], self.item.source_sha256)
        self.assertEqual(first["source"]["passage_sha256"], self.item.passage_sha256)
        self.assertEqual(
            first["snapshot_revisions"]["rights"], self.current.rights_revision
        )
        self.assertEqual(first["resulting_handoff_revision"], 1)
        for flag in (
            "dispatch_authorized",
            "publication_authority",
            "human_review_approved",
            "machine_review_approved",
            "enqueued",
        ):
            self.assertIs(first[flag], False)
        self.assertNotIn("PRIVATE PROVIDER SECRET", json.dumps(first))

        # Lost response after a real committed SQLite transaction. New process/
        # connection reuses the exact request key against durable bytes.
        self.conn.close()
        self.conn = sqlite3.connect(self.db, isolation_level=None, timeout=2)
        self.store = LocalPersistedBatchMachineHandoff(self.conn)
        self.assertEqual(self.submit(), first)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM dp242_machine_handoff").fetchone()[
                0
            ],
            1,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT handoff_revision FROM dp242_passage WHERE id=?",
                (self.item.passage_id,),
            ).fetchone()[0],
            1,
        )

    def test_same_key_conflict_and_independent_cas_revision_conflict(self):
        first = self.submit()
        with self.assertRaisesRegex(ValueError, "REQUEST_KEY_CONFLICT"):
            self.submit(expected_handoff_revision=1)
        with self.assertRaisesRegex(ValueError, "HANDOFF_REVISION_CONFLICT"):
            self.submit(request_key="operator:request:2")
        second = self.submit(
            request_key="operator:request:2",
            expected_handoff_revision=1,
        )
        self.assertEqual(second["resulting_handoff_revision"], 2)
        self.assertNotEqual(second["intent_fingerprint"], first["intent_fingerprint"])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM dp242_machine_handoff").fetchone()[
                0
            ],
            2,
        )

    def test_revoked_rights_block_first_write_and_old_key_replay(self):
        self.conn.execute(
            "UPDATE dp242_rights SET status='REVOKED', revision=revision+1 "
            "WHERE capture_id=?",
            (self.item.capture_id,),
        )
        with self.assertRaisesRegex(ValueError, "RIGHTS_NOT_CURRENT"):
            self.submit()
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM dp242_machine_handoff").fetchone()[
                0
            ],
            0,
        )
        self.conn.execute(
            "UPDATE dp242_rights SET status='CLEARED', revision=? WHERE capture_id=?",
            (self.current.rights_revision, self.item.capture_id),
        )
        self.submit()
        self.conn.execute(
            "UPDATE dp242_rights SET status='REVOKED', revision=revision+1 "
            "WHERE capture_id=?",
            (self.item.capture_id,),
        )
        with self.assertRaisesRegex(ValueError, "RIGHTS_NOT_CURRENT"):
            self.submit()

    def test_foreign_capture_source_or_passage_snapshot_cannot_submit(self):
        for sql, params in (
            (
                "UPDATE dp242_source SET collection_id=? WHERE id='source:fixture'",
                ("collection:foreign",),
            ),
            (
                "UPDATE dp242_source SET source_sha256=? WHERE id='source:fixture'",
                ("f" * 64,),
            ),
            (
                "UPDATE dp242_capture SET content_id=? WHERE id=?",
                ("content:foreign", self.item.capture_id),
            ),
            (
                "UPDATE dp242_capture SET capture_sha256=? WHERE id=?",
                ("f" * 64, self.item.capture_id),
            ),
            (
                "UPDATE dp242_capture SET hold_status='RIGHTS' WHERE id=?",
                (self.item.capture_id,),
            ),
            (
                "UPDATE dp242_passage SET selector_fingerprint=? WHERE id=?",
                ("foreign", self.item.passage_id),
            ),
            (
                "UPDATE dp242_passage SET content_id=? WHERE id=?",
                ("content:foreign", self.item.passage_id),
            ),
            (
                "UPDATE dp242_passage SET identity_revision=identity_revision+1 WHERE id=?",
                (self.item.passage_id,),
            ),
        ):
            with self.subTest(sql=sql):
                table = sql.split()[1]
                field = sql.split(" SET ")[1].split("=")[0]
                columns = [
                    item[1] for item in self.conn.execute(f"PRAGMA table_info({table})")
                ]
                original = dict(
                    zip(columns, self.conn.execute(f"SELECT * FROM {table}").fetchone())
                )
                self.conn.execute(sql, params)
                with self.assertRaisesRegex(ValueError, "SOURCE_OR_SNAPSHOT_STALE"):
                    self.submit()
                self.conn.execute(
                    f"UPDATE {table} SET {field}=? WHERE id=?",
                    (original[field], original["id"]),
                )

    def test_rollback_after_insert_failure_restores_revision_and_no_orphan(self):
        self.conn.execute(
            "CREATE TRIGGER abort_handoff BEFORE INSERT ON dp242_machine_handoff "
            "BEGIN SELECT RAISE(ABORT, 'injected crash'); END"
        )
        with self.assertRaisesRegex(sqlite3.DatabaseError, "injected crash"):
            self.submit()
        self.assertEqual(
            self.conn.execute(
                "SELECT handoff_revision FROM dp242_passage WHERE id=?",
                (self.item.passage_id,),
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM dp242_machine_handoff").fetchone()[
                0
            ],
            0,
        )
        self.conn.execute("DROP TRIGGER abort_handoff")
        self.assertEqual(self.submit()["resulting_handoff_revision"], 1)

    def test_two_connections_racing_same_revision_only_one_durable_cas_wins(self):
        start = Barrier(2)

        def competing_request(key):
            connection = sqlite3.connect(self.db, isolation_level=None, timeout=3)
            try:
                local_store = LocalPersistedBatchMachineHandoff(connection)
                start.wait(timeout=3)
                try:
                    result = local_store.persist_held_batch_handoff(
                        plan=self.plan,
                        index=self.index,
                        passage_id=self.item.passage_id,
                        expected_receipt_sha256=self.index.receipt_sha256,
                        expected_capture_sha256=CAPTURE_SHA,
                        expected_snapshot_sha256=self.snapshot_pin,
                        expected_handoff_revision=0,
                        request_key=key,
                    )
                    return result["status"]
                except ValueError as exc:
                    return str(exc)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(competing_request, "operator:race:a")
            b = pool.submit(competing_request, "operator:race:b")
            outcomes = {a.result(timeout=5), b.result(timeout=5)}
        self.assertEqual(
            outcomes,
            {
                "HELD_MACHINE_AUTHORITY_UNAVAILABLE",
                "STUDIO_MACHINE_HANDOFF_REVISION_CONFLICT",
            },
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM dp242_machine_handoff").fetchone()[
                0
            ],
            1,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT handoff_revision FROM dp242_passage WHERE id=?",
                (self.item.passage_id,),
            ).fetchone()[0],
            1,
        )

    def test_missing_or_invalid_b_authority_never_materializes_downstream_job(self):
        receipt = self.submit()
        self.assertEqual(
            receipt["machine_authority_status"], "NOT_CONFIGURED_OR_NOT_ATTESTED"
        )
        self.assertEqual(receipt["action"], "AWAIT_INDEPENDENT_B_MACHINE_AUTHORITY")
        self.assertFalse(receipt["dispatch_authorized"])
        self.assertEqual(
            self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%job%'"
            ).fetchall(),
            [],
        )


if __name__ == "__main__":
    unittest.main()
