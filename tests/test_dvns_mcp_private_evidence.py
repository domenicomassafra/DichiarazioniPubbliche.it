"""Public DVNS MCP → versioned, rights-guarded private Evidence boundary."""
import sys
import unittest
import io
import json
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.dvns_mcp_private_evidence import (
    SOURCE_URL, POLICY_VERSION, DvnsMcpError, import_opencoesione_snapshot,
    persist_private_candidate, rights_subject, fetch_public_mcp_snapshot,
    official_licence_receipt, observe_official_reference, OfficialReferenceReceipt,
)
from dichiarazioni_pubbliche.rights_registry import (
    PRIVATE_RIGHTS_RECORD_VERSION, PrivateRightsRecord, rights_subject_fingerprint,
)


RECEIPT = "sha256:" + "a" * 64
OFFICIAL = OfficialReferenceReceipt("sha256:" + "b" * 64, "2026-06-30", 46437)


def permission_record():
    subject = rights_subject()
    return PrivateRightsRecord(
        id="private-rights:approved", subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=subject.source_family, locator_kind=subject.locator_kind,
        locator_value=subject.locator_value, content_id=None, evidence_id=None,
        transcript_segment_id=None, canonical_segment_id=None, passage_id=None,
        rights_status="CLEARED", rights_receipt_ref=RECEIPT,
        permitted_uses=("FETCH", "STORE_BODY"),
        attribution_requirements=("ATTRIBUTION_REQUIRED",),
        reviewed_at="2026-10-25T09:00:00+00:00", expires_at="2026-11-24T09:00:00+00:00",
        reviewer_ref="machine:dp329-official-licence-check", policy_version=POLICY_VERSION,
        record_visibility="PRIVATE", supersedes_id=None, version_state="CURRENT",
        record_version=PRIVATE_RIGHTS_RECORD_VERSION,
    )


class RightsReader:
    def __init__(self, record):
        self.record = record

    def read_current(self, _subject):
        return self.record


class MemoryEvidenceStore:
    def __init__(self):
        self.evidence = []
        self.observations = []

    def upsert_evidence(self, **kwargs):
        self.evidence.append(kwargs)

    def insert_evidence_observation(self, **kwargs):
        self.observations.append(kwargs)


class FakeResponse(io.BytesIO):
    def __init__(self, body, *, media, url):
        super().__init__(body)
        self.status = 200
        self.headers = {"Content-Type": media}
        self.url = url

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, body, media):
        self.body, self.media = body, media

    def open(self, request, timeout):
        return FakeResponse(self.body, media=self.media, url=request.full_url)


def official_response():
    return {
        "ok": True, "dataset": "opencoesione_progetti",
        "data": {
            "schemaVersion": 1,
            "generatedAt": "2026-08-20T08:51:13+00:00",
            "referenceDate": "2026-04-30",
            "scope": "national-overview",
            "source": {
                "owner": "Dipartimento per le Politiche di Coesione",
                "endpoint": "https://opencoesione.gov.it/it/api/aggregati/",
                "license": "CC BY 4.0",
            },
            "themes": [{
                "slug": "ricerca-e-innovazione",
                "sourceUrl": SOURCE_URL,
                "projects": 46402,
            }],
        },
    }


