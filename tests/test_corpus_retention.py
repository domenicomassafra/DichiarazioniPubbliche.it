import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord  # noqa: E402
from dichiarazioni_pubbliche.corpus_retention import (  # noqa: E402
    COMPLETE_CAPTURE_ARCHIVE_SQL_V1,
    FAIL_CAPTURE_BODY_PURGE_SQL_V1,
    FINALIZE_CAPTURE_BODY_PURGE_SQL_V1,
    MARK_CAPTURE_ARCHIVE_PENDING_SQL_V1,
    RELEASE_CAPTURE_HOLD_SQL_V1,
    REQUEST_CAPTURE_ARCHIVE_SQL_V1,
    SET_CAPTURE_HOLD_SQL_V1,
    START_CAPTURE_BODY_PURGE_SQL_V1,
    archive_transition_decision,
    body_purge_decision,
    capture_downstream_use_decision,
    lifecycle_event_id,
    purge_local_capture_body,
)


def capture(**overrides):
    body = b"capture-body"
    values = {
        "id": "capture:1",
        "content_id": "content:1",
        "observed_at": "2026-09-29T09:00:00+02:00",
        "final_url": "https://example.org/a",
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "body_ref": "captures/body.bin",
        "retrieval_method": "HTTP",
        "retrieval_version": "safe-fetch-v1",
        "retention_class": "EPHEMERAL",
    }
    values.update(overrides)
    return ContentCaptureRecord(**values)


class CorpusRetentionTests(unittest.TestCase):
    def test_only_ephemeral_without_hold_is_purge_eligible(self):
        self.assertTrue(body_purge_decision(capture()).allowed)
        self.assertEqual(
            body_purge_decision(capture(retention_class="POLICY_PENDING")).code,
            "RETENTION_NOT_PURGEABLE:POLICY_PENDING",
        )
        self.assertEqual(
            body_purge_decision(capture(hold_status="LEGAL_HOLD")).code,
            "HOLD_ACTIVE:LEGAL_HOLD",
        )
        self.assertEqual(
            body_purge_decision(capture(status="QUARANTINED")).code,
            "CAPTURE_STATUS_BLOCKED:QUARANTINED",
        )

    def test_purged_capture_can_supply_metadata_but_not_body(self):
        purged = capture(
            body_ref=None,
            status="PURGED_BODY",
            body_purged_at="2026-09-29T10:00:00+02:00",
            purge_reason="EPHEMERAL_MINIMIZATION",
            purge_receipt={"deleted": True},
        )
        self.assertTrue(capture_downstream_use_decision(purged, requires_body=False).allowed)
        body_use = capture_downstream_use_decision(purged, requires_body=True)
        self.assertFalse(body_use.allowed)
        self.assertEqual(body_use.code, "BODY_PURGED")

    def test_hold_blocks_private_downstream_use(self):
        decision = capture_downstream_use_decision(
            capture(hold_status="COPYRIGHT_HOLD"), requires_body=False
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "HOLD_ACTIVE:COPYRIGHT_HOLD")

    def test_archive_failure_requires_receipt_and_never_becomes_success(self):
        self.assertTrue(
            archive_transition_decision(
                "REQUESTED", "FAILED", provider="perma", receipt={"error": "timeout"}
            ).allowed
        )
        missing = archive_transition_decision(
            "REQUESTED", "FAILED", provider="perma", receipt={}
        )
        self.assertFalse(missing.allowed)
        self.assertEqual(missing.code, "ARCHIVE_COMPLETION_RECEIPT_REQUIRED")
        invalid = archive_transition_decision(
            "FAILED", "SUCCEEDED", provider="perma", receipt={"url": "x"}
        )
        self.assertFalse(invalid.allowed)
        self.assertIn("ARCHIVE_TRANSITION_INVALID", invalid.code)

    def test_local_body_purge_is_dry_run_by_default_and_hash_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "captures" / "body.bin"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"capture-body")
            rec = capture()
            dry = purge_local_capture_body(rec, storage_root=root)
            self.assertTrue(dry.eligible)
            self.assertFalse(dry.deleted)
            self.assertEqual(dry.code, "DRY_RUN_ELIGIBLE")
            self.assertTrue(target.exists())
            actual = purge_local_capture_body(rec, storage_root=root, dry_run=False)
            self.assertTrue(actual.deleted)
            self.assertEqual(actual.bytes_observed, len(b"capture-body"))
            self.assertFalse(target.exists())

    def test_local_body_purge_refuses_hash_mismatch_path_escape_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "captures").mkdir()
            bad = root / "captures" / "body.bin"
            bad.write_bytes(b"wrong")
            self.assertEqual(
                purge_local_capture_body(capture(), storage_root=root).code,
                "BODY_HASH_MISMATCH",
            )
            escaped = capture(body_ref="../outside.bin")
            self.assertEqual(
                purge_local_capture_body(escaped, storage_root=root).code,
                "BODY_REF_NOT_LOCAL_RELATIVE",
            )
            outside = root / "outside.bin"
            outside.write_bytes(b"capture-body")
            bad.unlink()
            bad.symlink_to(outside)
            self.assertEqual(
                purge_local_capture_body(capture(), storage_root=root).code,
                "BODY_REF_SYMLINK_REFUSED",
            )

    def test_lifecycle_event_id_is_deterministic(self):
        a = lifecycle_event_id("capture:1", "BODY_PURGED", "op:1")
        self.assertEqual(a, lifecycle_event_id("capture:1", "BODY_PURGED", "op:1"))
        self.assertNotEqual(a, lifecycle_event_id("capture:1", "BODY_PURGED", "op:2"))

    def test_sql_transitions_write_receipt_before_current_state(self):
        self.assertIn("BODY_PURGE_REQUESTED", START_CAPTURE_BODY_PURGE_SQL_V1)
        self.assertIn("retention_class='EPHEMERAL'", START_CAPTURE_BODY_PURGE_SQL_V1)
        self.assertIn("hold_status='NONE'", START_CAPTURE_BODY_PURGE_SQL_V1)
        self.assertIn("BODY_PURGED", FINALIZE_CAPTURE_BODY_PURGE_SQL_V1)
        self.assertIn("purge_receipt", FINALIZE_CAPTURE_BODY_PURGE_SQL_V1)
        self.assertIn("BODY_PURGE_FAILED", FAIL_CAPTURE_BODY_PURGE_SQL_V1)
        self.assertIn("status='QUARANTINED'", FAIL_CAPTURE_BODY_PURGE_SQL_V1)
        self.assertIn("ARCHIVE_REQUESTED", REQUEST_CAPTURE_ARCHIVE_SQL_V1)
        self.assertIn("ARCHIVE_PENDING", MARK_CAPTURE_ARCHIVE_PENDING_SQL_V1)
        self.assertIn("archive_status='REQUESTED'", MARK_CAPTURE_ARCHIVE_PENDING_SQL_V1)
        self.assertIn("ARCHIVE_SUCCEEDED", COMPLETE_CAPTURE_ARCHIVE_SQL_V1)
        self.assertIn("ARCHIVE_FAILED", COMPLETE_CAPTURE_ARCHIVE_SQL_V1)
        self.assertIn("HOLD_SET", SET_CAPTURE_HOLD_SQL_V1)
        self.assertIn("HOLD_RELEASED", RELEASE_CAPTURE_HOLD_SQL_V1)


