"""Offline process-contract and lifecycle acceptance for ArchiveBox issue #171."""

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_archive_flow import _valid_archivebox_snapshot
from dichiarazioni_pubbliche.capture_archivebox_adapter import ArchiveBoxArchiveAdapter
from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, capture_content
from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked
from tests.test_capture_pipeline import FakeCaptureStore, fetched


URL = "https://example.test/fictional-document"
BODY = b"<html><body><article><h1>Fictional council speech</h1></article></body></html>"
CRAWL = "11111111-1111-4111-8111-111111111111"
SNAPSHOT = "22222222-2222-4222-8222-222222222222"


class Guard:
    def __init__(self, revoked_at=0):
        self.calls = []
        self.revoked_at = revoked_at

    def bind_capture(self, *, content_id, url):
        if content_id != "content:archivebox" or url != URL:
            raise SourceUseBlocked("SOURCE_USE_CAPTURE_TARGET_MISMATCH")

    def bind_fetched(self, *, final_url):
        if final_url != URL:
            raise SourceUseBlocked("SOURCE_USE_FINAL_ARTIFACT_MISMATCH")

    def require(self, use, **kwargs):
        self.calls.append(use)
        if use == "ARCHIVE" and self.revoked_at and self.calls.count("ARCHIVE") >= self.revoked_at:
            raise SourceUseBlocked("SOURCE_USE_REVOKED")
        return SimpleNamespace(decision_fingerprint="a" * 64)


class ReceiptStore(FakeCaptureStore):
    def __init__(self):
        super().__init__()
        self.receipts = []

    def request_archive(self, **kwargs):
        self.receipts.append(("REQUESTED", kwargs["receipt"]))
        return super().request_archive(**kwargs)

    def mark_archive_pending(self, **kwargs):
        self.receipts.append(("PENDING", kwargs["receipt"]))
        return super().mark_archive_pending(**kwargs)

    def complete_archive(self, **kwargs):
        self.receipts.append((kwargs["outcome"], kwargs["receipt"]))
        return super().complete_archive(**kwargs)


def fake_archivebox(root, *, outcome="sealed"):
    executable = Path(root) / "fake-archivebox-python"
    counter = Path(root) / "calls"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, sys, pathlib\n"
        "assert sys.argv[1] == '-c'\n"
        "assert 'archivebox.cli.archivebox_add' in sys.argv[2]\n"
        f"assert sys.argv[3] == {URL!r}\n"
        "assert sys.argv[4].startswith('dp-')\n"
        f"counter = pathlib.Path({str(counter)!r})\n"
        "counter.write_text(counter.read_text() + '1' if counter.exists() else '1')\n"
        + (
            "import time; time.sleep(3)\n" if outcome == "timeout"
            else "sys.exit(3)\n" if outcome == "error"
            else (
                "print(json.dumps({"
                f"'archivebox_version': '0.9.73', 'crawl_id': {CRAWL!r},"
                f"'snapshot_id': {SNAPSHOT!r},"
                f"'snapshot_status': {outcome!r},"
                "'crawl_status': 'sealed', 'url_matches': True"
                "}))\n"
            )
        ),
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable, counter


