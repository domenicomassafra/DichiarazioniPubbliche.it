import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.citation_assurance import (  # noqa: E402
    CitationBinding,
    FindingAssertion,
    assure_material_assertions,
    finding_assertion_id,
)


class CitationAssuranceTests(unittest.TestCase):
    def assertion(self, *, text="Il valore osservato è 10.", relation="SUPPORT", material=True):
        return FindingAssertion(
            assertion_id="assertion:1",
            text=text,
            material=material,
            required_relation=relation,
        )

    def binding(self, assertion, *, relation="SUPPORT", evidence_id="evidence:1", observation_id=None):
        return CitationBinding(
            assertion_id=assertion.assertion_id,
            assertion_text_sha256=assertion.text_sha256,
            evidence_id=evidence_id,
            relation=relation,
            observation_id=observation_id,
        )

    def test_material_assertion_with_approved_support_passes(self):
        assertion = self.assertion()
        result = assure_material_assertions(
            [assertion],
            [self.binding(assertion)],
            approved_evidence_ids=["evidence:1"],
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.supported_assertion_count, 1)

    def test_uncited_material_assertion_fails(self):
        assertion = self.assertion()
        result = assure_material_assertions(
            [assertion],
            [],
            approved_evidence_ids=["evidence:1"],
        )
        self.assertFalse(result.passed)
        self.assertIn("MATERIAL_ASSERTION_UNCITED", {issue.code for issue in result.issues})

    def test_contradiction_does_not_satisfy_support(self):
        assertion = self.assertion()
        result = assure_material_assertions(
            [assertion],
            [self.binding(assertion, relation="CONTRADICT")],
            approved_evidence_ids=["evidence:1"],
        )
        self.assertFalse(result.passed)
        self.assertIn("CITATION_RELATION_MISMATCH", {issue.code for issue in result.issues})

    def test_evidence_outside_finding_packet_fails(self):
        assertion = self.assertion()
        result = assure_material_assertions(
            [assertion],
            [self.binding(assertion, evidence_id="evidence:other")],
            approved_evidence_ids=["evidence:1"],
        )
        self.assertFalse(result.passed)
        self.assertIn("EVIDENCE_NOT_APPROVED_FOR_FINDING", {issue.code for issue in result.issues})

    def test_changed_assertion_text_stales_binding(self):
        old = self.assertion(text="Il valore osservato è 10.")
        changed = self.assertion(text="Il valore osservato è 11.")
        result = assure_material_assertions(
            [changed],
            [self.binding(old)],
            approved_evidence_ids=["evidence:1"],
        )
        self.assertFalse(result.passed)
        self.assertIn("ASSERTION_TEXT_HASH_STALE", {issue.code for issue in result.issues})

    def test_unapproved_observation_fails(self):
        assertion = self.assertion()
        result = assure_material_assertions(
            [assertion],
            [self.binding(assertion, observation_id="observation:1")],
            approved_evidence_ids=["evidence:1"],
            approved_observation_ids=[],
        )
        self.assertFalse(result.passed)
        self.assertIn("OBSERVATION_NOT_APPROVED_FOR_FINDING", {issue.code for issue in result.issues})

    def test_non_material_copy_does_not_require_citation(self):
        assertion = self.assertion(text="Approfondisci la fonte.", material=False)
        result = assure_material_assertions(
            [assertion],
            [],
            approved_evidence_ids=[],
        )
        self.assertTrue(result.passed)

    def test_finding_assertion_id_is_text_and_finding_versioned(self):
        first = finding_assertion_id("finding:1", "Rationale A")
        same = finding_assertion_id("finding:1", "Rationale A")
        changed_text = finding_assertion_id("finding:1", "Rationale B")
        changed_finding = finding_assertion_id("finding:2", "Rationale A")
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed_text)
        self.assertNotEqual(first, changed_finding)


if __name__ == "__main__":
    unittest.main()
