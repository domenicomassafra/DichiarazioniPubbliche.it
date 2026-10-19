"""A bounded synthetic source sequence; fixture rights are never live clearance."""

import hashlib
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from dichiarazioni_pubbliche.dp244_conditional_probe import (
    HttpResult,
    probe_permitted_source,
)
from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchCoverageSnapshot,
    WatchPolicy,
    WatchReadiness,
    WatchState,
    build_private_watch_daily_digest,
    policy_fingerprint,
)
from dichiarazioni_pubbliche.private_capture_rights import (
    SourceFamilyUseGuard,
    SourceUseBlocked,
)
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord,
    RightsSubject,
    rights_subject_fingerprint,
)

AT = datetime(2026, 10, 18, 14, tzinfo=UTC)
URL = "https://example.org/official/test.xml"


def setup():
    policy = WatchPolicy(
        source_id="fixture:official:test", locator_id=URL,
        source_family="OFFICIAL_XML", corpus_id="fixture:bounded",
        corpus_cutoff="2026-10-01", policy_revision="fixture:r1", enabled=True,
        base_backoff_seconds=1, max_backoff_seconds=60,
    )
    gate = WatchReadiness(
        source_id=policy.source_id, policy_fingerprint=policy_fingerprint(policy),
        corpus_id=policy.corpus_id, rights_status="READY",
        rights_receipt="fixture:only", capability_status="READY",
        capability_receipt="fixture:runtime", budget_status="READY",
        budget_receipt="fixture:unmetered", remaining_children=1,
    )
    subject = RightsSubject("OFFICIAL_XML", "URL", URL, content_id="fixture:content")
    record = PrivateRightsRecord(
        id="fixture:permit", subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=subject.source_family, locator_kind="URL", locator_value=URL,
        content_id=subject.content_id, evidence_id=None, transcript_segment_id=None,
        canonical_segment_id=None, passage_id=None, rights_status="CLEARED",
        rights_receipt_ref="fixture:rights", permitted_uses=("FETCH",),
        attribution_requirements=(), reviewed_at="2026-10-17T00:00:00+00:00",
        expires_at="2026-10-20T00:00:00+00:00", reviewer_ref="fixture:reviewer",
        policy_version="fixture:v1", record_visibility="PRIVATE",
        supersedes_id=None, version_state="CURRENT",
    )
    records = [record]
    guard = SourceFamilyUseGuard(
        read_current=lambda s: records[0], subject=subject,
        rights_record_id=record.id, policy_version="fixture:v1", clock=lambda: AT,
    )
    return policy, gate, records, guard


def attempt(policy, gate, guard, state, *, index, outcome, url=URL,
            fetched=None, current_gate=None):
    started = AT + timedelta(seconds=10 * index)
    observed = started + timedelta(seconds=1)
    def fetch(target, headers):
        if fetched is not None:
            fetched.append((target, headers))
        return outcome
    return probe_permitted_source(
        policy=policy, state=state, planning_gate=gate,
        current_gate=current_gate or (lambda: gate),
        rights_guard=guard, content_id="fixture:content", url=url,
        attempt_id=f"attempt:{index}", attempted_at=started, fetch=fetch,
        clock=lambda: observed,
    ).committed_attempt


