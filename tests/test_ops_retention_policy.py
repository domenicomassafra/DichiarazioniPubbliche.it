import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.retention_policy import (  # noqa: E402
    RULES,
    permanent_artifacts,
    purgeable_artifacts,
    validate_matrix,
)


class RetentionMatrixTests(unittest.TestCase):
    def test_matrix_is_structurally_coherent(self):
        self.assertEqual(validate_matrix(), ())

    def test_every_rule_has_an_implementation_anchor(self):
        self.assertTrue(RULES)
        for rule in RULES:
            self.assertTrue(rule.implemented_by.strip(), rule.artifact)

    def test_durable_provenance_is_never_purgeable(self):
        purgeable = set(purgeable_artifacts())
        for rule in RULES:
            if rule.data_class in {"DURABLE_PROVENANCE", "RECEIPT"}:
                self.assertNotIn(rule.artifact, purgeable)

    def test_transient_and_cache_artifacts_are_explicitly_purgeable(self):
        purgeable = set(purgeable_artifacts())
        expected = {
            rule.artifact
            for rule in RULES
            if rule.data_class in {"TRANSIENT", "CACHE"}
        }
        self.assertEqual(purgeable, expected)

    def test_permanent_artifacts_include_public_history(self):
        self.assertTrue(
            any("public projection bundle" in item for item in permanent_artifacts())
        )


if __name__ == "__main__":
    unittest.main()
