"""DP-314 synthetic preflight only; no real evidence truth/gold or publication."""

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.verification_requirements_v1 import (  # noqa: E402
    RequirementClaim,
    RequirementEvidence,
    SequenceEventObservation,
    compare_private_event_sequence,
    preflight_verification_requirements,
    select_requirement_profile,
)


def claim(kind="EVENT_SEQUENCE", **kwargs):
    return replace(
        RequirementClaim(
            "claim:synthetic",
            kind,
            "2025-06-01",
            "jurisdiction:it",
            "a" * 64,
            "policy:test:v1",
            "2025-07-01",
            "COMPLETED",
        ),
        **kwargs,
    )


def record(name, role, root, *, sha=None, **kwargs):
    return replace(
        RequirementEvidence(
            "evidence:" + name,
            sha or (name[0] * 64),
            root,
            "source:" + root,
            "locator:" + name,
            role,
            "2025-05-25",
            "jurisdiction:it",
            "SUPPORT",
            "APPROVED",
            "APPROVED",
        ),
        **kwargs,
    )


def sources():
    return (
        record("alpha", "PRIMARY_RECORD", "root:a"),
        record("beta", "INDEPENDENT_RECORD", "root:b"),
    )


def sequence_sources():
    raw_rows = (
        record("alpha", "PRIMARY_RECORD", "root:a"),
        record("beta", "INDEPENDENT_RECORD", "root:b"),
        record("gamma", "PRIMARY_RECORD", "root:c"),
        record("delta", "INDEPENDENT_RECORD", "root:d"),
    )
    rows = tuple(replace(row, evidence_sha256=f"{index + 1:064x}")
                 for index, row in enumerate(raw_rows))
    observations = tuple(
        SequenceEventObservation(
            evidence_id=row.evidence_id,
            evidence_sha256=row.evidence_sha256,
            event_ref="event:left" if index < 2 else "event:right",
            occurred_on="2025-05-10" if index < 2 else "2025-05-20",
        )
        for index, row in enumerate(rows)
    )
    return rows, observations


