import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche import launch_preflight  # noqa: E402
from dichiarazioni_pubbliche.launch_preflight import (  # noqa: E402
    CONDITIONAL_SURFACE_TICKETS,
    REQUIRED_RELEASE_ARTIFACTS,
    REQUIRED_LEGAL_QUESTIONS,
    REQUIRED_TICKETS,
    evaluate_launch_preflight,
    parse_legal_statuses,
    parse_plan_statuses,
    read_ticket_detail_statuses,
    repository_launch_preflight,
)


class LaunchPreflightTests(unittest.TestCase):
    def test_blocked_rehearsal_packet_cannot_clear_a_release_gate(self):
        self.assertIn(
            "RELEASE_REHEARSAL_INCOMPLETE",
            launch_preflight.rehearsal_packet_blockers({
                "version": "launch-rehearsal-v1",
                "execution_status": "BLOCKED_PREREQUISITES",
                "disposition": "NO-GO",
            }),
        )

    def test_complete_claim_without_consumer_and_rollback_evidence_is_rejected(self):
        blockers = launch_preflight.rehearsal_packet_blockers({
            "version": "launch-rehearsal-v1",
            "execution_status": "COMPLETE",
            "source_public_use_authorized": True,
            "proofs": {},
        })
        self.assertIn("RELEASE_REHEARSAL_PROOF_MISSING:rollback", blockers)
        self.assertIn("RELEASE_REHEARSAL_PROOF_MISSING:correction", blockers)
        self.assertIn("RELEASE_REHEARSAL_REVIEW_INCOMPLETE", blockers)

    def test_complete_packet_requires_six_distinct_consumer_receipts_and_review(self):
        proofs = {
            name: {
                "status": "VERIFIED",
                "receipt_id": "receipt:" + name,
                "sha256": "%064x" % (index + 1),
                "consumer": "minipc",
            }
            for index, name in enumerate(launch_preflight.REHEARSAL_PROOF_NAMES)
        }
        packet = {
            "version": "launch-rehearsal-v1",
            "execution_status": "COMPLETE",
            "source_public_use_authorized": True,
            "proofs": proofs,
            "automated_review": {
                "primary": {
                    "agent_id": "agent-primary",
                    "model": "model-a",
                    "input_sha256": "a" * 64,
                    "receipt_sha256": "b" * 64,
                    "checks": {
                        name: "PASS" for name in launch_preflight.AUTOMATED_REVIEW_CHECKS
                    },
                },
                "independent": {
                    "agent_id": "agent-independent",
                    "model": "model-b",
                    "input_sha256": "a" * 64,
                    "receipt_sha256": "c" * 64,
                    "checks": {
                        name: "PASS" for name in launch_preflight.AUTOMATED_REVIEW_CHECKS
                    },
                },
            },
            "disposition": "NO-GO",
        }
        # A NO-GO outcome must stay on HOLD even with six plausible receipts.
        self.assertIn(
            "RELEASE_REHEARSAL_NO_GO",
            launch_preflight.rehearsal_packet_blockers(packet),
        )
        # Hash-looking values and named agents are claims, not verified proofs.
        self.assertIn(
            "RELEASE_REHEARSAL_PROVENANCE_UNVERIFIED",
            launch_preflight.rehearsal_packet_blockers(packet),
        )
        for disposition in ("GO-CANARY", "GO-WITH-HOLDS"):
            packet["disposition"] = disposition
            self.assertIn(
                "RELEASE_REHEARSAL_PROVENANCE_UNVERIFIED",
                launch_preflight.rehearsal_packet_blockers(packet),
            )
        plan = {ticket: "DONE" for ticket in REQUIRED_TICKETS}
        plan.update({ticket: "DONE" for ticket in CONDITIONAL_SURFACE_TICKETS})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses={question: "DECIDED" for question in REQUIRED_LEGAL_QUESTIONS},
            artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
            rehearsal_evidence_blockers=launch_preflight.rehearsal_packet_blockers(packet),
        )
        self.assertEqual(result.disposition, "NO-GO")
        self.assertIn("RELEASE_REHEARSAL_PROVENANCE_UNVERIFIED", result.blockers)
        self.assertFalse(result.launchable)
        packet["automated_review"]["independent"]["model"] = "model-a"
        self.assertIn(
            "RELEASE_REHEARSAL_REVIEW_INCOMPLETE",
            launch_preflight.rehearsal_packet_blockers(packet),
        )
        packet["automated_review"]["independent"]["model"] = "model-b"
        packet["automated_review"]["independent"]["input_sha256"] = "d" * 64
        self.assertIn(
            "RELEASE_REHEARSAL_REVIEW_INCOMPLETE",
            launch_preflight.rehearsal_packet_blockers(packet),
        )
        packet["automated_review"]["independent"]["input_sha256"] = "a" * 64
        packet["proofs"]["rollback"] = dict(packet["proofs"]["correction"])
        self.assertIn(
            "RELEASE_REHEARSAL_PROOF_DUPLICATE",
            launch_preflight.rehearsal_packet_blockers(packet),
        )
        packet["proofs"]["rollback"] = {
            "status": "VERIFIED",
            "receipt_id": "receipt:rollback",
            "sha256": "%064x" % 6,
            "consumer": "minipc",
        }
        packet["proofs"]["rollback"]["sha256"] = "invalid"
        self.assertIn(
            "RELEASE_REHEARSAL_PROOF_MISSING:rollback",
            launch_preflight.rehearsal_packet_blockers(packet),
        )

    def test_incomplete_repository_rehearsal_remains_an_explicit_blocker(self):
        result = repository_launch_preflight(ROOT)
        self.assertIn("RELEASE_REHEARSAL_INCOMPLETE", result.blockers)

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

    def test_all_mechanical_inputs_wait_for_delegated_release_authority(self):
        plan = {ticket_id: "DONE" for ticket_id in REQUIRED_TICKETS}
        plan.update({ticket_id: "DONE" for ticket_id in CONDITIONAL_SURFACE_TICKETS})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            legal_statuses={question_id: "DECIDED" for question_id in REQUIRED_LEGAL_QUESTIONS},
            artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
        )
        self.assertEqual(result.disposition, "PENDING-RELEASE-AUTHORITY")
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

    def test_real_corpus_challenger_and_qualified_review_are_release_dependencies(self):
        # M2 real private corpus, DP-229 adversarial reviewer and DP-307 qualified
        # legal review must not disappear from the M7 graph just because old M2
        # ranges or Q-306 row statuses happened to be marked complete.
        for critical in ("DP-214", "DP-229", "DP-307"):
            with self.subTest(critical=critical):
                plan = {ticket: "DONE" for ticket in REQUIRED_TICKETS}
                plan.update({ticket: "DONE" for ticket in CONDITIONAL_SURFACE_TICKETS})
                plan[critical] = "IN PROGRESS"
                result = evaluate_launch_preflight(
                    plan_statuses=plan,
                    legal_statuses={
                        question: "DECIDED" for question in REQUIRED_LEGAL_QUESTIONS
                    },
                    artifact_presence={
                        name: True for name in REQUIRED_RELEASE_ARTIFACTS
                    },
                )
                self.assertIn(
                    f"TICKET_NOT_DONE:{critical}:IN PROGRESS",
                    result.blockers,
                )
                self.assertEqual(result.disposition, "NO-GO")

    def test_source_promotion_dependencies_cannot_regress_after_completed_milestone(self):
        # The critical private provenance/promotion path is a dependency, not a
        # narrative assumption hidden behind a green UI/release status.
        for critical in ("DP-112", "DP-113", "DP-117", "DP-118", "DP-209", "DP-210", "DP-211", "DP-212", "DP-213"):
            with self.subTest(critical=critical):
                self.assertIn(critical, REQUIRED_TICKETS)

    def test_full_v1_requires_public_and_studio_m4_closure(self):
        # The informational six-page preview is independently scoped in
        # LAUNCH.md. A full v1 release additionally needs the complete M4
        # public/Studio chain, including corpus UX and explicit Case decision.
        self.assertTrue(
            {f"DP-{number}" for number in range(400, 435)}.issubset(REQUIRED_TICKETS)
        )
        for critical in ("DP-416", "DP-418", "DP-420", "DP-421", "DP-422", "DP-429"):
            with self.subTest(critical=critical):
                plan = {ticket: "DONE" for ticket in REQUIRED_TICKETS}
                plan.update({ticket: "DONE" for ticket in CONDITIONAL_SURFACE_TICKETS})
                plan[critical] = "IN PROGRESS"
                result = evaluate_launch_preflight(
                    plan_statuses=plan,
                    legal_statuses={
                        question: "DECIDED" for question in REQUIRED_LEGAL_QUESTIONS
                    },
                    artifact_presence={
                        name: True for name in REQUIRED_RELEASE_ARTIFACTS
                    },
                )
                self.assertEqual(result.disposition, "NO-GO")
                self.assertIn(
                    f"TICKET_NOT_DONE:{critical}:IN PROGRESS", result.blockers
                )

    def test_plan_done_does_not_override_a_still_open_canonical_ticket(self):
        plan = {ticket: "DONE" for ticket in REQUIRED_TICKETS}
        plan.update({ticket: "DONE" for ticket in CONDITIONAL_SURFACE_TICKETS})
        result = evaluate_launch_preflight(
            plan_statuses=plan,
            ticket_detail_statuses={**plan, "DP-214": "IN PROGRESS"},
            legal_statuses={
                question: "DECIDED" for question in REQUIRED_LEGAL_QUESTIONS
            },
            artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
        )
        self.assertEqual(result.disposition, "NO-GO")
        self.assertIn(
            "TICKET_DETAIL_STATUS_MISMATCH:DP-214:PLAN=DONE:DETAIL=IN PROGRESS",
            result.blockers,
        )

    def test_status_file_cannot_disappear_or_become_undecodable(self):
        plan = {ticket: "DONE" for ticket in REQUIRED_TICKETS}
        plan.update({ticket: "DONE" for ticket in CONDITIONAL_SURFACE_TICKETS})
        for detail in ({}, {"DP-214": "BOGUS"}):
            with self.subTest(detail=detail):
                result = evaluate_launch_preflight(
                    plan_statuses=plan,
                    ticket_detail_statuses=detail,
                    legal_statuses={
                        question: "DECIDED" for question in REQUIRED_LEGAL_QUESTIONS
                    },
                    artifact_presence={name: True for name in REQUIRED_RELEASE_ARTIFACTS},
                )
                self.assertEqual(result.disposition, "NO-GO")
                self.assertTrue(any(
                    blocker.startswith("TICKET_DETAIL_STATUS_MISMATCH:DP-214:")
                    for blocker in result.blockers
                ))

    def test_real_ticket_header_reader_normalizes_annotations_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "docs" / "tickets"
            folder.mkdir(parents=True)
            (folder / "DP-214-corpus.md").write_text(
                "# DP-214\nStatus: IN PROGRESS\n", encoding="utf-8"
            )
            (folder / "DP-208-diarization.md").write_text(
                "# DP-208\nStatus: FUTURE (blocked on real reference)\n",
                encoding="utf-8",
            )
            (folder / "DP-229-challenger.md").write_text(
                "# DP-229\nStatus: DONEISH\n", encoding="utf-8",
            )
            self.assertEqual(read_ticket_detail_statuses(Path(directory)), {
                "DP-208": "FUTURE",
                "DP-214": "IN PROGRESS",
                "DP-229": "INVALID",
            })
            (folder / "DP-214-duplicate.md").write_text(
                "# DP-214\nStatus: DONE\n", encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "LAUNCH_TICKET_DETAIL_DUPLICATE:DP-214"):
                read_ticket_detail_statuses(Path(directory))

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

    def test_duplicate_canonical_ticket_rows_fail_even_if_status_is_the_same(self):
        # A duplicated plan ticket must not disappear silently when converting
        # the canonical backlog to the release checklist snapshot.
        text = (
            "| DP-201 | BLOCKED | provider blocker | x |\n"
            "| DP-201 | BLOCKED | duplicate hiding in another section | x |\n"
        )
        with self.assertRaisesRegex(ValueError, "LAUNCH_PLAN_DUPLICATE_STATUS:DP-201"):
            parse_plan_statuses(text)

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
