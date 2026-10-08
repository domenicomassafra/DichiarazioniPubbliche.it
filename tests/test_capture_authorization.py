"""DP-214/215/304/305: operator capture rights binding, not legal approval."""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.capture_authorization import (  # noqa: E402
    PRIVATE_CAPTURE_USE,
    PrivateCaptureAuthorizationBlocked,
    private_capture_rights_guard,
    require_private_capture_rights,
    require_operator_capture_content,
)
from dichiarazioni_pubbliche.capture_pipeline import CaptureBodyStore, capture_content  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PRIVATE_RIGHTS_RECORD_VERSION,
    PrivateRightsRecord,
)
from test_capture_pipeline import FakeCaptureStore, fetched  # noqa: E402

CONTENT_ID = "content:rights-proof"
URL = "https://example.test/real-article"
SOURCE_FAMILY = "REPORTING"
NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def record(**changes) -> PrivateRightsRecord:
    base = PrivateRightsRecord(
        id="private-rights:reviewed",
        subject_fingerprint="a" * 64,
        source_family=SOURCE_FAMILY,
        locator_kind="URL",
        locator_value=URL,
        content_id=CONTENT_ID,
        evidence_id=None,
        transcript_segment_id=None,
        canonical_segment_id=None,
        passage_id=None,
        rights_status="CLEARED",
        rights_receipt_ref="operator-receipt:123",
        permitted_uses=(PRIVATE_CAPTURE_USE,),
        attribution_requirements=(),
        reviewed_at="2026-10-07T12:00:00+00:00",
        expires_at=None,
        reviewer_ref="reviewer:documented",
        policy_version="reviewed-private-processing-v1",
        record_visibility="PRIVATE",
        supersedes_id=None,
        version_state="CURRENT",
        record_version=PRIVATE_RIGHTS_RECORD_VERSION,
    )
    return replace(base, **changes)


def authorize(current: PrivateRightsRecord | None, *, now=NOW) -> None:
    require_private_capture_rights(
        current,
        rights_record_id="private-rights:reviewed",
        content_id=CONTENT_ID,
        canonical_url=URL,
        source_family=SOURCE_FAMILY,
        now=now,
    )


def content_state(**updates):
    state = {
        "id": CONTENT_ID,
        "canonical_url": URL,
        "rights_status": "CLEARED",
        "inactive_collection_count": 0,
        "forbidden_membership_count": 0,
    }
    state.update(updates)
    return state


