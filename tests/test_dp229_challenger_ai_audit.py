from __future__ import annotations

import unittest
from dataclasses import replace
from decimal import Decimal

from dichiarazioni_pubbliche.challenger_ai_audit import (
    AiChallengerReview,
    AiExecutionIdentity,
    AiResearchExecution,
    ApprovedMaterialManifest,
    audit_ai_challenger,
)
from dichiarazioni_pubbliche.challenger_material_inventory import ChallengerMaterialInventory
from dichiarazioni_pubbliche.challenger_research import ChallengerResearchRequest
from dichiarazioni_pubbliche.countercase import CounterEvidence, build_countercase_packet


def _input():
    packet = build_countercase_packet(
        claim_id="claim-1", research_complete=True,
        evidence=[
            CounterEvidence("official-1", "CONTRADICT", "OFFICIAL_RECORD", True, True, "origin-1"),
            CounterEvidence("context-2", "LIMITATION", "TIME_SCOPE", True, True, "origin-2"),
        ],
    )
    inventory = ChallengerMaterialInventory("claim-1", "a" * 64, 2, 0, 2, ())
    request = ChallengerResearchRequest(
        "request-1", "claim-1", "READY", ("assignment-1",),
        ("Find strongest contrary primary record",), ("official-adapter",),
        2, 5, 3, Decimal("0"), ("Stop at query budget",), (),
    )
    generator = AiExecutionIdentity(
        "generator", "gen-1", "session-gen", "openai", "gpt", "gpt-6",
        "1" * 64, "2" * 64,
    )
    reviewers = (
        AiExecutionIdentity("critic-1", "review-1", "session-1", "anthropic", "claude", "claude-4", "3" * 64, "4" * 64),
        AiExecutionIdentity("critic-2", "review-2", "session-2", "google", "gemini", "gemini-2", "5" * 64, "6" * 64),
    )
    execution = AiResearchExecution(
        "request-1", "research-receipt-1", 1, 2, Decimal("0"),
        ("assignment-1",), ("official-1", "context-2"),
    )
    manifest = ApprovedMaterialManifest(
        "claim-1", "record-v1", "a" * 64,
        ("official-1", "context-2"), ("official-1",), "approved-source-ledger-1",
    )
    reviews = tuple(
        AiChallengerReview(
            role=role, identity=identity, receipt_id="ai-receipt-" + str(n),
            claim_id="claim-1", record_version="record-v1",
            packet_id=packet.packet_id, material_sha256=inventory.material_sha256,
            research_receipt_id=execution.receipt_id,
            examined_evidence_ids=("official-1", "context-2"),
            counterexample_evidence_ids=("official-1",),
            limitation_codes=("TIME_SCOPE",), review_action="EXAMINED",
        )
        for n, (role, identity) in enumerate(zip(("COUNTEREVIDENCE", "LIMITATIONS"), reviewers), 1)
    )
    return dict(generator=generator, manifest=manifest, inventory=inventory,
                packet=packet, research_request=request, execution=execution, reviews=reviews)


