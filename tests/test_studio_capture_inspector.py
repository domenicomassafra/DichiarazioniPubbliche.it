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
        self.rows = {A: row(A), B: row(
            B, status="PURGED_BODY", archive_status="SUCCEEDED",
            archive_provider="archive:fixture", archive_requested_at="2026-10-08T09:00:00Z",
            archive_completed_at="2026-10-08T11:00:00Z",
            archive_receipt={"receipt_id": "fixture:archive"},
            body_ref=None, body_purged_at="2026-10-08T12:00:00Z",
            purge_reason="retention_expired", purge_receipt={"receipt_id": "fixture:purge"},
        )} if rows is None else rows
        self.error = error
        self.calls = []

    def find_capture(self, content_id, content_sha256):
        self.calls.append((content_id, content_sha256))
        if self.error is not None:
            raise self.error
        return self.rows.get(content_sha256)


class StudioCaptureInspectorTests(unittest.TestCase):
    def test_archive_completion_cannot_precede_request_in_persisted_lifecycle(self):
        # The actual archive request/completion SQL stamps both transitions
        # with now(). A coherent receipt cannot complete before it was asked.
        baseline = FakeCaptureStore().rows[B]
        for outcome in ("SUCCEEDED", "FAILED"):
            for completed_at in (
                "2026-10-08T08:59:59Z",
                "2026-10-08T10:00:00+02:00",  # 08:00Z, not 10:00Z
            ):
                with self.subTest(outcome=outcome, completed_at=completed_at):
                    later = {**baseline, "archive_status": outcome,
                             "archive_completed_at": completed_at}
                    with self.assertRaisesRegex(ValueError, "STUDIO_CAPTURE_ARCHIVE_PROOF_INVALID"):
                        inspect_capture_versions(
                            FakeCaptureStore(rows={A: row(A), B: later}),
                            content_id="content:one", earlier_hash=A, later_hash=B,
                        )
        # Timestamps with different offsets can represent the same instant.
        equal_instant = {**baseline, "archive_completed_at": "2026-10-08T10:00:00+01:00"}
        result = inspect_capture_versions(
            FakeCaptureStore(rows={A: row(A), B: equal_instant}),
            content_id="content:one", earlier_hash=A, later_hash=B,
        )
        self.assertEqual(result["later"]["archive_state"], "SUCCEEDED")
        self.assertNotIn("archive_completed_at", json.dumps(result))

    def test_archive_success_and_purged_body_require_persisted_completion_receipts(self):
        baseline = FakeCaptureStore().rows[B]
        tampered = (
            {"archive_completed_at": None},
            {"archive_receipt": {}},
            {"archive_provider": None},
            {"archive_requested_at": None},
            {"body_ref": "private/body/stale"},
            {"body_purged_at": None},
            {"purge_reason": None},
            {"purge_receipt": {}},
            {"status": "CAPTURED"},
        )
        for changes in tampered:
            with self.subTest(changes=changes):
                store = FakeCaptureStore(rows={A: row(A), B: {**baseline, **changes}})
                with self.assertRaisesRegex(ValueError, "STUDIO_CAPTURE_(ARCHIVE|PURGE)_PROOF_INVALID"):
                    inspect_capture_versions(store, content_id="content:one", earlier_hash=A, later_hash=B)

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
