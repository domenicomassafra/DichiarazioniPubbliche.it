"""DP-314 general verifier: classifications, counter-case and spoofing fixtures."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.dp314_general_verifier_v1 import (  # noqa: E402
    ClaimVerification,
    CounterCase,
    classify_claim,
)
from dichiarazioni_pubbliche.verification_requirements_v1 import (  # noqa: E402
    RequirementClaim,
    RequirementEvidence,
)


def claim(kind="EVENT_SEQUENCE", **kwargs):
    return replace(
        RequirementClaim(
            "claim:pilot",
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


def row(name, role, root, **kwargs):
    return replace(
        RequirementEvidence(
            "evidence:" + name,
            hashlib.sha256(name.encode("utf-8")).hexdigest(),
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


def pair(**kwargs):
    return (
        row("alpha", "PRIMARY_RECORD", "root:a"),
        row("beta", "INDEPENDENT_RECORD", "root:b"),
    )


def counter(outcome="SOURCE_REFUTES_COUNTER", ids=("evidence:alpha", "evidence:beta"),
            **kwargs):
    return CounterCase(
        "counter:pilot",
        "b" * 64,
        outcome,
        ids,
    ) if not kwargs else replace(
        CounterCase("counter:pilot", "b" * 64, outcome, ids), **kwargs
    )


def refused(rows):
    return tuple(row for row in rows if row.source_use_status != "APPROVED")


class ClaimClassificationTests(unittest.TestCase):
    def test_checkable_claim_with_refuted_counter_case_is_verifiable(self):
        result = classify_claim(claim(), pair(), counter())
        self.assertEqual(result.status, "VERIFIABLE")
        self.assertEqual(result.reason_code, "COUNTER_CASE_REFUTED_BY_SOURCES")
        self.assertEqual(
            result.eligible_evidence_ids, ("evidence:alpha", "evidence:beta")
        )
        self.assertEqual(result.required_roles, ("PRIMARY_RECORD", "INDEPENDENT_RECORD"))
        self.assertIsNone(result.verdict)
        self.assertTrue(result.private_only)
        self.assertFalse(result.finding_authority)
        self.assertFalse(result.publication_authority)
        self.assertEqual(len(result.snapshot_sha256), 64)

    def test_refuting_evidence_with_supported_counter_case_is_false(self):
        rows = (
            row("alpha", "PRIMARY_RECORD", "root:a", stance="REFUTE"),
            row("beta", "INDEPENDENT_RECORD", "root:b", stance="REFUTE"),
        )
        result = classify_claim(claim(), rows, counter("SOURCE_SUPPORTS_COUNTER"))
        self.assertEqual(result.status, "FALSE")
        self.assertEqual(result.reason_code, "CLAIM_CONTRADICTED_BY_REVIEWED_EVIDENCE")
        self.assertIsNone(result.verdict)
        self.assertFalse(result.publication_authority)

    def test_single_refuting_row_cannot_make_a_claim_false(self):
        rows = (
            row("alpha", "PRIMARY_RECORD", "root:a", stance="REFUTE"),
            row("beta", "INDEPENDENT_RECORD", "root:b"),
        )
        result = classify_claim(claim(), rows, counter("SOURCE_SUPPORTS_COUNTER"))
        self.assertEqual(result.status, "HELD")
        self.assertNotEqual(result.status, "FALSE")

    def test_counter_case_is_mandatory_before_any_classification(self):
        result = classify_claim(claim(), pair(), None)
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "COUNTER_CASE_REQUIRED")

    def test_unobserved_counter_case_cannot_classify(self):
        result = classify_claim(claim(), pair(), counter("NOT_OBSERVED"))
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "COUNTER_CASE_NOT_OBSERVED")

    def test_counter_case_requires_its_own_independent_evidence_for_verifiable(self):
        # Claim sources are independent, but the counter-case cites only one.
        # The other claim source must not silently count for the counter-case.
        result = classify_claim(
            claim(), pair(), counter(ids=("evidence:alpha",))
        )
        self.assertEqual(result.status, "HELD")
        self.assertEqual(
            result.reason_code, "COUNTER_CASE_INDEPENDENT_EVIDENCE_MISSING"
        )
        self.assertFalse(result.finding_authority)
        self.assertFalse(result.publication_authority)

    def test_counter_case_requires_its_own_independent_evidence_for_false(self):
        rows = (
            row("alpha", "PRIMARY_RECORD", "root:a", stance="REFUTE"),
            row("beta", "INDEPENDENT_RECORD", "root:b", stance="REFUTE"),
        )
        result = classify_claim(
            claim(), rows,
            counter("SOURCE_SUPPORTS_COUNTER", ids=("evidence:beta",)),
        )
        self.assertEqual(result.status, "HELD")
        self.assertEqual(
            result.reason_code, "COUNTER_CASE_INDEPENDENT_EVIDENCE_MISSING"
        )
        self.assertFalse(result.publication_authority)

    def test_counter_case_does_not_borrow_source_family_independence(self):
        # These counter-case rows have two roots, but the same source family.
        # A third row makes the *claim* independent, not this counter-case.
        rows = pair() + (
            row(
                "gamma", "INDEPENDENT_RECORD", "root:c",
                source_family_ref="source:root:a",
            ),
        )
        result = classify_claim(
            claim(), rows,
            counter(ids=("evidence:alpha", "evidence:gamma")),
        )
        self.assertEqual(result.status, "HELD")
        self.assertEqual(
            result.reason_code, "COUNTER_CASE_INDEPENDENT_EVIDENCE_MISSING"
        )

    def test_unknown_counter_case_stance_never_confers_classification(self):
        rows = (pair()[0], replace(pair()[1], stance="UNKNOWN"))
        result = classify_claim(claim(), rows, counter())
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "COUNTER_CASE_STANCE_UNKNOWN")

    def test_counter_case_cannot_cite_excluded_evidence(self):
        rows = pair() + (row("gamma", "PRIMARY_RECORD", "root:c",
                             source_use_status="REVOKED"),)
        result = classify_claim(claim(), rows, counter(ids=("evidence:gamma",)))
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "COUNTER_CASE_EVIDENCE_NOT_ELIGIBLE")

    def test_unknown_claim_kind_is_not_verifiable(self):
        result = classify_claim(claim("OPINION"), pair(), counter())
        self.assertEqual(result.status, "NOT_VERIFIABLE")
        self.assertEqual(result.reason_code, "NO_REQUIREMENT_PROFILE")

    def test_non_factual_claim_is_not_verifiable(self):
        result = classify_claim(claim("NON_FACTUAL"), (), None)
        self.assertEqual(result.status, "NOT_VERIFIABLE")
        self.assertEqual(result.reason_code, "NOT_A_FACTUAL_CLAIM")

    def test_missing_rights_or_review_hold_the_claim(self):
        rows = tuple(
            replace(inner, source_use_status="HELD") for inner in pair()
        )
        result = classify_claim(claim(), rows, counter(ids=("evidence:alpha",)))
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "EVIDENCE_INSUFFICIENT_OR_EXCLUDED")
        self.assertIn("EVIDENCE_OR_RIGHTS_NOT_APPROVED", result.reason_codes)

    def test_conflicting_observations_hold_the_claim(self):
        rows = (
            row("alpha", "PRIMARY_RECORD", "root:a"),
            row("beta", "INDEPENDENT_RECORD", "root:b", stance="REFUTE"),
        )
        result = classify_claim(claim(), rows, counter())
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "OBSERVATIONS_CONFLICT")

    def test_not_started_run_cannot_be_classified(self):
        result = classify_claim(claim(run_state="NOT_STARTED"), pair(), counter())
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "CLAIM_NOT_CHECKED")

    def test_support_with_supported_counter_case_is_a_contradiction(self):
        result = classify_claim(claim(), pair(), counter("SOURCE_SUPPORTS_COUNTER"))
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "COUNTER_CASE_CONTRADICTED_BY_SOURCES")

    def test_unknown_stance_is_held(self):
        rows = (
            row("alpha", "PRIMARY_RECORD", "root:a", stance="UNKNOWN"),
            row("beta", "INDEPENDENT_RECORD", "root:b", stance="UNKNOWN"),
        )
        result = classify_claim(claim(), rows, counter())
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "EVIDENCE_STANCE_UNKNOWN")

    def test_rejected_input_becomes_a_held_code_not_an_exception(self):
        result = classify_claim(claim(review_cutoff_date="2025-05-01"), pair(), counter())
        self.assertEqual(result.status, "HELD")
        self.assertEqual(result.reason_code, "CLAIM_INPUT_REJECTED")
        self.assertIn("REQUIREMENT_RUN_INPUT_INVALID", result.reason_codes)

    def test_shape_violations_are_rejected(self):
        class Tuple(tuple):
            def __iter__(self):
                return iter(())

        class Spoiled(RequirementEvidence):
            pass

        class Outcome(str):
            def __eq__(self, other):
                return True

            def __hash__(self):
                return hash("SOURCE_REFUTES_COUNTER")

        cases = (
            (claim(), list(pair()), counter(), "CLAIM_INPUT_INVALID"),
            (claim(), Tuple(pair()), counter(), "CLAIM_INPUT_INVALID"),
            (claim(), (Spoiled(*pair()[0].__dict__.values()),), counter(),
             "CLAIM_EVIDENCE_INPUT_INVALID"),
            (claim(), pair(), counter(outcome=Outcome("NOT_OBSERVED")),
             "COUNTER_CASE_OUTCOME_UNKNOWN"),
            (claim(), pair(), counter(ids=("evidence:alpha", "evidence:alpha")),
             "COUNTER_CASE_INVALID"),
        )
        for claim_value, rows, case, expected in cases:
            with self.subTest(expected=expected):
                if expected in {"CLAIM_INPUT_INVALID", "CLAIM_EVIDENCE_INPUT_INVALID"}:
                    with self.assertRaises(ValueError) as raised:
                        classify_claim(claim_value, rows, case)
                    self.assertEqual(str(raised.exception), expected)
                else:
                    result = classify_claim(claim_value, rows, case)
                    self.assertEqual(result.status, "HELD")
                    self.assertEqual(result.reason_code, expected)

    def test_snapshot_is_deterministic_and_bound_to_the_inputs(self):
        first = classify_claim(claim(), pair(), counter())
        second = classify_claim(claim(), tuple(reversed(pair())), counter())
        self.assertEqual(first.snapshot_sha256, second.snapshot_sha256)
        other = classify_claim(claim(), pair(), counter("SOURCE_SUPPORTS_COUNTER"))
        self.assertNotEqual(first.snapshot_sha256, other.snapshot_sha256)

    def test_result_never_carries_publication_authority(self):
        fields = ClaimVerification.__dataclass_fields__
        self.assertEqual(fields["verdict"].default, None)
        self.assertEqual(fields["publication_authority"].default, False)
        self.assertEqual(fields["finding_authority"].default, False)
        self.assertNotIn("public_text", fields)
        self.assertEqual(len(refused(pair())), 0)


if __name__ == "__main__":
    unittest.main()
