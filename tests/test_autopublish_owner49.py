"""Decision 49: executable autopublish consent and uncertainty escalation."""

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from dichiarazioni_pubbliche.autopublish_contract import load_autopublish_contract
from dichiarazioni_pubbliche.autonomous_operations import AutonomousOperations
from dichiarazioni_pubbliche.autonomous_publication import (
    AgentReview, AutonomousProofPacket, candidate_fingerprint,
    evaluate_autonomous_publication,
)
from tests.test_autonomous_operations import (
    NOW, Capture, Challenge, Journal, Reviewer, Surface, fixture_execution_witness,
)
from tests.test_autonomous_publication import candidate, reviews


class OwnerDecision49Tests(unittest.TestCase):
    def setUp(self):
        policy = patch(
            "dichiarazioni_pubbliche.autonomous_publication.APPROVED_REVIEW_MODELS",
            frozenset({"gemini:flash", "local:reviewer", "other:model"}),
        )
        policy.start()
        self.addCleanup(policy.stop)

    def test_contract_cites_exact_owner_decision_and_date(self):
        policy = load_autopublish_contract()
        self.assertEqual(policy["owner_decision"]["number"], 49)
        self.assertEqual(policy["owner_decision"]["date"], "2026-11-10")
        self.assertEqual(policy["normal_review"], "ONE_EDITORIAL")
        self.assertFalse(policy["per_record_owner_go"])
        self.assertEqual(policy["uncertain_review"], "TWO_INDEPENDENT_PLUS_THIRD_AUDIT")

    def test_tampered_or_missing_contract_blocks_publication(self):
        item = candidate()
        first = reviews(item)[0]
        with TemporaryDirectory() as root:
            path = Path(root) / "autopublish.json"
            with patch.dict("os.environ", {
                "DICHIARAZIONI_PUBBLICHE_AUTOPUBLISH_CONFIG": str(path),
            }):
                self.assertIn(
                    "AUTOPUBLISH_CONTRACT",
                    evaluate_autonomous_publication(item, first, None).reason_codes,
                )
                parsed = dict(load_autopublish_contract(
                    str(Path(__file__).resolve().parents[1] / "config/autopublish.v1.json")
                ))
                parsed["owner_decision"] = {**parsed["owner_decision"], "number": 48}
                path.write_text(json.dumps(parsed), encoding="utf-8")
                self.assertIn(
                    "AUTOPUBLISH_CONTRACT",
                    evaluate_autonomous_publication(item, first, None).reason_codes,
                )

    def test_ready_record_publishes_with_one_authenticated_editorial_receipt(self):
        item = candidate()
        capture = Capture(item)
        first = Reviewer("agent:editor", "gemini:flash")
        second = Reviewer("agent:independent", "local:reviewer")
        surface = Surface()
        operations = AutonomousOperations(
            capture=capture, challenge=Challenge(), first=first, second=second,
            public_surface=surface, journal=Journal(),
            verify_provider_execution=fixture_execution_witness,
        )
        receipt = operations.evaluate_and_apply(item.record_id, now=NOW)
        self.assertEqual(receipt.disposition, "PUBLISH")
        self.assertEqual((first.calls, second.calls), (1, 0))
        self.assertEqual(surface.current_evidence_sha256(item.record_id),
                         candidate_fingerprint(item))

    def test_second_reviewer_is_optional_for_ready_record(self):
        item = candidate()
        editor = Reviewer("agent:editor", "gemini:flash")
        surface = Surface()
        operations = AutonomousOperations(
            capture=Capture(item), challenge=Challenge(), first=editor,
            public_surface=surface, journal=Journal(),
            verify_provider_execution=fixture_execution_witness,
        )
        self.assertEqual(
            operations.evaluate_and_apply(item.record_id, now=NOW).disposition,
            "PUBLISH",
        )
        self.assertEqual(editor.calls, 1)

    def test_uncertain_record_requires_2_plus_1_with_three_actual_executions(self):
        item = replace(candidate(), uncertainty_reasons=("SPEAKER_CONFLICT",))
        first = Reviewer("agent:editor", "gemini:flash")
        second = Reviewer("agent:independent", "local:reviewer")
        third = Reviewer("agent:auditor", "other:model")
        surface = Surface()
        ops = AutonomousOperations(
            capture=Capture(item), challenge=Challenge(), first=first, second=second,
            uncertainty_auditor=third, public_surface=surface, journal=Journal(),
            verify_provider_execution=fixture_execution_witness,
        )
        receipt = ops.evaluate_and_apply(item.record_id, now=NOW)
        self.assertEqual(receipt.disposition, "PUBLISH")
        self.assertEqual((first.calls, second.calls, third.calls), (1, 1, 1))
        self.assertEqual(surface.current_evidence_sha256(item.record_id),
                         candidate_fingerprint(item))
        packet = AutonomousProofPacket(
            item, first.last_review, second.last_review, third.last_review,
        )
        self.assertTrue(evaluate_autonomous_publication(
            item, packet.primary, packet.independent, third=packet.third,
        ).publishable)
        self.assertIn(
            "THIRD_AUDIT",
            evaluate_autonomous_publication(
                item, packet.primary, packet.independent,
            ).reason_codes,
        )
        revoked = replace(item, rights_cleared=False)
        ops.capture.item = revoked
        self.assertEqual(ops.evaluate_and_apply(item.record_id, now=NOW).disposition, "HOLD")
        self.assertIsNone(surface.current_evidence_sha256(item.record_id))

    def test_uncertainty_with_unwitnessed_third_receipt_never_publishes(self):
        item = replace(candidate(), uncertainty_reasons=("SOURCE_AMBIGUITY",))
        third = Reviewer("agent:auditor", "other:model")
        ops = AutonomousOperations(
            capture=Capture(item), challenge=Challenge(),
            first=Reviewer("agent:editor", "gemini:flash"),
            second=Reviewer("agent:independent", "local:reviewer"),
            uncertainty_auditor=third,
            public_surface=Surface(), journal=Journal(),
            verify_provider_execution=lambda review: (
                review.agent_id != "agent:auditor"
                and fixture_execution_witness(review)
            ),
        )
        receipt = ops.evaluate_and_apply(item.record_id, now=NOW)
        self.assertEqual(receipt.disposition, "HOLD")
        self.assertIn("REVIEW_EXECUTION_UNVERIFIED", receipt.reason_codes)
        self.assertEqual(third.calls, 1)
        self.assertFalse(ops.surface.visible)

    def test_statement_projection_honors_the_uncertain_third_verification(self):
        from dichiarazioni_pubbliche.public_projection import build_public_projection
        from tests.test_dp435_public_statement_seam import IsolatedStatementSource, STAMP

        source = IsolatedStatementSource()
        original = source.autonomous_publication_evidence

        def escalated(statement_id, version_id):
            packet = original(statement_id, version_id)
            item = replace(packet.candidate, uncertainty_reasons=("CONTEXT_AMBIGUITY",))
            binding = candidate_fingerprint(item)
            return AutonomousProofPacket(
                item,
                replace(packet.primary, evidence_sha256=binding),
                replace(packet.independent, evidence_sha256=binding),
                AgentReview(
                    "agent:third", "model:3", binding,
                    packet.primary.checked_stages, True,
                ),
            )

        source.autonomous_publication_evidence = escalated
        with patch(
            "dichiarazioni_pubbliche.autonomous_publication.APPROVED_REVIEW_MODELS",
            frozenset({"model:1", "model:2", "model:3"}),
        ):
            self.assertEqual(len(build_public_projection(
                source, generated_at=STAMP, include_public_statements=True,
            )["statements"]), 1)
            source.autonomous_publication_evidence = lambda *args: replace(
                escalated(*args), third=None,
            )
            self.assertEqual(build_public_projection(
                source, generated_at=STAMP, include_public_statements=True,
            )["statements"], [])


if __name__ == "__main__":
    unittest.main()
