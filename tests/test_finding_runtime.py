import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.finding_runtime import (  # noqa: E402
    finding_draft_from_verification,
    publication_status_for_verification,
)
from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    FindingPublicationStatus,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.verification_runtime import (  # noqa: E402
    VerificationResult,
)


class FindingRuntimeTests(unittest.TestCase):
    def test_deterministic_results_never_auto_publish(self):
        for assessment in (
            VerificationAssessment.SUPPORTED,
            VerificationAssessment.FACTUALLY_FALSE,
            VerificationAssessment.OUTDATED_DATA,
        ):
            self.assertEqual(
                publication_status_for_verification(assessment),
                FindingPublicationStatus.POLICY_HOLD,
            )

    def test_insufficient_and_unresolved_keep_explicit_states(self):
        self.assertEqual(
            publication_status_for_verification(
                VerificationAssessment.INSUFFICIENT_EVIDENCE
            ),
            FindingPublicationStatus.NEEDS_MORE_EVIDENCE,
        )
        self.assertEqual(
            publication_status_for_verification(VerificationAssessment.UNRESOLVED),
            FindingPublicationStatus.UNRESOLVED,
        )

    def test_finding_id_is_verification_and_policy_versioned(self):
        result = VerificationResult(
            claim_id="claim:a",
            assessment=VerificationAssessment.FACTUALLY_FALSE,
            evidence_ids=("evidence:a",),
            blockers=(),
            rationale_codes=("NUMERIC_EXACT_MISMATCH",),
            result={"expected": 10, "observed": 12},
            statement_cutoff="2026-09-01",
        )
        first = finding_draft_from_verification(
            verification_run_id="verification:a",
            input_fingerprint="f" * 64,
            result=result,
        )
        same = finding_draft_from_verification(
            verification_run_id="verification:a",
            input_fingerprint="f" * 64,
            result=result,
        )
        changed = finding_draft_from_verification(
            verification_run_id="verification:b",
            input_fingerprint="f" * 64,
            result=result,
        )
        self.assertEqual(first.finding_id, same.finding_id)
        self.assertNotEqual(first.finding_id, changed.finding_id)
        self.assertEqual(
            first.publication_status, FindingPublicationStatus.POLICY_HOLD.value
        )


if __name__ == "__main__":
    unittest.main()
