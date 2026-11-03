"""Concurrent private captures cannot overwrite an already-attested body."""

from __future__ import annotations

import hashlib
import stat
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, CapturePipelineError


class CaptureBodyAtomicityTests(unittest.TestCase):
    def _parallel_writes(self, first: bytes, second: bytes):
        with tempfile.TemporaryDirectory() as tmp:
            store = CaptureBodyStore(Path(tmp))
            barrier = threading.Barrier(2)
            original_mkstemp = tempfile.mkstemp

            def synchronize_after_missing_target(*args, **kwargs):
                temporary = original_mkstemp(*args, **kwargs)
                barrier.wait(timeout=5)
                return temporary

            def attempt(body: bytes):
                try:
                    return store.write(
                        capture_id="same-capture-id",
                        body=body,
                        content_sha256=hashlib.sha256(body).hexdigest(),
                    )
                except CapturePipelineError as exc:
                    return exc.code

            with patch(
                "dichiarazioni_pubbliche.capture_pipeline.tempfile.mkstemp",
                side_effect=synchronize_after_missing_target,
            ):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(attempt, (first, second)))

            body_ref = store._relative_ref("same-capture-id")
            target = store.path(body_ref)
            return outcomes, store.read(body_ref), stat.S_IMODE(target.stat().st_mode), list(Path(tmp).rglob(".capture-*"))

    def test_different_bytes_never_receive_two_success_receipts(self):
        first = b"first independent capture"
        second = b"second independent capture"
        outcomes, saved, mode, leftovers = self._parallel_writes(first, second)
        receipts = [value for value in outcomes if not isinstance(value, str)]
        errors = [value for value in outcomes if isinstance(value, str)]

        self.assertEqual([receipt.state for receipt in receipts], ["WRITTEN"])
        self.assertEqual(errors, ["BODY_STORE_EXISTING_HASH_MISMATCH"])
        self.assertEqual(saved, first if receipts[0].content_sha256 == hashlib.sha256(first).hexdigest() else second)
        self.assertEqual(mode, 0o600)
        self.assertEqual(leftovers, [])

    def test_identical_bytes_are_idempotent_under_concurrency(self):
        body = b"identical captured source"
        outcomes, saved, mode, leftovers = self._parallel_writes(body, body)

        self.assertFalse(any(isinstance(value, str) for value in outcomes))
        self.assertEqual(sorted(receipt.state for receipt in outcomes), ["EXISTING", "WRITTEN"])
        self.assertEqual({receipt.content_sha256 for receipt in outcomes}, {hashlib.sha256(body).hexdigest()})
        self.assertEqual(saved, body)
        self.assertEqual(mode, 0o600)
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
