import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.linked_data import projection_ntriples  # noqa: E402
from dichiarazioni_pubbliche.public_api import API_BASE_PATH, dispatch  # noqa: E402
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    build_public_projection,
    dossier_jsonld,
    projection_jsonld,
    render_dossier_html,
    write_public_bundle,
)
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_dossier,
)
from tests.test_public_projection import FakeSource, valid_row  # noqa: E402


PRIVATE_SENTINELS = {
    "high_risk_score": "PRIVATE-HIGH-RISK-SCORE-71",
    "high_risk_notes": "PRIVATE-HIGH-RISK-NOTES",
    "reviewer_actor_ref": "PRIVATE-REVIEWER-ACTOR-REF",
    "credential_fingerprint": "PRIVATE-CREDENTIAL-FINGERPRINT",
    "credential_id": "PRIVATE-REVIEWER-CREDENTIAL-ID",
    "identity_authority_receipt_id": "PRIVATE-REVIEWER-AUTHORITY-RECEIPT",
    "identity_authority_binding_sha256": "PRIVATE-REVIEWER-AUTHORITY-BINDING",
    "authority_version": "PRIVATE-REVIEWER-AUTHORITY-VERSION",
    "secret_hex": "PRIVATE-REVIEWER-SECRET",
    "mac_sha256": "PRIVATE-REVIEWER-RECEIPT-MAC",
    "high_risk_private_reason": "PRIVATE-HIGH-RISK-REASON",
}


def contaminated_row():
    row = valid_row()
    row["corrections"] = [
        {
            "id": "correction:private-high-risk",
            "finding_id": "finding:new",
            "previous_finding_id": row["finding_id"],
            "reason": "Correzione pubblicabile senza dettagli interni.",
            "changed_fields": {
                **PRIVATE_SENTINELS,
                "status_reason": "HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED",
            },
            "created_at": "2026-09-22T12:00:00+00:00",
            "publication_review_approved": True,
        }
    ]
    row["high_risk_decision"] = {
        "reason_codes": ["HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED"],
        **PRIVATE_SENTINELS,
    }
    return row


def assert_private_sentinels_absent(testcase: unittest.TestCase, value):
    encoded = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    for key, sentinel in PRIVATE_SENTINELS.items():
        testcase.assertNotIn(key, encoded)
        testcase.assertNotIn(sentinel, encoded)
    testcase.assertNotIn("HOLD_HIGH_RISK_", encoded)


class HighRiskPublicSerializerLeakTests(unittest.TestCase):
    def payload(self):
        payload = build_public_projection(FakeSource([contaminated_row()]))
        self.assertEqual(payload["dossier_count"], 1)
        self.assertEqual(payload["omitted_count"], 0)
        self.assertEqual(payload["dossiers"][0]["corrections"], [])
        return payload

    def test_projection_drops_private_high_risk_correction_material(self):
        payload = self.payload()
        assert_private_sentinels_absent(self, payload)

    def test_public_schema_rejects_bypass_with_private_high_risk_material(self):
        dossier = build_public_projection(FakeSource([valid_row()]))["dossiers"][0]
        dossier["corrections"] = [
            {
                "id": "correction:bypass",
                "finding_id": "finding:new",
                "previous_finding_id": dossier["finding_id"],
                "reason": "Correzione pubblica.",
                "changed_fields": dict(PRIVATE_SENTINELS),
                "created_at": "2026-09-22T12:00:00+00:00",
            }
        ]
        with self.assertRaisesRegex(
            PublicSchemaValidationError,
            "internal-only material",
        ):
            validate_dossier(dossier)

    def test_html_jsonld_rdf_and_written_bundle_do_not_expose_private_material(self):
        payload = self.payload()
        dossier = payload["dossiers"][0]
        for serializer_output in (
            dossier_jsonld(dossier),
            projection_jsonld(payload),
            render_dossier_html(dossier),
            projection_ntriples(payload),
        ):
            assert_private_sentinels_absent(self, serializer_output)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_public_bundle(output, payload)
            artifacts = "\n".join(
                path.read_text(encoding="utf-8")
                for path in sorted(output.rglob("*"))
                if path.is_file()
            )
        assert_private_sentinels_absent(self, artifacts)

    def test_public_api_routes_do_not_expose_private_material(self):
        payload = self.payload()
        with tempfile.TemporaryDirectory() as directory:
            projection_path = Path(directory) / "projection.json"
            projection_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            paths = (
                f"{API_BASE_PATH}/index.json",
                f"{API_BASE_PATH}/findings",
                f"{API_BASE_PATH}/findings/finding%3Aa",
                f"{API_BASE_PATH}/records",
                f"{API_BASE_PATH}/people",
                f"{API_BASE_PATH}/topics",
            )
            bodies = []
            for path in paths:
                response = dispatch("GET", path, projection_path=projection_path)
                self.assertEqual(response.status, 200, path)
                bodies.append(response.body.decode("utf-8"))
        assert_private_sentinels_absent(self, "\n".join(bodies))

    def test_public_api_rejects_fingerprint_valid_private_material_bypass(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        payload["dossiers"][0]["corrections"] = [
            {
                "id": "correction:bypass",
                "finding_id": "finding:new",
                "previous_finding_id": payload["dossiers"][0]["finding_id"],
                "reason": "Correzione pubblica.",
                "changed_fields": {
                    **PRIVATE_SENTINELS,
                    "status_reason": "HOLD_HIGH_RISK_HUMAN_REVIEW_REQUIRED",
                },
                "created_at": "2026-09-22T12:00:00+00:00",
            }
        ]
        payload["dataset_sha256"] = projection_dataset_sha256(payload)
        with tempfile.TemporaryDirectory() as directory:
            projection_path = Path(directory) / "projection.json"
            projection_path.write_text(json.dumps(payload), encoding="utf-8")
            response = dispatch(
                "GET",
                f"{API_BASE_PATH}/index.json",
                projection_path=projection_path,
            )
        self.assertEqual(response.status, 503)
        assert_private_sentinels_absent(self, response.body.decode("utf-8"))
        self.assertNotIn("HOLD_HIGH_RISK_", response.body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
