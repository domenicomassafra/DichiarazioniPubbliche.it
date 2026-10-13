"""DP-214 second wave: bounded official metadata without rights, capture or ingest."""

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_tracer import _safe_url  # noqa: E402
from dichiarazioni_pubbliche.research_pilot_readiness import load_unreviewed_public_leads  # noqa: E402
from tests.test_dp214_public_lead_catalog_20261013 import url_identity  # noqa: E402

CATALOG = ROOT / "config/garlasco-public-discovery-leads.v1.json"
WAVE26 = ROOT / "config/garlasco-source-governance-wave26.v1.json"
WAVE2_KEY = "metadata_only_official_probes_wave2"
EXPECTED = {
    "lead:garlasco:cassazione-26919-2024-defamation": (
        "https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP32834",
        "2024-07-08", "JUDICIAL_DECISION_RELATED_DEFAMATION_NOT_HOMICIDE", "text/html",
        "cassazione:penale:26919-2024",
    ),
    "lead:garlasco:garanteprivacy-10149350-2025": (
        "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10149350",
        "2025-07-11", "DATA_PROTECTION_AUTHORITY_DECISION_NOT_COURT_JUDGMENT", "text/html",
        "garanteprivacy:docweb:10149350",
    ),
    "lead:garlasco:garanteprivacy-10273026-2026": (
        "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10273026",
        "2026-07-03", "DATA_PROTECTION_AUTHORITY_DECISION_NOT_COURT_JUDGMENT", "text/html",
        "garanteprivacy:docweb:10273026",
    ),
    "lead:garlasco:ministero-giustizia-bonetti-4-05562-2025": (
        "https://www.giustizia.it/cmsresources/cms/documents/interrogazione_bonetti_risposta_25ago2025.pdf",
        "2025-08-25", "FIRST_PARTY_MINISTERIAL_PARLIAMENTARY_REPLY_NOT_JUDGMENT", "application/pdf",
        "giustizia:written-reply:camera19:4-05562:2025-08-25",
    ),
}
FORBIDDEN_KEYS = {
    "body", "text", "full_text", "transcript", "extracted_text", "pdf_bytes",
    "body_sha256", "capture_id", "passage_id", "content_id", "discovery_ref",
    "publisher_approved", "speaker_approved", "publication_authorized", "PUBLISH",
}
ALLOWED_KEYS = {
    "id", "url", "document_identity_key", "document_title", "document_date",
    "document_date_basis", "publisher", "document_kind", "record_locator",
    "proposed_family", "discovery_type", "status", "identity_review_status",
    "checked_on", "http_head_status", "http_reachability", "http_content_type",
    "official_metadata_evidence_url", "verification_scope", "related_document_identity_key",
    "relation", "rights_status", "provenance_status", "candidate_only",
    "capture_authorized", "capture_performed", "count_as_logical_item",
}


def _lineage_url_set(wave26):
    """Compare actual upstream locators; multiple refs to one URL are one identity."""
    urls = set()
    for row in wave26["source_reviews"]:
        for key in ("original_url", "identity_evidence_url", "rights_evidence_url"):
            value = row.get(key)
            if isinstance(value, str) and value.startswith("https://"):
                urls.add(url_identity(value))
    for row in wave26["parliamentary_probes"]:
        for key in ("transcript_url", "video_index_url"):
            value = row.get(key)
            if isinstance(value, str) and value.startswith("https://"):
                urls.add(url_identity(value))
    return urls


