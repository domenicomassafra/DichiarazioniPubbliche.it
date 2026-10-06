import copy
import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.dvns_structured_evidence import (  # noqa: E402
    DVNS_AUTHORITY_SCOPE,
    DvnsStructuredEvidenceError,
    import_dvns_structured_evidence,
)
from dichiarazioni_pubbliche.structured_evidence import StructuredEvidenceError  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "dvns-structured-evidence-v1.json"


def fixture_payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class DvnsStructuredEvidenceTests(unittest.TestCase):
    def test_offline_import_preserves_versions_statuses_and_exact_field_provenance(self):
        payload = fixture_payload()
        result = import_dvns_structured_evidence(
            payload,
            expected_provider_id="dvns-synthetic",
        )

        self.assertEqual(result.source_schema_version, payload["schema_version"])
        self.assertEqual(result.source_version, payload["source_version"])
        self.assertEqual(result.rights_status, payload["rights_status"])
        self.assertEqual(result.availability_status, payload["availability_status"])
        self.assertEqual(result.authority_scope, DVNS_AUTHORITY_SCOPE)
        self.assertEqual(
            result.normalized_batch.values[0].source_record_id,
            payload["records"][0]["external_id"],
        )
        self.assertEqual(
            result.provenance[0].fields,
            tuple(sorted(payload["records"][0]["field_provenance"].items())),
        )
        self.assertEqual(
            result.normalized_batch.provider_receipt["rights_status"],
            payload["rights_status"],
        )
        self.assertEqual(
            result.normalized_batch.provider_receipt["availability_status"],
            payload["availability_status"],
        )

    def test_replay_is_order_independent_and_exact_duplicates_are_deduplicated(self):
        payload = fixture_payload()
        second = copy.deepcopy(payload["records"][0])
        second["external_id"] = "dataset:missioni:2026-q2:de"
        second["source_url"] = "https://data.example.test/datasets/missioni/2026-q2/de"
        second["dimensions"] = {"territory": "DE"}
        second["field_provenance"]["dimensions.territory"] = (
            "records[1].dimensions.territory"
        )
        second["field_provenance"]["external_id"] = "records[1].id"
        second["field_provenance"]["source_url"] = "records[1].canonical_url"
        payload["records"].append(second)

        first = import_dvns_structured_evidence(payload)
        reversed_payload = copy.deepcopy(payload)
        reversed_payload["records"].reverse()
        replay = import_dvns_structured_evidence(reversed_payload)
        self.assertEqual(first.replay_id, replay.replay_id)

        duplicate_payload = copy.deepcopy(payload)
        duplicate_payload["records"].append(copy.deepcopy(payload["records"][0]))
        deduped = import_dvns_structured_evidence(duplicate_payload)
        self.assertEqual(len(deduped.normalized_batch.values), 2)
        self.assertEqual(
            deduped.normalized_batch.provider_receipt["deduplicated_record_count"],
            1,
        )
        self.assertEqual(deduped.replay_id, first.replay_id)

    def test_source_version_changes_record_and_replay_identity(self):
        first_payload = fixture_payload()
        second_payload = fixture_payload()
        second_payload["source_version"] = "release-2026-10-06"

        first = import_dvns_structured_evidence(first_payload)
        second = import_dvns_structured_evidence(second_payload)

        self.assertEqual(
            first.normalized_batch.values[0].source_record_id,
            second.normalized_batch.values[0].source_record_id,
        )
        self.assertNotEqual(
            first.normalized_batch.values[0].record_id,
            second.normalized_batch.values[0].record_id,
        )
        self.assertNotEqual(first.replay_id, second.replay_id)

    def test_same_stable_record_identity_with_conflicting_public_content_fails_closed(self):
        payload = fixture_payload()
        conflict = copy.deepcopy(payload["records"][0])
        conflict["value_numeric"] = 10
        payload["records"].append(conflict)

        with self.assertRaisesRegex(
            DvnsStructuredEvidenceError,
            "DVNS_DUPLICATE_RECORD_CONFLICT",
        ):
            import_dvns_structured_evidence(payload)

    def test_unknown_fields_and_schema_drift_fail_closed(self):
        payload = fixture_payload()
        payload["verdict"] = "TRUE"
        with self.assertRaisesRegex(
            DvnsStructuredEvidenceError,
            "DVNS_PAYLOAD_UNKNOWN_FIELD:VERDICT",
        ):
            import_dvns_structured_evidence(payload)

        payload = fixture_payload()
        payload["records"][0]["publication_authority"] = True
        with self.assertRaisesRegex(
            DvnsStructuredEvidenceError,
            "DVNS_RECORD_UNKNOWN_FIELD:PUBLICATION_AUTHORITY",
        ):
            import_dvns_structured_evidence(payload)

        payload = fixture_payload()
        payload["schema_version"] = "dvns-style-readonly-evidence-v2"
        with self.assertRaisesRegex(
            DvnsStructuredEvidenceError,
            "DVNS_SCHEMA_VERSION_UNSUPPORTED",
        ):
            import_dvns_structured_evidence(payload)

    def test_private_fields_are_excluded_and_input_is_not_mutated(self):
        payload = fixture_payload()
        before = copy.deepcopy(payload)
        result = import_dvns_structured_evidence(payload)

        changed_private = copy.deepcopy(payload)
        changed_private["records"][0]["private_fields"]["operator_note"] = "different secret"
        replay = import_dvns_structured_evidence(changed_private)

        self.assertEqual(payload, before)
        self.assertEqual(result.replay_id, replay.replay_id)
        serialized = json.dumps(asdict(result), default=str, sort_keys=True)
        self.assertNotIn("operator_note", serialized)
        self.assertNotIn("internal_case_id", serialized)
        self.assertNotIn("private-123", serialized)

    def test_field_provenance_is_required_exactly_for_imported_public_fields(self):
        payload = fixture_payload()
        del payload["records"][0]["field_provenance"]["value_numeric"]
        with self.assertRaisesRegex(
            DvnsStructuredEvidenceError,
            "DVNS_FIELD_PROVENANCE_MISSING:VALUE_NUMERIC",
        ):
            import_dvns_structured_evidence(payload)

        payload = fixture_payload()
        payload["records"][0]["field_provenance"]["verdict"] = "records[0].verdict"
        with self.assertRaisesRegex(
            DvnsStructuredEvidenceError,
            "DVNS_FIELD_PROVENANCE_UNKNOWN:VERDICT",
        ):
            import_dvns_structured_evidence(payload)

    def test_private_fields_cannot_be_used_as_public_provenance(self):
        payload = fixture_payload()
        payload["records"][0]["field_provenance"]["metric"] = "private_fields.metric"
        with self.assertRaisesRegex(
            DvnsStructuredEvidenceError,
            "DVNS_PRIVATE_PROVENANCE_FORBIDDEN",
        ):
            import_dvns_structured_evidence(payload)

    def test_source_url_must_be_safe_https(self):
        payload = fixture_payload()
        payload["records"][0]["source_url"] = "http://data.example.test/records/1"
        with self.assertRaisesRegex(
            StructuredEvidenceError,
            "STRUCTURED_SOURCE_URL_INVALID",
        ):
            import_dvns_structured_evidence(payload)

        payload = fixture_payload()
        payload["records"][0]["source_url"] = "https://user:pass@data.example.test/records/1"
        with self.assertRaisesRegex(
            StructuredEvidenceError,
            "STRUCTURED_SOURCE_URL_INVALID",
        ):
            import_dvns_structured_evidence(payload)

    def test_non_success_state_preserves_statuses_and_cannot_carry_records(self):
        payload = fixture_payload()
        payload["fetch_state"] = "BLOCKED"
        payload["availability_status"] = "TEMPORARILY_UNAVAILABLE"
        payload["blocker"] = "SOURCE_EXPORT_UNAVAILABLE"
        payload["records"] = []
        result = import_dvns_structured_evidence(payload)
        self.assertEqual(result.normalized_batch.fetch_state, "BLOCKED")
        self.assertEqual(result.availability_status, "TEMPORARILY_UNAVAILABLE")
        self.assertEqual(result.normalized_batch.values, ())

        payload = fixture_payload()
        payload["fetch_state"] = "FAILED"
        payload["blocker"] = "UPSTREAM_FAILED"
        with self.assertRaisesRegex(
            StructuredEvidenceError,
            "STRUCTURED_NON_SUCCESS_RECORDS_FORBIDDEN",
        ):
            import_dvns_structured_evidence(payload)


if __name__ == "__main__":
    unittest.main()
