import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.effective_time import (  # noqa: E402
    EffectiveRecordVersion,
    select_effective_version,
)


def version(
    version_id,
    *,
    valid_from=None,
    valid_to=None,
    publication_date="2026-01-01",
    status="APPROVED",
    superseded_at=None,
):
    return EffectiveRecordVersion(
        version_id=version_id,
        valid_from=valid_from,
        valid_to=valid_to,
        publication_date=publication_date,
        status=status,
        superseded_at=superseded_at,
    )


class EffectiveTimeTests(unittest.TestCase):
    def test_interval_is_start_inclusive_end_exclusive(self):
        row = version("v1", valid_from="2026-01-01", valid_to="2026-06-01")
        self.assertTrue(select_effective_version([row], as_of="2026-01-01").resolved)
        self.assertFalse(select_effective_version([row], as_of="2026-06-01").resolved)

    def test_future_version_cannot_prove_earlier_status(self):
        result = select_effective_version(
            [version("v2", valid_from="2026-07-01")],
            as_of="2026-06-01",
        )
        self.assertEqual(result.status, "INSUFFICIENT")
        self.assertIn("NO_EFFECTIVE_VERSION", result.blockers)

    def test_overlapping_approved_versions_are_unresolved(self):
        result = select_effective_version(
            [
                version("v1", valid_from="2026-01-01"),
                version("v2", valid_from="2026-05-01"),
            ],
            as_of="2026-06-01",
        )
        self.assertEqual(result.status, "UNRESOLVED")
        self.assertEqual(result.blockers, ("CONFLICTING_EFFECTIVE_VERSIONS",))

    def test_post_statement_publication_does_not_backfill_knowledge(self):
        result = select_effective_version(
            [
                version(
                    "v1",
                    valid_from="2026-01-01",
                    publication_date="2026-06-10",
                )
            ],
            as_of="2026-06-01",
            publication_cutoff="2026-06-01",
        )
        self.assertEqual(result.status, "UNRESOLVED")
        self.assertIn("POST_STATEMENT_VERSION_ONLY", result.blockers)

    def test_superseded_version_stops_being_effective(self):
        result = select_effective_version(
            [
                version(
                    "v1",
                    valid_from="2026-01-01",
                    superseded_at="2026-05-15",
                )
            ],
            as_of="2026-06-01",
        )
        self.assertEqual(result.status, "INSUFFICIENT")

    def test_unapproved_version_is_not_selectable(self):
        result = select_effective_version(
            [version("v1", valid_from="2026-01-01", status="CANDIDATE")],
            as_of="2026-06-01",
        )
        self.assertEqual(result.status, "INSUFFICIENT")


if __name__ == "__main__":
    unittest.main()