def validate_wave2(catalog, wave26):
    if catalog["version"] != "garlasco-public-discovery-leads-v1" or catalog["state"] != "UNREVIEWED_CANDIDATES_ONLY":
        raise ValueError("CATALOG_STATE_CHANGED")
    rows = catalog[WAVE2_KEY]
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("WAVE2_BOUNDS_MISMATCH")
    if set(row["id"] for row in rows) != set(EXPECTED):
        raise ValueError("UNVERIFIED_WAVE2_ITEM")
    prior = catalog["candidates"] + catalog["source_locator_only"] + catalog["metadata_only_official_probes"]
    if len(prior) != 11:
        raise ValueError("ORIGINAL_LEADS_CHANGED")
    ids = [row["id"] for row in prior + rows]
    urls = [url_identity(row["url"]) for row in prior + rows]
    if len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
        raise ValueError("DUPLICATE_SOURCE_ID_OR_URL")
    if set(urls[-4:]) & _lineage_url_set(wave26):
        raise ValueError("DUPLICATE_OF_WAVE26")
    document_keys = [row["document_identity_key"] for row in catalog["metadata_only_official_probes"] + rows]
    if len(set(document_keys)) != len(document_keys):
        raise ValueError("DUPLICATE_DOCUMENT_IDENTITY")
    for row in rows:
        expected_url, date, kind, mime, identity = EXPECTED[row["id"]]
        if row["url"] != expected_url or not _safe_url(row["url"]):
            raise ValueError("UNVERIFIED_WAVE2_URL")
        if set(row) - ALLOWED_KEYS or set(row) & FORBIDDEN_KEYS:
            raise ValueError("FORBIDDEN_SOURCE_CONTENT_OR_AUTHORITY")
        if row["document_date"] != date or row["document_identity_key"] != identity or row["document_kind"] != kind:
            raise ValueError("UNVERIFIED_WAVE2_IDENTITY")
        if not row.get("document_title") or not row.get("record_locator") or not row.get("publisher"):
            raise ValueError("MISSING_OFFICIAL_METADATA")
        if row["document_date_basis"] not in {"OFFICIAL_INSTITUTIONAL_INDEX", "OFFICIAL_DOCUMENT_NUMBER_AND_DATE"}:
            raise ValueError("DATE_AUTHORITY_MISSING")
        if row["proposed_family"] != "OFFICIAL_PROCEDURAL" or row["status"] != "UNREVIEWED" or row["rights_status"] != "UNKNOWN":
            raise ValueError("RIGHTS_OR_SOURCE_STATE_ESCALATED")
        if row["provenance_status"] != "UNVERIFIED_IN_DATABASE":
            raise ValueError("PERSISTED_PROVENANCE_FABRICATED")
        for key, expected_flag in (("candidate_only", True), ("capture_authorized", False),
                                   ("capture_performed", False), ("count_as_logical_item", False)):
            if row.get(key) is not expected_flag:
                raise ValueError("UNAUTHORIZED_INGEST_OR_CAPTURE")
        if row["http_head_status"] != 200 or row["http_reachability"] != "HEAD_200" or row["checked_on"] != "2026-10-13":
            raise ValueError("HTTP_OBSERVATION_UNVERIFIED")
        if not row["http_content_type"].startswith(mime):
            raise ValueError("MIME_TYPE_MISREPRESENTED")
        evidence_url = row["official_metadata_evidence_url"]
        if not _safe_url(evidence_url):
            raise ValueError("INVALID_INSTITUTIONAL_EVIDENCE")
        if urlsplit(evidence_url).hostname not in {
            "www.cortedicassazione.it", "www.garanteprivacy.it", "www.giustizia.it",
        }:
            raise ValueError("NON_INSTITUTIONAL_EVIDENCE")
        if row.get("related_document_identity_key"):
            if row["related_document_identity_key"] not in {r["document_identity_key"] for r in rows if r is not row}:
                raise ValueError("INVENTED_RELATED_DOCUMENT")
            if row.get("relation") != "SAME_GARLASCO_PRIVACY_TOPIC_DISTINCT_PROCEEDING_NOT_HOMICIDE_EVIDENCE":
                raise ValueError("RELATED_DECISION_OVERCLAIM")
    serialized = json.dumps(sorted((r["id"], r["url"], r["document_identity_key"]) for r in rows),
                            separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


class DP214PublicLeadsWave2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.wave26 = json.loads(WAVE26.read_text(encoding="utf-8"))

    def test_four_new_official_records_replay_and_not_accepted(self):
        self.assertEqual(validate_wave2(self.catalog, self.wave26),
                         validate_wave2(copy.deepcopy(self.catalog), self.wave26))
        unchanged = load_unreviewed_public_leads(CATALOG)
        self.assertEqual((unchanged["unreviewed_file_candidates"], unchanged["source_locator_only"],
                          unchanged["file_leads_counted_in_pilot"]), (6, 1, 0))

    def test_reject_duplicate_url_or_prior_wave26_alias(self):
        changed = copy.deepcopy(self.catalog)
        changed[WAVE2_KEY][1]["url"] = changed[WAVE2_KEY][0]["url"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SOURCE_ID_OR_URL"):
            validate_wave2(changed, self.wave26)
        changed = copy.deepcopy(self.catalog)
        changed[WAVE2_KEY][0]["url"] = self.wave26["parliamentary_probes"][0]["transcript_url"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SOURCE_ID_OR_URL|DUPLICATE_OF_WAVE26"):
            validate_wave2(changed, self.wave26)

    def test_no_rights_capture_body_publication_or_fabricated_relation(self):
        for key, value in (("rights_status", "CLEARED"), ("capture_authorized", True),
                           ("capture_performed", True), ("count_as_logical_item", True),
                           ("body", "copied judicial body"), ("discovery_ref", "invented"),
                           ("http_head_status", 404), ("document_date", "2024-07-07")):
            with self.subTest(field=key):
                changed = copy.deepcopy(self.catalog)
                changed[WAVE2_KEY][0][key] = value
                with self.assertRaises(ValueError):
                    validate_wave2(changed, self.wave26)
        changed = copy.deepcopy(self.catalog)
        changed[WAVE2_KEY][2]["related_document_identity_key"] = "invented:judgment"
        with self.assertRaisesRegex(ValueError, "INVENTED_RELATED_DOCUMENT"):
            validate_wave2(changed, self.wave26)


if __name__ == "__main__":
    unittest.main()
