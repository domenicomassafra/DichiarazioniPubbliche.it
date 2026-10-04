import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.ops.restore_drill import main as restore_main  # noqa: E402
from dichiarazioni_pubbliche.ops.restore_verify import (  # noqa: E402
    build_report,
    check_bundle,
    check_table,
    format_report,
    read_dataset_sha256,
    validate_drill,
)


class RestoreVerificationTests(unittest.TestCase):
    def test_equal_table_counts_restore(self):
        self.assertTrue(check_table("finding", 7, 7).ok)

    def test_missing_or_mismatched_counts_fail_closed(self):
        self.assertEqual(check_table("finding", 7, 0).result, "MISSING")
        self.assertEqual(check_table("finding", None, 7).result, "UNKNOWN")
        self.assertEqual(check_table("finding", 7, 8).result, "MISMATCH")

    def test_bundle_requires_identical_dataset_hash(self):
        self.assertTrue(check_bundle("public", "abc", "abc").ok)
        self.assertEqual(check_bundle("public", "abc", "def").result, "MISMATCH")
        self.assertEqual(check_bundle("public", None, "def").result, "UNKNOWN")

    def test_missing_required_measurement_is_failure(self):
        report = build_report({}, required_tables=("finding",))
        self.assertFalse(report.passed)
        self.assertIn("table:finding:UNKNOWN", report.failures[0])
        self.assertEqual(validate_drill(report), ())
        self.assertIn("do not publish", format_report(report))

    def test_dataset_sha_reader_is_bounded_to_declared_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            path.write_text(json.dumps({"dataset_sha256": "abc", "secret": "ignored"}))
            self.assertEqual(read_dataset_sha256(str(path)), "abc")
            path.write_text("{not-json")
            self.assertIsNone(read_dataset_sha256(str(path)))

    def test_backup_and_restore_inventory_include_research_corpus(self):
        from dichiarazioni_pubbliche.ops.restore_verify import LOAD_BEARING_TABLES

        tables = (
            "content_capture",
            "research_collection",
            "research_collection_content",
            "passage",
            "statement_candidate",
            "statement_candidate_passage",
            "claim_candidate",
        )
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        for table in tables:
            self.assertIn(table, LOAD_BEARING_TABLES)
            self.assertIn(table, backup)

    def test_cli_passes_only_when_all_required_counts_match(self):
        from dichiarazioni_pubbliche.ops.restore_verify import LOAD_BEARING_TABLES

        with tempfile.TemporaryDirectory() as tmp:
            counts = Path(tmp) / "counts.txt"
            counts.write_text(
                "\n".join(f"{table} 1 1" for table in LOAD_BEARING_TABLES) + "\n"
            )
            self.assertEqual(restore_main(["--counts", str(counts)]), 0)


if __name__ == "__main__":
    unittest.main()
