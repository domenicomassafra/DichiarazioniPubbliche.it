"""DP-516: real isolated append-only checkpoint CAS and restart semantics."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from dichiarazioni_pubbliche.historical_batch_gate_v1 import CompletedCapture
from dichiarazioni_pubbliche.historical_batch_checkpoint_store import SQLiteHistoricalCheckpointStore


class DurableCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dp516-checkpoint-local-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "batch.sqlite"
        self.first = SQLiteHistoricalCheckpointStore(self.path)
        self.other = SQLiteHistoricalCheckpointStore(self.path)
        self.batch = "batch:demo"
        self.manifest = "a" * 64
        self.one = CompletedCapture("item:one", "person:one", "content:one",
                                    "ARCHIVE", "b" * 64, "c" * 64)
        self.two = CompletedCapture("item:two", "person:two", "content:two",
                                    "ARCHIVE", "d" * 64, "e" * 64)

    def test_crash_resume_idempotency_stale_cas_and_restart(self):
        self.assertIsNone(self.first.read(self.batch))
        first = self.first.commit_capture(batch_id=self.batch,
            manifest_fingerprint=self.manifest, expected_revision=0,
            capture=self.one, verify_persisted_capture=lambda row: row == self.one)
        self.assertEqual(first.revision, 1)
        self.assertEqual(first.completed, (self.one,))
        self.assertEqual(self.other.read(self.batch), first)
        self.assertEqual(self.other.commit_capture(batch_id=self.batch,
            manifest_fingerprint=self.manifest, expected_revision=1,
            capture=self.one, verify_persisted_capture=lambda row: True), first)
        with self.assertRaisesRegex(ValueError, "DP516_CHECKPOINT_REVISION_CONFLICT"):
            self.other.commit_capture(batch_id=self.batch,
                manifest_fingerprint=self.manifest, expected_revision=0,
                capture=self.two, verify_persisted_capture=lambda row: True)
        second = self.other.commit_capture(batch_id=self.batch,
            manifest_fingerprint=self.manifest, expected_revision=1,
            capture=self.two, verify_persisted_capture=lambda row: True)
        self.assertEqual(second.revision, 2)
        self.assertEqual(second.completed, (self.one, self.two))
        self.assertEqual(SQLiteHistoricalCheckpointStore(self.path).read(self.batch), second)
        self.assertEqual(self.first.revision_count(self.batch), 2)

    def test_receipt_and_manifest_scope_cannot_be_forged_or_reused(self):
        self.first.commit_capture(batch_id=self.batch, manifest_fingerprint=self.manifest,
            expected_revision=0, capture=self.one, verify_persisted_capture=lambda row: True)
        with self.assertRaisesRegex(ValueError, "DP516_CHECKPOINT_MANIFEST_MISMATCH"):
            self.other.commit_capture(batch_id=self.batch, manifest_fingerprint="f" * 64,
                expected_revision=1, capture=self.two, verify_persisted_capture=lambda row: True)
        with self.assertRaisesRegex(ValueError, "DP516_CAPTURE_NOT_ATTESTED"):
            self.other.commit_capture(batch_id=self.batch, manifest_fingerprint=self.manifest,
                expected_revision=1, capture=self.two, verify_persisted_capture=lambda row: False)
        with self.assertRaisesRegex(ValueError, "DP516_CAPTURE_NOT_ATTESTED"):
            self.other.commit_capture(batch_id=self.batch, manifest_fingerprint=self.manifest,
                expected_revision=1, capture=self.two, verify_persisted_capture=None)
        self.assertEqual(self.other.revision_count(self.batch), 1)

    def test_collision_and_immutable_snapshot_history(self):
        self.first.commit_capture(batch_id=self.batch, manifest_fingerprint=self.manifest,
            expected_revision=0, capture=self.one, verify_persisted_capture=lambda row: True)
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError, "DP516_CHECKPOINT_CAPTURE_CONFLICT"):
            self.other.commit_capture(batch_id=self.batch, manifest_fingerprint=self.manifest,
                expected_revision=1,
                capture=replace(self.one, persisted_receipt_sha256="0" * 64),
                verify_persisted_capture=lambda row: True)
        with sqlite3.connect(self.path) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM historical_checkpoint_version")
        self.assertEqual(self.first.revision_count(self.batch), 1)


if __name__ == "__main__":
    unittest.main()
