"""Offline acceptance for the optional private Monolith archiver (issue #161)."""

import hashlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_monolith_adapter import (
    MONOLITH_LINUX_X86_64_SHA256, MonolithArchiveAdapter,
)
from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, capture_content
from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked
from test_capture_pipeline import FakeCaptureStore, fetched


URL = "https://example.test/article"
HTML = b"<!doctype html><html><body><h1>Fictional parliamentary debate</h1></body></html>"


class OfflineGuard:
    def __init__(self, *, permitted=True, revoke_on_archive_call=None):
        self.permitted = permitted
        self.calls = []
        self.revoke_on_archive_call = revoke_on_archive_call

    def bind_capture(self, *, content_id, url):
        if url != URL or content_id != "content:monolith":
            raise SourceUseBlocked("SOURCE_USE_CAPTURE_TARGET_MISMATCH")

    def bind_fetched(self, *, final_url):
        if final_url != URL:
            raise SourceUseBlocked("SOURCE_USE_FINAL_ARTIFACT_MISMATCH")

    def require(self, use, **kwargs):
        self.calls.append(use)
        if use == "ARCHIVE" and (
            not self.permitted or (
                self.revoke_on_archive_call is not None
                and self.calls.count("ARCHIVE") >= self.revoke_on_archive_call
            )
        ):
            raise SourceUseBlocked("SOURCE_USE_NOT_PERMITTED")
        return SimpleNamespace(decision_fingerprint="a" * 64)


def make_binary(root, *, behavior="ok"):
    binary = Path(root) / "fake-monolith"
    snippet = {
        "ok": "sys.stdout.buffer.write(sys.stdin.buffer.read())",
        "invalid": "sys.stdout.buffer.write(b'not html')",
        "oversize": "sys.stdout.buffer.write(b'<html>' + b'x' * 10000 + b'</html>')",
        "failed": "sys.exit(4)",
        "timeout": "import time; time.sleep(3)",
    }[behavior]
    binary.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "if '-V' in sys.argv:\n"
        "    print('monolith 2.11.6')\n"
        "    sys.exit(0)\n"
        "assert sys.argv[-1] == '-'\n"
        "assert '-a' in sys.argv and '-c' in sys.argv and '-f' in sys.argv\n"
        "assert '-F' in sys.argv and '-i' in sys.argv and '-j' in sys.argv\n"
        "assert '-v' in sys.argv and '-d' in sys.argv\n"
        "assert '-b' in sys.argv and 'https://example.test/article' in sys.argv\n"
        + snippet + "\n",
        encoding="utf-8",
    )
    binary.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return binary, hashlib.sha256(binary.read_bytes()).hexdigest()


