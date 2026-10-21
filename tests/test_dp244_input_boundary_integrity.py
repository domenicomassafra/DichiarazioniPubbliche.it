"""DP-244: a reviewed coverage scope must not be widened by hostile primitives."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from dichiarazioni_pubbliche.coverage_catalog_v1 import (
    build_source_coverage, public_freshness_descriptor,
)
from tests.test_dp244_coverage_catalog import NOW, SHA, observation, unit


def decide(rows):
    return build_source_coverage(
        unit(), rows, now=NOW, baseline_sha256=SHA,
        rights_ready=True, budget_ready=True, capability_ready=True,
    )


class CoverageInputBoundaryTests(unittest.TestCase):
    def test_tuple_subclass_cannot_hide_later_revocation(self):
        good = observation(attempt_id="attempt:good", attempted_at=NOW - timedelta(minutes=15))
        revoked = replace(
            good, attempt_id="attempt:revoked", attempted_at=NOW,
            status="RIGHTS_BLOCKED", rights_status="REVOKED",
            source_version=None, content_sha256=None,
            observation_receipt_id=None, enumerated_scope_review_id=None,
            enumeration_complete_within_scope=False,
        )

        class HideRevocation(tuple):
            def __iter__(self):
                return iter((tuple.__getitem__(self, 0),))

        actual = decide((good, revoked))
        self.assertEqual(actual.state, "UNKNOWN")
        self.assertIsNone(public_freshness_descriptor(actual, public_scope_review_id="review:public"))
        hidden = HideRevocation((good, revoked))
        self.assertEqual(len(hidden), 2)
        with self.assertRaisesRegex(ValueError, "COVERAGE_INPUT_UNBOUNDED"):
            forged = decide(hidden)
            self.assertIsNone(public_freshness_descriptor(forged, public_scope_review_id="review:public"))

    def test_str_subclass_cannot_spoof_cleared_rights(self):
        class LieCleared(str):
            def __eq__(self, other):
                return other == "CLEARED" if isinstance(other, str) else False

            def __ne__(self, other):
                return not self.__eq__(other)

            def __hash__(self):
                return hash("CLEARED")

        self.assertEqual(str(LieCleared("REVOKED")), "REVOKED")
        with self.assertRaisesRegex(ValueError, "COVERAGE_OBSERVATION_STATUS_INVALID"):
            forged = observation(rights_status=LieCleared("REVOKED"))
            decision = decide((forged,))
            self.assertIsNone(public_freshness_descriptor(decision, public_scope_review_id="review:public"))
        revoked = observation(
            rights_status="REVOKED", enumeration_complete_within_scope=False,
            enumerated_scope_review_id=None,
        )
        self.assertEqual(decide((revoked,)).state, "UNKNOWN")
        self.assertEqual(decide((observation(),)).state, "CURRENT_WITHIN_OBSERVED_SCOPE")

    def test_string_leaf_subclasses_rejected_in_unit_and_observation(self):
        class SpoofedText(str):
            pass

        for field, text in (
            ("source_family", "OFFICIAL_TEST_FAMILY"),
            ("mode", "HISTORICAL_BACKFILL"),
            ("version", "source-coverage-catalog-v1"),
        ):
            with self.subTest(unit_field=field), self.assertRaises(ValueError):
                unit(**{field: SpoofedText(text)})
        for field, text in (
            ("status", "UNCHANGED"), ("rights_status", "CLEARED"),
            ("source_version", "version:1"), ("observation_receipt_id", "receipt:test"),
            ("enumerated_scope_review_id", "review:scope:1"),
        ):
            with self.subTest(observation_field=field), self.assertRaises(ValueError):
                observation(**{field: SpoofedText(text)})

    def test_datetime_subclasses_rejected_but_normal_timezone_works(self):
        class SpoofedTime(datetime):
            def astimezone(self, tz=None):
                return datetime(1920, 1, 1, tzinfo=timezone.utc)

        instant = SpoofedTime(2026, 10, 11, 17, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "COVERAGE_AWARE_TIME_REQUIRED"):
            observation(attempted_at=instant)
        with self.assertRaisesRegex(ValueError, "COVERAGE_AWARE_TIME_REQUIRED"):
            unit(interval_start=instant)
        with self.assertRaisesRegex(ValueError, "COVERAGE_AWARE_TIME_REQUIRED"):
            build_source_coverage(unit(), (observation(),), now=instant)
        offset = timezone(timedelta(hours=2))
        ordinary = observation(attempted_at=NOW.astimezone(offset))
        self.assertEqual(decide((ordinary,)).state, "CURRENT_WITHIN_OBSERVED_SCOPE")

    def test_frozen_dataclass_mutation_does_not_elevate_rights(self):
        record = observation()
        object.__setattr__(record, "rights_status", 1)
        with self.assertRaisesRegex(ValueError, "COVERAGE_OBSERVATION_STATUS_INVALID"):
            decide((record,))

    def test_exact_unit_instance_cannot_override_scope_fingerprint_method(self):
        original = unit()
        widened = unit(
            interval_start=datetime(1920, 1, 1, tzinfo=timezone.utc),
            interval_end=datetime(1950, 1, 1, tzinfo=timezone.utc),
        )
        object.__setattr__(widened, "scope_fingerprint", original.scope_fingerprint)
        with self.assertRaisesRegex(ValueError, "COVERAGE_MIXED_SCOPE"):
            build_source_coverage(
                widened, (observation(),), now=NOW, baseline_sha256=SHA,
                rights_ready=True, budget_ready=True, capability_ready=True,
            )


if __name__ == "__main__":
    unittest.main()
