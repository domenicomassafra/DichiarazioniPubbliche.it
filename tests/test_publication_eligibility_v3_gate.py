"""DP-413C: historical standard reviewer records are not autonomous v3 authority."""

import unittest

from dichiarazioni_pubbliche.publication_eligibility import evaluate_publication_eligibility
from dichiarazioni_pubbliche.publication_review_persistence import DurableReviewReplay
from tests.test_publication_eligibility import risk, review_event, safety


class LegacyStandardRuntimeGateTests(unittest.TestCase):
    def test_legacy_standard_review_stays_hold_without_v3_authority(self):
        proof = safety()
        standard = risk("STANDARD")
        legacy_approval = review_event(safety_result=proof, risk_result=standard)

        class ReplayStore:
            def replay_attested_chain(self, record_id, *, authority):
                return DurableReviewReplay((legacy_approval,), ())

        result = evaluate_publication_eligibility(
            record_id="finding:1",
            record_version="finding:v1",
            publication_safety=proof,
            high_risk=standard,
            high_risk_input_binding_sha256="b" * 64,
            review_store=ReplayStore(),
            review_authority=object(),
        )
        self.assertEqual(result.disposition, "HOLD_FOR_PUBLICATION_REVIEW")
        self.assertIn("AUTONOMOUS_V3_REVIEW_REQUIRED", result.blockers)
        self.assertEqual(result.counted_review_event_ids, ())


if __name__ == "__main__":
    unittest.main()
