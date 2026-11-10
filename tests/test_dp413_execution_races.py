"""DP-413: provider revocation and challenge races on public boundaries."""

import unittest
from unittest.mock import patch

from dichiarazioni_pubbliche.autonomous_publication import AutonomousProofPacket
from tests.test_autonomous_operations import (
    NOW, Reviewer, fixture_execution_witness, harness,
)


class ExecutionRaceTests(unittest.TestCase):
    def setUp(self):
        models = patch(
            "dichiarazioni_pubbliche.autonomous_publication.APPROVED_REVIEW_MODELS",
            frozenset({"gemini:model-1", "local:model-2", "other:model-3"}),
        )
        models.start()
        self.addCleanup(models.stop)

    def test_provider_witness_revoked_during_public_write_withdraws(self):
        ops, _, _, _, _, surface, _ = harness()
        state = {"witness_valid": True}
        ops.verify_provider_execution = lambda review: (
            state["witness_valid"] and fixture_execution_witness(review)
        )
        original_publish = surface.publish

        def revoke_during_write(packet):
            original_publish(packet)
            state["witness_valid"] = False

        surface.publish = revoke_during_write
        result = ops.evaluate_and_apply("finding:413", now=NOW)
        self.assertEqual(result.disposition, "HOLD")
        self.assertEqual(result.reason_codes, ("REVIEW_EXECUTION_UNVERIFIED",))
        self.assertFalse(surface.visible)

    def test_nightly_audit_skips_third_provider_when_challenge_opens_in_preflight(self):
        ops, capture, challenge, first, second, surface, _ = harness()
        self.assertEqual(ops.evaluate_and_apply("finding:413", now=NOW).disposition, "PUBLISH")
        packet = AutonomousProofPacket(
            capture.item, first.last_review,
            second.review(capture.item, first.last_review.evidence_sha256),
        )
        witnesses = []

        def challenge_during_witness(review):
            witnesses.append(review.agent_id)
            if len(witnesses) == 2:
                challenge.held = True
            return fixture_execution_witness(review)

        ops.verify_provider_execution = challenge_during_witness
        auditor = Reviewer("agent:nightly", "other:model-3")
        result = ops.audit_and_apply(packet, auditor, now=NOW)
        self.assertEqual(result.disposition, "AUDIT_HOLD")
        self.assertEqual(auditor.calls, 0)
        self.assertFalse(surface.visible)
