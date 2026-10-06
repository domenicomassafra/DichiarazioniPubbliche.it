import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_tracer import (  # noqa: E402
    GARLASCO_COLLECTION_ID,
    PilotItem,
    REQUIRED_SOURCE_FAMILIES,
    TracerManifest,
    evaluate_preflight,
    evaluate_replay,
    manifest_sha256,
)


def manifest():
    families = sorted(REQUIRED_SOURCE_FAMILIES)
    items = tuple(
        PilotItem(
            item_id=f"pilot:{index:03d}",
            canonical_url=f"https://example.test/garlasco/{index:03d}",
            discovery_ref=f"discovery:run:fixture:hit:{index:03d}",
            source_family=families[index % len(families)],
            rights_status="REVIEW_REQUIRED",
        )
        for index in range(100)
    )
    claims = tuple(f"claim:garlasco:baseline:{index:02d}" for index in range(30))
    return TracerManifest(GARLASCO_COLLECTION_ID, items, claims)


class GarlascoTracerTests(unittest.TestCase):
    def test_exact_100_item_manifest_with_all_source_families_is_ready(self):
        value = manifest()
        result = evaluate_preflight(
            value, observed_baseline_claim_ids=value.baseline_claim_ids
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.item_count, 100)
        self.assertEqual(result.baseline_claim_count, 30)

    def test_manifest_hash_is_order_independent_but_material_sensitive(self):
        value = manifest()
        reordered = TracerManifest(
            value.collection_id,
            tuple(reversed(value.items)),
            tuple(reversed(value.baseline_claim_ids)),
        )
        self.assertEqual(manifest_sha256(value), manifest_sha256(reordered))
        changed_items = list(value.items)
        changed_items[0] = PilotItem(
            item_id=changed_items[0].item_id,
            canonical_url="https://example.test/garlasco/changed",
            discovery_ref=changed_items[0].discovery_ref,
            source_family=changed_items[0].source_family,
            rights_status=changed_items[0].rights_status,
        )
        self.assertNotEqual(
            manifest_sha256(value),
            manifest_sha256(
                TracerManifest(value.collection_id, tuple(changed_items), value.baseline_claim_ids)
            ),
        )

    def test_preflight_rejects_wrong_item_count_duplicate_or_missing_family(self):
        value = manifest()
        short = TracerManifest(value.collection_id, value.items[:-1], value.baseline_claim_ids)
        self.assertIn(
            "PILOT_ITEM_COUNT_NOT_100",
            evaluate_preflight(short, observed_baseline_claim_ids=short.baseline_claim_ids).blockers,
        )
        duplicate_items = list(value.items)
        duplicate_items[-1] = duplicate_items[0]
        duplicate = TracerManifest(value.collection_id, tuple(duplicate_items), value.baseline_claim_ids)
        blockers = evaluate_preflight(
            duplicate, observed_baseline_claim_ids=duplicate.baseline_claim_ids
        ).blockers
        self.assertIn("ITEM_ID_DUPLICATE", blockers)
        self.assertIn("CANONICAL_URL_DUPLICATE", blockers)

        one_family = TracerManifest(
            value.collection_id,
            tuple(
                PilotItem(
                    row.item_id,
                    row.canonical_url,
                    row.discovery_ref,
                    "SECONDARY_REPORTING",
                    row.rights_status,
                )
                for row in value.items
            ),
            value.baseline_claim_ids,
        )
        self.assertTrue(
            any(
                code.startswith("SOURCE_FAMILY_COVERAGE_MISSING:")
                for code in evaluate_preflight(
                    one_family, observed_baseline_claim_ids=one_family.baseline_claim_ids
                ).blockers
            )
        )

    def test_current_27_claim_readback_would_block_ticket_claim_of_30(self):
        value = manifest()
        result = evaluate_preflight(
            value,
            observed_baseline_claim_ids=value.baseline_claim_ids[:27],
        )
        self.assertFalse(result.ready)
        self.assertIn("BASELINE_CLAIM_SET_MISMATCH", result.blockers)

    def test_replay_preserves_logical_items_claims_and_publication_count(self):
        claims = [f"claim:{index}" for index in range(30)]
        receipt = evaluate_replay(
            before_logical_items=100,
            after_logical_items=100,
            before_claim_ids=claims,
            after_claim_ids=list(reversed(claims)),
            before_public_findings=9,
            after_public_findings=9,
            intentionally_new_capture_versions=3,
        )
        self.assertTrue(receipt.stable)

    def test_ingestion_that_changes_public_findings_or_claim_set_fails_closed(self):
        receipt = evaluate_replay(
            before_logical_items=100,
            after_logical_items=100,
            before_claim_ids=["claim:a"],
            after_claim_ids=["claim:a", "claim:new"],
            before_public_findings=9,
            after_public_findings=10,
        )
        self.assertFalse(receipt.stable)
        self.assertIn("BASELINE_CLAIM_SET_CHANGED", receipt.blockers)
        self.assertIn("PUBLIC_FINDING_COUNT_CHANGED_FROM_INGESTION", receipt.blockers)

    def test_unsafe_or_missing_provenance_and_rights_block_preflight(self):
        value = manifest()
        rows = list(value.items)
        rows[0] = PilotItem(
            rows[0].item_id,
            "http://localhost/private",
            "",
            rows[0].source_family,
            "",
        )
        result = evaluate_preflight(
            TracerManifest(value.collection_id, tuple(rows), value.baseline_claim_ids),
            observed_baseline_claim_ids=value.baseline_claim_ids,
        )
        self.assertIn("CANONICAL_URL_UNSAFE", result.blockers)
        self.assertIn("DISCOVERY_PROVENANCE_MISSING", result.blockers)
        self.assertIn("RIGHTS_STATUS_MISSING", result.blockers)


if __name__ == "__main__":
    unittest.main()
