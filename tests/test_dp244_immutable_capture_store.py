"""DP-244 immutable capture store: write-once, integrity and replay fixtures."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.immutable_capture_store_v1 import (  # noqa: E402
    CaptureRecord,
    CaptureStoreError,
    store_capture,
    verify_capture,
)

NOW = datetime(2026, 10, 23, 13, tzinfo=timezone.utc)
BODY = b"<akn:akomaNtoso>testo originale</akn:akomaNtoso>"


def store(root, body=BODY, **changes):
    options = dict(
        body=body,
        source_id="source:senato-akn",
        locator_id="locator:akn-01457617",
        media_type="application/xml",
        observed_at=NOW,
    )
    options.update(changes)
    return store_capture(root, **options)


class ImmutableCaptureStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "captures"

    def tearDown(self):
        self.directory.cleanup()

    def test_capture_is_content_addressed_and_written_once(self):
        record, written = store(self.root)
        self.assertTrue(written)
        self.assertEqual(record.content_sha256, record.capture_id.split(":")[-1])
        self.assertEqual(record.byte_length, len(BODY))
        self.assertEqual(len(record.receipt_sha256), 64)
        self.assertTrue(record.private_only)
        self.assertFalse(record.publication_authorized)
        self.assertIsNone(record.measured_cost_micro_eur)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), sorted([
            f"{record.content_sha256}.bin", f"{record.content_sha256}.receipt.json",
        ]))
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(
            (self.root / f"{record.content_sha256}.bin").stat().st_mode & 0o777,
            0o600,
        )

    def test_replay_is_idempotent_and_never_rewrites_bytes(self):
        first, written = store(self.root)
        second, written_again = store(self.root)
        self.assertTrue(written)
        self.assertFalse(written_again)
        self.assertEqual(first, second)
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_replay_returns_original_receipt_despite_new_observation_metadata(self):
        first, _ = store(self.root, measured_cost_micro_eur=12)
        replay, written = store(
            self.root,
            observed_at=datetime(2026, 10, 24, 13, tzinfo=timezone.utc),
            measured_cost_micro_eur=34,
        )
        self.assertFalse(written)
        self.assertEqual(replay, first)
        self.assertEqual(replay, verify_capture(self.root, first.capture_id))

    def test_replay_rejects_conflicting_source_provenance(self):
        first, _ = store(self.root)
        for changes in (
            {"source_id": "source:other"},
            {"locator_id": "locator:other"},
            {"media_type": "text/plain"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(CaptureStoreError) as raised:
                    store(self.root, **changes)
                self.assertEqual(str(raised.exception), "CAPTURE_PROVENANCE_MISMATCH")
        self.assertEqual(verify_capture(self.root, first.capture_id), first)

    def test_replay_rejects_a_corrupted_receipt(self):
        first, _ = store(self.root)
        path = self.root / f"{first.content_sha256}.receipt.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["byte_length"] += 1
        corrupted = json.dumps(payload)
        path.write_text(corrupted, encoding="utf-8")
        with self.assertRaises(CaptureStoreError) as raised:
            store(self.root)
        self.assertEqual(str(raised.exception), "CAPTURE_RECEIPT_MISMATCH")
        self.assertEqual(path.read_text(encoding="utf-8"), corrupted)

    def test_replay_does_not_invent_a_missing_receipt(self):
        first, _ = store(self.root)
        path = self.root / f"{first.content_sha256}.receipt.json"
        path.unlink()
        with self.assertRaises(CaptureStoreError) as raised:
            store(self.root)
        self.assertEqual(str(raised.exception), "CAPTURE_NOT_FOUND")
        self.assertFalse(path.exists())

    def test_distinct_versions_produce_distinct_immutable_captures(self):
        old, _ = store(self.root, body=b"versione 2025")
        new, _ = store(self.root, body=b"versione 2026")
        self.assertNotEqual(old.content_sha256, new.content_sha256)
        self.assertEqual(verify_capture(self.root, old.capture_id).content_sha256,
                         old.content_sha256)
        self.assertEqual(verify_capture(self.root, new.capture_id).content_sha256,
                         new.content_sha256)

    def test_tampered_body_is_reported_and_never_repaired(self):
        record, _ = store(self.root)
        target = self.root / f"{record.content_sha256}.bin"
        target.write_bytes(b"contenuto sostituito")
        with self.assertRaises(CaptureStoreError) as raised:
            verify_capture(self.root, record.capture_id)
        self.assertEqual(str(raised.exception), "CAPTURE_INTEGRITY_FAILED")
        self.assertEqual(target.read_bytes(), b"contenuto sostituito")

    def test_tampered_receipt_is_reported(self):
        record, _ = store(self.root)
        path = self.root / f"{record.content_sha256}.receipt.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["byte_length"] = payload["byte_length"] + 1
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(CaptureStoreError) as raised:
            verify_capture(self.root, record.capture_id)
        self.assertEqual(str(raised.exception), "CAPTURE_RECEIPT_MISMATCH")

    def test_expected_digest_and_inputs_are_enforced(self):
        record, _ = store(self.root)
        cases = (
            (dict(expected_sha256="a" * 64), "CAPTURE_HASH_MISMATCH"),
            (dict(body=b""), "CAPTURE_BODY_INVALID"),
            (dict(media_type="not a media type"), "CAPTURE_MEDIA_TYPE_INVALID"),
            (dict(observed_at=datetime(2026, 10, 23, 13)), "CAPTURE_CLOCK_INVALID"),
            (dict(source_id=""), "CAPTURE_SOURCE_ID_INVALID"),
            (dict(measured_cost_micro_eur=-1), "CAPTURE_COST_INVALID"),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(CaptureStoreError) as raised:
                    store(self.root, **changes)
                self.assertEqual(str(raised.exception), expected)
        self.assertEqual(store(self.root, expected_sha256=record.content_sha256)[0],
                         record)

    def test_unknown_capture_and_bad_id_are_refused(self):
        with self.assertRaises(CaptureStoreError) as raised:
            verify_capture(self.root, "capture:sha256:" + "b" * 64)
        self.assertEqual(str(raised.exception), "CAPTURE_NOT_FOUND")
        with self.assertRaises(CaptureStoreError) as raised:
            verify_capture(self.root, "capture:other:" + "b" * 64)
        self.assertEqual(str(raised.exception), "CAPTURE_ID_INVALID")

    def test_record_has_no_publication_switches(self):
        fields = CaptureRecord.__dataclass_fields__
        self.assertEqual(fields["private_only"].default, True)
        self.assertEqual(fields["publication_authorized"].default, False)
        self.assertNotIn("public_url", fields)


if __name__ == "__main__":
    unittest.main()
