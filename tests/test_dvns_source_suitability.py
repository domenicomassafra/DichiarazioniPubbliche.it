import copy
import json
import sys
import unittest
from dataclasses import asdict, replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.dvns_source_suitability import (  # noqa: E402
    HELD,
    READY_FOR_DP215_ASSESSMENT,
    DvnsSourceSuitabilityError,
    derive_dvns_candidate_suitability,
)
from dichiarazioni_pubbliche.dvns_structured_evidence import (  # noqa: E402
    import_dvns_structured_evidence,
)
from dichiarazioni_pubbliche.source_intelligence import (  # noqa: E402
    load_source_intelligence_contract,
)


FIXTURE = ROOT / "tests" / "fixtures" / "dvns-structured-evidence-v1.json"


def compatible_payload():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    record = payload["records"][0]
    record["metric"] = "employment_rate_pct"
    record["unit"] = "percent"
    record["reference_period"] = "2026-07"
    record["publication_date"] = "2026-09-01"
    record["effective_from"] = "2026-01-01"
    record["effective_to"] = "2027-01-01"
    record["dimensions"] = {"population": "working_age", "geography": "IT"}
    record["source_roles"] = ["SECONDARY_REFERENCE"]
    record["field_provenance"] = {
        "external_id": "records[0].id",
        "source_version": "$.source_version",
        "source_url": "records[0].canonical_url",
        "metric": "records[0].metric",
        "value_state": "records[0].value_state",
        "value_numeric": "records[0].value_numeric",
        "unit": "records[0].unit",
        "reference_period": "records[0].reference_period",
        "publication_date": "records[0].publication_date",
        "observed_at": "records[0].observed_at",
        "effective_from": "records[0].effective_from",
        "effective_to": "records[0].effective_to",
        "dimensions.population": "records[0].dimensions.population",
        "dimensions.geography": "records[0].dimensions.geography",
        "source_roles": "records[0].source_roles",
    }
    return payload


class DvnsSourceSuitabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_source_intelligence_contract()
        cls.profile = cls.contract.evidence_profiles_by_registry_id["istat-sdmx"]
        cls.scope = cls.profile.authority_scopes[0]

    def bridge(self, payload=None, **overrides):
        values = {
            "target_id": "claim-candidate:dvns-test",
            "statement_date": "2026-09-04",
            "claim_requirements": {
                "metric": "employment_rate_pct",
                "unit": "percent",
                "population": "working_age",
                "geography": "IT",
                "reference_period": "2026-07",
                "jurisdiction": "IT",
                "dataset_class": "ISTAT_SDMX",
                "effective_at": "2026-07-15",
            },
            "source_profile": self.profile,
            "evidence_role": "OFFICIAL_STATISTICS",
            "authority_scope": self.scope,
        }
        values.update(overrides)
        return derive_dvns_candidate_suitability(
            import_dvns_structured_evidence(payload or compatible_payload()),
            **values,
        )

    def test_explicit_dp215_profile_role_and_scope_bound_candidate_establishment(self):
        result = self.bridge()
        self.assertEqual(result.candidate_state, READY_FOR_DP215_ASSESSMENT)
        self.assertEqual(result.source_profile_id, self.profile.id)
        self.assertEqual(result.evidence_role, "OFFICIAL_STATISTICS")
        self.assertEqual(result.authority_scope_id, self.scope.id)
        self.assertEqual(len(result.records), 1)

        record = result.records[0]
        self.assertEqual(record.candidate_state, READY_FOR_DP215_ASSESSMENT)
        self.assertTrue(record.metric_match)
        self.assertTrue(record.scope_match)
        self.assertTrue(record.temporal_match)
        self.assertTrue(record.value_present)
        establishment = dict(record.bounded_establishment)
        self.assertEqual(establishment["evidence_role"], "OFFICIAL_STATISTICS")
        self.assertEqual(establishment["authority.jurisdiction"], "IT")
        self.assertEqual(establishment["authority.dataset_class"], "ISTAT_SDMX")
        self.assertEqual(establishment["metric"], "employment_rate_pct")
        self.assertEqual(establishment["dimension.geography"], "IT")

        # The imported self-declared role is deliberately SECONDARY_REFERENCE. It never
        # grants or replaces the explicit DP-215 role/scope binding above.
        self.assertEqual(
            import_dvns_structured_evidence(compatible_payload()).normalized_batch.values[0].source_roles,
            ("SECONDARY_REFERENCE",),
        )

    def test_role_or_scope_cannot_be_self_promoted_outside_profile(self):
        secondary = self.contract.evidence_profiles_by_registry_id["normattiva-opendata"]
        with self.assertRaisesRegex(
            DvnsSourceSuitabilityError,
            "DVNS_DP215_ROLE_NOT_GRANTED_BY_PROFILE",
        ):
            self.bridge(
                source_profile=secondary,
                evidence_role="OFFICIAL_STATISTICS",
                authority_scope=secondary.authority_scopes[0],
            )

        with self.assertRaisesRegex(
            DvnsSourceSuitabilityError,
            "DVNS_DP215_SCOPE_NOT_GRANTED_BY_PROFILE",
        ):
            self.bridge(authority_scope=secondary.authority_scopes[0])

    def test_metric_scope_and_temporal_compatibility_are_exact(self):
        cases = (
            ({"metric": "unemployment_rate_pct"}, "METRIC_MISMATCH", "metric_match"),
            ({"jurisdiction": "EU"}, "AUTHORITY_JURISDICTION_MISMATCH", "scope_match"),
            ({"geography": "EU"}, "DIMENSION_GEOGRAPHY_MISMATCH", "scope_match"),
            ({"reference_period": "2026-06"}, "REFERENCE_PERIOD_MISMATCH", "temporal_match"),
            ({"effective_at": "2027-01-01"}, "EFFECTIVE_INTERVAL_MISMATCH", "temporal_match"),
        )
        for changed, reason, flag in cases:
            with self.subTest(reason=reason):
                requirements = {
                    "metric": "employment_rate_pct",
                    "unit": "percent",
                    "population": "working_age",
                    "geography": "IT",
                    "reference_period": "2026-07",
                    "jurisdiction": "IT",
                    "dataset_class": "ISTAT_SDMX",
                    "effective_at": "2026-07-15",
                }
                requirements.update(changed)
                record = self.bridge(claim_requirements=requirements).records[0]
                self.assertEqual(record.candidate_state, HELD)
                self.assertIn(reason, record.reason_codes)
                self.assertFalse(getattr(record, flag))

        late = compatible_payload()
        late["records"][0]["publication_date"] = "2026-09-05"
        record = self.bridge(late).records[0]
        self.assertEqual(record.candidate_state, HELD)
        self.assertIn("POST_STATEMENT_EVIDENCE", record.reason_codes)
        self.assertFalse(record.temporal_match)

    def test_statement_date_requires_whole_valid_iso_date_or_timestamp(self):
        for value in (
            "2026-09-04NOT_A_DATE",
            "2026-09-04T99:99:99+00:00",
            "2026-09-04T12:30:00Zgarbage",
            "2026-09-04T12:30:00+25:00",
            "2026-02-30",
            " 2026-09-04 ",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    DvnsSourceSuitabilityError,
                    "DVNS_DP215_STATEMENT_DATE_INVALID",
                ):
                    self.bridge(statement_date=value)

        for value in (
            "2026-09-04",
            "2026-09-04T12:30:00+02:00",
            "2026-09-04T12:30:00.123456Z",
            "2026-09-04 12:30:00+02:00",
            "2026-09-04T12:30Z",
        ):
            with self.subTest(valid=value):
                self.assertEqual(
                    self.bridge(statement_date=value).candidate_state,
                    READY_FOR_DP215_ASSESSMENT,
                )

    def test_effective_at_requires_whole_valid_iso_date_or_timestamp(self):
        basic_requirements = {
            "metric": "employment_rate_pct",
            "unit": "percent",
            "population": "working_age",
            "geography": "IT",
            "reference_period": "2026-07",
            "jurisdiction": "IT",
            "dataset_class": "ISTAT_SDMX",
        }
        for value in (
            "2026-07-15NOT_A_DATE",
            "2026-07-15T99:99:99+00:00",
            "2026-07-15T10:30:00Zgarbage",
            "2026-07-15T10:30:00+25:00",
            "2026-02-30",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    DvnsSourceSuitabilityError,
                    "DVNS_DP215_EFFECTIVE_AT_INVALID",
                ):
                    self.bridge(claim_requirements={**basic_requirements, "effective_at": value})

        for value in (
            "2026-07-15",
            "2026-07-15T08:45:00+02:00",
            "2026-07-15T08:45:00Z",
        ):
            with self.subTest(valid=value):
                self.assertEqual(
                    self.bridge(claim_requirements={**basic_requirements, "effective_at": value}).candidate_state,
                    READY_FOR_DP215_ASSESSMENT,
                )

    def test_authority_scope_validity_requires_whole_valid_iso_dates(self):
        for field, code in (
            ("valid_from", "DVNS_DP215_AUTHORITY_VALID_FROM_INVALID"),
            ("valid_until", "DVNS_DP215_AUTHORITY_VALID_UNTIL_INVALID"),
        ):
            for value in (
                "2026-01-01garbage",
                "2026-01-01T99:99:99Z",
                "2026-01-01T10:00:00+25:00",
            ):
                with self.subTest(field=field, value=value):
                    bad_scope = replace(self.scope, **{field: value})
                    profile = replace(
                        self.profile,
                        authority_scopes=tuple(
                            bad_scope if scope.id == self.scope.id else scope
                            for scope in self.profile.authority_scopes
                        ),
                    )
                    with self.assertRaisesRegex(DvnsSourceSuitabilityError, code):
                        self.bridge(source_profile=profile, authority_scope=bad_scope)

        valid_scope = replace(
            self.scope,
            valid_from="2026-01-01T00:00:00+01:00",
            valid_until="2027-01-01T00:00:00Z",
        )
        profile = replace(
            self.profile,
            authority_scopes=tuple(
                valid_scope if scope.id == self.scope.id else scope
                for scope in self.profile.authority_scopes
            ),
        )
        self.assertEqual(
            self.bridge(source_profile=profile, authority_scope=valid_scope).candidate_state,
            READY_FOR_DP215_ASSESSMENT,
        )

    def test_blocked_failed_or_degraded_rights_availability_dominate(self):
        for field, state, reason in (
            ("rights_status", "BLOCKED", "DVNS_RIGHTS_BLOCKED"),
            ("rights_status", "FAILED", "DVNS_RIGHTS_FAILED"),
            ("rights_status", "DEGRADED", "DVNS_RIGHTS_DEGRADED"),
            ("availability_status", "BLOCKED", "DVNS_AVAILABILITY_BLOCKED"),
            ("availability_status", "FAILED", "DVNS_AVAILABILITY_FAILED"),
            ("availability_status", "DEGRADED", "DVNS_AVAILABILITY_DEGRADED"),
        ):
            with self.subTest(field=field, state=state):
                payload = compatible_payload()
                payload[field] = state
                result = self.bridge(payload)
                self.assertEqual(result.candidate_state, HELD)
                self.assertIn(reason, result.blocking_reasons)
                self.assertEqual(result.records[0].candidate_state, HELD)
                self.assertIsNone(result.records[0].metric_match)

        degraded_profile = replace(self.profile, access_status="DEGRADED")
        result = self.bridge(source_profile=degraded_profile, authority_scope=degraded_profile.authority_scopes[0])
        self.assertEqual(result.candidate_state, HELD)
        self.assertIn("DP215_PROFILE_ACCESS_DEGRADED", result.blocking_reasons)

    def test_non_success_fetch_state_is_held_without_candidate_records(self):
        payload = compatible_payload()
        payload["fetch_state"] = "DEGRADED"
        payload["availability_status"] = "DEGRADED"
        payload["blocker"] = "UPSTREAM_PARTIAL"
        payload["records"] = []
        result = self.bridge(payload)
        self.assertEqual(result.candidate_state, HELD)
        self.assertEqual(result.records, ())
        self.assertIn("DVNS_FETCH_DEGRADED", result.blocking_reasons)
        self.assertIn("DVNS_AVAILABILITY_DEGRADED", result.blocking_reasons)

    def test_bridge_output_is_deterministic_candidate_only_and_has_no_decision_authority(self):
        payload = compatible_payload()
        second = copy.deepcopy(payload["records"][0])
        second["external_id"] = "dataset:missioni:2026-q2:second"
        second["source_url"] = "https://data.example.test/datasets/missioni/2026-q2/second"
        second["field_provenance"]["external_id"] = "records[1].id"
        second["field_provenance"]["source_url"] = "records[1].canonical_url"
        payload["records"].append(second)

        first = self.bridge(payload)
        reversed_payload = copy.deepcopy(payload)
        reversed_payload["records"].reverse()
        replay = self.bridge(reversed_payload)
        self.assertEqual(first.input_fingerprint, replay.input_fingerprint)
        self.assertEqual(first.records, replay.records)

        serialized = json.dumps(asdict(first), sort_keys=True)
        self.assertIn('"candidate_only": true', serialized)
        for forbidden in ("verdict", "approval", "publication_authority", "publishable"):
            self.assertNotIn(forbidden, serialized.lower())

    def test_metric_requirement_is_mandatory_for_exact_compatibility(self):
        with self.assertRaisesRegex(
            DvnsSourceSuitabilityError,
            "DVNS_DP215_METRIC_REQUIRED",
        ):
            self.bridge(claim_requirements={"reference_period": "2026-07"})


if __name__ == "__main__":
    unittest.main()
