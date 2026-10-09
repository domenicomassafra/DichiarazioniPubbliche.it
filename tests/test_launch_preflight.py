import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.launch_preflight import (  # noqa: E402
    CONDITIONAL_SURFACE_TICKETS,
    REQUIRED_RELEASE_ARTIFACTS,
    REQUIRED_LEGAL_QUESTIONS,
    REQUIRED_TICKETS,
    evaluate_launch_preflight,
    parse_legal_statuses,
    parse_plan_statuses,
    repository_launch_preflight,
)


class LaunchPreflightTests(unittest.TestCase):
    def test_current_repository_is_explicit_no_go(self):
        result = repository_launch_preflight(ROOT)
        self.assertEqual(result.disposition, "NO-GO")
        self.assertFalse(result.launchable)
        self.assertTrue(any(code.startswith("TICKET_NOT_DONE:DP-201:BLOCKED") for code in result.blockers))
        self.assertTrue(any(code.startswith("LEGAL_DECISION_NOT_CLOSED:Q-306-01:OPEN") for code in result.blockers))
        self.assertTrue(any(code.startswith("RELEASE_ARTIFACT_MISSING:") for code in result.blockers))

    def test_green_local_ticket_subset_cannot_override_external_or_owner_blocker(self):
        plan = {ticket_id: "DONE" for ticket_id in REQUIRED_TICKETS}
        plan.update({ticket_id: "DONE" for ticket_id in CONDITIONAL_SURFACE_TICKETS})
        legal = {"Q-306-01": "OPEN"}
        artifacts = {name: True for name in REQUIRED_RELEASE_ARTIFACTS}
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses=legal,
            artifact_presence=artifacts,
        )
        self.assertEqual(result.disposition, "NO-GO")
        self.assertIn("LEGAL_DECISION_NOT_CLOSED:Q-306-01:OPEN", result.blockers)

    def test_all_mechanical_inputs_can_only_reach_pending_owner(self):
        plan = {ticket_id: "DONE" for ticket_id in REQUIRED_TICKETS}
        plan.update({ticket_id: "DONE" for ticket_id in CONDITIONAL_SURFACE_TICKETS})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses={question_id: "DECIDED" for question_id in REQUIRED_LEGAL_QUESTIONS},
            artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
        )
        self.assertEqual(result.disposition, "PENDING-OWNER")
        self.assertEqual(result.blockers, ())
        self.assertFalse(result.launchable)

    def test_conditional_admin_or_intake_surface_needs_explicit_decision(self):
        plan = {ticket_id: "DONE" for ticket_id in REQUIRED_TICKETS}
        plan.update({"DP-507": "FUTURE", "DP-508": "FUTURE"})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses={question_id: "DECIDED" for question_id in REQUIRED_LEGAL_QUESTIONS},
            artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
            conditional_surface_decisions={"DP-507": "NOT_APPLICABLE"},
        )
        self.assertIn("CONDITIONAL_SURFACE_UNDECIDED:DP-508:FUTURE", result.blockers)
        self.assertNotIn("CONDITIONAL_SURFACE_UNDECIDED:DP-507:FUTURE", result.blockers)

    def test_missing_release_evidence_is_no_go_even_if_tickets_say_done(self):
        plan = {ticket_id: "DONE" for ticket_id in REQUIRED_TICKETS}
        plan.update({ticket_id: "DONE" for ticket_id in CONDITIONAL_SURFACE_TICKETS})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses={question_id: "DECIDED" for question_id in REQUIRED_LEGAL_QUESTIONS},
            artifact_presence={name: False for name in REQUIRED_RELEASE_ARTIFACTS},
        )
        self.assertEqual(result.disposition, "NO-GO")
        self.assertEqual(set(result.missing_artifacts), set(REQUIRED_RELEASE_ARTIFACTS))

    def test_receipt_is_deterministic_and_changes_with_gate_state(self):
        plan = {ticket_id: "DONE" for ticket_id in REQUIRED_TICKETS}
        plan.update({ticket_id: "DONE" for ticket_id in CONDITIONAL_SURFACE_TICKETS})
        kwargs = dict(
            legal_statuses={question_id: "DECIDED" for question_id in REQUIRED_LEGAL_QUESTIONS},
            artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
        )
        first = evaluate_launch_preflight(plan_statuses=plan, **kwargs)
        second = evaluate_launch_preflight(plan_statuses=dict(reversed(list(plan.items()))), **kwargs)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        changed = dict(plan)
        changed["DP-201"] = "BLOCKED"
        third = evaluate_launch_preflight(plan_statuses=changed, **kwargs)
        self.assertNotEqual(first.receipt_sha256, third.receipt_sha256)

    def test_version_strings_do_not_turn_a_blocker_into_go(self):
        text = "| DP-201 | BLOCKED | x | x |\n| DP-705 | DONE | v1.0.0 release | x |"
        statuses = parse_plan_statuses(text)
        self.assertEqual(statuses["DP-201"], "BLOCKED")
        self.assertEqual(statuses["DP-705"], "DONE")

    def test_legal_parser_uses_only_explicit_decision_status_rows(self):
        text = (
            "| Q-306-01 (DP-301) | x | source | `OPEN` | owner | surface | default | `BLOCKER` |\n"
            "| Q-306-02 (DP-301) | x | source | `DECIDED` | owner | surface | default | `CLOSED` |\n"
        )
        self.assertEqual(
            parse_legal_statuses(text),
            {"Q-306-01": "OPEN", "Q-306-02": "DECIDED"},
        )

    def test_missing_15_legal_rows_cannot_turn_green_subset_into_pending_owner(self):
        plan = {ticket_id: "DONE" for ticket_id in REQUIRED_TICKETS}
        plan.update({ticket_id: "DONE" for ticket_id in CONDITIONAL_SURFACE_TICKETS})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses={"Q-306-01": "DECIDED"},
            artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
        )
        self.assertEqual(result.disposition, "NO-GO")
        self.assertEqual(
            sum(code.endswith(":MISSING") for code in result.blockers), 15,
        )
        self.assertFalse(result.launchable)

    def test_deferred_and_evidence_collected_rows_remain_explicit_blockers(self):
        rows = (
            "| Q-306-01 (DP-301) | question | evidence | `EVIDENCE_COLLECTED` | reviewer | surface | default | `BLOCKER` |\n"
            "| Q-306-02 (DP-301) | question | evidence | `DEFERRED` | reviewer | surface | default | `BLOCKER` |\n"
        )
        statuses = parse_legal_statuses(rows)
        self.assertEqual(statuses, {"Q-306-01": "EVIDENCE_COLLECTED", "Q-306-02": "DEFERRED"})
        with self.assertRaisesRegex(ValueError, "LAUNCH_LEGAL_DUPLICATE_STATUS"):
            parse_legal_statuses(rows + rows.splitlines()[0] + "\n")
        result = evaluate_launch_preflight(
            plan_statuses={ticket: "DONE" for ticket in REQUIRED_TICKETS},
            legal_statuses=statuses,
            artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
            conditional_surface_decisions={ticket: "NOT_APPLICABLE" for ticket in CONDITIONAL_SURFACE_TICKETS},
        )
        self.assertIn("LEGAL_DECISION_NOT_CLOSED:Q-306-01:EVIDENCE_COLLECTED", result.blockers)
        self.assertIn("LEGAL_DECISION_NOT_CLOSED:Q-306-02:DEFERRED", result.blockers)


if __name__ == "__main__":
    unittest.main()
