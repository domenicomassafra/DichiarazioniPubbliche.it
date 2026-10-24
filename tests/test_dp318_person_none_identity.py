"""DP-318: an explicit NONE identity is not an attested person."""

import unittest

from dichiarazioni_pubbliche.relation_runtime import (
    StatementRelationKind,
    evaluate_scoped_statement_relation,
)
from tests.test_dp318_relations import statement


class PersonIdentitySentinelTests(unittest.TestCase):
    def test_none_identity_cannot_create_same_person_longitudinal_relation(self):
        for unresolved in ("NONE", "person:none"):
            with self.subTest(unresolved=unresolved):
                first = statement(person=unresolved)
                second = statement(
                    "statement:b", person=unresolved,
                    date="2025-06-01", position="OPPOSE",
                )
                decision = evaluate_scoped_statement_relation(first, second)
                self.assertEqual(decision.kind, StatementRelationKind.HOLD)
                self.assertEqual(decision.person_cardinality, 0)
                self.assertIn("PERSON_ID_UNVERIFIED", decision.rationale_codes)
                self.assertFalse(decision.publication_authority)

    def test_none_identity_cannot_create_cross_person_relation(self):
        first = statement(person="person:none")
        second = statement(
            "statement:b", person="person:verified",
            date="2025-06-01", position="OPPOSE",
        )
        decision = evaluate_scoped_statement_relation(first, second)
        self.assertEqual(decision.kind, StatementRelationKind.HOLD)
        self.assertEqual(decision.person_cardinality, 0)
        self.assertIn("PERSON_ID_UNVERIFIED", decision.rationale_codes)


if __name__ == "__main__":
    unittest.main()
