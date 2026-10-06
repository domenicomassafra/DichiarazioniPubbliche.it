import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESTORE_SCRIPT = ROOT / "deploy" / "ops" / "restore_drill.sh"
VERIFY_BUNDLE_SCRIPT = ROOT / "deploy" / "ops" / "verify_projection_bundle.py"
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
from dichiarazioni_pubbliche.ops.table_inventory import (  # noqa: E402
    repository_persistent_tables,
)
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256  # noqa: E402


class RestoreVerificationTests(unittest.TestCase):
    def _write_fake_tool(self, root: Path, name: str, body: str) -> None:
        path = root / name
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _run_restore_driver_with_psql(self, psql_body: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fakebin = root / "bin"
            fakebin.mkdir()
            self._write_fake_tool(fakebin, "psql", psql_body)
            self._write_fake_tool(fakebin, "pg_restore", "exit 0\n")
            env = os.environ.copy()
            env["PATH"] = str(fakebin) + os.pathsep + env.get("PATH", "")
            return subprocess.run(
                [
                    str(RESTORE_SCRIPT),
                    "--backup-root",
                    str(root / "backups"),
                    "--restore-url",
                    "postgresql:///restore-target",
                ],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

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

    def test_projection_bundle_verifier_hashes_first_class_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            payload = {
                "schema_version": "dichiarazioni-pubbliche-public-v2",
                "generated_at": "2026-10-06T12:00:00+00:00",
                "dataset_sha256": "",
                "dossier_count": 0,
                "omitted_count": 0,
                "methodology": {"aggregate_person_score": False},
                "dossiers": [],
                "topics": [],
                "contents": [],
            }
            payload["dataset_sha256"] = projection_dataset_sha256(payload)
            (bundle / "index.json").write_text(json.dumps(payload))

            proc = subprocess.run(
                [sys.executable, str(VERIFY_BUNDLE_SCRIPT), str(bundle)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("BUNDLE VERIFY: OK", proc.stdout)

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

    def test_backup_and_restore_inventory_include_durable_publication_reviews(self):
        from dichiarazioni_pubbliche.ops.restore_verify import LOAD_BEARING_TABLES

        table = "publication_review_event_durable"
        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        self.assertIn(table, LOAD_BEARING_TABLES)
        self.assertIn(table, backup)

    def test_backup_and_restore_inventory_include_reply_governance_ledgers(self):
        from dichiarazioni_pubbliche.ops.restore_verify import LOAD_BEARING_TABLES

        backup = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        for table in ("private_intake_abuse_event", "private_reply_retention_event"):
            self.assertIn(table, LOAD_BEARING_TABLES)
            self.assertIn(table, backup)

    def test_backup_and_restore_inventory_cover_all_persistent_tables(self):
        from dichiarazioni_pubbliche.ops.restore_verify import LOAD_BEARING_TABLES

        persistent_tables = set(repository_persistent_tables(ROOT))

        backup_text = (ROOT / "deploy" / "ops" / "backup.sh").read_text()
        match = re.search(r'^TABLES="(.*?)"$', backup_text, re.DOTALL | re.MULTILINE)
        self.assertIsNotNone(match, "backup.sh TABLES inventory is not parseable")
        backup_tables = set(re.findall(r"\b[a-z][a-z0-9_]+\b", match.group(1)))
        restore_tables = set(LOAD_BEARING_TABLES)

        self.assertEqual(backup_tables, restore_tables)
        self.assertEqual(persistent_tables, backup_tables)
        self.assertIn("checked-in table inventory drifted from schema+migrations", backup_text)
        self.assertIn("live durable table inventory drifted from schema+migrations", backup_text)

    def test_restore_driver_refuses_canonical_production_database(self):
        proc = self._run_restore_driver_with_psql("echo dichiarazioni_pubbliche\n")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("refusing canonical production database", proc.stderr)

    def test_restore_inventory_comparisons_use_bytewise_sort(self):
        text = RESTORE_SCRIPT.read_text()
        self.assertGreaterEqual(text.count("LC_ALL=C sort"), 2)

    def test_restore_driver_refuses_nonempty_target(self):
        proc = self._run_restore_driver_with_psql(
            'case "$*" in\n'
            '  *current_database*) echo dp_restore_test ;;\n'
            '  *) echo 1 ;;\n'
            'esac\n'
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("is not empty", proc.stderr)

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