class PrivateCaptureAuthorizationTests(unittest.TestCase):
    def test_recalled_rights_during_capture_lookup_blocks_before_body_write(self):
        with tempfile.TemporaryDirectory() as temp:
            current = [record()]

            class RecallingStore(FakeCaptureStore):
                def find_capture(self, content_id, content_sha256):
                    current[0] = record(rights_status="REVOKED")
                    return super().find_capture(content_id, content_sha256)

            store = RecallingStore()
            guard = private_capture_rights_guard(
                read_current=lambda subject: current[0],
                rights_record_id="private-rights:reviewed",
                content_id=CONTENT_ID,
                canonical_url=URL,
                source_family=SOURCE_FAMILY,
            )
            with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                capture_content(
                    content_id=CONTENT_ID,
                    url=URL,
                    store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    fetcher=lambda url, **kwargs: fetched(b"<p>Late rights revocation.</p>", url=url),
                    rights_guard=guard,
                )
            self.assertEqual(store.captures, {})
            self.assertEqual(store.passages, {})
            self.assertFalse(list(Path(temp).rglob("*.body")))

    def test_content_state_allows_only_cleared_active_authorized_memberships(self):
        require_operator_capture_content(
            content_state(), content_id=CONTENT_ID, canonical_url=URL
        )
        for state in (
            None,
            content_state(id="content:other"),
            content_state(canonical_url="https://example.test/other"),
            content_state(rights_status="UNKNOWN"),
            content_state(rights_status="REVOKED"),
            content_state(inactive_collection_count=1),
            content_state(forbidden_membership_count=1),
        ):
            with self.subTest(state=state):
                with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                    require_operator_capture_content(
                        state, content_id=CONTENT_ID, canonical_url=URL
                    )

    def test_garlasco_paused_collection_blocks_even_with_a_cleared_rights_record(self):
        checks = []

        def lookup(_):
            checks.append("content")
            return content_state(inactive_collection_count=1)

        guard = private_capture_rights_guard(
            read_current=lambda subject: record(),
            read_content_state=lookup,
            rights_record_id="private-rights:reviewed",
            content_id=CONTENT_ID,
            canonical_url=URL,
            source_family=SOURCE_FAMILY,
        )
        with self.assertRaisesRegex(PrivateCaptureAuthorizationBlocked, "COLLECTION_NOT_ACTIVE"):
            guard()
        self.assertEqual(checks, ["content"])

    def test_collection_revocation_during_fetch_blocks_before_persistence(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            state = [content_state()]
            guard = private_capture_rights_guard(
                read_current=lambda subject: record(),
                read_content_state=lambda content_id: state[0],
                rights_record_id="private-rights:reviewed",
                content_id=CONTENT_ID,
                canonical_url=URL,
                source_family=SOURCE_FAMILY,
            )

            def fetch_then_pause(url, *, max_response_bytes):
                state[0] = content_state(inactive_collection_count=1)
                return fetched(b"<p>No storage after collection pause.</p>", url=url)

            with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                capture_content(
                    content_id=CONTENT_ID,
                    url=URL,
                    store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    fetcher=fetch_then_pause,
                    rights_guard=guard,
                )
            self.assertFalse(store.captures)
            self.assertFalse(store.passages)
            self.assertFalse(list(Path(temp).rglob("*.body")))

    def test_current_scoped_reviewed_permission_works_for_private_capture_only(self):
        authorize(record())
        self.assertNotIn("QUOTATION_EXCERPT_PUBLIC", record().permitted_uses)

    def test_missing_rights_does_not_authorize_capture(self):
        with self.assertRaisesRegex(PrivateCaptureAuthorizationBlocked, "RIGHTS_MISSING"):
            authorize(None)

    def test_unreviewed_unknown_and_public_link_only_are_blocked(self):
        for override in (
            {"rights_status": "UNKNOWN"},
            {"rights_status": "REVOKED"},
            {"rights_status": "RIGHTS_HOLD"},
            {"permitted_uses": ("LINK_PUBLIC",)},
            {"reviewed_at": None},
            {"reviewer_ref": None},
            {"rights_receipt_ref": None},
        ):
            with self.subTest(override=override):
                with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                    authorize(record(**override))

    def test_subject_scope_and_version_must_match_exactly(self):
        for override in (
            {"id": "private-rights:old"},
            {"version_state": "HISTORICAL"},
            {"record_version": "stale-version"},
            {"record_visibility": "PUBLIC"},
            {"source_family": "OTHER"},
            {"locator_kind": "DOMAIN"},
            {"locator_value": "https://example.test/other"},
            {"content_id": "content:other"},
            {"passage_id": "passage:other"},
            {"transcript_segment_id": "segment:other"},
        ):
            with self.subTest(override=override):
                with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                    authorize(record(**override))

    def test_expired_future_review_and_malformed_date_are_blocked(self):
        for override in (
            {"expires_at": "2026-10-07T00:00:00+00:00"},
            {"reviewed_at": "2026-10-09T00:00:00+00:00"},
            {"expires_at": "not-a-date"},
            {"reviewed_at": "2026-10-07T12:00:00"},  # naive
        ):
            with self.subTest(override=override):
                with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                    authorize(record(**override))

    def test_authorization_guard_replays_current_rights_every_time(self):
        records = [record(), record(), record(rights_status="REVOKED")]
        observed = []

        def read_current(subject):
            self.assertEqual(subject.content_id, CONTENT_ID)
            self.assertEqual(subject.locator_value, URL)
            observed.append(subject)
            return records.pop(0)

        guard = private_capture_rights_guard(
            read_current=read_current,
            rights_record_id="private-rights:reviewed",
            content_id=CONTENT_ID,
            canonical_url=URL,
            source_family=SOURCE_FAMILY,
        )
        guard()
        guard()
        with self.assertRaises(PrivateCaptureAuthorizationBlocked):
            guard()
        self.assertEqual(len(observed), 3)

    def test_capture_blocks_recalled_rights_after_network_before_any_body_write(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FakeCaptureStore()
            current = [record()]
            guard = private_capture_rights_guard(
                read_current=lambda subject: current[0],
                rights_record_id="private-rights:reviewed",
                content_id=CONTENT_ID,
                canonical_url=URL,
                source_family=SOURCE_FAMILY,
            )

            def fetch_then_revoke(url, *, max_response_bytes):
                current[0] = record(rights_status="REVOKED")
                return fetched(b"<p>Private content not to be stored.</p>", url=url)

            with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                capture_content(
                    content_id=CONTENT_ID,
                    url=URL,
                    store=store,
                    body_store=CaptureBodyStore(Path(temp)),
                    fetcher=fetch_then_revoke,
                    rights_guard=guard,
                )
            self.assertEqual(store.captures, {})
            self.assertEqual(store.passages, {})
            self.assertEqual(list(Path(temp).rglob("*.body")), [])

    def test_denied_initial_rights_never_reaches_remote_fetch(self):
        with tempfile.TemporaryDirectory() as temp:
            def unexpected_fetch(url, *, max_response_bytes):
                self.fail("remote fetch should never happen")

            guard = private_capture_rights_guard(
                read_current=lambda subject: None,
                rights_record_id="private-rights:reviewed",
                content_id=CONTENT_ID,
                canonical_url=URL,
                source_family=SOURCE_FAMILY,
            )
            with self.assertRaises(PrivateCaptureAuthorizationBlocked):
                capture_content(
                    content_id=CONTENT_ID,
                    url=URL,
                    store=FakeCaptureStore(),
                    body_store=CaptureBodyStore(Path(temp)),
                    fetcher=unexpected_fetch,
                    rights_guard=guard,
                )


if __name__ == "__main__":
    unittest.main()
