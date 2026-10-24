"""DP-319: a READY assignment with no executable search budget is held."""

import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.investigation_attempts_v1 import propose_investigation
from tests.test_dp319_investigation_attempts import assignment, spec


class ZeroResearchCapacityTests(unittest.TestCase):
    def test_ready_lane_with_zero_query_or_result_budget_is_not_proposed(self):
        baseline = assignment()
        for changes in (
            {"max_queries": 0},
            {"max_results": 0},
            {"max_results_per_host": 0},
            {"max_results": 1, "max_results_per_host": 2},
        ):
            with self.subTest(changes=changes):
                unusable = replace(baseline, **changes)
                result = propose_investigation(
                    spec=spec(),
                    assignments=(unusable,),
                    observations=(),
                    budget_ready=True,
                    capability_ready=True,
                )
                self.assertEqual(result.status, "WAIT_EXTERNAL")
                self.assertEqual(result.reason_code, "INVESTIGATION_NO_AUTHORIZED_PLAN")
                self.assertIsNone(result.proposed_attempt_id)
                self.assertFalse(result.publication_authority)

        ready = propose_investigation(
            spec=spec(),
            assignments=(baseline,),
            observations=(),
            budget_ready=True,
            capability_ready=True,
        )
        self.assertEqual(ready.status, "READY_PRIVATE_PROPOSAL")
        self.assertIsNotNone(ready.proposed_attempt_id)


if __name__ == "__main__":
    unittest.main()
