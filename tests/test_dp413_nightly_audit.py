"""DP-413E: nightly audit coordination at the public operation boundary."""
from datetime import datetime, date, timezone, timedelta
from dataclasses import replace
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'poc'))
from dichiarazioni_pubbliche.nightly_audit import NightlyAuditCoordinator
from dichiarazioni_pubbliche.autonomous_publication import AgentReview, AutonomousProofPacket, candidate_fingerprint
from tests.test_autonomous_operations import harness, Reviewer, NOW
from tests.test_autonomous_publication import candidate, reviews


class MemoryLedger:
    def __init__(self):
        self.manifest = None
        self.saved = {}
        self.evidence = {}
        self.completed = None

    def begin(self, manifest):
        if self.manifest is None:
            self.manifest = manifest
        return self.manifest

    def recorded(self, run_id):
        return dict(self.saved)

    def append(self, run_id, receipt, evidence):
        self.saved.setdefault(receipt.record_id, receipt)
        self.evidence.setdefault(receipt.record_id, evidence)

    def complete(self, run_id, metrics, at):
        if self.completed is None:
            self.completed = metrics

    def readback(self, run_id):
        return self.completed


class PacketAuthority:
    def __init__(self, packets):
        self.packets = packets

    def current_packet(self, record_id):
        return self.packets.get(record_id)


