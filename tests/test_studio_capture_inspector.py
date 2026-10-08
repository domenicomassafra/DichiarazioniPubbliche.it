import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_capture_inspector import inspect_capture_versions  # noqa: E402

A = "a" * 64
B = "b" * 64


def row(digest, **override):
    return {
        "id": f"capture:{digest[:6]}", "content_id": "content:one",
        "content_sha256": digest, "status": "CAPTURED",
        "hold_status": "NONE", "archive_status": "NOT_REQUESTED",
        "body_ref": f"private/body/{digest}",
        "body_purged_at": None,
        "metadata": {"private_transcript": "must never leak", "api_key": "secret"},
        "archive_receipt": {"private_archive_url": "not public"},
        "final_url": "https://private.example/fetch-with-auth",
        **override,
    }


class FakeCaptureStore:
    def __init__(self, rows=None, error=None):
        self.rows = {A: row(A), B: row(B, archive_status="SUCCEEDED", body_purged_at="2026-10-08T12:00:00Z")} if rows is None else rows
        self.error = error
        self.calls = []

    def find_capture(self, content_id, content_sha256):
        self.calls.append((content_id, content_sha256))
        if self.error is not None:
            raise self.error
        return self.rows.get(content_sha256)


class StudioCaptureInspectorTests(unittest.TestCase):
    def test_selects_only_source_version_metadata_and_detects_change(self):
        store = FakeCaptureStore()
        result = inspect_capture_versions(store, content_id="content:one", earlier_hash=A, later_hash=B)
        self.assertEqual(store.calls, [("content:one", A), ("content:one", B)])
        self.assertTrue(result["changes"]["body_hash_changed"])
        self.assertTrue(result["changes"]["archive_changed"])
        self.assertTrue(result["changes"]["body_storage_changed"])
        self.assertEqual(result["earlier"]["body_state"], "STORED_UNVERIFIED")
        self.assertEqual(result["later"]["body_state"], "PURGED")
        self.assertFalse(result["publication_authority"])
        encoded = json.dumps(result)
        for forbidden in ("private_transcript", "must never leak", "api_key", "secret", "private_archive_url", "private.example"):
            self.assertNotIn(forbidden, encoded)

    def test_missing_stale_or_tampered_versions_fail_closed(self):
        for kwargs in (
            {"earlier_hash": "x", "later_hash": B},
            {"earlier_hash": A, "later_hash": A},
            {"earlier_hash": A, "later_hash": B, "content_id": "content:unsafe\n"},
        ):
            with self.subTest(kwargs), self.assertRaises(ValueError):
                inspect_capture_versions(
                    FakeCaptureStore(), **({
                        "content_id": "content:one", "earlier_hash": A, "later_hash": B,
                    } | kwargs),
                )
        with self.assertRaisesRegex(RuntimeError, "STUDIO_CAPTURE_VERSION_MISSING"):
            inspect_capture_versions(FakeCaptureStore(rows={A: row(A)}), content_id="content:one", earlier_hash=A, later_hash=B)
        with self.assertRaisesRegex(ValueError, "STUDIO_CAPTURE_BINDING_MISMATCH"):
            inspect_capture_versions(FakeCaptureStore(rows={A: row(A, content_id="content:other"), B: row(B)}), content_id="content:one", earlier_hash=A, later_hash=B)
        with self.assertRaisesRegex(RuntimeError, "STUDIO_CAPTURE_IDENTITY_COLLISION"):
            inspect_capture_versions(FakeCaptureStore(rows={A: row(A, id="capture:same"), B: row(B, id="capture:same")}), content_id="content:one", earlier_hash=A, later_hash=B)

    def test_store_failure_is_bounded_without_database_or_secret_error(self):
        with self.assertRaisesRegex(RuntimeError, "^STUDIO_CAPTURE_STORE_UNAVAILABLE$") as ctx:
            inspect_capture_versions(FakeCaptureStore(error=OSError("PASSWORD=do-not-log")), content_id="content:one", earlier_hash=A, later_hash=B)
        self.assertIsNone(ctx.exception.__cause__)
        self.assertNotIn("do-not-log", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
