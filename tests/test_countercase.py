import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.countercase import (  # noqa: E402
    CounterEvidence,
    build_countercase_packet,
    evaluate_challenger_readiness,
    evaluate_high_risk_challenger_readiness,
)
from dichiarazioni_pubbliche.high_risk_assertion import (  # noqa: E402
    evaluate_high_risk_candidate,
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
    @staticmethod
    def high_risk_decision():
        return evaluate_high_risk_candidate(
            source_text="Secondo la procura, Rossi avrebbe commesso una frode.",
            normalized_text="Secondo la procura, Rossi avrebbe commesso una frode.",
            identity_resolved=True,
            privacy_allows=True,
            official_record_approved=False,
            jurisdiction_match=False,
            effective_time_match=False,
            human_review_approved=True,
            dual_control_approved=True,
            qualified_policy_accepted=True,
            policy_decision_ref="policy:qualified:challenger-waiver",
        )

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

    def test_changed_evidence_lineage_and_rationale_stales_exact_review(self):
        # Same IDs, relations and aggregate sets must not hide a change in
        # which source supports which rationale and independence lineage.
        original_rows = (
            CounterEvidence(
                evidence_id="e:official:procedure-a",
                relation="CONTRADICT",
                rationale_code="OFFICIAL_RECORD_DISAGREES",
                approved=True,
                suitable=True,
                independence_group="lineage:official-record",
            ),
            CounterEvidence(
                evidence_id="e:report:method-b",
                relation="LIMITATION",
                rationale_code="REPORT_METHODOLOGY_LIMIT",
                approved=True,
                suitable=True,
                independence_group="lineage:independent-report",
            ),
        )
        original = build_countercase_packet(
            claim_id="claim:countercase-replay",
            evidence=original_rows,
            research_complete=True,
        )
        replayed = build_countercase_packet(
            claim_id="claim:countercase-replay",
            evidence=tuple(reversed(original_rows)),
            research_complete=True,
        )
        self.assertEqual(original.packet_id, replayed.packet_id)

        revised = build_countercase_packet(
            claim_id="claim:countercase-replay",
            evidence=(
                replace(
                    original_rows[0],
                    rationale_code=original_rows[1].rationale_code,
                    independence_group=original_rows[1].independence_group,
                ),
                replace(
                    original_rows[1],
                    rationale_code=original_rows[0].rationale_code,
                    independence_group=original_rows[0].independence_group,
                ),
            ),
            research_complete=True,
        )
        self.assertEqual(original.evidence_ids, revised.evidence_ids)
        self.assertEqual(original.rationale_codes, revised.rationale_codes)
        self.assertEqual(original.independence_groups, revised.independence_groups)
        self.assertEqual(original.contradicting_evidence_ids, revised.contradicting_evidence_ids)
        self.assertEqual(original.limitation_evidence_ids, revised.limitation_evidence_ids)
        self.assertNotEqual(original.packet_id, revised.packet_id)
        decision = evaluate_challenger_readiness(
            revised,
            incorporated_packet_id=original.packet_id,
            reviewed_packet_id=original.packet_id,
        )
        self.assertFalse(decision.ready)
        self.assertTrue(decision.review_stale)
        self.assertIn("MATERIAL_CHALLENGER_NOT_INCORPORATED", decision.blockers)
        self.assertIn("CHALLENGER_REVIEW_STALE", decision.blockers)

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

    def test_dp309_high_risk_decision_requires_exact_challenger_packet(self):
        packet = build_countercase_packet(
            claim_id="claim:high-risk",
            evidence=[],
            research_complete=True,
        )
        decision = evaluate_high_risk_challenger_readiness(
            packet,
            high_risk_decision=self.high_risk_decision(),
            incorporated_packet_id=None,
            reviewed_packet_id=None,
        )
        self.assertFalse(decision.ready)
        self.assertIn("HIGH_RISK_CHALLENGER_REQUIRED", decision.blockers)
        self.assertIn("HIGH_RISK_CHALLENGER_REVIEW_REQUIRED", decision.blockers)

        ready = evaluate_high_risk_challenger_readiness(
            packet,
            high_risk_decision=self.high_risk_decision(),
            incorporated_packet_id=packet.packet_id,
            reviewed_packet_id=packet.packet_id,
        )
        self.assertTrue(ready.ready)

    def test_dp309_challenger_waiver_must_bind_exact_qualified_policy_decision(self):
        packet = build_countercase_packet(
            claim_id="claim:waiver",
            evidence=[],
            research_complete=True,
        )
        risk = self.high_risk_decision()
        wrong = evaluate_high_risk_challenger_readiness(
            packet,
            high_risk_decision=risk,
            incorporated_packet_id=None,
            reviewed_packet_id=None,
            challenger_waiver_policy_decision_ref="policy:other",
        )
        self.assertFalse(wrong.ready)

        waived = evaluate_high_risk_challenger_readiness(
            packet,
            high_risk_decision=risk,
            incorporated_packet_id=None,
            reviewed_packet_id=None,
            challenger_waiver_policy_decision_ref=risk.policy_decision_ref,
        )
        self.assertTrue(waived.ready)


if __name__ == "__main__":
    unittest.main()
