"""Read-only DP-214 catalog evidence: official URL hints confer no intake authority."""

import copy
import hashlib
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_tracer import _safe_url  # noqa: E402
from dichiarazioni_pubbliche.research_pilot_readiness import load_unreviewed_public_leads  # noqa: E402

REGISTRY = ROOT / "config/garlasco-public-discovery-leads.v1.json"
GOVERNANCE = ROOT / "config/garlasco-source-governance-wave26.v1.json"
EXPECTED_OFFICIAL_URLS = {
    "https://www.senato.it/show-doc?id=279270&idoggetto=0&leg=15&tipodoc=Sindisp",
    "https://www.camera.it/leg19/410?idSeduta=0579&tipo=atti_indirizzo_controllo",
    "https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm",
    "https://www.senato.it/show-doc?id=1477466&leg=19&part=doc_dc-ressten_rs&tipodoc=Resaula",
}
VERIFIED_RECORD_DATES = {
    "https://www.senato.it/show-doc?id=279270&idoggetto=0&leg=15&tipodoc=Sindisp": "2007-09-19",
    "https://www.camera.it/leg19/410?idSeduta=0579&tipo=atti_indirizzo_controllo": "2025-12-05",
    "https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm": "2026-02-03",
    "https://www.senato.it/show-doc?id=1477466&leg=19&part=doc_dc-ressten_rs&tipodoc=Resaula": "2025-10-30",
}
OFFICIAL_PROBE_FIELDS = {
    "id", "url", "document_identity_key", "document_title", "record_locator",
    "document_date", "publisher", "document_kind", "proposed_family",
    "discovery_type", "status", "identity_review_status", "checked_on",
    "http_head_status", "http_reachability", "verification_scope", "lineage",
    "rights_status", "provenance_status", "candidate_only", "capture_authorized",
    "capture_performed", "count_as_logical_item",
}


def url_identity(value):
    """Detect query-param-order aliases without guessing cross-document equality."""
    url = urlsplit(value)
    return (url.scheme.lower(), url.hostname.lower(), url.path,
            tuple(sorted(parse_qsl(url.query, keep_blank_values=True))))


