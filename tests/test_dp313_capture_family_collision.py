"""DP-313: synthetic immutable capture identifiers across source families."""

import unittest

from dichiarazioni_pubbliche.procedural_document_roles import assess_procedural_independence
from tests.test_dp313_procedural_roles import digest, source


class ProceduralCaptureFamilyCollisionTests(unittest.TestCase):
    def test_capture_id_cannot_be_reused_across_distinct_document_families(self):
        # An immutable capture locator cannot identify two unrelated originals.
        # Different hashes and origin refs must not hide that collision.
        other_text = "Documento sintetico differente."
        same_capture = assess_procedural_independence((
            source(),
            source(
                text=other_text,
                original_record_ref="origin:synthetic-2",
                family_ref="family:court-2",
                source_sha256=digest(other_text),
                page_ranges=((1, 0, len(other_text)),),
            ),
        ))
        self.assertEqual(same_capture.state, "HOLD")
        self.assertIn("CROSS_FAMILY_CAPTURE_CONFLICT", same_capture.reason_codes)
        self.assertEqual(same_capture.independent_evidence_proven, 0)

        distinct_capture = assess_procedural_independence((
            source(),
            source(
                text=other_text,
                capture_ref="capture:test-2",
                original_record_ref="origin:synthetic-2",
                family_ref="family:court-2",
                source_sha256=digest(other_text),
                page_ranges=((1, 0, len(other_text)),),
            ),
        ))
        self.assertEqual(distinct_capture.state, "OBSERVED_LINEAGES_ONLY")
        self.assertEqual(distinct_capture.independent_evidence_proven, 0)


if __name__ == "__main__":
    unittest.main()
