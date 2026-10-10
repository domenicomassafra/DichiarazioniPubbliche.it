"""DP-214 replay identity acceptance: equal totals are insufficient evidence."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_tracer import evaluate_replay
from dichiarazioni_pubbliche.garlasco_replay_identity import (
    audit_replay_snapshots,
    load_replay_snapshot,
    ReplayIdentityError,
)


def baseline():
    return {
        "collection_id": "research:garlasco",
        "content_ids": [f"content:garlasco:{i:03d}" for i in range(100)],
        "claim_ids": [f"claim:garlasco:{i:03d}" for i in range(30)],
        "public_finding_ids": ["finding:published:1", "finding:published:2"],
        "captures": [
            {"id": "capture:1", "content_id": "content:garlasco:000", "content_sha256": "a" * 64}
        ],
    }


class ReplayIdentityTests(unittest.TestCase):
    def test_equal_counts_cannot_hide_content_substitution(self):
        before = baseline()
        after = baseline()
        after["content_ids"][1] = "content:garlasco:replacement"
        # Existing structural helper cannot distinguish these inventories.
        legacy = evaluate_replay(
            before_logical_items=100,
            after_logical_items=100,
            before_claim_ids=before["claim_ids"],
            after_claim_ids=after["claim_ids"],
            before_public_findings=2,
            after_public_findings=2,
        )
        self.assertTrue(legacy.stable)
        result = audit_replay_snapshots(before, after)
        self.assertFalse(result.stable)
        self.assertIn("LOGICAL_CONTENT_SET_CHANGED", result.blockers)

    def test_equal_counts_cannot_hide_replaced_publication(self):
        before, after = baseline(), baseline()
        after["public_finding_ids"][0] = "finding:published:new"
        result = audit_replay_snapshots(before, after)
        self.assertFalse(result.stable)
        self.assertIn("PUBLIC_PUBLISH_SET_CHANGED", result.blockers)

    def test_immutable_capture_rebound_or_deleted_is_rejected(self):
        before, after = baseline(), baseline()
        after["captures"][0]["content_sha256"] = "b" * 64
        result = audit_replay_snapshots(before, after)
        self.assertIn("EXISTING_CAPTURE_MUTATED", result.blockers)
        after["captures"] = []
        result = audit_replay_snapshots(before, after)
        self.assertIn("EXISTING_CAPTURE_REMOVED", result.blockers)

    def test_explicit_new_immutable_capture_version_is_permitted(self):
        before, after = baseline(), baseline()
        after["captures"].append({
            "id": "capture:2", "content_id": "content:garlasco:000", "content_sha256": "b" * 64,
        })
        self.assertIn("UNAUTHORIZED_NEW_CAPTURE", audit_replay_snapshots(before, after).blockers)
        result = audit_replay_snapshots(before, after, authorized_new_capture_ids=("capture:2",))
        self.assertTrue(result.stable)
        self.assertEqual(result.new_capture_ids, ("capture:2",))

    def test_capture_cannot_reference_outside_collection(self):
        before = baseline()
        before["captures"][0]["content_id"] = "content:elsewhere:1"
        with self.assertRaisesRegex(ReplayIdentityError, "CAPTURE_CONTENT_OUT_OF_SCOPE"):
            audit_replay_snapshots(before, baseline())

    def test_duplicate_content_claim_capture_and_finding_ids_fail_closed(self):
        for key in ("content_ids", "claim_ids", "public_finding_ids", "captures"):
            with self.subTest(key=key):
                before = baseline()
                before[key].append(before[key][0])
                with self.assertRaisesRegex(ReplayIdentityError, "DUPLICATE"):
                    audit_replay_snapshots(before, baseline())

    def test_strict_bounded_file_loading_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "snapshot.json"
            path.write_text('{"collection_id":"research:garlasco","collection_id":"other"}')
            with self.assertRaisesRegex(ReplayIdentityError, "DUPLICATE_JSON_KEY"):
                load_replay_snapshot(path)
            path.write_bytes(b"x" * 300_000)
            with self.assertRaisesRegex(ReplayIdentityError, "FILE_TOO_LARGE"):
                load_replay_snapshot(path)

    def test_reorder_only_is_stable_and_input_is_unmodified(self):
        before, after = baseline(), baseline()
        after["content_ids"].reverse()
        after["claim_ids"].reverse()
        after["public_finding_ids"].reverse()
        snapshot = json.dumps(after)
        receipt = audit_replay_snapshots(before, after)
        self.assertTrue(receipt.stable)
        self.assertEqual(json.dumps(after), snapshot)
        self.assertEqual(receipt.before_sha256, receipt.after_sha256)


if __name__ == "__main__":
    unittest.main()