def check_official_metadata(data, governance):
    if data["version"] != "garlasco-public-discovery-leads-v1":
        raise ValueError("VERSION_CHANGED")
    if data["state"] != "UNREVIEWED_CANDIDATES_ONLY":
        raise ValueError("STATE_ESCALATED")
    if len(data["candidates"]) != 6 or len(data["source_locator_only"]) != 1:
        raise ValueError("LEGACY_POOL_CHANGED")
    probes = data["metadata_only_official_probes"]
    if len(probes) != 4:
        raise ValueError("UNVERIFIED_OFFICIAL_ITEM")
    original = data["candidates"] + data["source_locator_only"]
    ids = [row["id"] for row in original + probes]
    urls = [row["url"] for row in original + probes]
    if len(set(ids)) != len(ids) or len({url_identity(url) for url in urls}) != len(urls):
        raise ValueError("DUPLICATE_ID_OR_LOCATOR")
    if {row["url"] for row in probes} != EXPECTED_OFFICIAL_URLS:
        raise ValueError("UNVERIFIED_OFFICIAL_ITEM")
    identities = [row["document_identity_key"] for row in probes]
    if len(set(identities)) != len(identities):
        raise ValueError("DUPLICATE_DOCUMENT_IDENTITY")
    upstream = {row["probe_id"]: row for row in governance["parliamentary_probes"]}
    for row in probes:
        if set(row) - OFFICIAL_PROBE_FIELDS:
            raise ValueError("UNAUTHORIZED_SOURCE_BODY_OR_AUTHORITY")
        if not _safe_url(row["url"]):
            raise ValueError("NONCANONICAL_URL")
        if urlsplit(row["url"]).hostname not in {
            "www.senato.it", "www.camera.it", "documenti.camera.it",
        }:
            raise ValueError("NONINSTITUTIONAL_URL")
        if any(row.get(key) is not expected for key, expected in (
            ("candidate_only", True), ("capture_authorized", False),
            ("capture_performed", False), ("count_as_logical_item", False),
        )):
            raise ValueError("CAPTURE_OR_PILOT_ESCALATED")
        if (row.get("status") != "UNREVIEWED"
                or row.get("rights_status") != "UNKNOWN"
                or row.get("provenance_status") != "UNVERIFIED_IN_DATABASE"
                or row.get("proposed_family") != "OFFICIAL_PROCEDURAL"
                or row.get("document_kind") != "PARLIAMENTARY_RECORD_NOT_COURT_EVIDENCE"):
            raise ValueError("SOURCE_AUTHORITY_ESCALATED")
        if row.get("http_head_status") not in {200, 202}:
            raise ValueError("UNSUPPORTED_HEAD_STATUS")
        if row.get("http_head_status") == 202 and row.get("http_reachability") != "HEAD_202_NOT_HTTP_200":
            raise ValueError("HEAD_202_MISREPRESENTED")
        if row.get("http_head_status") == 200 and row.get("http_reachability") != "HEAD_200":
            raise ValueError("HEAD_200_MISREPRESENTED")
        if row.get("checked_on") != "2026-10-13":
            raise ValueError("OBSERVATION_DATE_UNVERIFIED")
        try:
            date.fromisoformat(row["document_date"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("DOCUMENT_DATE_UNVERIFIED") from exc
        if row["document_date"] != VERIFIED_RECORD_DATES[row["url"]]:
            raise ValueError("DOCUMENT_DATE_UNVERIFIED")
        if not row.get("document_title") or not row.get("record_locator"):
            raise ValueError("MISSING_INSTITUTIONAL_LOCATOR")
        if any(key in row for key in (
            "discovery_ref", "content_id", "capture_id", "passage_id",
            "body", "full_text", "transcript", "extracted_text", "published",
        )):
            raise ValueError("UNAUTHORIZED_SOURCE_BODY_OR_AUTHORITY")
        lineage = row.get("lineage")
        if lineage is not None:
            if lineage.get("registry") != "config/garlasco-source-governance-wave26.v1.json":
                raise ValueError("INVENTED_REGISTRY_LINEAGE")
            parent = upstream.get(lineage.get("probe_id"))
            if parent is None or parent.get("transcript_url") != row["url"]:
                raise ValueError("INVENTED_SOURCE_LINEAGE")
    return hashlib.sha256(json.dumps(
        sorted((row["id"], row["url"], row["document_identity_key"])
               for row in probes), separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


class DP214OfficialMetadataCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.governance = json.loads(GOVERNANCE.read_text(encoding="utf-8"))

    def test_four_explicit_official_urls_and_replay_identity(self):
        first = check_official_metadata(self.data, self.governance)
        second = check_official_metadata(copy.deepcopy(self.data), self.governance)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_existing_six_leads_keep_exactly_zero_pilot_authority(self):
        report = load_unreviewed_public_leads(REGISTRY)
        self.assertEqual(report["unreviewed_file_candidates"], 6)
        self.assertEqual(report["source_locator_only"], 1)
        self.assertEqual(report["file_leads_counted_in_pilot"], 0)
        self.assertFalse(report["file_candidates_capture_authorized"])
        self.assertFalse(report["file_candidates_verified_in_postgres"])

    def test_duplicate_identity_and_query_order_alias_fail(self):
        altered = copy.deepcopy(self.data)
        altered["metadata_only_official_probes"][1]["document_identity_key"] = (
            altered["metadata_only_official_probes"][0]["document_identity_key"]
        )
        with self.assertRaisesRegex(ValueError, "DUPLICATE_DOCUMENT_IDENTITY"):
            check_official_metadata(altered, self.governance)
        altered = copy.deepcopy(self.data)
        altered["metadata_only_official_probes"][1]["url"] = (
            altered["metadata_only_official_probes"][0]["url"]
        )
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ID_OR_LOCATOR"):
            check_official_metadata(altered, self.governance)
        altered = copy.deepcopy(self.data)
        altered["metadata_only_official_probes"][1]["url"] = (
            "https://www.senato.it/show-doc?leg=15&tipodoc=Sindisp"
            "&id=279270&idoggetto=0"
        )
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ID_OR_LOCATOR"):
            check_official_metadata(altered, self.governance)
        self.assertEqual(
            url_identity("https://www.senato.it/show-doc?leg=15&id=279270"),
            url_identity("https://www.senato.it/show-doc?id=279270&leg=15"),
        )

    def test_no_invented_lineage_and_no_capture_permission(self):
        for field, value, reason in (
            ("rights_status", "CLEARED", "SOURCE_AUTHORITY_ESCALATED"),
            ("capture_authorized", True, "CAPTURE_OR_PILOT_ESCALATED"),
            ("count_as_logical_item", True, "CAPTURE_OR_PILOT_ESCALATED"),
            ("body", "unapproved copied text", "UNAUTHORIZED_SOURCE_BODY_OR_AUTHORITY"),
        ):
            with self.subTest(field=field):
                altered = copy.deepcopy(self.data)
                altered["metadata_only_official_probes"][0][field] = value
                with self.assertRaisesRegex(ValueError, reason):
                    check_official_metadata(altered, self.governance)
        altered = copy.deepcopy(self.data)
        altered["metadata_only_official_probes"][2]["lineage"]["probe_id"] = "wave26:not-real"
        with self.assertRaisesRegex(ValueError, "INVENTED_SOURCE_LINEAGE"):
            check_official_metadata(altered, self.governance)


if __name__ == "__main__":
    unittest.main()
