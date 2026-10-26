"""DP-413B: durable agentic runner and version-bound, restart-safe HOLD."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.autonomous_publication import candidate_fingerprint
from dichiarazioni_pubbliche.autonomous_runner_v3 import SQLiteRunJournal, PersistentRunner
from dichiarazioni_pubbliche.autonomous_operations import AutonomousOperations
from tests.test_autonomous_operations import (
    Capture, Challenge, Reviewer, Surface,
)

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


class PersistentRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "autonomous.sqlite3"
        self.capture = Capture()
        self.challenge = Challenge()
        self.surface = Surface()
        self.first = Reviewer("agent:first", "model:first")
        self.second = Reviewer("agent:second", "model:second")

    def make_runner(self):
        journal = SQLiteRunJournal(self.db)
        operations = AutonomousOperations(
            capture=self.capture, challenge=self.challenge, first=self.first,
            second=self.second, public_surface=self.surface, journal=journal,
        )
        return PersistentRunner(operations, journal)

    def test_repeat_across_restart_keeps_one_publish_and_two_model_calls(self):
        first = self.make_runner().run("finding:413", now=NOW)
        repeated = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(first.disposition, "PUBLISH")
        self.assertEqual(repeated, first)
        self.assertEqual((self.first.calls, self.second.calls), (1, 1))
        self.assertEqual(
            [event.disposition for event in SQLiteRunJournal(self.db).events("finding:413")],
            ["INTENT", "PUBLISH"],
        )

    def test_evidence_change_invalidates_approval_and_retries(self):
        original = self.make_runner().run("finding:413", now=NOW)
        self.capture.item = replace(
            self.capture.item, source_version="next-source", snapshot_sha256="f" * 64,
        )
        changed = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(changed.disposition, "PUBLISH")
        self.assertNotEqual(changed.evidence_sha256, original.evidence_sha256)
        self.assertEqual((self.first.calls, self.second.calls), (2, 2))
        self.assertEqual(self.surface.visible["finding:413"], candidate_fingerprint(self.capture.item))

    def test_challenge_withdraws_prior_publish_on_same_evidence(self):
        self.make_runner().run("finding:413", now=NOW)
        self.challenge.held = True
        hold = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(hold.disposition, "HOLD")
        self.assertIn("CHALLENGE_HOLD", hold.reason_codes)
        self.assertIsNone(self.surface.current_evidence_sha256("finding:413"))
        self.assertEqual((self.first.calls, self.second.calls), (1, 1))
        self.assertEqual(self.make_runner().run("finding:413", now=NOW), hold)

    def test_provider_unavailable_is_durable_hold_and_does_not_retry_same_inputs(self):
        self.second.review = lambda *_: (_ for _ in ()).throw(RuntimeError("HTTP_429"))
        first = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(first.disposition, "HOLD")
        self.assertIn("INDEPENDENT_REVIEW_UNAVAILABLE", first.reason_codes)
        self.assertEqual(self.make_runner().run("finding:413", now=NOW), first)
        self.assertFalse(self.surface.visible)

    def test_same_model_two_real_agent_identities_never_publish(self):
        self.second.model_id = self.first.model_id
        hold = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(hold.disposition, "HOLD")
        self.assertIn("INDEPENDENT_REVIEW", hold.reason_codes)
        self.assertFalse(self.surface.visible)

    def test_new_provider_quota_epoch_retries_old_hold_once(self):
        original = self.second.review
        self.second.review = lambda *_: (_ for _ in ()).throw(RuntimeError("HTTP_429"))
        blocked = self.make_runner().run("finding:413", now=NOW)
        self.assertEqual(blocked.disposition, "HOLD")
        self.second.review = original
        self.assertEqual(
            self.make_runner().run("finding:413", now=NOW).disposition, "HOLD",
        )
        retried = self.make_runner().run(
            "finding:413", now=NOW, provider_revision="quota-restored-epoch-2",
        )
        self.assertEqual(retried.disposition, "PUBLISH")
        self.assertEqual((self.first.calls, self.second.calls), (2, 1))

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
        )
        operations.evaluate_and_apply("finding:413", now=NOW)
        recovered = PersistentRunner(operations, journal).run("finding:413", now=NOW)
        self.assertEqual(recovered.disposition, "PUBLISH")
        self.assertEqual((self.first.calls, self.second.calls), (2, 2))


if __name__ == "__main__":
    unittest.main()
