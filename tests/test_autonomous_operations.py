"""DP #413: autonomous execution, withdrawal, readback, audit and daily counts."""

from dataclasses import replace
from datetime import date, datetime, timezone, timedelta
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.autonomous_publication import (  # noqa: E402
    AgentReview, AutonomousProofPacket, candidate_fingerprint,
)
from dichiarazioni_pubbliche.autonomous_operations import (  # noqa: E402
    AutonomousOperations, CorrectionMetricEvent, PublicationSafetyError, daily_metrics,
    nightly_sample,
)
from tests.test_autonomous_publication import candidate, reviews  # noqa: E402

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
STAGES = ("PROVENANCE", "WORDING", "SPEAKER", "PERSON", "RIGHTS_PRIVACY")


class Capture:
    def __init__(self, item=None):
        self.item = item or candidate()
        self.calls = 0

    def current(self, record_id):
        self.calls += 1
        return self.item if record_id == self.item.record_id else None


class Challenge:
    held = False

    def current(self, record_id):
        return self.held


class Reviewer:
    def __init__(self, agent_id, model_id, *, accepted=True):
        self.agent_id = agent_id
        self.model_id = model_id
        self.accepted = accepted
        self.calls = 0

    def review(self, item, evidence_sha256):
        self.calls += 1
        return AgentReview(
            self.agent_id, self.model_id, evidence_sha256,
            STAGES, self.accepted,
        )


class Surface:
    def __init__(self):
        self.visible = {}
        self.withdrawals = []
        self.fail_readback = False

    def publish(self, packet):
        self.visible[packet.candidate.record_id] = candidate_fingerprint(packet.candidate)

    def withdraw(self, record_id):
        self.withdrawals.append(record_id)
        self.visible.pop(record_id, None)

    def current_evidence_sha256(self, record_id):
        if self.fail_readback and record_id in self.visible:
            return "f" * 64
        return self.visible.get(record_id)


class Journal:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)


def harness():
    capture, hold = Capture(), Challenge()
    first, second = Reviewer("agent:one", "gemini:model-1"), Reviewer(
        "agent:two", "local:model-2"
    )
    surface, journal = Surface(), Journal()
    operations = AutonomousOperations(
        capture=capture, challenge=hold, first=first, second=second,
        public_surface=surface, journal=journal,
    )
    return operations, capture, hold, first, second, surface, journal


