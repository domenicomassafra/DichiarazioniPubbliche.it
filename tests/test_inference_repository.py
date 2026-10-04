import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.domain_vocabulary import (  # noqa: E402
    INFERENCE_VERSION,
    InferenceKind,
    InferenceRiskClass,
    InferenceSupportLevel,
)
from dichiarazioni_pubbliche.inference_repository import (  # noqa: E402
    INSERT_INFERENCE_CANDIDATE_SQL_V1,
    InferenceCandidateRecord,
    deterministic_inference_id,
    inference_candidate_to_sql_parameters,
    normalize_inference_candidate_record,
)


class InferenceRepositoryTests(unittest.TestCase):
    def valid(self) -> dict:
        return {
            "claim_id": "claim:test",
            "conclusion_text": "The available evidence supports proposition X more than the listed alternatives.",
            "inference_kind": InferenceKind.ABDUCTIVE_BEST_EXPLANATION.value,
            "support_level": InferenceSupportLevel.MODERATE.value,
            "premise_refs": ["evidence:a", "observation:b"],
            "assumptions": ["The evidence is authentic."],
            "alternative_hypotheses": ["Alternative A", "Alternative B"],
            "countervailing_factors": ["One premise also supports an innocent mechanism."],
            "disconfirmers": ["A stronger independent observation supporting Alternative A"],
            "risk_class": InferenceRiskClass.STANDARD.value,
            "metadata": {"source": "unit-test"},
        }

    def test_normalizes_and_generates_deterministic_id(self):
        record = normalize_inference_candidate_record(self.valid())
        self.assertTrue(record.resolved_id.startswith("inference:"))
        self.assertEqual(record.inference_version, INFERENCE_VERSION)
        self.assertEqual(record.status, "CANDIDATE")
        self.assertTrue(record.publication_blocked)
        self.assertEqual(
            record.resolved_id,
            deterministic_inference_id(
                claim_id=record.claim_id,
                conclusion_text=record.conclusion_text,
                inference_kind=record.inference_kind,
                premise_refs=record.premise_refs,
            ),
        )

    def test_non_deductive_inference_requires_alternatives(self):
        data = self.valid()
        data["alternative_hypotheses"] = []
        with self.assertRaisesRegex(ValueError, "INFERENCE_ALTERNATIVES_REQUIRED"):
            normalize_inference_candidate_record(data)

    def test_high_risk_inference_requires_disconfirmers(self):
        data = self.valid()
        data["risk_class"] = InferenceRiskClass.IDENTITY_ATTRIBUTION.value
        data["disconfirmers"] = []
        with self.assertRaisesRegex(ValueError, "INFERENCE_DISCONFIRMERS_REQUIRED"):
            normalize_inference_candidate_record(data)

    def test_high_risk_inference_requires_countervailing_factors(self):
        data = self.valid()
        data["risk_class"] = InferenceRiskClass.IDENTITY_ATTRIBUTION.value
        data["countervailing_factors"] = []
        with self.assertRaisesRegex(
            ValueError, "INFERENCE_COUNTERVAILING_FACTORS_REQUIRED"
        ):
            normalize_inference_candidate_record(data)

    def test_numeric_confidence_is_not_part_of_contract(self):
        data = self.valid()
        data["confidence"] = 0.99
        with self.assertRaisesRegex(ValueError, "INFERENCE_RECORD_UNKNOWN_FIELDS"):
            normalize_inference_candidate_record(data)

    def test_publication_cannot_be_enabled(self):
        data = self.valid()
        data["publication_blocked"] = False
        with self.assertRaisesRegex(ValueError, "INFERENCE_PUBLICATION_BLOCK_REQUIRED"):
            normalize_inference_candidate_record(data)

    def test_direct_deduction_does_not_require_alternatives(self):
        record = InferenceCandidateRecord(
            claim_id="claim:direct",
            conclusion_text="The document states X.",
            inference_kind=InferenceKind.DEDUCTIVE.value,
            support_level=InferenceSupportLevel.DIRECT.value,
            premise_refs=("evidence:document",),
        )
        self.assertEqual(record.alternative_hypotheses, ())

    def test_sql_is_private_candidate_insert(self):
        sql = INSERT_INFERENCE_CANDIDATE_SQL_V1
        self.assertIn("INSERT INTO inference_candidate", sql)
        self.assertIn("'CANDIDATE'", sql)
        self.assertIn("true", sql)
        self.assertNotIn("INSERT INTO finding", sql)
        self.assertNotIn("INSERT INTO review_event", sql)

    def test_sql_parameters_are_json_arrays(self):
        params = inference_candidate_to_sql_parameters(self.valid())
        self.assertEqual(params["inference_version"], INFERENCE_VERSION)
        self.assertEqual(params["risk_class"], InferenceRiskClass.STANDARD.value)
        self.assertIn("evidence:a", params["premise_refs"])


if __name__ == "__main__":
    unittest.main()
