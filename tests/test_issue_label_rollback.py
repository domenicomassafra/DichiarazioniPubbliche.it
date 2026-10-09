import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.issue_label_rollback import labels_by_name, proposed_overlay, capture_public_labels  # noqa: E402

MANIFEST = {
    "schema_version": "dichiarazioni-pubbliche-labels-v1",
    "labels": [
        {"name": "bug", "color": "d73a4a", "description": "New description", "public_allowed": True},
        {"name": "new-label", "color": "c5def5", "description": "Safe public", "public_allowed": True},
        {"name": "security-private", "color": "b60205", "description": "Private", "public_allowed": False},
    ],
}
BEFORE = [
    {"name": "bug", "color": "123456", "description": "Existing description"},
    {"name": "wontfix", "color": "ffffff", "description": "Existing unowned label"},
]


class IssueLabelRollbackTests(unittest.TestCase):
    def test_hosted_overlay_proves_exact_rollback_without_mutating_input(self):
        original = json.dumps(BEFORE, sort_keys=True)
        receipt = proposed_overlay(BEFORE, MANIFEST)
        self.assertEqual(receipt["before_count"], 2)
        self.assertEqual(receipt["after_count"], 3)
        self.assertEqual(receipt["change_count"], 2)
        self.assertEqual(receipt["changes"], [
            {"name": "bug", "action": "update"},
            {"name": "new-label", "action": "create"},
        ])
        self.assertEqual(receipt["before_sha256"], receipt["rollback_sha256"])
        self.assertNotEqual(receipt["before_sha256"], receipt["proposed_sha256"])
        self.assertFalse(receipt["remote_mutation_performed"])
        self.assertEqual(json.dumps(BEFORE, sort_keys=True), original)
        self.assertNotIn("security-private", json.dumps(receipt))

    def test_tampered_hosted_or_private_state_cannot_generate_plan(self):
        for rows in (
            [BEFORE[0], BEFORE[0]], [{"name": "bad\nname", "color": "123456"}],
            [{"name": "fine", "color": "SECRET"}], "wrong",
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                proposed_overlay(rows, MANIFEST)
        for changes in (
            {"schema_version": "untrusted"},
            {"labels": [{"name": "unknown", "color": "cccccc", "public_allowed": None}]},
            {"labels": MANIFEST["labels"] + [MANIFEST["labels"][0]]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                proposed_overlay(BEFORE, MANIFEST | changes)

    def test_remote_capture_is_read_only_and_page_bounded(self):
        with patch("tools.issue_label_rollback._gh_get", return_value=BEFORE) as read:
            self.assertEqual(capture_public_labels(), BEFORE)
            read.assert_called_once_with(
                "repos/domenicomassafra/DichiarazioniPubbliche.it/labels?per_page=100&page=1"
            )


if __name__ == "__main__":
    unittest.main()