class ChallengerAiAuditTests(unittest.TestCase):
    def test_bounded_cross_family_candidate_is_never_publication_authority(self):
        data = _input()
        result = audit_ai_challenger(**data)
        self.assertEqual(result.status, "NON_AUTHORITATIVE_REVIEW_CANDIDATE")
        self.assertEqual(result.blockers, ())
        self.assertFalse(result.publication_authority)
        self.assertNotEqual(result.status, "READY")
        self.assertEqual(result.audit_sha256, audit_ai_challenger(**data).audit_sha256)
        swapped = replace(data["reviews"][0], receipt_id="other-review")
        self.assertNotEqual(result.audit_sha256,
                            audit_ai_challenger(**(data | {"reviews": (swapped, data["reviews"][1])})).audit_sha256)

    def test_same_model_family_and_actor_are_not_independent(self):
        data = _input()
        same = replace(data["reviews"][1].identity, model_family="claude", actor_ref="critic-1")
        data["reviews"] = (data["reviews"][0], replace(data["reviews"][1], identity=same))
        self.assertIn("CHALLENGER_AI_EXECUTION_NOT_INDEPENDENT", audit_ai_challenger(**data).blockers)

    def test_same_generator_prompt_and_session_blocked(self):
        data = _input()
        same = replace(data["reviews"][0].identity,
                       session_id=data["generator"].session_id,
                       prompt_sha256=data["generator"].prompt_sha256)
        data["reviews"] = (replace(data["reviews"][0], identity=same), data["reviews"][1])
        result = audit_ai_challenger(**data)
        self.assertIn("CHALLENGER_AI_EXECUTION_NOT_INDEPENDENT", result.blockers)
        self.assertIn("CHALLENGER_AI_PROMPT_NOT_SEPARATE", result.blockers)

    def test_conflict_disclosure_blocks(self):
        data = _input()
        conflict = replace(data["reviews"][0].identity, conflict_codes=("SAME_SOURCE_SPONSOR",))
        data["reviews"] = (replace(data["reviews"][0], identity=conflict), data["reviews"][1])
        self.assertIn("CHALLENGER_REVIEW_CONFLICT_DECLARED", audit_ai_challenger(**data).blockers)

    def test_stale_or_unverified_inventory_and_bad_primary_source_hold(self):
        data = _input()
        data["inventory"] = replace(data["inventory"], material_sha256="b" * 64,
                                    pending_or_unverified=1)
        data["manifest"] = replace(data["manifest"], primary_evidence_ids=("unknown",))
        blockers = audit_ai_challenger(**data).blockers
        for expected in ("CHALLENGER_MATERIAL_STALE", "CHALLENGER_MATERIAL_PENDING_OR_UNVERIFIED",
                         "CHALLENGER_PRIMARY_SOURCE_NOT_APPROVED"):
            self.assertIn(expected, blockers)

    def test_unapproved_and_missing_counterevidence_block(self):
        data = _input()
        data["reviews"] = (
            replace(data["reviews"][0], counterexample_evidence_ids=("fabricated",), examined_evidence_ids=("context-2",)),
            replace(data["reviews"][1], examined_evidence_ids=("official-1",)),
        )
        blockers = audit_ai_challenger(**data).blockers
        self.assertIn("CHALLENGER_AI_COUNTEREXAMPLE_NOT_APPROVED", blockers)
        self.assertIn("CHALLENGER_AI_PRIMARY_SOURCE_NOT_EXAMINED", blockers)
        self.assertIn("CHALLENGER_AI_COUNTEREVIDENCE_NOT_EXAMINED", blockers)

    def test_query_result_and_cost_caps_are_bounded(self):
        data = _input()
        data["execution"] = replace(data["execution"], query_count=3,
                                    result_count=6, cost_usd=Decimal("1"))
        blockers = audit_ai_challenger(**data).blockers
        self.assertIn("CHALLENGER_EXECUTED_QUERY_BUDGET_INVALID", blockers)
        self.assertIn("CHALLENGER_EXECUTED_RESULT_BUDGET_INVALID", blockers)
        self.assertIn("CHALLENGER_EXECUTED_COST_BUDGET_INVALID", blockers)

    def test_fake_completed_search_rejected_when_no_queries(self):
        data = _input()
        data["execution"] = replace(data["execution"], query_count=0, executed_assignment_ids=())
        blockers = audit_ai_challenger(**data).blockers
        self.assertIn("CHALLENGER_EXECUTED_QUERY_BUDGET_INVALID", blockers)
        self.assertIn("CHALLENGER_ASSIGNMENT_EXECUTION_INCOMPLETE", blockers)

    def test_review_on_previous_packet_or_version_is_stale(self):
        data = _input()
        data["reviews"] = (replace(data["reviews"][0], packet_id="older-packet",
                                   record_version="record-v0"), data["reviews"][1])
        self.assertIn("CHALLENGER_AI_REVIEW_BINDING_MISMATCH", audit_ai_challenger(**data).blockers)

    def test_review_with_needs_more_never_accepted(self):
        data = _input()
        data["reviews"] = (replace(data["reviews"][0], review_action="NEEDS_MORE"), data["reviews"][1])
        self.assertEqual(audit_ai_challenger(**data).status, "HOLD")

    def test_invalid_budget_types_fail_closed(self):
        data = _input()
        data["execution"] = replace(data["execution"], query_count=True, cost_usd=Decimal("NaN"))
        blockers = audit_ai_challenger(**data).blockers
        self.assertIn("CHALLENGER_EXECUTED_QUERY_BUDGET_INVALID", blockers)
        self.assertIn("CHALLENGER_EXECUTED_COST_BUDGET_INVALID", blockers)

    def test_missing_role_is_a_blocker(self):
        data = _input()
        data["reviews"] = data["reviews"][:1]
        self.assertIn("CHALLENGER_AI_ROLE_COVERAGE_INCOMPLETE", audit_ai_challenger(**data).blockers)

    def test_forged_ready_request_cannot_inflate_native_caps(self):
        data = _input()
        data["research_request"] = replace(data["research_request"],
                                           max_queries=1000000, max_results=1000000,
                                           cost_cap_usd=Decimal("1000000"))
        data["execution"] = replace(data["execution"], query_count=100,
                                    result_count=100, cost_usd=Decimal("100"))
        self.assertIn("CHALLENGER_REQUEST_NATIVE_BUDGET_EXCEEDED",
                      audit_ai_challenger(**data).blockers)

    def test_every_reviewer_must_examine_entire_material_packet(self):
        data = _input()
        data["reviews"] = (replace(data["reviews"][0],
                                   examined_evidence_ids=("official-1",)), data["reviews"][1])
        self.assertIn("CHALLENGER_AI_MATERIAL_NOT_FULLY_EXAMINED",
                      audit_ai_challenger(**data).blockers)

    def test_reviewer_receipt_reuse_is_blocked(self):
        data = _input()
        data["reviews"] = (data["reviews"][0],
                           replace(data["reviews"][1], receipt_id=data["reviews"][0].receipt_id))
        self.assertIn("CHALLENGER_AI_REVIEW_RECEIPT_REUSED",
                      audit_ai_challenger(**data).blockers)

    def test_case_variation_cannot_hide_same_model_family(self):
        data = _input()
        same = replace(data["reviews"][1].identity, model_family=" CLAUDE ")
        data["reviews"] = (data["reviews"][0], replace(data["reviews"][1], identity=same))
        self.assertIn("CHALLENGER_AI_EXECUTION_NOT_INDEPENDENT",
                      audit_ai_challenger(**data).blockers)


if __name__ == "__main__":
    unittest.main()