class MonolithArchiveTests(unittest.TestCase):
    class ReceiptStore(FakeCaptureStore):
        def __init__(self):
            super().__init__()
            self.archive_receipts = []

        def request_archive(self, **kwargs):
            self.archive_receipts.append(("REQUESTED", dict(kwargs["receipt"])))
            return super().request_archive(**kwargs)

        def mark_archive_pending(self, **kwargs):
            self.archive_receipts.append(("PENDING", dict(kwargs["receipt"])))
            return super().mark_archive_pending(**kwargs)

        def complete_archive(self, **kwargs):
            self.archive_receipts.append((kwargs["outcome"], dict(kwargs["receipt"])))
            return super().complete_archive(**kwargs)

    def run_capture(self, root, *, behavior="ok", binary=None, digest=None,
                    permitted=True, max_bytes=2_048, timeout=1):
        private_root = Path(root) / "private"
        body_store = CaptureBodyStore(private_root)
        guard = OfflineGuard(permitted=permitted)
        if binary is None:
            binary, digest = make_binary(root, behavior=behavior)
        adapter = MonolithArchiveAdapter(
            binary_path=binary, binary_sha256=digest,
            private_root=private_root, source_use_guard=guard,
            max_output_bytes=max_bytes, timeout_seconds=timeout,
        )
        store = self.ReceiptStore()
        receipt = capture_content(
            content_id="content:monolith", url=URL,
            store=store, body_store=body_store,
            source_use_guard=guard, archive_adapter=adapter,
            fetcher=lambda url, **_: fetched(HTML, url=url),
        )
        return receipt, store, guard, private_root

    def test_private_success_receipt_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, digest = make_binary(tmp)
            root = Path(tmp) / "private"
            store = self.ReceiptStore()
            body_store = CaptureBodyStore(root)
            guard = OfflineGuard()
            adapter = MonolithArchiveAdapter(
                binary_path=binary, binary_sha256=digest,
                private_root=root, source_use_guard=guard,
            )
            def go():
                return capture_content(
                    content_id="content:monolith", url=URL, store=store,
                    body_store=body_store, source_use_guard=guard,
                    archive_adapter=adapter, fetcher=lambda url, **_: fetched(HTML, url=url),
                )
            first = go()
            self.assertEqual(first.archive_status, "SUCCEEDED")
            self.assertEqual([step for step, _ in store.archive_receipts], [
                "REQUESTED", "PENDING", "SUCCEEDED",
            ])
            self.assertEqual(store.archive_receipts[-1][1]["publication_state"], "HOLD")
            record = next(iter(store.captures.values()))["record"]
            outcome = adapter.archive(capture=record, body_path=body_store.path(record.body_ref))
            self.assertEqual(outcome.status, "SUCCEEDED")
            archive_ref = outcome.receipt["snapshot_ref"]
            self.assertNotIn("archive_url", outcome.receipt)
            self.assertEqual(outcome.receipt["source_capture_id"], record.id)
            self.assertEqual(outcome.receipt["snapshot_sha256"], hashlib.sha256(HTML).hexdigest())
            self.assertEqual((root / archive_ref).read_bytes(), HTML)
            self.assertEqual(stat.S_IMODE((root / archive_ref).stat().st_mode), 0o600)
            self.assertEqual(go().archive_status, "SUCCEEDED")
            self.assertEqual(len(store.archive_receipts), 3)
            self.assertEqual(len(list(root.rglob("*.html"))), 1)
            self.assertGreaterEqual(guard.calls.count("ARCHIVE"), 3)

    def test_real_pinned_monolith_on_synthetic_html_when_available(self):
        executable = os.environ.get("DP_MONOLITH_TEST_BINARY")
        if not executable:
            self.skipTest("real donor executable not configured")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "private"
            guard = OfflineGuard()
            store = self.ReceiptStore()
            result = capture_content(
                content_id="content:monolith", url=URL,
                store=store, body_store=CaptureBodyStore(root),
                source_use_guard=guard,
                archive_adapter=MonolithArchiveAdapter(
                    binary_path=Path(executable),
                    binary_sha256=MONOLITH_LINUX_X86_64_SHA256,
                    private_root=root, source_use_guard=guard,
                ),
                fetcher=lambda url, **_: fetched(HTML, url=url),
            )
            self.assertEqual(result.archive_status, "SUCCEEDED")
            artifact = store.archive_receipts[-1][1]
            self.assertEqual(artifact["snapshot_kind"], "PRIVATE_HTML")
            self.assertEqual(artifact["publication_state"], "HOLD")
            self.assertIn(b"Fictional parliamentary debate", (root / artifact["snapshot_ref"]).read_bytes())

    def test_failed_subprocess_invalid_html_oversize_and_timeout(self):
        for behavior, code in (("failed", "MONOLITH_PROCESS_FAILED"),
                               ("invalid", "MONOLITH_OUTPUT_INVALID"),
                               ("oversize", "MONOLITH_OUTPUT_TOO_LARGE"),
                               ("timeout", "MONOLITH_TIMEOUT")):
            with self.subTest(behavior=behavior), tempfile.TemporaryDirectory() as tmp:
                result, store, _, root = self.run_capture(tmp, behavior=behavior)
                self.assertEqual(result.archive_status, "FAILED")
                self.assertEqual([step for step, _ in store.archive_receipts], [
                    "REQUESTED", "PENDING", "FAILED",
                ])
                self.assertEqual(store.archive_receipts[-1][1]["error_category"], code)
                archive = next(iter(store.captures.values()))["record"]
                self.assertFalse(list(root.rglob("*.html")))
                # Existing pipeline retains independently successful capture / passage.
                self.assertEqual(result.parse_status, "SUCCEEDED")

    def test_missing_invalid_or_replaced_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, digest = make_binary(tmp)
            for candidate, expected_digest, error in (
                (Path(tmp) / "missing", digest, "MONOLITH_BINARY_INVALID"),
                (binary, "0" * 64, "MONOLITH_BINARY_INVALID"),
            ):
                with self.subTest(candidate=candidate, expected=expected_digest):
                    receipt, store, _, root = self.run_capture(
                        tmp, binary=candidate, digest=expected_digest,
                    )
                    self.assertEqual(receipt.archive_status, "FAILED")
                    self.assertEqual(store.archive_receipts[-1][1]["error_category"], error)
                    self.assertFalse(list(root.rglob("*.html")))

    def test_failure_can_retry_without_duplicate_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "private"
            body_store = CaptureBodyStore(root)
            guard = OfflineGuard()
            store = self.ReceiptStore()
            binary, digest = make_binary(tmp, behavior="failed")

            def go(sha):
                adapter = MonolithArchiveAdapter(
                    binary_path=binary, binary_sha256=sha,
                    private_root=root, source_use_guard=guard,
                )
                return capture_content(
                    content_id="content:monolith", url=URL,
                    store=store, body_store=body_store, source_use_guard=guard,
                    archive_adapter=adapter, fetcher=lambda url, **_: fetched(HTML, url=url),
                )
            self.assertEqual(go(digest).archive_status, "FAILED")
            _, repaired_sha = make_binary(tmp, behavior="ok")
            self.assertEqual(go(repaired_sha).archive_status, "SUCCEEDED")
            self.assertEqual(go(repaired_sha).archive_status, "SUCCEEDED")
            self.assertEqual(len(list(root.rglob("*.html"))), 1)
            self.assertEqual(len(store.archive_receipts), 6)

    def test_revocation_before_commit_leaves_no_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, digest = make_binary(tmp)
            root = Path(tmp) / "private"
            store = self.ReceiptStore()
            guard = OfflineGuard(revoke_on_archive_call=4)
            adapter = MonolithArchiveAdapter(
                binary_path=binary, binary_sha256=digest,
                private_root=root, source_use_guard=guard,
            )
            result = capture_content(
                content_id="content:monolith", url=URL,
                store=store, body_store=CaptureBodyStore(root),
                source_use_guard=guard, archive_adapter=adapter,
                fetcher=lambda url, **_: fetched(HTML, url=url),
            )
            self.assertEqual(result.archive_status, "FAILED")
            self.assertEqual(
                store.archive_receipts[-1][1]["error_category"], "SOURCE_USE_NOT_PERMITTED",
            )
            self.assertFalse(list(root.rglob("*.html")))

    def test_policy_denial_precedes_fetch_and_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, digest = make_binary(tmp)
            guard = OfflineGuard(permitted=False)
            adapter = MonolithArchiveAdapter(
                binary_path=binary, binary_sha256=digest,
                private_root=Path(tmp) / "private", source_use_guard=guard,
            )
            with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_NOT_PERMITTED"):
                capture_content(
                    content_id="content:monolith", url=URL,
                    store=FakeCaptureStore(), body_store=CaptureBodyStore(Path(tmp) / "private"),
                    archive_adapter=adapter, source_use_guard=guard,
                    fetcher=lambda *_args, **_kwargs: self.fail("fetch not permitted"),
                )

    def test_disallowed_url_fails_without_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, digest = make_binary(tmp)
            guard = OfflineGuard()
            adapter = MonolithArchiveAdapter(
                binary_path=binary, binary_sha256=digest,
                private_root=Path(tmp) / "private", source_use_guard=guard,
            )
            for url in ("http://example.test", "https://127.0.0.1/private",
                        "https://localhost/private", "https://2130706433/private"):
                with self.subTest(url=url), self.assertRaisesRegex(Exception, "CAPTURE_URL"):
                    capture_content(
                        content_id="content:monolith", url=url,
                        store=FakeCaptureStore(), body_store=CaptureBodyStore(Path(tmp) / "private"),
                        archive_adapter=adapter, source_use_guard=guard,
                        fetcher=lambda *_args, **_kwargs: self.fail("unexpected fetch"),
                    )


if __name__ == "__main__":
    unittest.main()
