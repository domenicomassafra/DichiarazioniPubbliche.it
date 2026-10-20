"""DP-314 rejects evidence overflow before inspecting row metadata."""
import unittest
from dataclasses import replace
from unittest.mock import patch

from dichiarazioni_pubbliche.requirement_research_batch_v1 import build_research_batch
from tests.test_dp314_verification_requirements import claim, sources


class GuardedField(str):
    def __deepcopy__(self, memo):
        raise AssertionError("EXCESS_EVIDENCE_FIELD_COPIED")


class PrecopyEvidenceLimitTests(unittest.TestCase):
    def test_oversize_per_claim_and_global_fail_before_metadata_snapshot(self):
        requirement = claim()
        first, _ = sources()
        poison = replace(first, locator_ref=GuardedField("locator:overflow"))
        for count in (129, 513):
            with self.subTest(count=count):
                rows = (first,) * (count - 1) + (poison,)
                with patch(
                    "dichiarazioni_pubbliche.requirement_research_batch_v1._snap",
                    side_effect=AssertionError("EXCESS_EVIDENCE_SNAPSHOT"),
                ) as snapshot:
                    with self.assertRaisesRegex(ValueError, "^BATCH_TOO_LARGE$"):
                        build_research_batch((requirement,), {requirement.claim_id: rows})
                    snapshot.assert_not_called()
                self.assertEqual(str(poison.locator_ref), "locator:overflow")


if __name__ == "__main__":
    unittest.main()
