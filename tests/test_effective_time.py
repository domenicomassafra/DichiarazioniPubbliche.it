import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.effective_time import (  # noqa: E402
    EffectiveRecordVersion,
    select_effective_version,
    select_verification_version,
)


def version(
    version_id,
    *,
    valid_from=None,
    valid_to=None,
    publication_date="2026-01-01",
    status="APPROVED",
    superseded_at=None,
    observation_date=None,
    reference_period=None,
    authority_id=None,
    record_status="ACTIVE",
):
    return EffectiveRecordVersion(
        version_id=version_id,
        valid_from=valid_from,
        valid_to=valid_to,
        publication_date=publication_date,
        status=status,
        superseded_at=superseded_at,
        observation_date=observation_date,
        reference_period=reference_period,
        authority_id=authority_id,
        record_status=record_status,
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

    def test_temporal_verification_fixture_contract(self):
        fixture_path = ROOT / "tests" / "fixtures" / "effective_time_cases.json"
        cases = json.loads(fixture_path.read_text())
        for case in cases:
            with self.subTest(case=case["id"]):
                rows = [EffectiveRecordVersion(**raw) for raw in case["versions"]]
                result = select_verification_version(
                    rows,
                    statement_date=case["statement_date"],
                    as_of=case["as_of"],
                    scope=case["scope"],
                )
                expected = case["expected"]
                self.assertEqual(result.status, expected["status"])
                self.assertEqual(
                    result.selected_version_id,
                    expected.get("selected_version_id"),
                )
                self.assertEqual(list(result.blockers), expected.get("blockers", []))

    def test_observation_and_reference_period_do_not_backdate_publication(self):
        row = version(
            "stats-v1",
            valid_from="2025-01-01",
            publication_date="2026-06-10",
            observation_date="2026-06-11",
            reference_period="2025",
            authority_id="istat",
        )
        historical = select_verification_version(
            [row],
            statement_date="2026-06-01",
            as_of="2026-06-01",
            scope="HISTORICAL",
        )
        later_outcome = select_verification_version(
            [row],
            statement_date="2026-06-01",
            as_of="2026-06-15",
            scope="LATER_OUTCOME",
        )
        self.assertEqual(historical.blockers, ("POST_STATEMENT_EVIDENCE",))
        self.assertTrue(later_outcome.resolved)

    def test_historical_scope_can_use_later_observation_of_preexisting_source(self):
        row = version(
            "law-v1",
            valid_from="2026-01-01",
            publication_date="2026-01-01",
            observation_date="2026-08-01",
            authority_id="normattiva",
        )
        result = select_verification_version(
            [row],
            statement_date="2026-06-01",
            as_of="2026-06-01",
            scope="HISTORICAL",
        )
        self.assertTrue(result.resolved)

    def test_invalid_scope_relationships_fail_closed(self):
        row = version("v1", valid_from="2026-01-01")
        with self.assertRaisesRegex(ValueError, "HISTORICAL_AS_OF_AFTER_STATEMENT"):
            select_verification_version(
                [row],
                statement_date="2026-06-01",
                as_of="2026-06-02",
                scope="HISTORICAL",
            )
        with self.assertRaisesRegex(ValueError, "LATER_OUTCOME_AS_OF_NOT_AFTER_STATEMENT"):
            select_verification_version(
                [row],
                statement_date="2026-06-01",
                as_of="2026-06-01",
                scope="LATER_OUTCOME",
            )

    def test_unknown_record_status_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "RECORD_STATUS_INVALID"):
            version(
                "v1",
                valid_from="2026-01-01",
                record_status="UNKNOWN",
            )


if __name__ == "__main__":
    unittest.main()
