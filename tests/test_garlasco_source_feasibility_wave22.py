"""Wave 22: public source URL metadata is a preview, never capture permission."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from preview_garlasco_public_sources_wave22 import (  # noqa: E402
    PreviewError, build_preview, load_source_plan,
)

REGISTRY = ROOT / "config" / "garlasco-public-discovery-leads.v1.json"
PLAN = ROOT / "config" / "garlasco-source-feasibility-wave22.v1.json"


class SourceFeasibilityWave22Tests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_6_verified_candidates_and_two_distinct_sources_are_metadata_only(self):
        preview = build_preview(self.registry, self.plan)
        self.assertEqual(preview["existing_verified_leads"], 6)
        self.assertEqual(preview["additional_verified_leads"], 2)
        self.assertEqual(preview["distinct_candidate_urls"], 8)
        self.assertEqual(preview["source_family_counts"]["VIDEO_PODCAST"], 3)
        self.assertEqual(preview["source_family_counts"]["DIRECT_INTERVIEW_ARTICLE"], 1)
        self.assertEqual(preview["source_family_counts"]["OFFICIAL_PROCEDURAL"], 1)
        self.assertEqual(preview["missing_required_source_families"], [])
        self.assertEqual(preview["source_origin_followups"], 1)
        self.assertEqual(preview["publication_authorized"], False)
        self.assertEqual(preview["capture_authorized"], False)
        self.assertEqual(preview["candidate_plan_persisted_discovery_hits"], 0)
        self.assertIsNone(preview["historical_database_snapshot"])

    def test_exact_registry_linkage_required(self):
        tampered = copy.deepcopy(self.plan)
        tampered["verified_existing_leads"][0]["url"] = "https://example.org/other"
        tampered["verified_existing_leads"][0]["evidence_urls"][0] = "https://example.org/other"
        with self.assertRaisesRegex(PreviewError, "REGISTRY_BINDING_MISMATCH"):
            build_preview(self.registry, tampered)

    def test_never_convert_unreviewed_hints_to_rights_or_database_provenance(self):
        for key, value in (("rights_status", "CLEARED"),
                           ("capture_authorized", True),
                           ("provenance_status", "APPROVED")):
            with self.subTest(key=key):
                tampered = copy.deepcopy(self.plan)
                tampered["verified_existing_leads"][0][key] = value
                with self.assertRaisesRegex(PreviewError, "UNREVIEWED_ONLY"):
                    build_preview(self.registry, tampered)

    def test_third_party_statement_cannot_claim_original_review(self):
        tampered = copy.deepcopy(self.plan)
        item = next(row for row in tampered["verified_existing_leads"]
                    if row["id"] == "lead:garlasco:rai-legal-communique-2026-05")
        item["origin_verified"] = True
        with self.assertRaisesRegex(PreviewError, "ORIGIN_NOT_PROVEN"):
            build_preview(self.registry, tampered)

    def test_reprinted_official_communication_has_real_issuer_link(self):
        expected = "https://procura-pavia.giustizia.it/resources/cms/documents/Comunicato_Stampa_28.09.2026.pdf"
        reprint = next(row for row in self.plan["verified_existing_leads"]
                       if row["id"] == "lead:garlasco:ilticino-communique-2026-09")
        self.assertEqual(reprint["original_url"], expected)
        original = next(row for row in self.plan["additional_verified_leads"]
                        if row["proposed_family"] == "OFFICIAL_PROCEDURAL")
        self.assertEqual(original["url"], expected)
        tampered = copy.deepcopy(self.plan)
        replacement = next(row for row in tampered["verified_existing_leads"]
                           if row["id"] == reprint["id"])
        replacement["original_url"] = replacement["url"]
        with self.assertRaisesRegex(PreviewError, "ORIGIN_NOT_PROVEN"):
            build_preview(self.registry, tampered)

    def test_duplicate_new_url_or_missing_evidence_fails_closed(self):
        tampered = copy.deepcopy(self.plan)
        tampered["additional_verified_leads"][0]["url"] = self.plan["verified_existing_leads"][0]["url"]
        with self.assertRaisesRegex(PreviewError, "DUPLICATE_URL"):
            build_preview(self.registry, tampered)
        tampered = copy.deepcopy(self.plan)
        tampered["additional_verified_leads"][0]["evidence_urls"] = []
        with self.assertRaisesRegex(PreviewError, "EVIDENCE_MISSING"):
            build_preview(self.registry, tampered)

    def test_dated_issuer_identity_is_not_a_self_declared_official_family(self):
        tampered = copy.deepcopy(self.plan)
        official = next(row for row in tampered["additional_verified_leads"]
                        if row["page_role"] == "OFFICIAL_PROCEDURAL_DOCUMENT")
        fake = "https://example.org/fake-procura-letter.pdf"
        official["url"] = fake
        official["original_url"] = fake
        official["evidence_urls"] = [fake]
        with self.assertRaisesRegex(PreviewError, "OFFICIAL_ORIGIN_INVALID"):
            build_preview(self.registry, tampered)
        tampered = copy.deepcopy(self.plan)
        tampered["additional_verified_leads"][0]["observed_date"] = "2027-01-01"
        with self.assertRaisesRegex(PreviewError, "DATE_INVALID"):
            build_preview(self.registry, tampered)

    def test_snapshot_is_readonly_context_and_cannot_promote_candidates(self):
        snapshot = dict(collection_id="research:garlasco", collection_status="PAUSED",
                        included_members=18, rights_unknown_members=18,
                        discovery_hit_rows=0, capture_authorized_members=0,
                        captures=0, passages=0, statement_candidates=0,
                        claim_candidates=0, historical_claims=30)
        preview = build_preview(self.registry, self.plan, historical_snapshot=snapshot)
        self.assertEqual(preview["historical_database_snapshot"]["included_members"], 18)
        self.assertEqual(preview["prospective_max_if_all_candidates_reviewed"], 26)
        self.assertEqual(preview["remaining_after_hypothetical_review"], 74)
        self.assertEqual(preview["remaining_actual_included"], 82)
        self.assertFalse(preview["capture_authorized"])
        with self.assertRaisesRegex(PreviewError, "SNAPSHOT_INVALID"):
            build_preview(self.registry, self.plan,
                          historical_snapshot={**snapshot, "rights_unknown_members": 19})

    def test_checked_files_load_and_never_acquire_network(self):
        self.assertEqual(load_source_plan(REGISTRY, PLAN)["observed_on"], "2026-10-10")


if __name__ == "__main__":
    unittest.main()
