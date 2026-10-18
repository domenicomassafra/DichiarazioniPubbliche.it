"""DP-516: real isolated append-only checkpoint CAS and restart semantics."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from dichiarazioni_pubbliche.historical_batch_gate_v1 import CompletedCapture
from dichiarazioni_pubbliche.historical_batch_checkpoint_store import SQLiteHistoricalCheckpointStore
from dichiarazioni_pubbliche.incremental_source_watch import policy_fingerprint
from tests.test_dp516_historical_batch_gate import plan, resources
from tests.test_dp243_historical_corpus_preflight import NOW, entry, two


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

    @staticmethod
    def _four_source_manifests():
        originals = two()
        return (
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

    @staticmethod
    def _receipt(proposal):
        return CompletedCapture(
            proposal.item_key, proposal.person_id, proposal.content_id,
            proposal.source_family, proposal.capture_sha256, "f" * 64,
        )

    def _commit_selected(self, initial, selected):
        checkpoint = None
        for revision, proposal in enumerate(selected):
            receipt = self._receipt(proposal)
            checkpoint = self.first.commit_capture(
                batch_id=initial.batch_id,
                manifest_fingerprint=initial.manifest_fingerprint,
                expected_revision=revision,
                capture=receipt,
                verify_persisted_capture=lambda row, expected=receipt: row == expected,
            )
        return checkpoint

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
        manifests = self._four_source_manifests()
        originals = two()
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
        checkpoint = self._commit_selected(initial, selected)
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

    def test_restart_rejects_stale_or_unverified_durable_checkpoint(self):
        manifests = self._four_source_manifests()
        initial = plan(manifests=manifests)
        selected = [
            next(p for p in initial.proposals if p.original_language == language)
            for language in ("it", "de")
        ]
        stale = self._commit_selected(initial, selected[:1])
        current = self.first.commit_capture(
            batch_id=initial.batch_id,
            manifest_fingerprint=initial.manifest_fingerprint,
            expected_revision=stale.revision,
            capture=self._receipt(selected[1]),
            verify_persisted_capture=lambda row: row == self._receipt(selected[1]),
        )
        restarted = SQLiteHistoricalCheckpointStore(self.path)
        self.assertEqual(restarted.read(initial.batch_id), current)
        self.assertFalse(restarted.verify_current(stale, initial.batch_id))

        for checkpoint, verifier, reason in (
            (stale, restarted.verify_current, "CHECKPOINT_EXTERNAL_TRUST_FAILED"),
            (current, None, "CHECKPOINT_EXTERNAL_TRUST_REQUIRED"),
        ):
            with self.subTest(reason=reason):
                held = plan(
                    manifests=manifests, checkpoint=checkpoint,
                    verify_checkpoint=verifier,
                )
                self.assertEqual(held.status, "HELD")
                self.assertIn(reason, held.holds)
                self.assertEqual(held.proposals, ())
                self.assertIsNone(held.proposed_budget_state)
                self.assertFalse(held.dispatch_authorized)
                self.assertFalse(held.public_eligible)
        self.assertEqual(restarted.revision_count(initial.batch_id), 2)

    def test_durable_restart_rejects_cross_person_and_source_identity(self):
        manifests = self._four_source_manifests()
        initial = plan(manifests=manifests)
        self.assertEqual(len(initial.proposals), 4)
        for language in ("it", "de"):
            selected = next(p for p in initial.proposals if p.original_language == language)
            foreign = next(p for p in initial.proposals if p.original_language != language)
            for field, foreign_value in (
                ("person_id", foreign.person_id),
                ("content_id", foreign.content_id),
                ("capture_sha256", foreign.capture_sha256),
            ):
                with self.subTest(language=language, field=field):
                    # A locally persisted receipt with a valid checksum is not
                    # permission to transfer work to another historical person.
                    store = SQLiteHistoricalCheckpointStore(
                        self.path.parent / f"identity-{language}-{field}.sqlite"
                    )
                    forged = replace(self._receipt(selected), **{field: foreign_value})
                    store.commit_capture(
                        batch_id=initial.batch_id,
                        manifest_fingerprint=initial.manifest_fingerprint,
                        expected_revision=0,
                        capture=forged,
                        verify_persisted_capture=lambda row: row == forged,
                    )
                    restarted = SQLiteHistoricalCheckpointStore(store.path)
                    persisted = restarted.read(initial.batch_id)
                    self.assertTrue(restarted.verify_current(persisted, initial.batch_id))
                    held = plan(
                        manifests=manifests, checkpoint=persisted,
                        verify_checkpoint=restarted.verify_current,
                    )
                    self.assertEqual(held.status, "HELD")
                    self.assertIn("CHECKPOINT_FOREIGN_ITEM", held.holds)
                    self.assertEqual(held.proposals, ())
                    self.assertIsNone(held.proposed_budget_state)
                    self.assertFalse(held.dispatch_authorized)
                    self.assertFalse(held.public_eligible)

    def test_durable_restart_rechecks_italian_and_german_rights_and_versions(self):
        manifests = self._four_source_manifests()
        initial = plan(manifests=manifests)
        selected = [
            next(p for p in initial.proposals if p.original_language == language)
            for language in ("it", "de")
        ]
        self._commit_selected(initial, selected)
        restarted = SQLiteHistoricalCheckpointStore(self.path)
        persisted = restarted.read(initial.batch_id)
        _, watches = resources(manifests)
        for proposal in selected:
            for condition, reason in (
                ("revoked", "WATCH_COMPLETED_RIGHTS_NOT_READY"),
                ("malformed_receipt", "WATCH_COMPLETED_RIGHTS_NOT_READY"),
                ("source_changed", "WATCH_COMPLETED_SOURCE_CHANGED"),
            ):
                with self.subTest(language=proposal.original_language, condition=condition):
                    watch = next(w for w in watches if w.content_id == proposal.content_id)
                    if condition == "revoked":
                        altered = replace(
                            watch, readiness=replace(watch.readiness, rights_status="REVOKED")
                        )
                    elif condition == "malformed_receipt":
                        altered = replace(
                            watch, readiness=replace(
                                watch.readiness, rights_receipt="synthetic:rights\nFORGED"
                            )
                        )
                    else:
                        altered = replace(
                            watch,
                            state=replace(
                                watch.state,
                                policy_fingerprint=policy_fingerprint(watch.policy),
                                content_sha256="0" * 64,
                                last_successful_observed_at=NOW - timedelta(minutes=1),
                            ),
                        )
                    current_watches = tuple(
                        altered if w.content_id == proposal.content_id else w
                        for w in watches
                    )
                    held = plan(
                        manifests=manifests, checkpoint=persisted,
                        verify_checkpoint=restarted.verify_current,
                        watches=current_watches,
                    )
                    self.assertEqual(held.status, "HELD")
                    self.assertIn(reason, held.holds)
                    self.assertEqual(held.proposals, ())
                    self.assertIsNone(held.proposed_budget_state)
                    self.assertFalse(held.dispatch_authorized)
                    self.assertFalse(held.public_eligible)
        self.assertEqual(restarted.read(initial.batch_id), persisted)
        self.assertEqual(restarted.revision_count(initial.batch_id), 2)


if __name__ == "__main__":
    unittest.main()
