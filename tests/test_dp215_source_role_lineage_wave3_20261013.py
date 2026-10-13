"""DP-215.9 planning descriptors for existing real URLs; never a live Content approval."""
import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
from dichiarazioni_pubbliche.source_intelligence import EVIDENCE_ROLES  # noqa: E402

CATALOG = ROOT / "config/garlasco-public-discovery-leads.v1.json"
GOVERNANCE = ROOT / "config/garlasco-source-governance-wave26.v1.json"
WAVE22 = ROOT / "config/garlasco-source-feasibility-wave22.v1.json"
KEY = "source_intelligence_proposals_wave3"
OFFICIAL_ROLES = {
    "PARLIAMENTARY_RECORD_NOT_COURT_EVIDENCE": "OFFICIAL_PROCEDURAL_RECORD",
    "JUDICIAL_DECISION_RELATED_DEFAMATION_NOT_HOMICIDE": "SECONDARY_REFERENCE",
    "DATA_PROTECTION_AUTHORITY_DECISION_NOT_COURT_JUDGMENT": "PRIMARY_RECORD",
    "FIRST_PARTY_MINISTERIAL_PARLIAMENTARY_REPLY_NOT_JUDGMENT": "OFFICIAL_PROCEDURAL_RECORD",
}


def url_identity(value):
    p = urlsplit(value)
    return (p.scheme.lower(), p.hostname.lower(), p.path,
            tuple(sorted(parse_qsl(p.query, keep_blank_values=True))))


def audit(catalog, governance, wave22):
    preview = catalog[KEY]
    if (set(preview) != {"status", "basis", "descriptors"}
            or preview["status"] != "UNREVIEWED_NOT_PERSISTED"
            or preview["basis"] != "EXISTING_PUBLIC_METADATA_NO_BODY_OR_RIGHTS_GRANT"):
        raise ValueError("PREVIEW_AUTHORITY_ESCALATED")
    official = catalog["metadata_only_official_probes"] + catalog["metadata_only_official_probes_wave2"]
    candidates = catalog["candidates"]
    locators = catalog["source_locator_only"]
    if (len(official), len(candidates), len(locators)) != (8, 6, 1):
        raise ValueError("SOURCE_SET_CHANGED")
    source = {r["id"]: r for r in candidates + official + locators}
    if (len(source) != 15 or len(preview["descriptors"]) != 15
            or len({url_identity(r["url"]) for r in source.values()}) != 15):
        raise ValueError("MISSING_OR_DUPLICATED_LOCATORS")
    wave26_reviews = {r["lead_id"]: r for r in governance["source_reviews"]}
    wave22_reviews = {r["id"]: r for r in wave22["verified_existing_leads"]}
    wave22_additional = {r["id"]: r for r in wave22["additional_verified_leads"]}
    existing_transcripts = {url_identity(r["transcript_url"]): r["probe_id"]
                            for r in governance["parliamentary_probes"]}
    seen = set()
    for desc in preview["descriptors"]:
        if set(desc) != {"lead_id", "proposed_role", "scope_class", "scope_review",
                         "reference_date", "date_basis", "version_review",
                         "lineage_relation", "lineage_group", "external_probe_id",
                         "related_document_key", "independence", "rights_state",
                         "capture_allowed", "publication_allowed", "included_in_pilot"}:
            raise ValueError("UNBOUNDED_OR_INCOMPLETE_DESCRIPTOR")
        lead = desc["lead_id"]
        if lead in seen or lead not in source:
            raise ValueError("DUPLICATED_OR_INVENTED_LEAD")
        seen.add(lead)
        row = source[lead]
        if lead in wave26_reviews:
            review = wave26_reviews[lead]
            expected = ("SECONDARY_REFERENCE", row["discovery_type"],
                        "UNREVIEWED_SOURCE_SCOPE", review["observed_date"],
                        "PUBLIC_PAGE_OBSERVATION", review["source_relation"],
                        review["dependent_on_lead_id"] or lead,
                        None, None)
            if (lead not in wave22_reviews
                    or wave22_reviews[lead]["url"] != row["url"]):
                raise ValueError("WAVE22_PROVENANCE_MISSING")
            upstream_id = review["dependent_on_lead_id"]
            if upstream_id is not None and (
                    upstream_id not in wave22_additional
                    or review["original_url"] != wave22_additional[upstream_id]["url"]):
                raise ValueError("INVENTED_SOURCE_DERIVATION")
        elif "document_identity_key" in row:
            identity = row["document_identity_key"]
            expected = (OFFICIAL_ROLES[row["document_kind"]], row["document_kind"],
                        row["identity_review_status"], row["document_date"],
                        "ISSUER_RECORD_DATE", "UNREVIEWED_DOCUMENT_LINEAGE",
                        identity, existing_transcripts.get(url_identity(row["url"])),
                        row.get("related_document_identity_key"))
        else:
            expected = ("SECONDARY_REFERENCE", "INSTITUTIONAL_HOMEPAGE_NOT_RECORD",
                        "UNREVIEWED_SOURCE_SCOPE", None, "NO_DOCUMENT_DATE",
                        "SOURCE_DIRECTORY_NOT_CASE_EVIDENCE", lead, None, None)
        actual = tuple(desc[key] for key in (
            "proposed_role", "scope_class", "scope_review", "reference_date",
            "date_basis", "lineage_relation", "lineage_group", "external_probe_id",
            "related_document_key"))
        if actual != expected or desc["proposed_role"] not in EVIDENCE_ROLES:
            raise ValueError("ROLE_SCOPE_DATE_OR_LINEAGE_MISMATCH")
        if desc["reference_date"] is not None:
            try:
                date.fromisoformat(desc["reference_date"])
            except (ValueError, TypeError) as exc:
                raise ValueError("INVALID_DATE") from exc
        if (desc["version_review"] != "UNREVIEWED"
                or desc["independence"] != "NOT_ESTABLISHED"
                or desc["rights_state"] != "UNKNOWN"
                or desc["capture_allowed"] is not False
                or desc["publication_allowed"] is not False
                or desc["included_in_pilot"] is not False):
            raise ValueError("EVIDENCE_RIGHTS_OR_INDEPENDENCE_ESCALATED")
        if (row.get("rights_status", "UNKNOWN") != "UNKNOWN"
                or row.get("capture_authorized", False) is not False
                or row.get("count_as_logical_item", False) is not False):
            raise ValueError("SOURCE_RIGHTS_ESCALATED")
        if (desc["external_probe_id"] is not None
                and not any(p["probe_id"] == desc["external_probe_id"]
                            and p["transcript_url"] == row["url"]
                            for p in governance["parliamentary_probes"])):
            raise ValueError("INVENTED_CROSS_CATALOG_SOURCE")
        if desc["related_document_key"] == desc["lineage_group"]:
            raise ValueError("RELATED_RECORD_FALSE_MERGE")
    if seen != set(source):
        raise ValueError("UNEXPLAINED_SOURCE")