class AutonomousOperationsTests(unittest.TestCase):
    def test_verified_publication_is_logged_and_read_back_without_people(self):
        ops, _, _, first, second, surface, journal = harness()
        outcome = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(outcome.disposition, "PUBLISH")
        self.assertEqual(surface.current_evidence_sha256("finding:413"), outcome.evidence_sha256)
        self.assertEqual((first.calls, second.calls), (1, 1))
        self.assertEqual([row.disposition for row in journal.events], ["INTENT", "PUBLISH"])

    def test_correction_withdraws_before_any_models_execute(self):
        ops, _, hold, first, second, surface, _ = harness()
        self.assertEqual(ops.evaluate_and_apply("finding:413", now=NOW).disposition, "PUBLISH")
        hold.held = True
        calls_before = (first.calls, second.calls)
        blocked = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(blocked.disposition, "HOLD")
        self.assertIn("CHALLENGE_HOLD", blocked.reason_codes)
        self.assertEqual((first.calls, second.calls), calls_before)
        self.assertIsNone(surface.current_evidence_sha256("finding:413"))

    def test_after_updated_rights_stale_old_decision_is_replaced_autonomously(self):
        ops, capture, _, _, second, surface, journal = harness()
        ops.evaluate_and_apply("finding:413", now=NOW)
        second.accepted = False
        self.assertEqual(ops.evaluate_and_apply("finding:413", now=NOW).disposition, "HOLD")
        self.assertIsNone(surface.current_evidence_sha256("finding:413"))
        capture.item = replace(capture.item, rights_cleared=True, snapshot_sha256="b" * 64)
        second.accepted = True
        reopened = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(reopened.disposition, "PUBLISH")
        self.assertEqual(surface.current_evidence_sha256("finding:413"), reopened.evidence_sha256)
        self.assertEqual(daily_metrics(journal.events, date(2026, 10, 25), corrections=())["published"], 1)
        self.assertEqual(daily_metrics(journal.events, date(2026, 10, 25), corrections=())["publish_events"], 2)

    def test_daily_metrics_report_current_holds_and_correction_lifecycle(self):
        ops, capture, hold, _, _, _, journal = harness()
        ops.evaluate_and_apply("finding:413", now=NOW - timedelta(days=1))
        capture.item = replace(candidate(), record_id="finding:other")
        ops.evaluate_and_apply("finding:other", now=NOW - timedelta(days=1))
        hold.held = True
        ops.evaluate_and_apply("finding:other", now=NOW)
        correction_events = (
            CorrectionMetricEvent("correction:1", NOW, "OPEN"),
            CorrectionMetricEvent("correction:1", NOW + timedelta(hours=1), "RESOLVED"),
            CorrectionMetricEvent("correction:2", NOW, "OPEN"),
        )
        metrics = daily_metrics(journal.events, NOW.date(), corrections=correction_events)
        self.assertEqual(metrics["published"], 1)
        self.assertEqual(metrics["held"], 1)
        self.assertEqual(metrics["corrections"], 2)
        self.assertEqual(metrics["corrections_resolved"], 1)
        self.assertEqual(metrics["corrections_pending"], 1)
        self.assertEqual(metrics["publish_events"], 0)

    def test_mismatch_in_current_capture_after_review_withholds(self):
        ops, capture, _, first, _, surface, _ = harness()
        old = first.review

        def replace_capture_after_review(item, sha):
            capture.item = replace(item, snapshot_sha256="d" * 64)
            return old(item, sha)

        first.review = replace_capture_after_review
        result = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("STALE_ORIGINAL", result.reason_codes)
        self.assertIsNone(surface.current_evidence_sha256("finding:413"))

    def test_public_readback_failure_rolls_back_publish(self):
        ops, _, _, _, _, surface, journal = harness()
        surface.fail_readback = True
        result = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("PUBLIC_READBACK_FAILED", result.reason_codes)
        self.assertIsNone(surface.current_evidence_sha256("finding:413"))
        self.assertEqual([r.disposition for r in journal.events], ["INTENT", "HOLD"])

    def test_cannot_claim_hold_when_withdrawal_not_observable(self):
        ops, _, hold, _, _, surface, _ = harness()
        hold.held = True
        surface.visible["finding:413"] = "a" * 64
        surface.withdraw = lambda record_id: None
        with self.assertRaises(PublicationSafetyError):
            ops.evaluate_and_apply("finding:413", now=NOW)

    def test_nightly_third_model_audit_disagreement_withdraws(self):
        ops, capture, _, _, _, surface, journal = harness()
        ops.evaluate_and_apply("finding:413", now=NOW)
        item = capture.item
        packet = AutonomousProofPacket(item, *reviews(item))
        third = Reviewer("agent:nightly", "other:model-3", accepted=False)
        outcome = ops.audit_and_apply(packet, third, now=NOW)
        self.assertEqual(outcome.disposition, "AUDIT_HOLD")
        self.assertIn("THIRD_REVIEW_FAILED", outcome.reason_codes)
        self.assertIsNone(surface.current_evidence_sha256("finding:413"))
        self.assertEqual(daily_metrics(journal.events, date(2026, 10, 25), corrections=())["audit_holds"], 1)

    def test_nightly_auditor_cannot_reuse_an_original_model(self):
        ops, capture, _, _, _, surface, _ = harness()
        ops.evaluate_and_apply("finding:413", now=NOW)
        packet = AutonomousProofPacket(capture.item, *reviews(capture.item))
        auditor = Reviewer("agent:nightly", packet.primary.model_id.upper())
        outcome = ops.audit_and_apply(packet, auditor, now=NOW)
        self.assertEqual(outcome.disposition, "AUDIT_HOLD")
        self.assertIsNone(surface.current_evidence_sha256("finding:413"))

    def test_nightly_sampling_is_deterministic_and_unique(self):
        ops, capture, _, _, _, _, journal = harness()
        for index in range(13):
            capture.item = replace(candidate(), record_id=f"finding:{index}")
            ops.evaluate_and_apply(capture.item.record_id, now=NOW)
        first = nightly_sample(journal.events, date(2026, 10, 25))
        second = nightly_sample(tuple(reversed(journal.events)), date(2026, 10, 25))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)

    def test_nightly_sample_excludes_retracted_item_even_same_instant(self):
        ops, _, hold, _, _, _, journal = harness()
        ops.evaluate_and_apply("finding:413", now=NOW)
        hold.held = True
        ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(nightly_sample(journal.events, date(2026, 10, 25)), ())

    def test_nightly_sample_includes_republished_item_at_same_instant(self):
        ops, _, hold, _, _, _, journal = harness()
        ops.evaluate_and_apply("finding:413", now=NOW)
        hold.held = True
        ops.evaluate_and_apply("finding:413", now=NOW)
        hold.held = False
        ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(
            daily_metrics(journal.events, NOW.date(), corrections=())["published"], 1
        )
        self.assertEqual(nightly_sample(journal.events, NOW.date()), ("finding:413",))

    def test_nightly_sample_rechecks_old_publications_on_subsequent_days(self):
        ops, _, _, _, _, _, journal = harness()
        ops.evaluate_and_apply("finding:413", now=NOW - timedelta(days=3))
        self.assertEqual(
            nightly_sample(journal.events, date(2026, 10, 25)), ("finding:413",)
        )

    def test_nightly_sample_executes_auditor_against_saved_current_packet(self):
        ops, capture, _, _, _, surface, journal = harness()
        ops.evaluate_and_apply("finding:413", now=NOW)
        packet = AutonomousProofPacket(capture.item, *reviews(capture.item))

        class Packets:
            def current_packet(self, record_id):
                return packet if record_id == packet.candidate.record_id else None

        auditor = Reviewer("agent:nightly", "other:model-3")
        outcomes = ops.audit_nightly_sample(
            journal_events=tuple(journal.events), day=date(2026, 10, 25),
            packet_authority=Packets(), third=auditor, now=NOW,
        )
        self.assertEqual([outcome.disposition for outcome in outcomes], ["AUDIT_PASS"])
        self.assertEqual(auditor.calls, 1)
        self.assertIn("finding:413", surface.visible)

    def test_missing_nightly_packet_withdraws_immediately(self):
        ops, _, _, _, _, surface, journal = harness()
        ops.evaluate_and_apply("finding:413", now=NOW)

        class Packets:
            def current_packet(self, record_id):
                return None

        outcomes = ops.audit_nightly_sample(
            journal_events=tuple(journal.events), day=date(2026, 10, 25),
            packet_authority=Packets(),
            third=Reviewer("agent:nightly", "other:model-3"), now=NOW,
        )
        self.assertEqual([outcome.disposition for outcome in outcomes], ["AUDIT_HOLD"])
        self.assertEqual(outcomes[0].reason_codes, ("AUDIT_PACKET_UNAVAILABLE",))
        self.assertNotIn("finding:413", surface.visible)


if __name__ == "__main__":
    unittest.main()