class ConditionalProbeTests(unittest.TestCase):
    def test_first_unchanged_changed_and_outage_preserve_independent_costs(self):
        policy, gate, _, guard = setup()
        state = WatchState(source_id=policy.source_id)
        requested = []
        first = attempt(
            policy, gate, guard, state, index=0,
            outcome=HttpResult(200, URL, b"official version one", etag='"v1"'),
            fetched=requested,
        )
        self.assertEqual(first.decision.disposition, "CHANGED")
        self.assertEqual(len(first.decision.children), 1)
        self.assertEqual(first.measured_cost_micro_eur, None)
        self.assertEqual(requested[0][1], ())
        self.assertEqual(first.decision.next_state.content_sha256,
                         hashlib.sha256(b"official version one").hexdigest())

        second = attempt(
            policy, gate, guard, first.decision.next_state, index=1,
            outcome=HttpResult(304, URL), fetched=requested,
        )
        self.assertEqual(second.decision.disposition, "UNCHANGED")
        self.assertEqual(second.decision.children, ())
        self.assertEqual(requested[1][1], (("If-None-Match", '"v1"'),))

        third = attempt(
            policy, gate, guard, second.decision.next_state, index=2,
            outcome=HttpResult(200, URL, b"corrected transcript", etag='"v2"'),
        )
        self.assertEqual(third.decision.disposition, "CHANGED")
        child = third.decision.children[0]
        self.assertEqual(child.previous_source_version, first.decision.next_state.source_version)
        self.assertEqual(child.observed_source_version, third.decision.next_state.source_version)
        self.assertNotEqual(child.previous_source_version, child.observed_source_version)
        self.assertEqual(child.stage, "SOURCE_REVALIDATION_REVIEW")

        fourth = attempt(
            policy, gate, guard, third.decision.next_state, index=3,
            outcome=HttpResult(None, URL, transport_error="NETWORK_ERROR"),
        )
        self.assertEqual(fourth.decision.disposition, "UNAVAILABLE")
        self.assertIsNotNone(fourth.decision.next_state.retry_not_before)
        self.assertEqual(fourth.decision.next_state.content_sha256,
                         third.decision.next_state.content_sha256)
        self.assertEqual(fourth.decision.children, ())
        digest = build_private_watch_daily_digest(
            day=date(2026, 10, 18), as_of=AT + timedelta(minutes=5),
            snapshots=(WatchCoverageSnapshot(policy, fourth.decision.next_state, gate),),
            committed_attempts=(first, second, third, fourth),
        )
        self.assertEqual(
            (digest.attempts, digest.new, digest.modified, digest.unchanged,
             digest.unavailable, digest.unknown_cost_attempts),
            (4, 1, 1, 1, 1, 4),
        )

    def test_expired_source_rights_prevent_even_first_http_call(self):
        policy, gate, records, guard = setup()
        records[0] = replace(records[0], rights_status="EXPIRED")
        requested = []
        with self.assertRaises(SourceUseBlocked):
            attempt(policy, gate, guard, WatchState(policy.source_id), index=0,
                    outcome=HttpResult(200, URL, b"not permitted"), fetched=requested)
        self.assertEqual(requested, [])

    def test_rights_revoked_during_fetch_prevents_success_receipt(self):
        policy, gate, records, guard = setup()
        requested = []
        def revoke(url, headers):
            requested.append(url)
            records[0] = replace(records[0], rights_status="REVOKED")
            return HttpResult(200, url, b"new material")
        with self.assertRaises(SourceUseBlocked):
            probe_permitted_source(
                policy=policy, state=WatchState(policy.source_id), planning_gate=gate,
                current_gate=lambda: gate, rights_guard=guard,
                content_id="fixture:content", url=URL,
                attempt_id="attempt:1", attempted_at=AT,
                fetch=revoke, clock=lambda: AT + timedelta(seconds=1),
            )
        self.assertEqual(requested, [URL])

    def test_redirect_or_wrong_source_cannot_write_observation(self):
        policy, gate, _, guard = setup()
        state = WatchState(policy.source_id)
        with self.assertRaises(SourceUseBlocked):
            attempt(policy, gate, guard, state, index=0,
                    outcome=HttpResult(200, "https://other.example/path", b"data"))
        with self.assertRaisesRegex(ValueError, "SOURCE_BINDING_MISMATCH"):
            attempt(policy, gate, guard, state, index=0,
                    outcome=HttpResult(200, URL, b"data"),
                    url="https://example.org/other")

    def test_no_body_on_304_and_size_limit_are_fail_closed(self):
        policy, gate, _, guard = setup()
        state = WatchState(policy.source_id)
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_BODY"):
            attempt(policy, gate, guard, state, index=0,
                    outcome=HttpResult(304, URL, b"not a conditional reply"))
        with self.assertRaisesRegex(ValueError, "RESPONSE_TOO_LARGE"):
            attempt(policy, gate, guard, state, index=0,
                    outcome=HttpResult(200, URL, b"z" * (512 * 1024 + 1)))

    def test_unexpected_304_without_prior_validator_is_an_unverified_failure(self):
        policy, gate, _, guard = setup()
        receipt = attempt(
            policy, gate, guard, WatchState(policy.source_id), index=0,
            outcome=HttpResult(304, URL),
        )
        self.assertEqual(receipt.decision.disposition, "UNAVAILABLE")
        self.assertEqual(receipt.decision.reason, "INVALID_CONDITIONAL_304")
        self.assertIsNone(receipt.decision.next_state.last_successful_observed_at)


if __name__ == "__main__":
    unittest.main()
