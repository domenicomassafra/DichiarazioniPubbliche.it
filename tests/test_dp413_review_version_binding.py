"""DP #413: receipt replay across statement and rights versions is forbidden."""

import unittest

from dichiarazioni_pubbliche.public_projection import build_public_projection
from tests.test_dp435_public_statement_seam import IsolatedStatementSource, SOURCE, STAMP


class StatementReviewVersionTests(unittest.TestCase):
    def test_old_autonomous_reviews_cannot_publish_a_new_statement_version_or_rights(self):
        for changed in ("version_id", "source_version", "rights_decision"):
            with self.subTest(changed=changed):
                source = IsolatedStatementSource()
                old_packet = source.autonomous_publication_evidence(
                    source.row["statement_id"], source.row["version_id"]
                )
                if changed == "rights_decision":
                    source.gates["rights"]["decision_id"] = "decision:rights:2"
                else:
                    source.row[changed] = f"{changed}:2"
                    for gate in source.gates.values():
                        gate[changed] = source.row[changed]
                    if changed == "source_version":
                        source.get_statement_source_text = lambda content_id, version: SOURCE
                source.statement_publication_attestations = lambda a, b: source.gates
                source.autonomous_publication_evidence = lambda a, b: old_packet
                bundle = build_public_projection(
                    source, generated_at=STAMP, include_public_statements=True,
                )
                self.assertEqual(bundle["statements"], [])


if __name__ == "__main__":
    unittest.main()