class DvnsMcpPrivateEvidenceTests(unittest.TestCase):
    def test_official_mcp_numeric_record_becomes_versioned_candidate(self):
        imported = import_opencoesione_snapshot(
            official_response(), observed_at="2026-10-25T10:00:00Z",
        )
        self.assertEqual(len(imported.normalized_batch.values), 1)
        row = imported.normalized_batch.values[0]
        self.assertEqual(row.value_numeric, 46402)
        self.assertEqual(row.source_record_id, "opencoesione_progetti:themes:ricerca-e-innovazione")
        self.assertEqual(row.source_url, SOURCE_URL)
        self.assertEqual(dict(imported.provenance[0].fields)["value_numeric"], "$.data.themes[0].projects")
        self.assertTrue(row.source_version.startswith("sha256:"))
        self.assertEqual(imported.rights_status, "UNRESOLVED")

    def test_mcp_rejects_schema_source_and_identity_drift(self):
        for key, replacement in (("dataset", "different"), ("ok", False)):
            with self.subTest(key=key):
                sample = official_response()
                sample[key] = replacement
                with self.assertRaises(DvnsMcpError):
                    import_opencoesione_snapshot(sample, observed_at="2026-10-25T10:00:00Z")
        sample = official_response()
        sample["data"]["themes"][0]["sourceUrl"] = "https://example.org/foreign"
        with self.assertRaises(DvnsMcpError):
            import_opencoesione_snapshot(sample, observed_at="2026-10-25T10:00:00Z")

    def test_source_use_permission_and_revocation_guard_actual_persistence(self):
        observed_at = "2026-10-25T10:00:00Z"
        imported = import_opencoesione_snapshot(official_response(), observed_at=observed_at)
        for record, reason in ((None, "RIGHTS_OR_LICENCE_NOT_CURRENT"),
                               (replace(permission_record(), rights_status="REVOKED"), "SOURCE_USE_REVOKED"),
                               (replace(permission_record(), expires_at="2026-10-24T00:00:00Z"), "SOURCE_USE_EXPIRED"),
                               (replace(permission_record(), permitted_uses=("FETCH",)), "SOURCE_USE_NOT_PERMITTED"),
                               (replace(permission_record(), policy_version="unrelated"), "SOURCE_USE_POLICY_MISMATCH")):
            with self.subTest(reason=reason):
                store = MemoryEvidenceStore()
                with self.assertRaisesRegex(DvnsMcpError, reason):
                    persist_private_candidate(imported, store=store, rights=RightsReader(record),
                                              licence_receipt=RECEIPT, observed_at=observed_at,
                                              official_reference=OFFICIAL)
                self.assertEqual(store.evidence, [])
                self.assertEqual(store.observations, [])
        store = MemoryEvidenceStore()
        receipt = persist_private_candidate(imported, store=store,
                                            rights=RightsReader(permission_record()),
                                            licence_receipt=RECEIPT, observed_at=observed_at,
                                            official_reference=OFFICIAL)
        self.assertEqual(receipt.suitability_state, "READY_FOR_DP215_ASSESSMENT")
        self.assertFalse(receipt.publication_authorized)
        self.assertEqual(store.evidence[0]["rights_status"], "CLEARED")
        self.assertEqual(store.evidence[0]["record_status"], "SUPERSEDED")
        self.assertTrue(store.evidence[0]["metadata"]["dvns_snapshot_superseded"])
        self.assertEqual(store.evidence[0]["metadata"]["official_current_projects"], 46437)
        self.assertIsNone(store.evidence[0].get("excerpt"))
        self.assertEqual(store.observations[0]["status"], "CANDIDATE")
        self.assertEqual(store.observations[0]["value_numeric"], 46402.0)

    def test_primary_source_revision_and_value_mismatch_hold_before_writes(self):
        imported = import_opencoesione_snapshot(official_response(), observed_at="2026-10-25T10:00:00Z")
        for official, reason in (
            (replace(OFFICIAL, reference_period="2026-04-30"), "DVNS_MCP_OFFICIAL_VALUE_CONFLICT"),
            (replace(OFFICIAL, reference_period="2026-02-28"), "DVNS_MCP_OFFICIAL_SOURCE_REGRESSED"),
        ):
            store = MemoryEvidenceStore()
            with self.subTest(reason=reason), self.assertRaisesRegex(DvnsMcpError, reason):
                persist_private_candidate(imported, store=store, rights=RightsReader(permission_record()),
                                          licence_receipt=RECEIPT, observed_at="2026-10-25T10:00:00Z",
                                          official_reference=official)
            self.assertFalse(store.evidence)
            self.assertFalse(store.observations)

    def test_official_primary_response_version_receipt(self):
        body = json.dumps({"data_aggiornamento": "20260630",
                           "aggregati": {"totali": {"progetti": "46437"}}}).encode()
        receipt = observe_official_reference(opener=FakeOpener(body, "application/json"))
        self.assertEqual(receipt.reference_period, "2026-06-30")
        self.assertEqual(receipt.projects, 46437)
        self.assertTrue(receipt.source_version.startswith("sha256:"))

    def test_real_sse_transport_shape_and_fail_closed_on_rpc_error(self):
        valid = {"jsonrpc": "2.0", "id": 1, "result": {
            "content": [{"type": "text", "text": json.dumps(official_response())}]}}
        blob = ("event: message\ndata: " + json.dumps(valid) + "\n\n").encode()
        self.assertEqual(fetch_public_mcp_snapshot(
            opener=FakeOpener(blob, "text/event-stream")), official_response())
        valid["error"] = {"code": -32000, "message": "unavailable"}
        blob = ("event: message\ndata: " + json.dumps(valid) + "\n\n").encode()
        with self.assertRaisesRegex(DvnsMcpError, "DVNS_MCP_RPC_FAILED"):
            fetch_public_mcp_snapshot(opener=FakeOpener(blob, "text/event-stream"))

    def test_licence_must_be_observed_on_official_site(self):
        with self.assertRaisesRegex(DvnsMcpError, "DVNS_MCP_OFFICIAL_LICENCE_NOT_VERIFIED"):
            official_licence_receipt(opener=FakeOpener(
                b"<html>Some other rights terms</html>", "text/html"))


if __name__ == "__main__":
    unittest.main()