class NightlyAuditIntegrationTests(unittest.TestCase):
    def test_zero_eligible_is_recorded_with_timestamp_and_no_model_call(self):
        ops, _, _, _, _, _, journal = harness()
        store = MemoryLedger()
        auditor = Reviewer('agent:third', 'third:model')
        result = NightlyAuditCoordinator(store).run(
            operations=ops, packet_authority=PacketAuthority({}), third=auditor,
            events=tuple(journal.events), corrections=(), day=NOW.date(), now=NOW,
        )
        self.assertEqual((result.denominator, result.sampled, result.audited), (0, (), 0))
        self.assertEqual(store.completed['published'], 0)
        self.assertEqual(store.completed['run_at'], NOW.isoformat())
        self.assertEqual(auditor.calls, 0)

    def test_one_eligible_repeats_idempotently_and_persists_auditor_result(self):
        ops, capture, _, first, second, surface, journal = harness()
        ops.evaluate_and_apply('finding:413', now=NOW)
        item = capture.item
        binding = candidate_fingerprint(item)
        packet = AutonomousProofPacket(item, first.review(item, binding), second.review(item, binding))
        auditor = Reviewer('agent:third', 'third:model')
        store = MemoryLedger()
        coordinator = NightlyAuditCoordinator(store)
        args = dict(operations=ops, packet_authority=PacketAuthority({'finding:413': packet}),
                    third=auditor, events=tuple(journal.events), corrections=(), day=NOW.date(), now=NOW)
        first_run = coordinator.run(**args)
        second_run = coordinator.run(**args)
        self.assertEqual(first_run.run_id, second_run.run_id)
        self.assertEqual((first_run.denominator, first_run.sampled, first_run.audited), (1, ('finding:413',), 1))
        self.assertEqual(auditor.calls, 1)
        self.assertEqual(store.saved['finding:413'].disposition, 'AUDIT_PASS')
        self.assertEqual(store.evidence['finding:413']['auditor_agent_id'], 'agent:third')
        self.assertTrue(store.evidence['finding:413']['verified_third_review'])
        self.assertEqual(store.evidence['finding:413']['rights_attestation_sha256'], item.rights_attestation_sha256)
        self.assertIn('finding:413', surface.visible)
        self.assertEqual(store.completed['audited'], 1)

    def test_missed_night_retry_metrics_count_on_actual_execution_day(self):
        ops, _, _, _, _, surface, journal = harness()
        ops.evaluate_and_apply('finding:413', now=NOW)
        store = MemoryLedger()
        next_day = NOW + timedelta(days=1)
        result = NightlyAuditCoordinator(store).run(
            operations=ops, packet_authority=PacketAuthority({}),
            third=Reviewer('agent:third', 'third:model'),
            events=tuple(journal.events), corrections=(), day=NOW.date(), now=next_day,
        )
        self.assertEqual(result.metrics['audit_holds'], 1)
        self.assertEqual(result.metrics['day'], next_day.date().isoformat())
        self.assertEqual(result.metrics['denominator'], 1)
        self.assertEqual(result.metrics['sampled'], 1)
        self.assertNotIn('finding:413', surface.visible)

    def test_tampered_packet_is_recorded_as_hold_without_crashing_receipt_capture(self):
        ops, capture, _, first, second, surface, journal = harness()
        ops.evaluate_and_apply('finding:413', now=NOW)
        bad_packet = AutonomousProofPacket('not-a-candidate', None, None)
        store = MemoryLedger()
        NightlyAuditCoordinator(store).run(
            operations=ops,
            packet_authority=PacketAuthority({'finding:413': bad_packet}),
            third=Reviewer('third', 'third:model'),
            events=tuple(journal.events), corrections=(), day=NOW.date(), now=NOW,
        )
        self.assertEqual(store.saved['finding:413'].disposition, 'AUDIT_HOLD')
        self.assertNotIn('finding:413', surface.visible)
        self.assertFalse(store.evidence['finding:413']['verified_third_review'])

    def test_third_review_with_malformed_identity_stays_a_durable_hold(self):
        ops, capture, _, first, second, surface, journal = harness()
        ops.evaluate_and_apply('finding:413', now=NOW)
        item = capture.item
        binding = candidate_fingerprint(item)
        packet = AutonomousProofPacket(
            item, first.review(item, binding), second.review(item, binding))

        class MalformedThird:
            agent_id = 'third'
            model_id = 'third:model'

            def review(self, candidate, evidence_sha256):
                return AgentReview(None, self.model_id, evidence_sha256,
                                   ('PROVENANCE', 'WORDING', 'SPEAKER', 'PERSON', 'RIGHTS_PRIVACY'), True)

        store = MemoryLedger()
        NightlyAuditCoordinator(store).run(
            operations=ops, packet_authority=PacketAuthority({'finding:413': packet}),
            third=MalformedThird(), events=tuple(journal.events),
            corrections=(), day=NOW.date(), now=NOW,
        )
        self.assertEqual(store.saved['finding:413'].disposition, 'AUDIT_HOLD')
        self.assertNotIn('finding:413', surface.visible)

    def test_retry_after_persisted_first_sample_counts_audits_once(self):
        ops, capture, _, first, second, surface, journal = harness()
        items = {f'finding:{idx}': replace(candidate(), record_id=f'finding:{idx}')
                 for idx in range(13)}
        capture.current = lambda record_id: items.get(record_id)
        packets = {}
        for record_id, item in items.items():
            ops.evaluate_and_apply(record_id, now=NOW)
            binding = candidate_fingerprint(item)
            packets[record_id] = AutonomousProofPacket(
                item, first.review(item, binding), second.review(item, binding))

        class OnceInterruptedLedger(MemoryLedger):
            interrupt = True

            def append(self, run_id, receipt, evidence):
                super().append(run_id, receipt, evidence)
                if self.interrupt:
                    self.interrupt = False
                    raise OSError('interrupted after durable write')

        store = OnceInterruptedLedger()
        coordinator = NightlyAuditCoordinator(store)
        auditor = Reviewer('agent:third', 'third:model')
        args = dict(operations=ops, packet_authority=PacketAuthority(packets),
                    third=auditor, corrections=(), day=NOW.date(), now=NOW)
        with self.assertRaises(OSError):
            coordinator.run(**args, events=tuple(journal.events))
        result = coordinator.run(**args, events=tuple(journal.events))
        self.assertEqual(result.denominator, 13)
        self.assertEqual(len(result.sampled), 2)
        self.assertEqual(result.metrics['audited'], 2)
        self.assertEqual(auditor.calls, 2)
        self.assertEqual(len(store.saved), 2)

    def test_missing_packet_is_durable_hold_and_removes_public_eligibility(self):
        ops, _, _, _, _, surface, journal = harness()
        ops.evaluate_and_apply('finding:413', now=NOW)
        store = MemoryLedger()
        result = NightlyAuditCoordinator(store).run(
            operations=ops, packet_authority=PacketAuthority({}), third=Reviewer('third', 'third:model'),
            events=tuple(journal.events), corrections=(), day=NOW.date(), now=NOW,
        )
        self.assertEqual(result.audited, 1)
        self.assertEqual(store.saved['finding:413'].disposition, 'AUDIT_HOLD')
        self.assertNotIn('finding:413', surface.visible)
        self.assertEqual(store.completed['audit_holds'], 1)
        self.assertEqual(store.completed['held'], 1)


if __name__ == '__main__':
    unittest.main()