class DP215Wave3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.governance = json.loads(GOVERNANCE.read_text(encoding="utf-8"))
        cls.wave22 = json.loads(WAVE22.read_text(encoding="utf-8"))

    def test_all_fifteen_existing_locators_have_bounded_explanations(self):
        audit(self.catalog, self.governance, self.wave22)

    def test_evidence_rights_scope_date_and_independence_cannot_be_invented(self):
        mutations = {
            "proposed_role": "AUTHENTIC_LEGAL_TEXT", "scope_class": "COURT_MURDER_JUDGMENT",
            "reference_date": "2026-10-13", "version_review": "APPROVED",
            "lineage_relation": "INDEPENDENT_OF", "independence": "ESTABLISHED",
            "rights_state": "CLEARED", "capture_allowed": True,
            "publication_allowed": True, "included_in_pilot": True,
        }
        for key, value in mutations.items():
            with self.subTest(key=key):
                changed = copy.deepcopy(self.catalog)
                changed[KEY]["descriptors"][0][key] = value
                with self.assertRaises(ValueError):
                    audit(changed, self.governance, self.wave22)

    def test_missing_duplicate_and_known_real_same_locator_are_not_independent(self):
        for mutation in ("missing", "duplicate", "camera_unlinked", "privacy_merger", "reprint_merger"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.catalog)
                descriptions = changed[KEY]["descriptors"]
                if mutation == "missing":
                    descriptions.pop()
                elif mutation == "duplicate":
                    descriptions[-1] = copy.deepcopy(descriptions[0])
                elif mutation == "camera_unlinked":
                    next(d for d in descriptions if d["lead_id"] == "lead:garlasco:camera-2026-sed0607-stenografico")["external_probe_id"] = None
                elif mutation == "privacy_merger":
                    next(d for d in descriptions if d["lead_id"] == "lead:garlasco:garanteprivacy-10273026-2026")["lineage_group"] = "garanteprivacy:docweb:10149350"
                else:
                    next(d for d in descriptions if d["lead_id"] == "lead:garlasco:ilticino-communique-2026-09")["lineage_group"] = "lead:garlasco:ilticino-communique-2026-09"
                with self.assertRaises(ValueError):
                    audit(changed, self.governance, self.wave22)


if __name__ == "__main__":
    unittest.main()
