"""SLO definition and evaluation tests (DP-504)."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.slo import (  # noqa: E402
    SLO_STATUSES,
    SLOS,
    evaluate,
    get_slo,
    pageable,
    validate_slos,
    worst_status,
)


def _all_measurements(**overrides):
    base = {
        "queue_oldest_queued_seconds": 0.0,
        "queue_drain_ratio": 1.0,
        "estimated_cost_usd_today": 0.0,
        "provider_receipts_today": 0.0,
        "projection_health": 1.0,
        "projection_generated_at_age_seconds": 0.0,
    }
    base.update(overrides)
    return base


class SloDefinitionTests(unittest.TestCase):
    def test_slo_set_is_coherent(self):
        self.assertEqual(validate_slos(), ())

    def test_every_required_dimension_is_covered(self):
        kinds = {slo.kind for slo in SLOS}
        self.assertEqual(
            kinds,
            {"AVAILABILITY", "FRESHNESS", "LATENCY", "DRAIN", "EXHAUSTION"},
            "an operational dimension has no SLO",
        )

    def test_every_slo_tells_the_operator_what_to_do(self):
        for slo in SLOS:
            self.assertTrue(slo.action.strip(), f"{slo.id} has no operator action")
            self.assertTrue(slo.rationale.strip(), f"{slo.id} has no rationale")

    def test_freshness_slo_forbids_gate_lowering_as_a_remedy(self):
        action = get_slo("SLO-PUBLIC-FRESHNESS").action
        self.assertIn("Do NOT lower a gate", action)

    def test_get_slo_rejects_an_unknown_id(self):
        with self.assertRaises(KeyError):
            get_slo("SLO-DOES-NOT-EXIST")


class SloEvaluationTests(unittest.TestCase):
    def test_healthy_measurements_are_all_ok(self):
        results = evaluate(_all_measurements())
        self.assertEqual(worst_status(results), "OK")
        self.assertEqual(pageable(results), ())

    def test_missing_measurement_is_unknown_not_ok(self):
        results = evaluate({"queue_drain_ratio": 1.0})
        statuses = {row["id"]: row["status"] for row in results}
        self.assertEqual(statuses["SLO-PUBLIC-FRESHNESS"], "UNKNOWN")
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "UNKNOWN")

    def test_unknown_worse_than_at_risk_below_breach(self):
        self.assertEqual(
            worst_status([{"status": "OK"}, {"status": "AT_RISK"}, {"status": "UNKNOWN"}]),
            "UNKNOWN",
        )
        self.assertEqual(
            worst_status([{"status": "UNKNOWN"}, {"status": "BREACH"}]), "BREACH"
        )

    def test_exhausted_budget_breaches_the_cost_slo(self):
        results = evaluate(_all_measurements(estimated_cost_usd_today=0.9))
        statuses = {row["id"]: row["status"] for row in results}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "BREACH")
        self.assertIn("SLO-COST-GLOBAL-DAILY", pageable(results))

    def test_per_source_cost_breach_is_independent_of_global(self):
        results = evaluate(
            _all_measurements(estimated_cost_usd_today=0.0, provider_receipts_today=0.95)
        )
        statuses = {row["id"]: row["status"] for row in results}
        self.assertEqual(statuses["SLO-COST-GLOBAL-DAILY"], "OK")
        self.assertEqual(statuses["SLO-COST-SOURCE-DAILY"], "BREACH")

    def test_stale_projection_breaches_freshness(self):
        results = evaluate(_all_measurements(projection_generated_at_age_seconds=90_000))
        statuses = {row["id"]: row["status"] for row in results}
        self.assertEqual(statuses["SLO-PUBLIC-FRESHNESS"], "BREACH")

    def test_non_numeric_measurement_is_unknown(self):
        slo = get_slo("SLO-PUBLIC-FRESHNESS")
        self.assertEqual(slo.evaluate("not-a-number"), "UNKNOWN")
        self.assertEqual(slo.evaluate(None), "UNKNOWN")

    def test_at_most_slo_escalates_through_at_risk(self):
        slo = get_slo("SLO-PUBLIC-FRESHNESS")
        target = slo.target
        self.assertEqual(slo.evaluate(0), "OK")
        self.assertEqual(slo.evaluate(target * 0.8), "AT_RISK")
        self.assertEqual(slo.evaluate(target + 1), "BREACH")

    def test_at_least_slo_escalates_through_at_risk(self):
        slo = get_slo("SLO-PUBLIC-AVAILABILITY")
        self.assertEqual(slo.evaluate(1.0), "OK")
        # The at-risk band is the first quarter of the gap between the target
        # and a perfect ratio, so it is narrow by design for a 99.5% objective.
        self.assertEqual(slo.evaluate(0.9955), "AT_RISK")
        self.assertEqual(slo.evaluate(0.99), "BREACH")

    def test_only_breach_pages(self):
        results = evaluate(
            _all_measurements(projection_generated_at_age_seconds=20_000)
        )
        paged = pageable(results)
        self.assertNotIn("SLO-PUBLIC-FRESHNESS", paged)
        for slo_id in paged:
            row = next(r for r in results if r["id"] == slo_id)
            self.assertEqual(row["status"], "BREACH")

    def test_every_status_is_in_the_declared_vocabulary(self):
        for row in evaluate(_all_measurements()):
            self.assertIn(row["status"], SLO_STATUSES)


if __name__ == "__main__":
    unittest.main()
