"""DP-413B: durable agentic runner and version-bound, restart-safe HOLD."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.autonomous_publication import (
    AutonomousProofPacket, candidate_fingerprint,
)
from dichiarazioni_pubbliche.autonomous_runner_v3 import SQLiteRunJournal, PersistentRunner
from dichiarazioni_pubbliche.autonomous_operations import AutonomousOperations
from tests.test_autonomous_operations import (
    Capture, Challenge, Reviewer, Surface, fixture_execution_witness,
)

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


class PersistentRunnerTests(unittest.TestCase):
    def setUp(self):
        policy = patch(
            "dichiarazioni_pubbliche.autonomous_publication.APPROVED_REVIEW_MODELS",
            frozenset({"model:first", "model:second", "model:third"}),
        )
        policy.start()
        self.addCleanup(policy.stop)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "autonomous.sqlite3"
        self.capture = Capture()
        self.challenge = Challenge()
        self.surface = Surface()
        self.first = Reviewer("agent:first", "model:first")
        self.second = Reviewer("agent:second", "model:second")
        self.third = Reviewer("agent:third", "model:third")

    def make_runner(self):
        journal = SQLiteRunJournal(self.db)
        operations = AutonomousOperations(
            capture=self.capture, challenge=self.challenge, first=self.first,
            second=self.second, public_surface=self.surface, journal=journal,
            verify_provider_execution=fixture_execution_witness,
            uncertainty_auditor=self.third,
        )
        return PersistentRunner(
            operations, journal, current_verified_packet=self.fixture_packet_reader,
        )

    def fixture_packet_reader(self, record_id, version_id):
        """Test-only substitute for the authenticated persisted packet reader."""
        item = self.capture.current(record_id)
        if (
            item is None or item.record_version_id != version_id
            or self.first.last_review is None
            or (item.uncertainty_reasons and (
                self.second.last_review is None or self.third.last_review is None
            ))
        ):
            return None
        return AutonomousProofPacket(
            item, self.first.last_review,
            self.second.last_review if item.uncertainty_reasons else None,
            self.third.last_review if item.uncertainty_reasons else None,
        )

    def test_repeat_across_restart_keeps_one_publish_and_one_editorial_call(self):
        first = self.make_runner().run("finding:413", now=NOW)
        repeated = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(first.disposition, "PUBLISH")
        self.assertEqual(repeated, first)
        self.assertEqual((self.first.calls, self.second.calls), (1, 0))
        self.assertEqual(
            [event.disposition for event in SQLiteRunJournal(self.db).events("finding:413")],
            ["INTENT", "PUBLISH"],
        )

    def test_old_unwitnessed_publish_checkpoint_is_revalidated_and_withdrawn(self):
        with patch.object(PersistentRunner, "EXECUTION_WITNESS_VERSION", "pre-witness"):
            self.assertEqual(
                self.make_runner().run("finding:413", now=NOW).disposition, "PUBLISH",
            )
        journal = SQLiteRunJournal(self.db)
        untrusted = AutonomousOperations(
            capture=self.capture, challenge=self.challenge,
            first=self.first, second=self.second,
            public_surface=self.surface, journal=journal,
        )
        result = PersistentRunner(untrusted, journal).run("finding:413", now=NOW)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("REVIEW_EXECUTION_UNVERIFIED", result.reason_codes)
        self.assertIsNone(self.surface.current_evidence_sha256("finding:413"))
        self.assertEqual((self.first.calls, self.second.calls), (2, 0))

    def test_current_publish_checkpoint_does_not_bypass_lost_provider_witness(self):
        self.assertEqual(
            self.make_runner().run("finding:413", now=NOW).disposition, "PUBLISH",
        )
        journal = SQLiteRunJournal(self.db)
        operations = AutonomousOperations(
            capture=self.capture, challenge=self.challenge,
            first=self.first, second=self.second,
            public_surface=self.surface, journal=journal,
        )
        result = PersistentRunner(
            operations, journal, current_verified_packet=self.fixture_packet_reader,
        ).run("finding:413", now=NOW)
        self.assertEqual(result.disposition, "HOLD")
        self.assertEqual(result.reason_codes, ("REVIEW_EXECUTION_UNVERIFIED",))
        self.assertFalse(self.surface.visible)
        self.assertEqual((self.first.calls, self.second.calls), (2, 0))

    def test_revoked_cached_witness_withdraws_before_retrying_providers(self):
        runner = self.make_runner()
        self.assertEqual(runner.run("finding:413", now=NOW).disposition, "PUBLISH")
        runner.operations.verify_provider_execution = lambda _review: False
        observed = []
        original_review = self.first.review

        def observe_visibility(item, binding):
            observed.append(self.surface.current_evidence_sha256(item.record_id))
            return original_review(item, binding)

        self.first.review = observe_visibility
        result = runner.run("finding:413", now=NOW)
        self.assertEqual(result.disposition, "HOLD")
        self.assertEqual(observed, [None])
        self.assertFalse(self.surface.visible)
        self.assertIn("CACHED_PUBLIC_AUTHORITY_LOST", (
            code for event in runner.journal.events("finding:413") for code in event.reason_codes
        ))

    def test_evidence_change_invalidates_approval_and_retries(self):
        original = self.make_runner().run("finding:413", now=NOW)
        self.capture.item = replace(
            self.capture.item, source_version="next-source", snapshot_sha256="f" * 64,
        )
        changed = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(changed.disposition, "PUBLISH")
        self.assertNotEqual(changed.evidence_sha256, original.evidence_sha256)
        self.assertEqual((self.first.calls, self.second.calls), (2, 0))
        self.assertEqual(self.surface.visible["finding:413"], candidate_fingerprint(self.capture.item))

    def test_old_policy_public_checkpoint_must_revalidate_after_policy_upgrade(self):
        # A previous policy accepted two different synthetic model routes.
        with patch(
            "dichiarazioni_pubbliche.autonomous_publication.POLICY_VERSION",
            "autonomous-publication-413-v1",
        ):
            prior = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(prior.disposition, "PUBLISH")
        # Current real subscription policy only approves one actual route.
        with patch(
            "dichiarazioni_pubbliche.autonomous_publication.APPROVED_REVIEW_MODELS",
            frozenset({"antigravity/gemini-3.8-flash-tiered"}),
        ):
            now = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(now.disposition, "HOLD")
        self.assertIn("EDITORIAL_REVIEW", now.reason_codes)
        self.assertFalse(self.surface.visible)
        self.assertEqual((self.first.calls, self.second.calls), (1, 0))

    def test_challenge_withdraws_prior_publish_on_same_evidence(self):
        self.make_runner().run("finding:413", now=NOW)
        self.challenge.held = True
        hold = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(hold.disposition, "HOLD")
        self.assertIn("CHALLENGE_HOLD", hold.reason_codes)
        self.assertIsNone(self.surface.current_evidence_sha256("finding:413"))
        self.assertEqual((self.first.calls, self.second.calls), (1, 0))
        self.assertEqual(self.make_runner().run("finding:413", now=NOW), hold)

    def test_provider_unavailable_is_durable_hold_and_does_not_retry_same_inputs(self):
        self.first.review = lambda *_: (_ for _ in ()).throw(RuntimeError("HTTP_429"))
        first = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(first.disposition, "HOLD")
        self.assertIn("EDITORIAL_REVIEW_UNAVAILABLE", first.reason_codes)
        self.assertEqual(self.make_runner().run("finding:413", now=NOW), first)
        self.assertFalse(self.surface.visible)

    def test_same_model_two_real_agent_identities_never_publish(self):
        self.capture.item = replace(self.capture.item, uncertainty_reasons=("CONFLICT",))
        self.second.model_id = self.first.model_id
        hold = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(hold.disposition, "HOLD")
        self.assertIn("INDEPENDENT_REVIEW", hold.reason_codes)
        self.assertFalse(self.surface.visible)

    def test_uncertain_record_retries_after_third_auditor_is_configured(self):
        self.capture.item = replace(self.capture.item, uncertainty_reasons=("ATTRIBUTION",))
        runner = self.make_runner()
        runner.operations.uncertainty_auditor = None
        held = runner.run("finding:413", now=NOW)
        self.assertEqual(held.disposition, "HOLD")
        self.assertIn("THIRD_AUDIT", held.reason_codes)
        self.assertEqual((self.first.calls, self.second.calls, self.third.calls), (0, 0, 0))
        runner.operations.uncertainty_auditor = self.third
        ready = runner.run("finding:413", now=NOW)
        self.assertEqual(ready.disposition, "PUBLISH")
        self.assertEqual((self.first.calls, self.second.calls, self.third.calls), (1, 1, 1))
        self.assertEqual(self.make_runner().run("finding:413", now=NOW), ready)
        self.assertEqual((self.first.calls, self.second.calls, self.third.calls), (1, 1, 1))

    def test_new_provider_quota_epoch_retries_old_hold_once(self):
        original = self.first.review
        self.first.review = lambda *_: (_ for _ in ()).throw(RuntimeError("HTTP_429"))
        blocked = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(blocked.disposition, "HOLD")
        self.first.review = original
        self.assertEqual(
            self.make_runner().run("finding:413", now=NOW).disposition, "HOLD",
        )
        retried = self.make_runner().run(
            "finding:413", now=NOW, provider_revision="quota-restored-epoch-2",
        )
        self.assertEqual(retried.disposition, "PUBLISH")
        self.assertEqual((self.first.calls, self.second.calls), (1, 0))

    def test_cannot_tamper_or_delete_append_only_ledger(self):
        self.make_runner().run("finding:413", now=NOW)
        with sqlite3.connect(self.db) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE autonomous_run_event SET disposition='HOLD'")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM autonomous_run_event")
        self.assertEqual(len(SQLiteRunJournal(self.db).events("finding:413")), 2)

    def test_recover_unfinished_intent_on_restart(self):
        journal = SQLiteRunJournal(self.db)
        operations = AutonomousOperations(
            capture=self.capture, challenge=self.challenge, first=self.first,
            second=self.second, public_surface=self.surface, journal=journal,
            verify_provider_execution=fixture_execution_witness,
        )
        operations.evaluate_and_apply("finding:413", now=NOW)
        recovered = PersistentRunner(operations, journal).run("finding:413", now=NOW)
        self.assertEqual(recovered.disposition, "PUBLISH")
        self.assertEqual((self.first.calls, self.second.calls), (2, 0))


if __name__ == "__main__":
    unittest.main()
