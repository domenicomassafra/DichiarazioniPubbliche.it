import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.studio_capture_inspector import (  # noqa: E402
    inspect_capture_versions, inspect_capture_passage_selectors,
)

A = "a" * 64
B = "b" * 64


def row(digest, **override):
    return {
        "id": f"capture:{digest[:6]}", "content_id": "content:one",
        "observed_at": ("2026-10-08T09:00:00Z" if digest == A
                        else "2026-10-08T10:00:00Z"),
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
        self.selectors = []
        self.selector_error = None

    def find_capture(self, content_id, content_sha256):
        self.calls.append((content_id, content_sha256))
        if self.error is not None:
            raise self.error
        return self.rows.get(content_sha256)

    def list_passage_selectors(self, capture_id, *, limit, after_id):
        if self.selector_error is not None:
            raise self.selector_error
        self.calls.append((capture_id, limit, after_id))
        return [p for p in self.selectors if p['id'] > (after_id or '')][:limit + 1]


def passage(pid, **override):
    return {
        'id': pid, 'content_id': 'content:one', 'capture_id': 'capture:aaaaaa',
        'canonical_segment_id': None, 'selector_type': 'TEXT_POSITION',
        'start_char': 5, 'end_char': 18, 'page_start': None, 'page_end': None,
        'text_sha256': 'f' * 64, 'private_text': 'SECRET SOURCE PASSAGE',
        'metadata': {'authorization': 'Bearer PRIVATE TOKEN'}, **override,
    }


class StudioCaptureInspectorTests(unittest.TestCase):
    def test_capture_comparison_refuses_reversed_or_unproven_observation_order(self):
        # The API labels caller-provided hashes "earlier" and "later"; do not
        # mistake that label for persisted chronology of the two captures.
        baseline = FakeCaptureStore()
        for changes in (
            {'observed_at': '2026-10-08T08:00:00Z'},
            {'observed_at': '2026-10-08T10:00:00+02:00'},
            {'observed_at': '2026-10-08T09:00:00Z'},
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(
                ValueError, 'STUDIO_CAPTURE_VERSION_ORDER_INVALID',
            ):
                inspect_capture_versions(
                    FakeCaptureStore(rows={A: baseline.rows[A],
                                           B: baseline.rows[B] | changes}),
                    content_id='content:one', earlier_hash=A, later_hash=B,
                )
        for bad in (None, 'not a timestamp', '2026-10-08T09:00:00'):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                ValueError, 'STUDIO_CAPTURE_OBSERVED_AT_INVALID',
            ):
                inspect_capture_versions(
                    FakeCaptureStore(rows={A: row(A, observed_at=bad), B: baseline.rows[B]}),
                    content_id='content:one', earlier_hash=A, later_hash=B,
                )
        valid = inspect_capture_versions(
            FakeCaptureStore(rows={
                A: row(A, observed_at='2026-10-08T11:00:00+02:00'),
                B: baseline.rows[B],
            }),
            content_id='content:one', earlier_hash=A, later_hash=B,
        )
        self.assertEqual(valid['earlier']['observed_at'], '2026-10-08T11:00:00+02:00')
        self.assertEqual(valid['later']['observed_at'], '2026-10-08T10:00:00Z')

    def test_persisted_passage_selectors_are_bounded_source_bound_and_private(self):
        store = FakeCaptureStore()
        store.selectors = [passage('passage:01'), passage('passage:02',
            selector_type='PAGE_RANGE', start_char=None, end_char=None,
            page_start=1, page_end=3)]
        first = inspect_capture_passage_selectors(
            store, content_id='content:one', capture_hash=A, limit=1)
        self.assertEqual(first['selectors'][0]['start_char'], 5)
        self.assertEqual(first['next_after_id'], 'passage:01')
        self.assertTrue(first['has_more'])
        self.assertFalse(first['rights_clearance'])
        self.assertFalse(first['publication_authority'])
        second = inspect_capture_passage_selectors(
            store, content_id='content:one', capture_hash=A, limit=1,
            after_id=first['next_after_id'])
        self.assertEqual(second['selectors'][0]['page_end'], 3)
        self.assertFalse(second['has_more'])
        self.assertEqual(store.calls, [
            ('content:one', A), ('capture:aaaaaa', 1, None),
            ('content:one', A), ('capture:aaaaaa', 1, 'passage:01'),
        ])
        for forbidden in ('SECRET SOURCE PASSAGE', 'PRIVATE TOKEN', 'metadata', 'private_text'):
            self.assertNotIn(forbidden, json.dumps((first, second)))

    def test_passage_inspection_rejects_cross_capture_unsupported_and_tampered_selectors(self):
        for updates in (
            {'capture_id': 'capture:other'}, {'content_id': 'content:other'},
            {'canonical_segment_id': 'segment:foreign'},
            {'selector_type': 'MEDIA_SEGMENT_REF'},
            {'start_char': -1}, {'end_char': 5}, {'end_char': True},
            {'text_sha256': 'bad'}, {'id': 'passage:secret\n'},
            {'page_start': 1}, {'selector_type': 'PAGE_RANGE'},
        ):
            with self.subTest(updates=updates):
                store = FakeCaptureStore()
                store.selectors = [passage('passage:01', **updates)]
                with self.assertRaises(ValueError):
                    inspect_capture_passage_selectors(
                        store, content_id='content:one', capture_hash=A)
        for limit in (0, -1, 21, True, '1'):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                inspect_capture_passage_selectors(
                    FakeCaptureStore(), content_id='content:one', capture_hash=A, limit=limit)
        store = FakeCaptureStore()
        store.selectors = [passage('passage:01'), passage('passage:01')]
        with self.assertRaises(ValueError):
            inspect_capture_passage_selectors(store, content_id='content:one', capture_hash=A)
        with self.assertRaises(ValueError):
            inspect_capture_passage_selectors(
                FakeCaptureStore(), content_id='content:one', capture_hash=A,
                after_id='unsafe\n')

    def test_passage_inspection_missing_capture_and_store_error_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'STUDIO_CAPTURE_VERSION_MISSING'):
            inspect_capture_passage_selectors(
                FakeCaptureStore(rows={}), content_id='content:one', capture_hash=A)
        store = FakeCaptureStore()
        store.selector_error = OSError('password=PRIVATE')
        with self.assertRaisesRegex(RuntimeError, '^STUDIO_CAPTURE_STORE_UNAVAILABLE$') as ctx:
            inspect_capture_passage_selectors(store, content_id='content:one', capture_hash=A)
        self.assertNotIn('PRIVATE', str(ctx.exception))
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
