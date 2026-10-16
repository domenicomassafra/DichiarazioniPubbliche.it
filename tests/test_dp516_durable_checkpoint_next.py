"""DP-516: real isolated append-only checkpoint CAS and restart semantics."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from dichiarazioni_pubbliche.historical_batch_gate_v1 import CompletedCapture
from dichiarazioni_pubbliche.historical_batch_checkpoint_store import SQLiteHistoricalCheckpointStore
from tests.test_dp516_historical_batch_gate import plan
from tests.test_dp243_historical_corpus_preflight import entry, two


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

    def test_persisted_checkpoint_replays_into_real_batch_planner_and_stale_fails(self):
        planned = plan()
        proposal = planned.proposals[0]
        capture = CompletedCapture(
            proposal.item_key, proposal.person_id, proposal.content_id,
            proposal.source_family, proposal.capture_sha256, "f" * 64,
        )
        saved = self.first.commit_capture(
            batch_id=planned.batch_id, manifest_fingerprint=planned.manifest_fingerprint,
            expected_revision=0, capture=capture, verify_persisted_capture=lambda row: row == capture,
        )
        held = plan(checkpoint=saved)
        self.assertIn("CHECKPOINT_EXTERNAL_TRUST_REQUIRED", held.holds)
        resumed = plan(checkpoint=self.other.read(planned.batch_id),
                       verify_checkpoint=self.other.verify_current)
        self.assertEqual(resumed.status, "PRIVATE_REVIEW_PLAN")
        self.assertIn(capture.item_key, resumed.completed_keys)
        self.assertEqual(len(resumed.proposals), len(planned.proposals) - 1)
        self.assertFalse(resumed.dispatch_authorized)
        self.assertFalse(resumed.pilot_accepted_by_system)
        # A source-only journal callback never serves as publication authority.
        wrong = self.other.verify_current(saved, "batch:foreign")
        self.assertFalse(wrong)

    def test_multi_person_italian_german_batch_recovers_without_duplicate_work(self):
        """Four bounded original sources survive a two-person crash and resume."""
        originals = two()
        manifests = (
            replace(
                originals[0],
                entries=(
                    originals[0].entries[0],
                    entry(content_id="source:synthetic:it:second", sha="c" * 64),
                ),
            ),
            replace(
                originals[1],
                entries=(
                    originals[1].entries[0],
                    entry(
                        subject="HITLER",
                        content_id="source:synthetic:de:second",
                        sha="d" * 64,
                        language="de",
                        collection_id="collection:de",
                        event_timezone="Europe/Berlin",
                    ),
                ),
            ),
        )
        initial = plan(manifests=manifests)
        self.assertEqual(initial.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(len(initial.proposals), 4)
        self.assertEqual(
            {(p.person_id, p.original_language) for p in initial.proposals},
            {
                (originals[0].person_id, "it"),
                (originals[1].person_id, "de"),
            },
        )

        # An interruption after one Capture per person must preserve both
        # identities and skip their expensive work after a new store opens.
        selected = [
            next(p for p in initial.proposals if p.person_id == person_id)
            for person_id in (originals[0].person_id, originals[1].person_id)
        ]
        checkpoint = None
        for revision, proposal in enumerate(selected):
            receipt = CompletedCapture(
                proposal.item_key,
                proposal.person_id,
                proposal.content_id,
                proposal.source_family,
                proposal.capture_sha256,
                "f" * 64,
            )
            checkpoint = self.first.commit_capture(
                batch_id=initial.batch_id,
                manifest_fingerprint=initial.manifest_fingerprint,
                expected_revision=revision,
                capture=receipt,
                verify_persisted_capture=lambda row, expected=receipt: row == expected,
            )
        self.assertIsNotNone(checkpoint)
        restarted = SQLiteHistoricalCheckpointStore(self.path)
        persisted = restarted.read(initial.batch_id)
        self.assertEqual(persisted, checkpoint)
        resumed = plan(
            manifests=manifests,
            checkpoint=persisted,
            verify_checkpoint=restarted.verify_current,
        )
        self.assertEqual(resumed.status, "PRIVATE_REVIEW_PLAN")
        self.assertEqual(len(resumed.proposals), 2)
        self.assertEqual(len(resumed.completed_keys), 2)
        self.assertTrue(
            set(resumed.completed_keys).isdisjoint(p.item_key for p in resumed.proposals)
        )
        self.assertEqual(
            {p.person_id for p in resumed.proposals},
            {p.person_id for p in selected},
        )
        self.assertFalse(resumed.dispatch_authorized)
        self.assertFalse(resumed.public_eligible)

        # Restarting again with the same immutable revision never adds work.
        self.assertEqual(
            plan(
                manifests=manifests,
                checkpoint=restarted.read(initial.batch_id),
                verify_checkpoint=restarted.verify_current,
            ),
            resumed,
        )


if __name__ == "__main__":
    unittest.main()