class ContentCaptureLifecycleValidationTests(unittest.TestCase):
    def test_capture_metadata_and_receipts_reject_explicit_secret_keys(self):
        with self.assertRaisesRegex(ValueError, "SECRET_KEY_FORBIDDEN"):
            capture(metadata={"Authorization": "Bearer do-not-store"})
        with self.assertRaisesRegex(ValueError, "SECRET_KEY_FORBIDDEN"):
            capture(archive_receipt={"nested": {"api_key": "do-not-store"}})
        ok = capture(metadata={"metrics": {"input_tokens": 42, "request_id": "r1"}})
        self.assertEqual(ok.metadata["metrics"]["input_tokens"], 42)

    def test_archive_success_requires_provider_dates_and_receipt(self):
        with self.assertRaisesRegex(ValueError, "ARCHIVE_COMPLETION_RECEIPT_INCOMPLETE"):
            capture(
                archive_status="SUCCEEDED",
                archive_provider="perma",
                archive_requested_at="2026-09-29T09:00:00+02:00",
            )
        ok = capture(
            archive_status="FAILED",
            archive_provider="perma",
            archive_requested_at="2026-09-29T09:00:00+02:00",
            archive_completed_at="2026-09-29T09:01:00+02:00",
            archive_receipt={"error": "timeout"},
        )
        self.assertEqual(ok.archive_status, "FAILED")

    def test_purged_body_requires_receipt_and_cleared_body_ref(self):
        with self.assertRaisesRegex(ValueError, "PURGED_BODY_RECEIPT_INCOMPLETE"):
            capture(status="PURGED_BODY")
        ok = capture(
            body_ref=None,
            status="PURGED_BODY",
            body_purged_at="2026-09-29T10:00:00+02:00",
            purge_reason="EPHEMERAL_MINIMIZATION",
            purge_receipt={"deleted": True},
        )
        self.assertIsNone(ok.body_ref)


if __name__ == "__main__":
    unittest.main()
