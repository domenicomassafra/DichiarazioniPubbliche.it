"""Wave26 governed intake review packet must never imply source-use approval."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from evaluate_garlasco_source_governance_wave26 import evaluate_packet, PacketBlocked  # noqa: E402


class SourceGovernanceWave26Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(
            (ROOT / "config/garlasco-source-feasibility-wave22.v1.json").read_text()
        )
        cls.packet = json.loads(
            (ROOT / "config/garlasco-source-governance-wave26.v1.json").read_text()
        )

    def test_real_referenced_packet_produces_governed_link_only_queue(self):
        result = evaluate_packet(self.baseline, self.packet)
        self.assertEqual(result["wave22_existing_candidates"], 8)
        self.assertEqual(result["new_parliamentary_document_candidates"], 3)
        self.assertEqual(result["official_source_candidates"], 4)
        self.assertEqual(result["matched_camera_transcript_video_sessions"], 2)
        self.assertEqual(result["unpaired_senato_transcript_sessions"], 1)
        self.assertEqual(result["unresolved_original_statement_sources"], 1)
        self.assertEqual(result["source_reuse_permissions_proven"], 0)
        self.assertEqual(result["source_body_capture_authorized"], 0)
        self.assertEqual(result["provider_call_authorized"], 0)
        self.assertEqual(result["persisted_discovery_hits_proven"], 0)
        self.assertTrue(all(x["next_action"].startswith("HUMAN_") for x in result["operator_review_queue"]))
        self.assertNotIn("Garlasco: Gli indizi", json.dumps(result))

    def test_single_authority_change_cannot_be_laundered_into_grant(self):
        for change in (
            {"rights_status": "CLEARED"},
            {"rights_evidence_status": "CC_BY_4_CONFIRMED"},
            {"original_status": "APPROVED"},
            {"source_relation": "APPROVED_DERIVATION"},
        ):
            tampered = copy.deepcopy(self.packet)
            tampered["source_reviews"][0].update(change)
            with self.subTest(change=change), self.assertRaises(PacketBlocked):
                evaluate_packet(self.baseline, tampered)

    def test_wave22_provenance_binds_ids_urls_dates_and_original(self):
        for key, invalid in (
            ("original_url", "https://example.org/fake"),
            ("observed_date", "2026-04-01"),
            ("lead_id", "lead:garlasco:invented"),
        ):
            tampered = copy.deepcopy(self.packet)
            tampered["source_reviews"][0][key] = invalid
            with self.subTest(key=key), self.assertRaises(PacketBlocked):
                evaluate_packet(self.baseline, tampered)

    def test_derived_reprint_binds_to_real_official_pdf_without_count_inflation(self):
        tampered = copy.deepcopy(self.packet)
        reprint = next(x for x in tampered["source_reviews"] if "ilticino" in x["lead_id"])
        reprint["dependent_on_lead_id"] = "lead:garlasco:rai-legal-communique-2026-05"
        with self.assertRaisesRegex(PacketBlocked, "DERIVATION_MISMATCH"):
            evaluate_packet(self.baseline, tampered)

    def test_parliamentary_speech_not_accepted_from_same_day_unrelated_video(self):
        tampered = copy.deepcopy(self.packet)
        tampered["parliamentary_probes"][0]["video_index_url"] = (
            "https://webtv.camera.it/archivio?NumeroLegislatura=19&NumeroSeduta=703"
        )
        with self.assertRaisesRegex(PacketBlocked, "PARLIAMENTARY_BINDING_INVALID"):
            evaluate_packet(self.baseline, tampered)

    def test_ccby_senato_open_data_cannot_upgrade_specific_speech_rights(self):
        tampered = copy.deepcopy(self.packet)
        tampered["parliamentary_probes"][2]["rights_status"] = "CLEARED"
        with self.assertRaisesRegex(PacketBlocked, "RIGHTS_UNREVIEWED_REQUIRED"):
            evaluate_packet(self.baseline, tampered)

    def test_unrelated_legal_url_cannot_replace_real_source_specific_terms(self):
        tampered = copy.deepcopy(self.packet)
        mediaset = next(x for x in tampered["source_reviews"] if "mediaset" in x["lead_id"])
        mediaset["rights_evidence_url"] = "https://example.org/imaginary-permissive-license"
        with self.assertRaisesRegex(PacketBlocked, "RIGHTS_PROOF_URL_INVALID"):
            evaluate_packet(self.baseline, tampered)

    def test_provenance_relationship_is_not_any_allowed_role_for_any_source(self):
        tampered = copy.deepcopy(self.packet)
        podcast = next(x for x in tampered["source_reviews"] if "burnout" in x["lead_id"])
        podcast["source_relation"] = "ORIGINAL_OFFICIAL_PROCEDURAL_COMMUNIQUE"
        with self.assertRaisesRegex(PacketBlocked, "SOURCE_SEMANTICS_INVALID"):
            evaluate_packet(self.baseline, tampered)

    def test_no_synthetic_timecoded_speaker_approval(self):
        for key in ("segment_time_verified", "speaker_approval_recorded"):
            tampered = copy.deepcopy(self.packet)
            tampered["parliamentary_probes"][1][key] = True
            with self.subTest(key=key), self.assertRaises(PacketBlocked):
                evaluate_packet(self.baseline, tampered)

    def test_duplicate_source_provenance_must_fail_before_queue(self):
        tampered = copy.deepcopy(self.packet)
        tampered["source_reviews"].append(copy.deepcopy(tampered["source_reviews"][0]))
        with self.assertRaises(PacketBlocked):
            evaluate_packet(self.baseline, tampered)


if __name__ == "__main__":
    unittest.main()