class RequirementPreflightTests(unittest.TestCase):
    def test_deterministic_event_sequence_comparison_is_private_and_replayable(self):
        evidence, facts = sequence_sources()
        result = compare_private_event_sequence(
            claim(), evidence, facts, left_event_ref="event:left",
            right_event_ref="event:right", claimed_order="BEFORE",
        )
        self.assertEqual(result.state, "CHECKABLE_PENDING")
        self.assertEqual(result.comparison_status, "OBSERVATIONS_AGREE")
        self.assertEqual(result.observed_order, "BEFORE")
        self.assertEqual(result.evidence_ids, tuple(sorted(row.evidence_id for row in evidence)))
        self.assertIsNone(result.verdict)
        self.assertTrue(result.private_only)
        self.assertFalse(result.source_proof_attested)
        self.assertFalse(result.finding_authority)
        self.assertFalse(result.publication_authority)
        self.assertEqual(
            result,
            compare_private_event_sequence(
                claim(), tuple(reversed(evidence)), tuple(reversed(facts)),
                left_event_ref="event:left", right_event_ref="event:right",
                claimed_order="BEFORE",
            ),
        )
        disagree = compare_private_event_sequence(
            claim(), evidence, facts, left_event_ref="event:left",
            right_event_ref="event:right", claimed_order="AFTER",
        )
        self.assertEqual(disagree.comparison_status, "OBSERVATIONS_DISAGREE")
        self.assertEqual(disagree.observed_order, "BEFORE")
        self.assertIsNone(disagree.verdict)
        self.assertNotEqual(result.snapshot_sha256, disagree.snapshot_sha256)

    def test_event_sequence_conflicting_or_duplicate_family_is_not_computable(self):
        evidence, facts = sequence_sources()
        conflicting = tuple(replace(x, occurred_on="2025-05-11") if
                            x.evidence_id == "evidence:beta" else x for x in facts)
        dispute = compare_private_event_sequence(
            claim(), evidence, conflicting, left_event_ref="event:left",
            right_event_ref="event:right", claimed_order="BEFORE",
        )
        self.assertEqual(dispute.state, "UNRESOLVED_CONFLICT")
        self.assertEqual(dispute.comparison_status, "NOT_COMPUTABLE")
        self.assertIn("CONFLICTING_EVENT_DATES", dispute.reason_codes)
        same_family = tuple(replace(row, source_family_ref="source:root:a") if
                            row.evidence_id == "evidence:beta" else row for row in evidence)
        held = compare_private_event_sequence(
            claim(), same_family, facts, left_event_ref="event:left",
            right_event_ref="event:right", claimed_order="BEFORE",
        )
        self.assertEqual(held.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("EVENT_INDEPENDENCE_MISSING", held.reason_codes)
        self.assertEqual(held.comparison_status, "NOT_COMPUTABLE")

    def test_event_sequence_requires_independent_role_sources_per_event(self):
        evidence, facts = sequence_sources()
        # Each event needs a primary and an independent record from different
        # roots AND families. A third primary cannot lend its family to an
        # independent record that shares its root.
        left_extra = replace(
            record("epsilon", "PRIMARY_RECORD", "root:b"),
            source_family_ref="source:separate", evidence_sha256=f"{5:064x}",
        )
        with_shared_origin = tuple(
            replace(row, source_family_ref="source:root:a")
            if row.evidence_id == "evidence:beta" else row for row in evidence
        ) + (left_extra,)
        left_extra_fact = SequenceEventObservation(
            left_extra.evidence_id, left_extra.evidence_sha256,
            "event:left", "2025-05-10",
        )
        blocked = compare_private_event_sequence(
            claim(), with_shared_origin, facts + (left_extra_fact,),
            left_event_ref="event:left", right_event_ref="event:right",
            claimed_order="BEFORE",
        )
        self.assertEqual(blocked.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertEqual(blocked.comparison_status, "NOT_COMPUTABLE")
        self.assertIn("EVENT_INDEPENDENCE_MISSING", blocked.reason_codes)
        # An actual fourth independent origin restores the proposal.
        independent = replace(
            record("zeta", "INDEPENDENT_RECORD", "root:z"),
            evidence_sha256=f"{6:064x}",
        )
        additional = SequenceEventObservation(
            independent.evidence_id, independent.evidence_sha256,
            "event:left", "2025-05-10",
        )
        valid = compare_private_event_sequence(
            claim(), with_shared_origin + (independent,),
            facts + (left_extra_fact, additional),
            left_event_ref="event:left", right_event_ref="event:right",
            claimed_order="BEFORE",
        )
        self.assertEqual(valid.state, "CHECKABLE_PENDING")
        self.assertEqual(valid.comparison_status, "OBSERVATIONS_AGREE")

    def test_same_calendar_day_cannot_refute_within_day_event_order(self):
        evidence, facts = sequence_sources()
        same_day = tuple(replace(row, occurred_on="2025-05-10")
                         if row.event_ref == "event:right" else row for row in facts)
        value = compare_private_event_sequence(
            claim(), evidence, same_day, left_event_ref="event:left",
            right_event_ref="event:right", claimed_order="BEFORE",
        )
        self.assertEqual(value.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertEqual(value.comparison_status, "NOT_COMPUTABLE")
        self.assertIsNone(value.observed_order)
        self.assertIn("SAME_DAY_EVENT_ORDER_UNRESOLVED", value.reason_codes)
        self.assertIsNone(value.verdict)

    def test_event_sequence_rights_wrong_dates_or_unbound_claim_never_compare(self):
        evidence, facts = sequence_sources()
        for change, code in (
            ({"source_use_status": "REVOKED"}, "EVENT_INDEPENDENCE_MISSING"),
            ({"published_date": "2026-01-01"}, "EVENT_INDEPENDENCE_MISSING"),
            ({"jurisdiction_ref": "jurisdiction:de"}, "EVENT_INDEPENDENCE_MISSING"),
        ):
            with self.subTest(change=change):
                withheld = tuple(replace(row, **change) if
                                 row.evidence_id == "evidence:beta" else row for row in evidence)
                result = compare_private_event_sequence(
                    claim(), withheld, facts, left_event_ref="event:left",
                    right_event_ref="event:right", claimed_order="BEFORE",
                )
                self.assertEqual(result.state, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertIn(code, result.reason_codes)
                self.assertEqual(result.comparison_status, "NOT_COMPUTABLE")
        future_event = tuple(replace(x, occurred_on="2025-06-05") if
                             x.event_ref == "event:right" else x for x in facts)
        postponed = compare_private_event_sequence(
            claim(), evidence, future_event, left_event_ref="event:left",
            right_event_ref="event:right", claimed_order="BEFORE",
        )
        self.assertEqual(postponed.comparison_status, "NOT_COMPUTABLE")
        self.assertIn("EVENT_AFTER_STATEMENT_CUTOFF", postponed.reason_codes)
        with self.assertRaisesRegex(ValueError, "SEQUENCE_OBSERVATION_EVIDENCE_SHA_MISMATCH"):
            compare_private_event_sequence(
                claim(), evidence, (replace(facts[0], evidence_sha256="f" * 64), *facts[1:]),
                left_event_ref="event:left", right_event_ref="event:right",
                claimed_order="BEFORE",
            )

    def test_no_run_and_unsupported_claim_never_compute_sequence(self):
        evidence, facts = sequence_sources()
        for kind, run_state, expected in (
            ("EVENT_SEQUENCE", "NOT_STARTED", "NOT_CHECKED"),
            ("FACTUAL_TEXT_COMPARISON", "COMPLETED", "NOT_CHECKABLE_PROFILE_UNAVAILABLE"),
        ):
            result = compare_private_event_sequence(
                claim(kind, run_state=run_state), evidence, facts,
                left_event_ref="event:left", right_event_ref="event:right",
                claimed_order="BEFORE",
            )
            self.assertEqual(result.state, expected)
            self.assertEqual(result.comparison_status, "NOT_COMPUTABLE")
            self.assertIsNone(result.verdict)

    def test_registry_is_explicit_not_universal(self):
        for kind in (
            "EVENT_SEQUENCE",
            "DOCUMENTARY_LEGAL_STATUS",
            "FACTUAL_DENIAL",
            "NUMERIC",
            "FACTUAL_TEXT_COMPARISON",
        ):
            self.assertIsNotNone(select_requirement_profile(kind))
        self.assertIsNone(select_requirement_profile("GENERIC_LLM_TRUE"))

    def test_no_run_attempted_insufficient_and_non_factual_are_distinct(self):
        self.assertEqual(
            preflight_verification_requirements(
                claim(run_state="NOT_STARTED"), ()
            ).state,
            "NOT_CHECKED",
        )
        self.assertEqual(
            preflight_verification_requirements(claim(), ()).state,
            "CHECKED_INSUFFICIENT_EVIDENCE",
        )
        self.assertEqual(
            preflight_verification_requirements(claim("NON_FACTUAL"), ()).state,
            "NON_FACTUAL",
        )
        self.assertEqual(
            preflight_verification_requirements(claim("MAGIC_LLM"), ()).state,
            "NOT_CHECKABLE_PROFILE_UNAVAILABLE",
        )

    def test_two_declared_independent_roles_only_propose_checkable_pending(self):
        result = preflight_verification_requirements(claim(), sources())
        self.assertEqual(result.state, "CHECKABLE_PENDING")
        self.assertEqual(result.observed_independent_roots, 2)
        self.assertEqual(len(result.eligible_evidence_ids), 2)
        self.assertIsNone(result.verdict)
        self.assertFalse(result.finding_authority)
        self.assertFalse(result.publication_authority)

    def test_one_article_and_derivative_copy_cannot_form_independent_roots(self):
        first, second = sources()
        copied = replace(second, primary_root_ref=first.primary_root_ref)
        result = preflight_verification_requirements(claim(), (first, copied))
        self.assertEqual(result.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("INDEPENDENT_ORIGINAL_ROOT_MISSING", result.reason_codes)
        copied = replace(second, evidence_sha256=first.evidence_sha256)
        result = preflight_verification_requirements(claim(), (first, copied))
        self.assertEqual(result.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("CROSS_ROOT_IDENTICAL_BYTES", result.reason_codes)

    def test_two_distinct_roots_from_same_source_family_do_not_meet_independence(self):
        first, second = sources()
        # Two different bytes/root identifiers cannot establish two independent
        # source families when both records come from the same publisher family.
        reused_family = replace(second, source_family_ref=first.source_family_ref)
        result = preflight_verification_requirements(
            claim(), (first, reused_family)
        )
        self.assertEqual(result.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("INDEPENDENT_SOURCE_FAMILY_MISSING", result.reason_codes)
        self.assertEqual(result.observed_independent_roots, 2)
        self.assertIsNone(result.verdict)
        self.assertFalse(result.publication_authority)

    def test_independent_required_roles_cannot_borrow_unrelated_root_or_family(self):
        first, second = sources()
        # Globally two roots and two families exist, but neither possible
        # PRIMARY/INDEPENDENT role pair has both a distinct root and family.
        reused_family = replace(second, source_family_ref=first.source_family_ref)
        new_family_same_root = record(
            "gamma", "PRIMARY_RECORD", second.primary_root_ref,
            source_family_ref="source:third", evidence_sha256=f"{3:064x}",
        )
        blocked = preflight_verification_requirements(
            claim(), (first, reused_family, new_family_same_root)
        )
        self.assertEqual(blocked.observed_independent_roots, 2)
        self.assertEqual(blocked.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertIn("INDEPENDENT_ROLE_SOURCE_PAIR_MISSING", blocked.reason_codes)
        # The same three sources plus a genuinely independent record meet
        # both original/family constraints with the required roles intact.
        independent = record(
            "delta", "INDEPENDENT_RECORD", "root:d",
            evidence_sha256=f"{4:064x}",
        )
        accepted = preflight_verification_requirements(
            claim(), (first, reused_family, new_family_same_root, independent)
        )
        self.assertEqual(accepted.state, "CHECKABLE_PENDING")
        self.assertNotIn("INDEPENDENT_ROLE_SOURCE_PAIR_MISSING", accepted.reason_codes)

    def test_unapproved_rights_and_reviewer_status_stay_excluded(self):
        first, second = sources()
        for change in (
            dict(source_use_status="REVOKED"),
            dict(evidence_review_status="PENDING"),
            dict(evidence_review_status="REVOKED"),
        ):
            row = replace(second, **change)
            outcome = preflight_verification_requirements(claim(), (first, row))
            self.assertEqual(outcome.state, "CHECKED_INSUFFICIENT_EVIDENCE")
            self.assertIn("EVIDENCE_OR_RIGHTS_NOT_APPROVED", outcome.reason_codes)

    def test_later_version_later_evidence_and_wrong_jurisdiction_not_retroactive(self):
        first, second = sources()
        for change, code in (
            (dict(published_date="2025-08-01"), "POST_STATEMENT_EVIDENCE_ONLY"),
            (dict(jurisdiction_ref="jurisdiction:de"), "JURISDICTION_MISMATCH"),
        ):
            outcome = preflight_verification_requirements(
                claim(), (first, replace(second, **change))
            )
            self.assertEqual(outcome.state, "CHECKED_INSUFFICIENT_EVIDENCE")
            self.assertIn(code, outcome.reason_codes)

    def test_conflicting_support_refute_is_not_truth(self):
        first, second = sources()
        result = preflight_verification_requirements(
            claim(), (first, replace(second, stance="REFUTE"))
        )
        self.assertEqual(result.state, "UNRESOLVED_CONFLICT")
        self.assertIn("CONTRADICTORY_REVIEWED_OBSERVATIONS", result.reason_codes)
        self.assertIsNone(result.verdict)

    def test_profiles_do_not_use_incorrect_roles_as_sufficient(self):
        for kind, role in (
            ("DOCUMENTARY_LEGAL_STATUS", "PRIMARY_LEGAL_RECORD"),
            ("NUMERIC", "PRIMARY_STATISTICS"),
            ("FACTUAL_TEXT_COMPARISON", "PRIMARY_TEXT"),
        ):
            with self.subTest(kind=kind):
                good = record("alpha", role, "root:a")
                self.assertEqual(
                    preflight_verification_requirements(claim(kind), (good,)).state,
                    "CHECKABLE_PENDING",
                )
                self.assertEqual(
                    preflight_verification_requirements(
                        claim(kind), (sources()[0],)
                    ).state,
                    "CHECKED_INSUFFICIENT_EVIDENCE",
                )

    def test_same_inputs_replay_hash_independent_of_order_but_policy_changes_hash(self):
        original = preflight_verification_requirements(claim(), sources())
        reversed_order = preflight_verification_requirements(
            claim(), tuple(reversed(sources()))
        )
        self.assertEqual(original.snapshot_sha256, reversed_order.snapshot_sha256)
        changed = preflight_verification_requirements(
            claim(policy_version="policy:test:v2"), sources()
        )
        self.assertNotEqual(original.snapshot_sha256, changed.snapshot_sha256)

    def test_malformed_input_duplicate_ids_and_bad_evidence_sha_fail_closed(self):
        first, second = sources()
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            preflight_verification_requirements(claim(), (first, first))
        with self.assertRaisesRegex(ValueError, "SHA_INVALID"):
            preflight_verification_requirements(
                claim(), (first, replace(second, evidence_sha256="bad"))
            )
        with self.assertRaisesRegex(ValueError, "INPUT_INVALID"):
            preflight_verification_requirements(claim(), (first,) * 129)
        with self.assertRaisesRegex(ValueError, "RUN_INPUT_INVALID"):
            preflight_verification_requirements(
                claim(review_cutoff_date="2024-01-01"), ()
            )

    def test_mutable_subclasses_cannot_change_approval_after_snapshot(self):
        class MutableEvidence(RequirementEvidence):
            def __getattribute__(self, name):
                if name == "evidence_review_status":
                    data = object.__getattribute__(self, "__dict__")
                    count = data.setdefault("_review_reads", 0)
                    data["_review_reads"] = count + 1
                    return "APPROVED" if count == 0 else "REVOKED"
                return super().__getattribute__(name)

        class MutableClaim(RequirementClaim):
            pass

        class MutableObservation(SequenceEventObservation):
            pass

        first, second = sources()
        with self.assertRaisesRegex(ValueError, "REQUIREMENT_INPUT_INVALID"):
            preflight_verification_requirements(
                MutableClaim(**vars(claim())), (first, second)
            )
        with self.assertRaisesRegex(ValueError, "REQUIREMENT_EVIDENCE_INPUT_INVALID"):
            preflight_verification_requirements(
                claim(), (first, MutableEvidence(**vars(second)))
            )
        evidence, observations = sequence_sources()
        with self.assertRaisesRegex(ValueError, "SEQUENCE_OBSERVATION_INPUT_INVALID"):
            compare_private_event_sequence(
                claim(), evidence,
                (MutableObservation(**vars(observations[0])), *observations[1:]),
                left_event_ref="event:left", right_event_ref="event:right",
                claimed_order="BEFORE",
            )

    def test_private_sequence_uses_same_detached_evidence_as_preflight(self):
        evidence, observations = sequence_sources()
        result = compare_private_event_sequence(
            claim(), evidence, observations,
            left_event_ref="event:left", right_event_ref="event:right",
            claimed_order="BEFORE",
        )
        self.assertEqual(result.comparison_status, "OBSERVATIONS_AGREE")
        self.assertFalse(result.publication_authority)
        modified = tuple(replace(row, evidence_review_status="REVOKED")
                         if row.evidence_id == evidence[1].evidence_id else row
                         for row in evidence)
        held = compare_private_event_sequence(
            claim(), modified, observations,
            left_event_ref="event:left", right_event_ref="event:right",
            claimed_order="BEFORE",
        )
        self.assertEqual(held.state, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertNotEqual(held.snapshot_sha256, result.snapshot_sha256)


if __name__ == "__main__":
    unittest.main()