class ArchiveBoxTests(unittest.TestCase):
    def prepare(self, temp, *, outcome="sealed", permission=True, revoke_at=0,
                timeout=5, collection_private=True):
        private = Path(temp) / "private"
        store = ReceiptStore()
        body_store = CaptureBodyStore(private)
        guard = Guard(revoked_at=revoke_at)
        python, calls = fake_archivebox(temp, outcome=outcome)
        collection = private / "archivebox-data"
        collection.mkdir(mode=0o700)
        if not collection_private:
            collection.chmod(0o755)
        adapter = ArchiveBoxArchiveAdapter(
            python_path=python, private_root=private, collection_dir=collection,
            source_use_guard=guard, network_fetch_permitted=permission,
            timeout_seconds=timeout,
        )
        def capture():
            return capture_content(
                content_id="content:archivebox", url=URL, store=store,
                body_store=body_store, source_use_guard=guard,
                archive_adapter=adapter,
                fetcher=lambda url, **_: fetched(BODY, url=url),
            )
        return capture, store, guard, private, calls, body_store, adapter

    def test_request_pending_success_immutable_receipt_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temp:
            capture, store, guard, private, calls, body_store, adapter = self.prepare(temp)
            first = capture()
            self.assertEqual(first.archive_status, "SUCCEEDED")
            self.assertEqual([state for state, _ in store.receipts], [
                "REQUESTED", "PENDING", "SUCCEEDED",
            ])
            proof = store.receipts[-1][1]
            self.assertEqual(proof["source_capture_sha256"], hashlib.sha256(BODY).hexdigest())
            self.assertEqual(proof["archivebox_snapshot_id"], SNAPSHOT)
            self.assertEqual(proof["publication_state"], "HOLD")
            self.assertEqual(proof["plugins"], "readability")
            self.assertNotIn("archive_url", proof)
            self.assertTrue(_valid_archivebox_snapshot(body_store, proof, first.content_sha256))
            marker = private / proof["snapshot_ref"]
            self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)
            self.assertEqual(calls.read_text(), "1")
            self.assertEqual(capture().archive_status, "SUCCEEDED")
            self.assertEqual(calls.read_text(), "1")
            self.assertEqual(len(store.receipts), 3)
            self.assertGreaterEqual(guard.calls.count("ARCHIVE"), 3)
            # A tampered receipt or private marker cannot be promoted.
            tampered = {**proof, "archivebox_snapshot_id": CRAWL}
            self.assertFalse(_valid_archivebox_snapshot(body_store, tampered, first.content_sha256))
            marker.write_text("{}")
            self.assertFalse(_valid_archivebox_snapshot(body_store, proof, first.content_sha256))

    def test_queued_remains_pending_and_never_claims_public_locator(self):
        with tempfile.TemporaryDirectory() as temp:
            capture, store, _, _, calls, _, _ = self.prepare(temp, outcome="queued")
            result = capture()
            self.assertEqual(result.archive_status, "PENDING")
            self.assertEqual([state for state, _ in store.receipts], [
                "REQUESTED", "PENDING", "PENDING",
            ])
            self.assertNotIn("archive_url", store.receipts[-1][1])
            self.assertEqual(calls.read_text(), "1")
            # Existing pending capture does not enqueue another ArchiveBox crawl.
            self.assertEqual(capture().archive_status, "PENDING")
            self.assertEqual(calls.read_text(), "1")

    def test_failure_retry_then_success_keeps_original_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            capture, store, _, private, calls, body_store, adapter = self.prepare(
                temp, outcome="error",
            )
            failed = capture()
            self.assertEqual(failed.archive_status, "FAILED")
            self.assertEqual(failed.parse_status, "SUCCEEDED")
            self.assertTrue(failed.passage_ids)
            self.assertEqual(store.receipts[-1][1]["error_category"], "ARCHIVEBOX_PROCESS_FAILED")
            replacement, _ = fake_archivebox(temp, outcome="sealed")
            adapter.python_path = replacement
            replay = capture()
            self.assertEqual(replay.archive_status, "SUCCEEDED")
            self.assertEqual(replay.primary_capture_id, failed.primary_capture_id)
            self.assertEqual(calls.read_text(), "11")

    def test_rights_denial_and_source_fetch_permit_block_before_process(self):
        for permission, revoked_at, expected in (
            (False, 0, "ARCHIVEBOX_SOURCE_FETCH_NOT_APPROVED"),
            (True, 3, "SOURCE_USE_REVOKED"),
        ):
            with self.subTest(permission=permission, revoked=revoked_at):
                with tempfile.TemporaryDirectory() as temp:
                    capture, store, _, _, calls, _, _ = self.prepare(
                        temp, permission=permission, revoke_at=revoked_at,
                    )
                    result = capture()
                    self.assertEqual(result.archive_status, "FAILED")
                    self.assertEqual(store.receipts[-1][1]["error_category"], expected)
                    self.assertFalse(calls.exists())

    def test_process_timeout_private_collection_and_invalid_outcome(self):
        for outcome, private, expected in (
            ("timeout", True, "ARCHIVEBOX_PROCESS_TIMEOUT"),
            ("sealed", False, "ARCHIVEBOX_COLLECTION_NOT_PRIVATE"),
            ("incomplete", True, "ARCHIVEBOX_SNAPSHOT_INCOMPLETE"),
        ):
            with self.subTest(outcome=outcome, private=private):
                with tempfile.TemporaryDirectory() as temp:
                    capture, store, _, _, _, _, _ = self.prepare(
                        temp, outcome=outcome, collection_private=private,
                        timeout=1,
                    )
                    self.assertEqual(capture().archive_status, "FAILED")
                    self.assertEqual(store.receipts[-1][1]["error_category"], expected)

    def test_body_hash_mismatch_and_revoke_after_process(self):
        with tempfile.TemporaryDirectory() as temp:
            capture, store, guard, _, calls, body_store, adapter = self.prepare(
                temp, revoke_at=4,
            )
            result = capture()
            self.assertEqual(result.archive_status, "FAILED")
            self.assertEqual(store.receipts[-1][1]["error_category"], "SOURCE_USE_REVOKED")
            self.assertTrue(calls.exists())
        with tempfile.TemporaryDirectory() as temp:
            capture, store, guard, _, calls, body_store, adapter = self.prepare(temp)
            # Capture immutable bytes are checked independently of provider process.
            record = capture()
            original = next(iter(store.captures.values()))["record"]
            body_store.path(original.body_ref).write_bytes(b"tampered")
            outcome = adapter.archive(capture=original, body_path=body_store.path(original.body_ref))
            self.assertEqual(outcome.status, "FAILED")
            self.assertEqual(outcome.receipt["error_category"], "ARCHIVEBOX_BODY_HASH_MISMATCH")


if __name__ == "__main__":
    unittest.main()
