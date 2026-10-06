import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.countercase import (  # noqa: E402
    CounterEvidence,
    build_countercase_packet,
    evaluate_challenger_readiness,
)


def evidence(evidence_id, relation, *, approved=True, suitable=True, group=None):
    return CounterEvidence(
        evidence_id=evidence_id,
        relation=relation,
        rationale_code=f"{relation}_CASE",
        approved=approved,
        suitable=suitable,
        independence_group=group,
    )


class CounterCaseTests(unittest.TestCase):
    def test_packet_keeps_counterevidence_separate_by_relation(self):
        packet = build_countercase_packet(
            claim_id="claim:1",
            evidence=[
                evidence("e1", "CONTRADICT", group="g1"),
                evidence("e2", "LIMITATION", group="g2"),
                evidence("e3", "CONTEXT", group="g3"),
            ],
            research_complete=True,
        )
        self.assertEqual(packet.status, "READY")
        self.assertEqual(packet.contradicting_evidence_ids, ("e1",))
        self.assertEqual(packet.limitation_evidence_ids, ("e2",))
        self.assertTrue(packet.has_material_countercase)

    def test_unapproved_evidence_cannot_enter_countercase(self):
        packet = build_countercase_packet(
            claim_id="claim:1",
            evidence=[evidence("e1", "CONTRADICT", approved=False)],
            research_complete=True,
        )
        self.assertEqual(packet.evidence_ids, ())
        self.assertFalse(packet.has_material_countercase)
        self.assertIn(
            "UNAPPROVED_OR_UNSUITABLE_COUNTEREVIDENCE_IGNORED",
            packet.blockers,
        )

    def test_incomplete_challenger_research_is_not_ready(self):
        packet = build_countercase_packet(
            claim_id="claim:1",
            evidence=[],
            research_complete=False,
        )
        self.assertEqual(packet.status, "INCOMPLETE")
        self.assertIn("CHALLENGER_RESEARCH_INCOMPLETE", packet.blockers)

    def test_absence_of_counterevidence_is_not_a_truth_verdict(self):
        packet = build_countercase_packet(
            claim_id="claim:1",
            evidence=[],
            research_complete=True,
        )
        self.assertEqual(packet.status, "READY")
        self.assertFalse(packet.has_material_countercase)
        self.assertFalse(hasattr(packet, "assessment"))
        self.assertFalse(hasattr(packet, "verdict"))

    def test_packet_identity_changes_with_material_counterevidence(self):
        empty = build_countercase_packet(
            claim_id="claim:1",
            evidence=[],
            research_complete=True,
        )
        counter = build_countercase_packet(
            claim_id="claim:1",
            evidence=[evidence("e1", "CONTRADICT")],
            research_complete=True,
        )
        self.assertNotEqual(empty.packet_id, counter.packet_id)

    def test_material_challenger_gain_stales_prior_readiness_and_review(self):
        prior = build_countercase_packet(
            claim_id="claim:1",
            evidence=[],
            research_complete=True,
        )
        updated = build_countercase_packet(
            claim_id="claim:1",
            evidence=[evidence("e1", "CONTRADICT")],
            research_complete=True,
        )
        decision = evaluate_challenger_readiness(
            updated,
            incorporated_packet_id=prior.packet_id,
            reviewed_packet_id=prior.packet_id,
        )
        self.assertFalse(decision.ready)
        self.assertTrue(decision.review_stale)
        self.assertIn("MATERIAL_CHALLENGER_NOT_INCORPORATED", decision.blockers)
        self.assertIn("CHALLENGER_REVIEW_STALE", decision.blockers)

        refreshed = evaluate_challenger_readiness(
            updated,
            incorporated_packet_id=updated.packet_id,
            reviewed_packet_id=updated.packet_id,
        )
        self.assertTrue(refreshed.ready)
        self.assertFalse(refreshed.review_stale)

    def test_high_risk_requires_exact_challenger_unless_qualified_policy_waives_it(self):
        packet = build_countercase_packet(
            claim_id="claim:1",
            evidence=[],
            research_complete=True,
        )
        required = evaluate_challenger_readiness(
            packet,
            incorporated_packet_id=None,
            reviewed_packet_id=None,
            high_risk=True,
        )
        self.assertFalse(required.ready)
        self.assertIn("HIGH_RISK_CHALLENGER_REQUIRED", required.blockers)

        waived = evaluate_challenger_readiness(
            packet,
            incorporated_packet_id=None,
            reviewed_packet_id=None,
            high_risk=True,
            qualified_policy_waives_challenger=True,
        )
        self.assertTrue(waived.ready)


if __name__ == "__main__":
    unittest.main()
