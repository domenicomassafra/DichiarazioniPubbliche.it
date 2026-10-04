"""Health/error taxonomy tests (DP-504, DP-505).

The taxonomy is the contract between an automated digest and a human at 3am.
These tests assert the properties that make that contract usable: every state
has an action, the tempting-but-forbidden remedies are recorded, and the
blocker list is de-duplicated so identical causes do not become N alerts.
"""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.taxonomy import (  # noqa: E402
    ENTRIES,
    JOB_STATES,
    SEVERITIES,
    SOURCE_HEALTH_STATES,
    actionable,
    classify_blocker_category,
    classify_source_status,
    get,
    validate_taxonomy,
)


class TaxonomyCoverageTests(unittest.TestCase):
    def test_taxonomy_is_coherent(self):
        self.assertEqual(validate_taxonomy(), ())

    def test_every_runtime_state_is_owned(self):
        for state in JOB_STATES + SOURCE_HEALTH_STATES:
            entry = get(state)
            self.assertTrue(
                entry.operator_action,
                f"{state} has no operator action",
            )

    def test_severities_come_from_the_declared_vocabulary(self):
        for entry in ENTRIES:
            self.assertIn(entry.severity, SEVERITIES)

    def test_every_blocked_state_names_the_product_invariant_it_defends(self):
        for entry in ENTRIES:
            if entry.state in {"BLOCKED", "DEAD_LETTER"}:
                self.assertTrue(
                    entry.invariants,
                    f"{entry.state} defends an invariant but names none",
                )
                self.assertTrue(
                    entry.forbidden_remedies,
                    f"{entry.state} has no recorded forbidden remedy",
                )


class ForbiddenRemedyTests(unittest.TestCase):
    """The taxonomy must actively discourage the tempting wrong fixes."""

    def test_blocked_states_forbid_switching_provider(self):
        for state in ("BLOCKED", "DEAD_LETTER", "OMNIROUTE_HTTP", "DEFERRED"):
            remedies = " ".join(get(state).forbidden_remedies)
            self.assertIn(
                "Do not switch provider or model",
                remedies,
                f"{state} does not forbid provider switching",
            )

    def test_blocked_states_forbid_fabricating_receipts(self):
        remedies = " ".join(get("BLOCKED").forbidden_remedies)
        self.assertIn("Do not fabricate", remedies)

    def test_freshness_slo_forbids_lowering_a_gate(self):
        from dichiarazioni_pubbliche.ops.slo import get_slo

        self.assertIn("Do NOT lower a gate", get_slo("SLO-PUBLIC-FRESHNESS").action)

    def test_evidence_blocker_forbids_claiming_an_unfetched_url(self):
        remedies = " ".join(get("EVIDENCE").forbidden_remedies)
        self.assertIn("Never record an evidence URL as fetched", remedies)

    def test_source_blocker_forbids_bypassing_access_restrictions(self):
        remedies = " ".join(get("SOURCE").forbidden_remedies)
        self.assertIn("access restriction", remedies)

    def test_transcript_blocker_forbids_editing_canonical_text(self):
        remedies = " ".join(get("TRANSCRIPT").forbidden_remedies)
        self.assertIn("Do not edit canonical transcript text", remedies)


class PagingPolicyTests(unittest.TestCase):
    def test_only_genuinely_bad_states_page(self):
        paging = {e.state for e in ENTRIES if e.page}
        self.assertIn("DEAD_LETTER", paging)
        self.assertIn("SLO_BREACH", paging)
        for quiet in ("QUEUED", "COMPLETED", "HEALTHY", "SLO_OK", "SLO_AT_RISK"):
            self.assertNotIn(quiet, paging, f"{quiet} must not page an operator")

    def test_budget_exhaustion_is_not_a_page(self):
        self.assertFalse(get("DEFERRED").page)
        self.assertFalse(get("COST").page)


class ClassificationTests(unittest.TestCase):
    def test_exact_category_maps_directly(self):
        self.assertEqual(
            classify_blocker_category("GROQ_API_KEY_MISSING").state,
            "GROQ_API_KEY_MISSING",
        )

    def test_prefixed_category_falls_back_to_its_family(self):
        self.assertEqual(
            classify_blocker_category("OMNIROUTE_HTTP_400:bad_request").state,
            "OMNIROUTE_HTTP",
        )

    def test_unknown_category_is_still_reported(self):
        entry = classify_blocker_category("SOMETHING_NEW")
        self.assertEqual(entry.state, "OTHER")
        self.assertTrue(entry.operator_action)

    def test_empty_category_is_other(self):
        self.assertEqual(classify_blocker_category("").state, "OTHER")

    def test_unknown_source_status_falls_back(self):
        self.assertEqual(classify_source_status("WEIRD").state, "UNKNOWN")


class ActionableNoiseTests(unittest.TestCase):
    """DP-505: the digest must be actionable, not noisy."""

    def test_identical_causes_collapse_to_one_action(self):
        rows = actionable(
            [
                {"category": "OMNIROUTE_API_KEY_MISSING", "count": 1467},
                {"category": "OMNIROUTE_API_KEY_MISSING", "count": 3},
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["count"], 1470)

    def test_one_row_per_distinct_cause(self):
        rows = actionable(
            [
                {"category": "GROQ_API_KEY_MISSING", "count": 9},
                {"category": "OMNIROUTE_API_KEY_MISSING", "count": 11},
                {"category": "TRANSCRIPT_UNCERTAIN", "count": 4635},
            ]
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual({r["category"] for r in rows}, {
            "GROQ_API_KEY_MISSING",
            "OMNIROUTE_API_KEY_MISSING",
            "TRANSCRIPT_UNCERTAIN",
        })

    def test_every_action_row_carries_a_remedy_and_a_forbidden_list(self):
        rows = actionable([{"category": "OMNIROUTE_HTTP", "count": 2}])
        self.assertTrue(rows[0]["operator_action"])
        self.assertTrue(rows[0]["meaning"])
        self.assertIsInstance(rows[0]["forbidden_remedies"], list)

    def test_rows_are_ordered_most_severe_first(self):
        rows = actionable(
            [
                {"category": "GROQ_API_KEY_MISSING", "count": 9},
                {"category": "DEAD_LETTER_CATEGORY", "count": 1},
                {"category": "COST", "count": 1},
            ]
        )
        severities = [r["severity"] for r in rows]
        rank = {"OUTAGE": 0, "CRITICAL": 1, "WARNING": 2, "NOTICE": 3, "INFO": 4}
        self.assertEqual(
            [rank[s] for s in severities],
            sorted(rank[s] for s in severities),
        )

    def test_empty_blocker_list_yields_no_actions(self):
        self.assertEqual(actionable([]), ())

    def test_blocker_counts_never_amplify_the_row_count(self):
        blockers = [
            {"category": "OMNIROUTE_API_KEY_MISSING", "count": 1467},
            {"category": "GROQ_API_KEY_MISSING", "count": 9},
        ]
        rows = actionable(blockers)
        self.assertLessEqual(len(rows), len(blockers))
        self.assertEqual(sum(r["count"] for r in rows), 1476)


if __name__ == "__main__":
    unittest.main()
