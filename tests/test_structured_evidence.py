import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.structured_evidence import (  # noqa: E402
    StructuredEvidenceError,
    normalize_structured_evidence_payload,
)


def payload(records, *, fetch_state="SUCCEEDED", blocker=None, schema="structured-evidence-v1"):
    return {
        "schema_version": schema,
        "provider_id": "dvns-style-test",
        "fetch_state": fetch_state,
        "blocker": blocker,
        "records": records,
    }


def row(**overrides):
    base = {
        "source_record_id": "record:1",
        "source_version": "v1",
        "source_url": "https://data.example.test/records/1",
        "metric": "spesa_euro",
        "value_state": "PRESENT",
        "value_numeric": 0,
        "value_text": None,
        "unit": "EUR",
        "reference_period": "2026-Q2",
        "publication_date": "2026-07-15",
        "observed_at": "2026-10-05T12:00:00+00:00",
        "effective_from": "2026-04-01",
        "effective_to": "2026-07-01",
        "dimensions": {"territory": "IT"},
        "source_roles": ["PRIMARY_RECORD"],
    }
    base.update(overrides)
    return base


class StructuredEvidenceTests(unittest.TestCase):
    def test_zero_is_present_not_missing(self):
        batch = normalize_structured_evidence_payload(payload([row(value_numeric=0)]))
        value = batch.values[0]
        self.assertEqual(value.value_state, "PRESENT")
        self.assertEqual(value.value_numeric, Decimal("0"))
        self.assertIsNone(value.value_text)

    def test_missing_is_distinct_from_zero(self):
        batch = normalize_structured_evidence_payload(
            payload(
                [
                    row(
                        value_state="MISSING",
                        value_numeric=None,
                        value_text=None,
                    )
                ]
            )
        )
        self.assertEqual(batch.values[0].value_state, "MISSING")
        self.assertIsNone(batch.values[0].value_numeric)

    def test_dates_and_reference_period_remain_separate(self):
        value = normalize_structured_evidence_payload(payload([row()])).values[0]
        self.assertEqual(value.reference_period, "2026-Q2")
        self.assertEqual(value.publication_date, "2026-07-15")
        self.assertEqual(value.observed_at, "2026-10-05T12:00:00+00:00")
        self.assertEqual(value.effective_from, "2026-04-01")
        self.assertEqual(value.effective_to, "2026-07-01")

    def test_schema_drift_fails_closed(self):
        with self.assertRaisesRegex(
            StructuredEvidenceError,
            "STRUCTURED_SCHEMA_VERSION_UNSUPPORTED",
        ):
            normalize_structured_evidence_payload(payload([], schema="structured-evidence-v2"))

    def test_failed_provider_is_not_empty_success(self):
        batch = normalize_structured_evidence_payload(
            payload([], fetch_state="FAILED", blocker="UPSTREAM_UNAVAILABLE")
        )
        self.assertEqual(batch.fetch_state, "FAILED")
        self.assertFalse(batch.usable_candidate_batch)
        self.assertEqual(batch.blocker, "UPSTREAM_UNAVAILABLE")

    def test_failed_provider_cannot_return_records(self):
        with self.assertRaisesRegex(
            StructuredEvidenceError,
            "STRUCTURED_NON_SUCCESS_RECORDS_FORBIDDEN",
        ):
            normalize_structured_evidence_payload(
                payload([row()], fetch_state="DEGRADED", blocker="PARTIAL_DATA")
            )

    def test_source_url_must_be_https(self):
        with self.assertRaisesRegex(
            StructuredEvidenceError,
            "STRUCTURED_SOURCE_URL_INVALID",
        ):
            normalize_structured_evidence_payload(
                payload([row(source_url="http://data.example.test/records/1")])
            )

    def test_record_is_candidate_only_without_verdict_or_approval(self):
        value = normalize_structured_evidence_payload(payload([row()])).values[0]
        self.assertFalse(hasattr(value, "assessment"))
        self.assertFalse(hasattr(value, "approved"))
        self.assertFalse(hasattr(value, "verdict"))

    def test_record_identity_changes_with_source_version(self):
        first = normalize_structured_evidence_payload(payload([row(source_version="v1")])).values[0]
        second = normalize_structured_evidence_payload(payload([row(source_version="v2")])).values[0]
        self.assertNotEqual(first.record_id, second.record_id)


if __name__ == "__main__":
    unittest.main()
