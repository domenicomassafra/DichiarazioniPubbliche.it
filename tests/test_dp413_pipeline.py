"""DP-413: one unattended tick over the existing autonomous authorities."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.autonomous_operations import (  # noqa: E402
    AutonomousOperations, PublicationSafetyError,
)
from dichiarazioni_pubbliche.autonomous_publication import (  # noqa: E402
    AutonomousProofPacket,
)
from dichiarazioni_pubbliche.autonomous_pipeline import AutonomousPipeline  # noqa: E402
from dichiarazioni_pubbliche.autonomous_runner_v3 import (  # noqa: E402
    PersistentRunner, SQLiteRunJournal,
)
from tests.test_autonomous_operations import (  # noqa: E402
    Capture, Challenge, Journal, Reviewer, Surface,
    fixture_execution_witness,
)
from tests.test_autonomous_publication import candidate  # noqa: E402

NOW = datetime(2026, 11, 8, 22, 0, tzinfo=timezone.utc)


class Queue:
    def __init__(self, ids=("finding:413",), *, error=None):
        self.ids = ids
        self.error = error
        self.calls = 0

    def current_record_ids(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.ids


class MultiCapture:
    """One exact item per record, like the live capture authority."""

    def __init__(self, *record_ids):
        self.items = {
            record_id: replace(candidate(), record_id=record_id)
            for record_id in record_ids
        }

    def current(self, record_id):
        return self.items.get(record_id)


class RecordingSurface(Surface):
    """Persist the exact witnessed packet the public reader must revalidate."""

    def __init__(self):
        super().__init__()
        self.packets = {}

    def publish(self, packet):
        super().publish(packet)
        self.packets[packet.candidate.record_id] = packet

    def withdraw(self, record_id):
        super().withdraw(record_id)
        self.packets.pop(record_id, None)


class PartialSurface(RecordingSurface):
    def __init__(self, broken):
        super().__init__()
        self.broken = broken

    def withdraw(self, record_id):
        if record_id == self.broken:
            raise PublicationSafetyError("PUBLIC_WITHDRAWAL_UNCONFIRMED")
        super().withdraw(record_id)

    def current_evidence_sha256(self, record_id):
        if record_id == self.broken:
            return "f" * 64
        return super().current_evidence_sha256(record_id)


class MemoryLedger:
    def __init__(self):
        self.manifest = None
        self.saved = {}
        self.completed = None

    def begin(self, manifest):
        if self.manifest is None:
            self.manifest = manifest
        return self.manifest

    def recorded(self, run_id):
        return dict(self.saved)

    def append(self, run_id, receipt, evidence):
        self.saved.setdefault(receipt.record_id, receipt)

    def complete(self, run_id, metrics, at):
        if self.completed is None:
            self.completed = metrics

    def readback(self, run_id):
        return self.completed


class PacketAuthority:
    def __init__(self, packets=None):
        self.packets = {} if packets is None else packets

    def current_packet(self, record_id, version_id=None):
        stored = self.packets.get(record_id)
        if stored is None:
            return None
        if version_id is not None and stored.candidate.record_version_id != version_id:
            return None
        return stored


def packet(item, first, second):
    """The exact witnessed packet a passing publication leaves behind."""
    return AutonomousProofPacket(item, first.last_review, second.last_review)


class AutonomousPipelineTests(unittest.TestCase):
    def setUp(self):
        # Synthetic model diversity exercises the tick lifecycle; the live
        # subscription policy is covered by the dedicated 413 tests.
        policy = patch(
            "dichiarazioni_pubbliche.autonomous_publication.APPROVED_REVIEW_MODELS",
            frozenset({"gemini:model-1", "local:model-2", "third:model"}),
        )
        policy.start()
        self.addCleanup(policy.stop)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "autonomous.sqlite3"
        self.capture = Capture()
        self.challenge = Challenge()
        self.surface = RecordingSurface()
        self.first = Reviewer("agent:one", "gemini:model-1")
        self.second = Reviewer("agent:two", "local:model-2")
        self.third = Reviewer("agent:third", "third:model")
        self.journal = SQLiteRunJournal(self.db)
        self.operations = AutonomousOperations(
            capture=self.capture, challenge=self.challenge, first=self.first,
            second=self.second, public_surface=self.surface, journal=self.journal,
            verify_provider_execution=fixture_execution_witness,
        )
        self.packet_authority = PacketAuthority(self.surface.packets)
        self.runner = PersistentRunner(
            self.operations, self.journal,
            current_verified_packet=self.packet_authority.current_packet,
        )

    def pipeline(self, *, queue=None, limit=25, corrections=lambda: (), audit=None):
        return AutonomousPipeline(
            operations=self.operations, runner=self.runner,
            queue=queue or Queue(), corrections=corrections, limit=limit,
            **(audit or {}),
        )

    def audit_authorities(self, *, packets=None):
        self.ledger = MemoryLedger()
        authority = (
            self.packet_authority if packets is None else PacketAuthority(packets)
        )
        return {
            "audit_ledger": self.ledger,
            "packet_authority": authority,
            "third": self.third,
        }

    def test_tick_publishes_with_two_independent_models_and_counts_the_day(self):
        report = self.pipeline().run(now=NOW)
        self.assertEqual(report.status, "TICK_OK")
        self.assertTrue(report.completed)
        self.assertEqual(report.processed, ("finding:413",))
        self.assertEqual([run.disposition for run in report.runs], ["PUBLISH"])
        self.assertEqual(
            [event.disposition for event in self.journal.all_events()],
            ["INTENT", "PUBLISH"],
        )
        self.assertEqual((self.first.calls, self.second.calls), (1, 0))
        self.assertEqual(report.metrics["published"], 1)
        self.assertEqual(report.metrics["publish_events"], 1)
        self.assertEqual(report.metrics["day"], NOW.date().isoformat())
        repeated = self.pipeline().run(now=NOW)
        self.assertEqual(repeated.runs, report.runs)
        self.assertEqual((self.first.calls, self.second.calls), (1, 0))

    def test_tick_is_bounded_and_defers_the_rest_without_model_work(self):
        self.operations.capture = MultiCapture("finding:413", "record:2", "record:3")
        queue = Queue(("finding:413", "record:2", "record:3"))
        report = self.pipeline(queue=queue, limit=2).run(now=NOW)
        self.assertEqual(report.processed, ("finding:413", "record:2"))
        self.assertEqual(report.deferred, ("record:3",))
        self.assertEqual(
            {event.record_id for event in self.journal.all_events()},
            {"finding:413", "record:2"},
        )
        self.assertEqual((self.first.calls, self.second.calls), (2, 0))

    def test_unavailable_queue_stops_before_any_model_or_publication(self):
        queue = Queue(error=RuntimeError("DP413_QUEUE_DOWN"))
        report = self.pipeline(queue=queue).run(now=NOW)
        self.assertEqual(report.status, "QUEUE_UNAVAILABLE")
        self.assertEqual(report.reason_codes, ("RECORD_QUEUE_UNAVAILABLE",))
        self.assertEqual(report.runs, ())
        self.assertEqual((self.first.calls, self.second.calls), (0, 0))
        self.assertEqual(self.surface.visible, {})
        self.assertEqual(self.journal.all_events(), ())

    def test_invalid_queue_entries_never_reach_the_runner(self):
        for bad in (("finding:413", "finding:413"), ("finding:413", None),
                    ("finding:413 ",), ("",)):
            with self.subTest(listed=bad):
                report = self.pipeline(queue=Queue(bad)).run(now=NOW)
                self.assertEqual(report.status, "QUEUE_INVALID")
                self.assertEqual(report.reason_codes, ("RECORD_QUEUE_INVALID",))
                self.assertEqual((self.first.calls, self.second.calls), (0, 0))
                self.assertEqual(self.journal.all_events(), ())

    def test_failed_record_does_not_block_or_hide_the_rest(self):
        self.operations.capture = MultiCapture("record:1", "record:2")
        self.operations.surface = PartialSurface("record:1")
        report = self.pipeline(queue=Queue(("record:1", "record:2"))).run(now=NOW)
        self.assertEqual(report.failed, ("record:1",))
        self.assertEqual([run.record_id for run in report.runs], ["record:2"])
        self.assertEqual(report.status, "RECORD_RUN_FAILED")
        self.assertIn("RECORD_RUN_FAILED", report.reason_codes)
        self.assertFalse(report.completed)
        self.assertEqual(
            self.operations.surface.current_evidence_sha256("record:2"),
            report.runs[0].evidence_sha256,
        )

    def test_nightly_audit_runs_once_per_utc_day_with_the_frozen_sample(self):
        self.pipeline().run(now=NOW)
        audit = self.audit_authorities()
        first = self.pipeline(audit=audit).run(now=NOW, audit_day=NOW.date())
        self.assertEqual(first.status, "TICK_OK")
        self.assertEqual(first.audit.audited, 1)
        self.assertEqual(first.audit.sampled, ("finding:413",))
        self.assertEqual(self.third.calls, 1)
        self.assertIsNotNone(
            self.surface.current_evidence_sha256("finding:413")
        )
        second = self.pipeline(audit=audit).run(
            now=NOW + timedelta(minutes=30), audit_day=NOW.date(),
        )
        self.assertEqual(second.audit.audited, 1)
        self.assertEqual(self.third.calls, 1)

    def test_future_audit_day_is_rejected_before_any_work(self):
        report = self.pipeline(audit=self.audit_authorities()).run(
            now=NOW, audit_day=NOW.date() + timedelta(days=1),
        )
        self.assertEqual(report.status, "AUDIT_REJECTED")
        self.assertEqual(report.reason_codes, ("NIGHTLY_AUDIT_DAY_INVALID",))
        self.assertEqual((self.first.calls, self.second.calls), (0, 0))
        self.assertEqual(self.journal.all_events(), ())

    def test_missing_audit_packet_withdraws_and_reports_a_durable_hold(self):
        self.pipeline().run(now=NOW)
        report = self.pipeline(
            audit=self.audit_authorities(packets={}),
        ).run(now=NOW, audit_day=NOW.date())
        self.assertEqual(report.audit.audited, 1)
        self.assertEqual(report.audit.metrics["audit_holds"], 1)
        self.assertIsNone(self.surface.current_evidence_sha256("finding:413"))
        self.assertIn(
            "AUDIT_HOLD",
            [event.disposition for event in self.journal.all_events()],
        )

    def test_audit_without_its_authorities_is_explicit_and_publishes_nothing_new(self):
        report = self.pipeline().run(now=NOW, audit_day=NOW.date())
        self.assertEqual(report.status, "AUDIT_UNAVAILABLE")
        self.assertEqual(report.reason_codes, ("AUDIT_NOT_CONFIGURED",))
        self.assertIsNone(report.audit)
        self.assertEqual(self.third.calls, 0)
        self.assertEqual(report.runs, ())
        self.assertEqual((self.first.calls, self.second.calls), (0, 0))
        self.assertEqual(self.surface.visible, {})

    def test_unavailable_correction_ledger_never_fabricates_metrics(self):
        def corrections():
            raise RuntimeError("DP413_CORRECTIONS_DOWN")

        report = self.pipeline(corrections=corrections).run(now=NOW)
        self.assertEqual(report.status, "METRICS_UNAVAILABLE")
        self.assertEqual(report.metrics, {})
        self.assertIn("CORRECTIONS_UNAVAILABLE", report.reason_codes)
        self.assertEqual(report.runs, ())
        self.assertEqual(report.deferred, ("finding:413",))
        self.assertEqual((self.first.calls, self.second.calls), (0, 0))
        self.assertEqual(self.surface.visible, {})

    def test_invalid_correction_ledger_rejects_before_publication(self):
        report = self.pipeline(corrections=lambda: ("not-an-event",)).run(now=NOW)
        self.assertEqual(report.status, "METRICS_INVALID")
        self.assertEqual(report.runs, ())
        self.assertEqual(report.deferred, ("finding:413",))
        self.assertEqual((self.first.calls, self.second.calls), (0, 0))
        self.assertEqual(self.surface.visible, {})

    def test_pipeline_refuses_mismatched_authorities(self):
        other_journal = SQLiteRunJournal(Path(self.directory.name) / "other.sqlite3")
        other = AutonomousOperations(
            capture=self.capture, challenge=self.challenge, first=self.first,
            second=self.second, public_surface=self.surface, journal=other_journal,
            verify_provider_execution=fixture_execution_witness,
        )
        cases = (
            dict(operations=other, runner=self.runner, queue=Queue()),
            dict(operations=self.operations,
                 runner=PersistentRunner(other, other_journal), queue=Queue()),
            dict(operations=self.operations, runner=self.runner, queue=object()),
            dict(operations=self.operations, runner=self.runner, queue=Queue(), limit=0),
        )
        for kwargs in cases:
            with self.subTest(kwargs=sorted(kwargs)):
                with self.assertRaises(ValueError):
                    AutonomousPipeline(corrections=lambda: (), **kwargs)
        with self.assertRaises(ValueError):
            AutonomousPipeline(
                operations=self.operations, runner=self.runner, queue=Queue(),
                corrections=lambda: (), audit_ledger=MemoryLedger(),
            )

    def test_durable_journal_is_required_and_memory_authority_refused(self):
        memory = Journal()
        operations = AutonomousOperations(
            capture=self.capture, challenge=self.challenge, first=self.first,
            second=self.second, public_surface=self.surface, journal=memory,
            verify_provider_execution=fixture_execution_witness,
        )
        with self.assertRaises(ValueError):
            AutonomousPipeline(
                operations=operations, runner=PersistentRunner(operations, memory),
                queue=Queue(), corrections=lambda: (),
            )

    def test_all_events_reads_the_whole_corpus_and_detects_tampering(self):
        self.operations.capture = MultiCapture("record:1", "record:2")
        self.pipeline(queue=Queue(("record:1", "record:2"))).run(now=NOW)
        self.assertEqual(
            [(event.record_id, event.disposition)
             for event in SQLiteRunJournal(self.db).all_events()],
            [(record_id, disposition) for record_id in ("record:1", "record:2")
             for disposition in ("INTENT", "PUBLISH")],
        )
        self.assertEqual(
            [event.record_id for event in SQLiteRunJournal(self.db).events("record:2")],
            ["record:2", "record:2"],
        )
        with sqlite3.connect(self.db) as conn:
            conn.execute("DROP TRIGGER autonomous_event_no_update")
            conn.execute("UPDATE autonomous_run_event SET event_json='{}' WHERE event_id=1")
        with self.assertRaises(ValueError):
            SQLiteRunJournal(self.db).all_events()


if __name__ == "__main__":
    unittest.main()
