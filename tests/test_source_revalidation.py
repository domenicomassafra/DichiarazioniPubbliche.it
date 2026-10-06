import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.source_revalidation import (  # noqa: E402
    RevalidationDisposition,
    SourceSnapshot,
    evaluate_reobservation,
    snapshot_ref,
)


SHA_A = hashlib.sha256(b"source version a").hexdigest()
SHA_B = hashlib.sha256(b"source version b").hexdigest()
NOW = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)


def snapshot(**overrides):
    values = dict(
        source_id="source:official:1",
        observed_at=NOW,
        availability="AVAILABLE",
        content_sha256=SHA_A,
        source_version="v1",
        etag='"etag-a"',
        canonical_url="https://example.test/official/1",
        rights_status="CLEARED",
    )
    values.update(overrides)
    return SourceSnapshot(**values)


class SourceRevalidationTests(unittest.TestCase):
    def test_identical_reobservation_is_idempotent_and_dedupable(self):
        previous = snapshot()
        current = replace(previous, observed_at=NOW.replace(hour=21))
        first = evaluate_reobservation(previous, current, as_of=date(2026, 10, 5))
        second = evaluate_reobservation(previous, current, as_of=date(2026, 10, 5))
        self.assertEqual(first.disposition, RevalidationDisposition.UNCHANGED)
        self.assertFalse(first.needs_reanalysis)
        self.assertEqual(first.event_key, second.event_key)
        self.assertEqual(first.previous_snapshot_ref, snapshot_ref(previous))

    def test_source_unavailable_is_retry_not_content_change(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            availability="UNAVAILABLE",
            content_sha256=None,
            etag=None,
        )
        result = evaluate_reobservation(previous, current, as_of=date(2026, 10, 5))
        self.assertEqual(result.disposition, RevalidationDisposition.AVAILABILITY_RETRY)
        self.assertIn("SOURCE_UNAVAILABLE", result.benign_change_codes)
        self.assertEqual(result.material_change_codes, ())

    def test_changed_bytes_trigger_reanalysis_and_targeted_hold_when_load_bearing(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            content_sha256=SHA_B,
            source_version="v2",
            etag='"etag-b"',
        )
        result = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 5),
            load_bearing_for_quote=True,
        )
        self.assertEqual(result.disposition, RevalidationDisposition.HOLD_REQUIRED)
        self.assertTrue(result.needs_reanalysis)
        self.assertTrue(result.needs_targeted_hold)
        self.assertIn("CONTENT_HASH_CHANGED", result.material_change_codes)

    def test_same_bytes_locator_and_etag_change_are_benign(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            etag='"etag-b"',
            canonical_url="https://example.test/official/renamed",
        )
        result = evaluate_reobservation(previous, current, as_of=date(2026, 10, 5))
        self.assertEqual(result.disposition, RevalidationDisposition.UNCHANGED)
        self.assertIn("ETAG_CHANGED_BYTES_STABLE", result.benign_change_codes)
        self.assertIn("CANONICAL_LOCATOR_CHANGED_BYTES_STABLE", result.benign_change_codes)

    def test_official_supersession_requires_review_and_hold_when_evidence_load_bearing(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            source_version="v2",
            supersedes_version="v1",
            content_sha256=SHA_B,
        )
        result = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 5),
            load_bearing_for_evidence=True,
        )
        self.assertIn("OFFICIAL_VERSION_SUPERSEDED", result.material_change_codes)
        self.assertEqual(result.disposition, RevalidationDisposition.HOLD_REQUIRED)

    def test_rights_and_authority_expiry_fail_closed(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            rights_expires_on=date(2026, 10, 5),
            authority_valid_until=date(2026, 10, 5),
        )
        result = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 5),
            load_bearing_for_evidence=True,
        )
        self.assertIn("RIGHTS_EXPIRED", result.material_change_codes)
        self.assertIn("AUTHORITY_SCOPE_EXPIRED", result.material_change_codes)
        self.assertTrue(result.needs_targeted_hold)

    def test_rights_revocation_is_material_even_if_bytes_are_stable(self):
        previous = snapshot()
        current = replace(
            previous,
            observed_at=NOW.replace(hour=21),
            rights_status="REVOKED",
        )
        result = evaluate_reobservation(
            previous,
            current,
            as_of=date(2026, 10, 5),
            load_bearing_for_quote=True,
        )
        self.assertIn("RIGHTS_STATE_BLOCKED", result.material_change_codes)
        self.assertEqual(result.disposition, RevalidationDisposition.HOLD_REQUIRED)

    def test_historical_snapshot_is_never_mutated(self):
        previous = snapshot(metadata={"private_note": "preserve me"})
        original = previous
        current = replace(previous, observed_at=NOW.replace(hour=21), content_sha256=SHA_B)
        evaluate_reobservation(previous, current, as_of=date(2026, 10, 5))
        self.assertEqual(previous, original)
        self.assertEqual(previous.content_sha256, SHA_A)

    def test_source_identity_and_observation_order_fail_closed(self):
        previous = snapshot()
        with self.assertRaisesRegex(ValueError, "SOURCE_ID_MISMATCH"):
            evaluate_reobservation(
                previous,
                replace(previous, source_id="source:other", observed_at=NOW.replace(hour=21)),
                as_of=date(2026, 10, 5),
            )
        with self.assertRaisesRegex(ValueError, "OBSERVATION_ORDER_INVALID"):
            evaluate_reobservation(
                previous,
                replace(previous, observed_at=NOW.replace(hour=19)),
                as_of=date(2026, 10, 5),
            )


if __name__ == "__main__":
    unittest.main()
