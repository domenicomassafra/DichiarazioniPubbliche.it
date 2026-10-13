"""DP-236 source-family per-artifact/per-use rights seam, offline acceptance."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, capture_content  # noqa: E402
from dichiarazioni_pubbliche.private_capture_rights import (  # noqa: E402
    SourceFamilyUseGuard, SourceUseBlocked, evaluate_source_use,
)
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PRIVATE_RIGHTS_RECORD_VERSION, PrivateRightsRecord, RightsSubject,
    rights_subject_fingerprint,
)
from test_capture_pipeline import FakeCaptureStore, fetched  # noqa: E402


NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
URL = "https://example.test/approved-article"
BODY = b"<p>Original documented words.</p>"
SHA = hashlib.sha256(BODY).hexdigest()
SUBJECT = RightsSubject(
    source_family="TEST_OFFICIAL_TEXT", locator_kind="URL",
    locator_value=URL, content_id="content:approved-article",
)
CAPTURE_USES = ("FETCH", "STORE_BODY", "PARSE_TEXT")


def reviewed(**overrides) -> PrivateRightsRecord:
    record = PrivateRightsRecord(
        id="private-rights:approved",
        subject_fingerprint=rights_subject_fingerprint(SUBJECT),
        source_family=SUBJECT.source_family,
        locator_kind="URL",
        locator_value=URL,
        content_id=SUBJECT.content_id,
        evidence_id=None,
        transcript_segment_id=None,
        canonical_segment_id=None,
        passage_id=None,
        rights_status="CLEARED",
        rights_receipt_ref="private-reviewed-receipt:1",
        permitted_uses=CAPTURE_USES,
        attribution_requirements=(),
        reviewed_at="2026-10-09T12:00:00+00:00",
        expires_at="2026-10-12T12:00:00+00:00",
        reviewer_ref="operator:qualified",
        policy_version="private-use-policy-v1",
        record_visibility="PRIVATE",
        supersedes_id=None,
        version_state="CURRENT",
        record_version=PRIVATE_RIGHTS_RECORD_VERSION,
    )
    return replace(record, **overrides)


def guard(read_current, **kwargs) -> SourceFamilyUseGuard:
    return SourceFamilyUseGuard(
        read_current=read_current, subject=SUBJECT,
        rights_record_id="private-rights:approved",
        policy_version="private-use-policy-v1",
        clock=lambda: NOW, **kwargs,
    )


def evaluate(record, *, use="FETCH"):
    return evaluate_source_use(
        record, subject=SUBJECT, rights_record_id="private-rights:approved",
        policy_version="private-use-policy-v1", use=use, now=NOW,
    )


class SourceUseContractTests(unittest.TestCase):
    def test_malformed_receipt_or_reviewer_cannot_authorize_capture(self):
        # Fake/current-rights readers can bypass the registry's write-time
        # normalization. Presence alone is not a reviewed rights receipt.
        for changed in (
            {"rights_receipt_ref": " "},
            {"rights_receipt_ref": "receipt with spaces"},
            {"rights_receipt_ref": 17},
            {"reviewer_ref": "\t"},
            {"reviewer_ref": 17},
        ):
            with self.subTest(changed=changed):
                record = reviewed(**changed)
                decision = evaluate(record)
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason_code, "SOURCE_USE_REVIEW_INVALID")
                with self.assertRaisesRegex(SourceUseBlocked, "^SOURCE_USE_REVIEW_INVALID$"):
                    guard(lambda _: record).require("FETCH")

    def test_malformed_receipt_ref_blocks_real_capture_before_fetch(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            with self.assertRaisesRegex(SourceUseBlocked, "^SOURCE_USE_REVIEW_INVALID$"):
                capture_content(
                    content_id=SUBJECT.content_id, url=URL, store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    source_use_guard=guard(
                        lambda _: reviewed(rights_receipt_ref=" ", reviewer_ref="operator:qualified"),
                    ),
                    fetcher=lambda *a, **k: self.fail("invalid receipt must block before fetch"),
                )
            self.assertFalse(store.captures)
            self.assertFalse(store.passages)
            self.assertFalse(list(Path(temp).rglob("*.body")))

    def test_malformed_use_list_cannot_authorize_a_substring(self):
        # Python's 'FETCH' in 'NOT_FETCH' must never act as a use grant.
        malformed = reviewed(permitted_uses="NOT_FETCH")
        decision = evaluate(malformed, use="FETCH")
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason_code, "SOURCE_USE_RECORD_CONTRACT_INVALID")
        with self.assertRaisesRegex(SourceUseBlocked, "^SOURCE_USE_RECORD_CONTRACT_INVALID$"):
            guard(lambda _: malformed).require("FETCH")

    def test_metadata_only_cannot_be_promoted_to_capture_ocr_asr_or_public(self):
        record = reviewed(permitted_uses=("DISCOVER_METADATA",))
        self.assertTrue(evaluate(record, use="DISCOVER_METADATA").permitted)
        for use in (
            "FETCH", "STORE_BODY", "PARSE_TEXT", "PARSE_OCR",
            "TRANSLATE", "ASR_MEDIA", "ARCHIVE", "EXCERPT_PUBLIC",
        ):
            with self.subTest(use=use):
                decision = evaluate(record, use=use)
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.status, "DENIED")
                self.assertNotIn(URL, str(decision))
        self.assertEqual(evaluate(record, use="EXCERPT_PUBLIC").action_code, "DP305_EXCERPT_REVIEW")

    def test_reviewed_exact_use_has_fingerprint_and_does_not_leak_receipt(self):
        first = evaluate(reviewed())
        second = evaluate(reviewed())
        self.assertEqual(first, second)
        self.assertTrue(first.permitted)
        self.assertEqual(len(first.decision_fingerprint or ""), 64)
        self.assertNotIn("private-reviewed-receipt", str(first))
        self.assertNotEqual(first.decision_fingerprint, evaluate(reviewed(), use="STORE_BODY").decision_fingerprint)
        self.assertNotEqual(
            first.decision_fingerprint,
            evaluate(reviewed(permitted_uses=CAPTURE_USES + ("ARCHIVE",))).decision_fingerprint,
        )

    def test_current_revision_policy_and_exact_artifact_are_required(self):
        for changed, reason in (
            ({"source_family": "OTHER_FAMILY"}, "SOURCE_USE_ARTIFACT_MISMATCH"),
            ({"locator_value": "https://example.test/unrelated"}, "SOURCE_USE_ARTIFACT_MISMATCH"),
            ({"content_id": "content:unrelated"}, "SOURCE_USE_ARTIFACT_MISMATCH"),
            ({"subject_fingerprint": "b" * 64}, "SOURCE_USE_ARTIFACT_MISMATCH"),
            ({"version_state": "HISTORICAL"}, "SOURCE_USE_RECORD_NOT_CURRENT"),
            ({"record_visibility": "PUBLIC"}, "SOURCE_USE_RECORD_CONTRACT_INVALID"),
            ({"policy_version": "outdated-policy"}, "SOURCE_USE_POLICY_MISMATCH"),
            ({"rights_status": "REVOKED"}, "SOURCE_USE_REVOKED"),
            ({"rights_status": "UNKNOWN"}, "SOURCE_USE_NOT_CLEARED"),
            ({"reviewed_at": None}, "SOURCE_USE_REVIEW_INVALID"),
            ({"reviewer_ref": None}, "SOURCE_USE_REVIEW_INVALID"),
            ({"rights_receipt_ref": None}, "SOURCE_USE_REVIEW_INVALID"),
            ({"reviewed_at": "2026-10-11T00:00:00+00:00"}, "SOURCE_USE_REVIEW_INVALID"),
            ({"expires_at": "2026-10-10T12:00:00+00:00"}, "SOURCE_USE_EXPIRED"),
            ({"expires_at": "2026-10-09T00:00:00"}, "SOURCE_USE_REVIEW_INVALID"),
        ):
            with self.subTest(changed=changed):
                self.assertEqual(evaluate(reviewed(**changed)).reason_code, reason)
        self.assertEqual(evaluate(None).status, "UNRESOLVED")

    def test_failing_rights_read_is_safe_and_live_revocation_is_rechecked(self):
        states = [reviewed(), reviewed(rights_status="REVOKED")]
        current = guard(lambda _: states.pop(0))
        current.require("FETCH")
        with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_REVOKED"):
            current.require("STORE_BODY")
        def unavailable(_):
            raise RuntimeError("legal receipt and tokens should never appear")
        with self.assertRaisesRegex(SourceUseBlocked, "^SOURCE_USE_READ_UNAVAILABLE$"):
            guard(unavailable).require("FETCH")

    def test_optional_byte_and_media_pins_are_narrowing_only(self):
        current = guard(lambda _: reviewed(), expected_sha256=SHA, expected_media_type="text/html")
        current.require("FETCH")
        current.require("STORE_BODY", content_sha256=SHA, media_type="text/html; charset=utf-8")
        with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_CAPTURE_HASH_MISMATCH"):
            current.require("STORE_BODY", content_sha256="b" * 64, media_type="text/html")
        with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_MEDIA_TYPE_MISMATCH"):
            current.require("PARSE_TEXT", content_sha256=SHA, media_type="video/mp4")
        with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_CAPTURE_TARGET_MISMATCH"):
            current.bind_capture(content_id=SUBJECT.content_id, url="https://example.test/wrong")
        with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_HASH_PIN_INVALID"):
            guard(lambda _: reviewed(), expected_sha256="not-a-sha")


class SourceUseCapturePipelineTests(unittest.TestCase):
    def test_open_ended_clearance_cannot_authorize_a_fetch(self):
        # A reviewed use without an expiry would otherwise remain active forever,
        # even after its original source terms or artifact change.
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            current = guard(lambda _: reviewed(expires_at=None))
            with self.assertRaisesRegex(SourceUseBlocked, "^SOURCE_USE_EXPIRY_REQUIRED$"):
                capture_content(
                    content_id=SUBJECT.content_id, url=URL, store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    source_use_guard=current,
                    fetcher=lambda *a, **k: self.fail("unbounded clearance must block before fetch"),
                )
            self.assertFalse(store.captures)
            self.assertFalse(store.passages)
            self.assertFalse(list(Path(temp).rglob("*.body")))

    def test_denied_use_blocks_before_fetch_and_body_persistence(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            current = guard(lambda _: reviewed(permitted_uses=("DISCOVER_METADATA", "FETCH")))
            calls = []
            with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_NOT_PERMITTED"):
                capture_content(
                    content_id=SUBJECT.content_id, url=URL, store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    source_use_guard=current,
                    fetcher=lambda *a, **k: calls.append("FETCHED"),
                )
            self.assertEqual(calls, [])
            self.assertFalse(store.captures)
            self.assertFalse(list(Path(temp).rglob("*.body")))

    def test_approved_same_source_captures_and_replays_with_legacy_receipt_shape(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            current = guard(lambda _: reviewed(), expected_sha256=SHA, expected_media_type="text/html")
            first = capture_content(
                content_id=SUBJECT.content_id, url=URL, store=store,
                body_store=CaptureBodyStore(Path(temp)),
                source_use_guard=current, rights_status="CLEARED",
                fetcher=lambda url, **_: fetched(BODY, url=url),
            )
            second = capture_content(
                content_id=SUBJECT.content_id, url=URL, store=store,
                body_store=CaptureBodyStore(Path(temp)),
                source_use_guard=current, rights_status="CLEARED",
                fetcher=lambda url, **_: fetched(BODY, url=url),
            )
            self.assertEqual(first.primary_capture_id, second.primary_capture_id)
            self.assertEqual(first.content_sha256, SHA)
            self.assertEqual(first.capture_state, "INSERTED")
            self.assertEqual(second.capture_state, "EXISTING")
            self.assertEqual(len(store.captures), 1)
            self.assertEqual(len(store.passages), len(first.passage_ids))
            self.assertEqual(set(first.__dict__), set(second.__dict__))
            self.assertNotIn("decision_fingerprint", first.__dict__)
            record = store.captures[(SUBJECT.content_id, SHA)]["record"]
            self.assertEqual(len(record.metadata["source_use_fingerprint"]), 64)
            self.assertNotIn("private-reviewed-receipt", str(record.metadata))

    def test_changed_review_has_distinct_append_only_reobservation_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            approved = reviewed()
            revised = reviewed(
                id="private-rights:second-decision",
                supersedes_id=approved.id,
                reviewed_at="2026-10-10T10:00:00+00:00",
            )
            first_guard = guard(lambda _: approved)
            second_guard = SourceFamilyUseGuard(
                read_current=lambda _: revised,
                subject=SUBJECT,
                rights_record_id=revised.id,
                policy_version=revised.policy_version,
                clock=lambda: NOW,
            )
            args = dict(
                content_id=SUBJECT.content_id, url=URL, store=store,
                body_store=CaptureBodyStore(Path(temp)),
                rights_status="CLEARED",
                fetcher=lambda url, **_: fetched(BODY, url=url),
            )
            first = capture_content(
                **args, observed_at="2026-10-10T12:00:00Z",
                source_use_guard=first_guard,
            )
            second = capture_content(
                **args, observed_at="2026-10-10T13:00:00Z",
                source_use_guard=second_guard,
            )
            self.assertEqual(first.primary_capture_id, second.primary_capture_id)
            self.assertEqual(len(store.captures), 1)
            observed = sorted(
                event["receipt"]["source_use_fingerprint"]
                for event in store.events.values()
                if event["event_type"] == "CAPTURE_REOBSERVED"
            )
            self.assertEqual(len(observed), 1)
            initial = store.captures[(SUBJECT.content_id, SHA)]["record"].metadata["source_use_fingerprint"]
            self.assertNotEqual(observed[0], initial)
            self.assertNotIn("private-reviewed-receipt", str(store.events))

    def test_revocation_during_fetch_blocks_before_write_or_parse(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            active = [reviewed()]
            current = guard(lambda _: active[0])

            def fetch_then_revoke(url, **_):
                active[0] = reviewed(rights_status="REVOKED")
                return fetched(BODY, url=url)

            with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_REVOKED"):
                capture_content(
                    content_id=SUBJECT.content_id, url=URL, store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    source_use_guard=current, fetcher=fetch_then_revoke,
                )
            self.assertFalse(store.captures)
            self.assertFalse(store.passages)
            self.assertFalse(list(Path(temp).rglob("*.body")))

    def test_wrong_content_hash_after_fetch_blocks_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_CAPTURE_HASH_MISMATCH"):
                capture_content(
                    content_id=SUBJECT.content_id, url=URL, store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    source_use_guard=guard(lambda _: reviewed(), expected_sha256=SHA),
                    fetcher=lambda url, **_: fetched(b"Changed published bytes", url=url),
                )
            self.assertFalse(store.captures)
            self.assertFalse(list(Path(temp).rglob("*.body")))

    def test_final_redirect_to_other_artifact_requires_its_own_rights(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_FINAL_ARTIFACT_MISMATCH"):
                capture_content(
                    content_id=SUBJECT.content_id, url=URL, store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    source_use_guard=guard(lambda _: reviewed()),
                    fetcher=lambda url, **_: fetched(
                        BODY, url="https://example.test/other-approved-looking-url",
                    ),
                )
            self.assertFalse(store.captures)
            self.assertFalse(list(Path(temp).rglob("*.body")))

    def test_ocr_parser_needs_separate_permission_before_fetch(self):
        class OcrParser:
            parser_method = "OFFLINE_OCR"
            parser_version = "test"

            def parse(self, fetched):
                self.fail("OCR should not execute without grant")

        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_NOT_PERMITTED"):
                capture_content(
                    content_id=SUBJECT.content_id, url=URL, store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    source_use_guard=guard(lambda _: reviewed()),
                    parser=OcrParser(),
                    fetcher=lambda url, **_: self.fail("fetch should not execute"),
                )
            self.assertFalse(store.captures)

    def test_archive_permission_is_separate_and_blocks_before_fetch(self):
        class NoArchive:
            provider = "offline"
            def archive(self, **_):
                self.fail("archive should never be called")
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            fetch_count = []
            with self.assertRaisesRegex(SourceUseBlocked, "SOURCE_USE_NOT_PERMITTED"):
                capture_content(
                    content_id=SUBJECT.content_id, url=URL, store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    source_use_guard=guard(lambda _: reviewed()),
                    archive_adapter=NoArchive(),
                    fetcher=lambda url, **_: fetch_count.append(url),
                )
            self.assertFalse(fetch_count)
            self.assertFalse(store.captures)


if __name__ == "__main__":
    unittest.main()
