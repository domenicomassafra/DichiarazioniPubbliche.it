"""Offline canary audit: content, privacy, rights evidence, and cost boundaries."""

import hashlib
import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.archivebox_multiformat_audit import (
    CanaryAuditError, DONOR_COMMIT, VERSION, validate,
)

SHA = "bba0d4576f1a9332eb89bb7f7291fa2e69ee2c2a9dd2e65499f84af7a25a56cc"
B = "a45de00f327e7894c00fb95f0ef54cc68b664d0879a04834487388c390be9235"
C = "c" * 64
CRAWL = "11111111-1111-4111-8111-111111111111"
SNAPSHOT = "22222222-2222-4222-8222-222222222222"


def fixture(root: Path) -> tuple[dict, Path]:
    root.chmod(0o700)
    outputs = root / "archivebox"
    outputs.mkdir(mode=0o700)
    artifacts = []
    for kind, name, contents in (
        ("WARC", "capture.warc", b"WARC/1.1\r\nWARC-Type: response\r\n\r\n"),
        ("PDF", "capture.pdf", b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"),
        ("METADATA", "metadata.json", json.dumps({
            "crawl_id": CRAWL,
            "snapshot_id": SNAPSHOT,
            "source_capture_sha256": B,
            "publication_state": "HOLD",
        }).encode()),
    ):
        file = outputs / name
        file.write_bytes(contents)
        file.chmod(0o600)
        artifacts.append({
            "kind": kind, "path": f"archivebox/{name}",
            "bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest(),
        })
    log = root / "run.log"
    log.write_text("isolated synthetic canary only; service stopped", encoding="utf-8")
    log.chmod(0o600)
    log_sha = hashlib.sha256(log.read_bytes()).hexdigest()
    manifest = {
        "schema": VERSION,
        "donor": {"tag": "v0.9.73", "commit": DONOR_COMMIT,
                  "license": "MIT",
                  "image": "archivebox/archivebox:0.9.73@sha256:" + C},
        "source": {
            "kind": "SYNTHETIC_HTTPS",
            "original_url_sha256": SHA,
            "capture_sha256": B,
            "rights_decision_sha256": C,
            "approved_uses": ["FETCH", "STORE_BODY", "PARSE_TEXT", "ARCHIVE"],
        },
        "receipt": {
            "crawl_id": CRAWL, "snapshot_id": SNAPSHOT,
            "source_capture_sha256": B, "original_url_sha256": SHA,
            "publication_state": "HOLD", "retention": "PRIVATE",
        },
        "artifacts": artifacts,
        "metrics": {
            "peak_rss_kib": 512000, "duration_ms": 6000,
            "disk_bytes": 4096, "max_rss_kib": 1024000,
            "max_duration_ms": 120000, "max_disk_bytes": 10485760,
        },
        "monolith": {
            "peak_rss_kib": 32000, "duration_ms": 800, "disk_bytes": 1000,
        },
        "rollback": {
            "service_stopped": True, "private_artifacts_preserved": True,
            "run_log_path": "run.log",
            "run_log_bytes": log.stat().st_size,
            "run_log_sha256": log_sha,
        },
    }
    path = root / "manifest.json"
    store(path, manifest)
    return manifest, path


def store(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)


class ArchiveBoxMultiformatAuditTests(unittest.TestCase):
    def test_unapproved_url_or_body_hash_cannot_pass_with_consistent_receipts(self):
        for changed in ("original_url_sha256", "capture_sha256"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                record, path = fixture(root)
                record["source"][changed] = "f" * 64
                receipt_key = ("original_url_sha256" if changed == "original_url_sha256"
                               else "source_capture_sha256")
                record["receipt"][receipt_key] = "f" * 64
                if changed == "capture_sha256":
                    metadata_path = root / "archivebox/metadata.json"
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    metadata["source_capture_sha256"] = "f" * 64
                    payload = json.dumps(metadata).encode()
                    metadata_path.write_bytes(payload)
                    record["artifacts"][2]["bytes"] = len(payload)
                    record["artifacts"][2]["sha256"] = hashlib.sha256(payload).hexdigest()
                store(path, record)
                with self.assertRaisesRegex(CanaryAuditError, "SOURCE_FIXTURE_MISMATCH"):
                    validate(root, path)

    def test_valid_private_synthetic_artifacts_and_measured_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, path = fixture(root)
            before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
            summary = validate(root, path)
            self.assertEqual(summary["artifacts"], 3)
            self.assertEqual(summary["peak_rss_kib"], 512000)
            self.assertEqual(summary["baseline_peak_rss_kib"], 32000)
            self.assertEqual(before, sorted(str(p.relative_to(root)) for p in root.rglob("*")))

    def test_tampering_and_format_spoofing_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, path = fixture(root)
            pdf = root / "archivebox/capture.pdf"
            pdf.write_bytes(b"x" + pdf.read_bytes()[1:])
            with self.assertRaisesRegex(CanaryAuditError, "ARTIFACT_HASH_MISMATCH"):
                validate(root, path)
            new_data = pdf.read_bytes()
            record["artifacts"][1]["sha256"] = hashlib.sha256(new_data).hexdigest()
            store(path, record)
            with self.assertRaisesRegex(CanaryAuditError, "ARTIFACT_FORMAT_MISMATCH"):
                validate(root, path)

    def test_compressed_warc_supported_with_hash_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, path = fixture(root)
            warc_path = root / "archivebox/capture.warc"
            packed = gzip.compress(warc_path.read_bytes())
            warc_path.write_bytes(packed)
            record["artifacts"][0]["bytes"] = len(packed)
            record["artifacts"][0]["sha256"] = hashlib.sha256(packed).hexdigest()
            store(path, record)
            self.assertEqual(validate(root, path)["artifacts"], 3)

    def test_compressed_warc_truncated_crc_or_expansion_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, manifest_path = fixture(root)
            warc_path = root / "archivebox/capture.warc"
            original = warc_path.read_bytes()

            def replace_warc(contents: bytes) -> None:
                warc_path.write_bytes(contents)
                record["artifacts"][0]["bytes"] = len(contents)
                record["artifacts"][0]["sha256"] = hashlib.sha256(contents).hexdigest()
                store(manifest_path, record)

            packed = gzip.compress(original)
            replace_warc(packed[:-8])  # missing CRC/ISIZE trailer
            with self.assertRaisesRegex(CanaryAuditError, "ARTIFACT_FORMAT_MISMATCH"):
                validate(root, manifest_path)

            replace_warc(packed[:-8] + b"\x00" * 8)  # corrupt trailer
            with self.assertRaisesRegex(CanaryAuditError, "ARTIFACT_FORMAT_MISMATCH"):
                validate(root, manifest_path)

            replace_warc(gzip.compress(original + b"x" * 256))
            with patch(
                "dichiarazioni_pubbliche.archivebox_multiformat_audit.MAX_WARC_UNCOMPRESSED", 64
            ):
                with self.assertRaisesRegex(CanaryAuditError, "WARC_UNCOMPRESSED_TOO_LARGE"):
                    validate(root, manifest_path)

    def test_missing_warc_or_duplicate_artifacts_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, path = fixture(root)
            record["artifacts"].pop(0)
            store(path, record)
            with self.assertRaisesRegex(CanaryAuditError, "REQUIRED_ARTIFACTS_MISSING"):
                validate(root, path)
            record["artifacts"].append(dict(record["artifacts"][0]))
            store(path, record)
            with self.assertRaisesRegex(CanaryAuditError, "DUPLICATE_ARTIFACT_KIND"):
                validate(root, path)

    def test_bad_rights_hold_or_runtime_pin_rejected(self):
        for section, key, value, expected in (
            ("source", "approved_uses", ["FETCH"], "SOURCE_PROOF_INCOMPLETE"),
            ("source", "rights_decision_sha256", "", "SOURCE_PROOF_INCOMPLETE"),
            ("receipt", "publication_state", "PUBLIC", "RECEIPT_NOT_PRIVATE"),
            ("receipt", "archive_url", "https://example.test/archive", "RECEIPT_NOT_PRIVATE"),
            ("donor", "image", "archivebox/archivebox:latest", "DONOR_NOT_PINNED"),
            ("donor", "commit", SHA, "DONOR_NOT_PINNED"),
            ("rollback", "service_stopped", False, "ROLLBACK_UNVERIFIED"),
        ):
            with self.subTest(section=section, field=key):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    record, path = fixture(root)
                    record[section][key] = value
                    store(path, record)
                    with self.assertRaisesRegex(CanaryAuditError, expected):
                        validate(root, path)

    def test_budget_and_missing_monolith_baseline_fail(self):
        for section, key, value, expected in (
            ("metrics", "peak_rss_kib", 2048000, "BUDGET_EXCEEDED"),
            ("metrics", "disk_bytes", 1, "BUDGET_EXCEEDED"),
            ("monolith", "duration_ms", 0, "MONOLITH_BASELINE_MISSING"),
        ):
            with self.subTest(section=section, key=key):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    record, path = fixture(root)
                    record[section][key] = value
                    store(path, record)
                    with self.assertRaisesRegex(CanaryAuditError, expected):
                        validate(root, path)

    def test_rollback_log_cannot_be_forged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, path = fixture(root)
            (root / "run.log").write_text("altered", encoding="utf-8")
            with self.assertRaisesRegex(CanaryAuditError, "ARTIFACT_SIZE_MISMATCH"):
                validate(root, path)

    def test_private_storage_path_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "private"
            root.mkdir(mode=0o700)
            record, path = fixture(root)
            target = root / "archivebox/capture.warc"
            target.chmod(0o644)
            with self.assertRaisesRegex(CanaryAuditError, "ARTIFACT_NOT_PRIVATE"):
                validate(root, path)
            target.chmod(0o600)
            external = Path(temp) / "external.warc"
            external.write_bytes(target.read_bytes())
            target.unlink()
            target.symlink_to(external)
            with self.assertRaisesRegex(CanaryAuditError, "SYMLINK_REJECTED"):
                validate(root, path)

    def test_metadata_provenance_mismatch_and_duplicate_manifest_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, path = fixture(root)
            metadata_path = root / "archivebox/metadata.json"
            modified = json.loads(metadata_path.read_text())
            modified["snapshot_id"] = CRAWL
            changed = json.dumps(modified).encode()
            metadata_path.write_bytes(changed)
            record["artifacts"][2]["bytes"] = len(changed)
            record["artifacts"][2]["sha256"] = hashlib.sha256(changed).hexdigest()
            store(path, record)
            with self.assertRaisesRegex(CanaryAuditError, "METADATA_PROVENANCE_MISMATCH"):
                validate(root, path)
            path.write_text('{"schema": "one", "schema": "two"}', encoding="utf-8")
            with self.assertRaisesRegex(CanaryAuditError, "DUPLICATE_JSON_KEY"):
                validate(root, path)

    def test_metadata_public_locator_must_not_bypass_private_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, path = fixture(root)
            metadata_path = root / "archivebox/metadata.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["public_locator"] = "https://example.test/public-snapshot"
            payload = json.dumps(metadata, sort_keys=True).encode()
            metadata_path.write_bytes(payload)
            record["artifacts"][2]["bytes"] = len(payload)
            record["artifacts"][2]["sha256"] = hashlib.sha256(payload).hexdigest()
            store(path, record)
            with self.assertRaisesRegex(CanaryAuditError, "METADATA_PROVENANCE_MISMATCH"):
                validate(root, path)


    def test_hardlink_to_file_outside_private_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "private"
            root.mkdir(mode=0o700)
            _, manifest = fixture(root)
            outside = Path(temp) / "external-retained.warc"
            os.link(root / "archivebox/capture.warc", outside)
            with self.assertRaisesRegex(CanaryAuditError, "ARTIFACT_HARDLINK_REJECTED"):
                validate(root, manifest)

    def test_manifest_hardlink_outside_private_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "private"
            root.mkdir(mode=0o700)
            _, manifest = fixture(root)
            os.link(manifest, Path(temp) / "external-manifest.json")
            with self.assertRaisesRegex(CanaryAuditError, "MANIFEST_HARDLINK_REJECTED"):
                validate(root, manifest)

    def test_metadata_original_url_hash_conflict_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record, manifest = fixture(root)
            metadata_path = root / "archivebox/metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["original_url_sha256"] = "f" * 64
            payload = json.dumps(metadata, sort_keys=True).encode("utf-8")
            metadata_path.write_bytes(payload)
            record["artifacts"][2]["bytes"] = len(payload)
            record["artifacts"][2]["sha256"] = hashlib.sha256(payload).hexdigest()
            store(manifest, record)
            with self.assertRaisesRegex(CanaryAuditError, "METADATA_PROVENANCE_MISMATCH"):
                validate(root, manifest)


if __name__ == "__main__":
    unittest.main()
