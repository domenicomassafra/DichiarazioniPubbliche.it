"""DP-303 callable correction/takedown/appeal runtime edge tests."""

from __future__ import annotations

import hashlib
import json
import socket
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.challenge_intake import (  # noqa: E402
    ChallengeLaunchProfile,
    ChallengeReplayKind,
    ChallengeServiceReason,
    ChallengeServiceState,
    submit_challenge,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import (  # noqa: E402
    ChallengeKind,
    ChallengeState,
)
from dichiarazioni_pubbliche.policy.intake_policy import (  # noqa: E402
    RateLimitProfile,
    RateLimitState,
    RateScope,
)


def _clock():
    return datetime(2026, 10, 5, 21, 0, tzinfo=timezone.utc)


def _profile(*kinds, limit=5, scope=RateScope.GLOBAL):
    return ChallengeLaunchProfile(
        configured=True,
        enabled=True,
        enabled_kinds=frozenset(kinds),
        rate_profile=RateLimitProfile(
            scope=scope,
            limit=limit,
            window_seconds=3600,
            configured=True,
        ),
    )


def _correction(**overrides):
    payload = {
        "kind": "CORRECTION",
        "finding_id": "finding:new",
        "previous_finding_id": "finding:old",
        "reason": "The reviewed source changes the assessment.",
        "changed_fields": {"assessment": ["SUPPORTED", "OUTDATED_DATA"]},
    }
    payload.update(overrides)
    return payload


def _takedown(**overrides):
    payload = {
        "kind": "TAKEDOWN",
        "target_finding_id": "finding:old",
        "reason": "Please review whether this record should remain visible.",
    }
    payload.update(overrides)
    return payload


def _appeal(**overrides):
    payload = {
        "kind": "APPEAL",
        "target_finding_id": "finding:old",
        "prior_decision_id": "review:prior",
        "reason": "Please independently review the prior decision.",
    }
    payload.update(overrides)
    return payload


class MemoryStore:
    def __init__(self, *, followup_exists=False, fail_private=False):
        self.findings = {
            "finding:old": {
                "finding_id": "finding:old",
                "claim_id": "claim:a",
                "content_id": "content:a",
                "publication_status": "PUBLISH",
                "supersedes_id": None,
            },
            "finding:new": {
                "finding_id": "finding:new",
                "claim_id": "claim:a",
                "content_id": "content:a",
                "publication_status": "HOLD",
                "supersedes_id": "finding:old",
            },
        }
        self.corrections = {}
        self.followups = {}
        self.followup_exists = followup_exists
        self.fail_private = fail_private
        self.finding_reads = 0
        self.publish_calls = 0
        self.finding_mutations = 0

    def finding_context(self, finding_id):
        self.finding_reads += 1
        if self.fail_private:
            raise RuntimeError("PRIVATE_STORE_DETAIL_SENTINEL")
        if finding_id not in self.findings:
            raise KeyError("PRIVATE_UNKNOWN_TARGET_SENTINEL")
        return dict(self.findings[finding_id])

    def claim_context(self, claim_id):
        return {"claim_id": claim_id, "content_id": "content:a"}

    def insert_correction(self, **kwargs):
        if self.fail_private:
            raise RuntimeError("PRIVATE_CORRECTION_DETAIL_SENTINEL")
        current = self.findings.get(kwargs["finding_id"])
        previous = self.findings.get(kwargs["previous_finding_id"])
        if (
            current is None
            or previous is None
            or current["claim_id"] != previous["claim_id"]
            or current["supersedes_id"] != previous["finding_id"]
        ):
            return False
        existing = self.corrections.get(kwargs["correction_id"])
        if existing is not None:
            return existing == kwargs
        self.corrections[kwargs["correction_id"]] = dict(kwargs)
        return True

    def enqueue_followup(self, **kwargs):
        job_id = "job:" + hashlib.sha256(
            (kwargs["job_type"] + "\0" + kwargs["content_id"] + "\0" + kwargs["variant"]).encode()
        ).hexdigest()
        if self.followup_exists or job_id in self.followups:
            return job_id, False
        self.followups[job_id] = dict(kwargs)
        return job_id, True

    def publish_correction_with_review(self, **kwargs):
        self.publish_calls += 1
        raise AssertionError("intake must not publish")

    def update_finding(self, *args, **kwargs):
        self.finding_mutations += 1
        raise AssertionError("intake must not mutate Finding")

    def delete_finding(self, *args, **kwargs):
        self.finding_mutations += 1
        raise AssertionError("intake must not delete Finding")

    def fetch(self, *args, **kwargs):
        raise AssertionError("intake must not fetch")

    def call_provider(self, *args, **kwargs):
        raise AssertionError("intake must not call provider")


class MemoryChallengeLedger:
    def __init__(self):
        self.requests = {}
        self.states = {}
        self.transitions = []

    def initiate_request(self, **kwargs):
        request_id = "challenge-request:" + hashlib.sha256(
            (kwargs["kind"].value + "\0" + kwargs["source_request_ref"]).encode()
        ).hexdigest()
        created = request_id not in self.requests
        request = SimpleNamespace(request_id=request_id, kind=kwargs["kind"])
        self.requests.setdefault(request_id, request)
        self.states.setdefault(request_id, ChallengeState.PRIVATE_RECEIVED)
        return SimpleNamespace(
            request=self.requests[request_id],
            event=SimpleNamespace(to_state=ChallengeState.PRIVATE_RECEIVED),
            created=created,
        )

    def replay_request(self, request_id):
        return SimpleNamespace(
            blockers=(),
            current_state=self.states[request_id],
        )

    def transition_request(self, request_id, **kwargs):
        kind = self.requests[request_id].kind
        target = (
            ChallengeState.TRIAGE_PENDING
            if kind is ChallengeKind.TAKEDOWN
            else ChallengeState.INDEPENDENT_REVIEW_PENDING
        )
        created = self.states[request_id] is ChallengeState.PRIVATE_RECEIVED
        self.states[request_id] = target
        self.transitions.append((request_id, kwargs, target))
        return SimpleNamespace(
            request=self.requests[request_id],
            event=SimpleNamespace(to_state=target),
            created=created,
        )


class ChallengeIntakeTests(unittest.TestCase):
    def test_disabled_by_default_before_payload_or_store_use(self):
        store = MemoryStore()
        receipt = submit_challenge(store, _correction(), clock=_clock)
        self.assertEqual(receipt.state, ChallengeServiceState.NOT_RECEIVED)
        self.assertEqual(receipt.reason, ChallengeServiceReason.LAUNCH_PROFILE_MISSING.value)
        self.assertEqual(store.finding_reads, 0)
        self.assertEqual(store.corrections, {})

    def test_correction_persists_only_through_private_canonical_path(self):
        store = MemoryStore()
        receipt = submit_challenge(
            store,
            _correction(),
            launch_profile=_profile(ChallengeKind.CORRECTION),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ChallengeServiceState.REANALYSIS_PENDING_PRIVATE)
        self.assertEqual(receipt.kind, ChallengeKind.CORRECTION)
        self.assertEqual(receipt.replay, ChallengeReplayKind.NONE)
        self.assertEqual(len(store.corrections), 1)
        self.assertEqual(len(store.followups), 1)
        followup = next(iter(store.followups.values()))
        self.assertEqual(followup["job_type"], "REGISTER_REANALYSIS")
        self.assertEqual(followup["payload"]["trigger_type"], "CORRECTION")
        self.assertEqual(store.publish_calls, 0)
        self.assertEqual(store.finding_mutations, 0)
        self.assertTrue(receipt.is_bounded())

    def test_correction_replay_is_idempotent_and_does_not_duplicate_work(self):
        store = MemoryStore()
        kwargs = {
            "launch_profile": _profile(ChallengeKind.CORRECTION),
            "rate_state": RateLimitState(),
            "clock": _clock,
        }
        first = submit_challenge(store, _correction(), **kwargs)
        second = submit_challenge(store, _correction(), **kwargs)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual(first.request_ref, second.request_ref)
        self.assertEqual(second.replay, ChallengeReplayKind.REPLAY_OR_CONCURRENT)
        self.assertEqual(len(store.corrections), 1)
        self.assertEqual(len(store.followups), 1)

    def test_concurrent_followup_winner_is_reported_without_duplicate_work(self):
        store = MemoryStore(followup_exists=True)
        receipt = submit_challenge(
            store,
            _correction(),
            launch_profile=_profile(ChallengeKind.CORRECTION),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ChallengeServiceState.REANALYSIS_PENDING_PRIVATE)
        self.assertEqual(receipt.replay, ChallengeReplayKind.REPLAY_OR_CONCURRENT)
        self.assertEqual(len(store.corrections), 1)
        self.assertEqual(len(store.followups), 0)

    def test_invalid_correction_chain_fails_before_persistence(self):
        store = MemoryStore()
        store.findings["finding:new"]["supersedes_id"] = "finding:other"
        receipt = submit_challenge(
            store,
            _correction(),
            launch_profile=_profile(ChallengeKind.CORRECTION),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ChallengeServiceState.NOT_RECEIVED)
        self.assertEqual(receipt.reason, ChallengeServiceReason.CORRECTION_CHAIN_INVALID.value)
        self.assertEqual(store.corrections, {})
        self.assertEqual(store.followups, {})

    def test_takedown_is_persisted_privately_and_stops_at_triage(self):
        store = MemoryStore()
        ledger = MemoryChallengeLedger()
        receipt = submit_challenge(
            store,
            _takedown(),
            launch_profile=_profile(ChallengeKind.TAKEDOWN),
            rate_state=RateLimitState(),
            clock=_clock,
            challenge_ledger=ledger,
        )
        self.assertEqual(receipt.kind, ChallengeKind.TAKEDOWN)
        self.assertEqual(receipt.state, ChallengeServiceState.TRIAGE_PENDING_PRIVATE)
        self.assertEqual(receipt.reason, ChallengeServiceReason.OK.value)
        self.assertEqual(len(ledger.requests), 1)
        self.assertEqual(len(ledger.transitions), 1)
        self.assertEqual(
            next(iter(ledger.states.values())), ChallengeState.TRIAGE_PENDING
        )
        self.assertEqual(store.finding_reads, 0)
        self.assertEqual(store.corrections, {})
        self.assertEqual(store.followups, {})

    def test_appeal_is_persisted_privately_and_stops_at_independent_review(self):
        store = MemoryStore()
        ledger = MemoryChallengeLedger()
        receipt = submit_challenge(
            store,
            _appeal(),
            launch_profile=_profile(ChallengeKind.APPEAL),
            rate_state=RateLimitState(),
            clock=_clock,
            challenge_ledger=ledger,
        )
        self.assertEqual(receipt.kind, ChallengeKind.APPEAL)
        self.assertEqual(
            receipt.state, ChallengeServiceState.INDEPENDENT_REVIEW_PENDING_PRIVATE
        )
        self.assertEqual(receipt.reason, ChallengeServiceReason.OK.value)
        self.assertEqual(len(ledger.requests), 1)
        self.assertEqual(len(ledger.transitions), 1)
        self.assertEqual(
            next(iter(ledger.states.values())),
            ChallengeState.INDEPENDENT_REVIEW_PENDING,
        )
        self.assertEqual(store.finding_reads, 0)
        self.assertEqual(store.corrections, {})
        self.assertEqual(store.followups, {})

    def test_kind_specific_fields_cannot_cross_workflow_gates(self):
        store = MemoryStore()
        cases = [
            (_takedown(changed_fields={"x": 1}), ChallengeKind.TAKEDOWN),
            (_appeal(previous_finding_id="finding:old"), ChallengeKind.APPEAL),
            (_correction(target_finding_id="finding:old"), ChallengeKind.CORRECTION),
        ]
        for payload, kind in cases:
            with self.subTest(kind=kind):
                receipt = submit_challenge(
                    store,
                    payload,
                    launch_profile=_profile(kind),
                    rate_state=RateLimitState(),
                    clock=_clock,
                )
                self.assertEqual(receipt.state, ChallengeServiceState.NOT_RECEIVED)
                self.assertEqual(receipt.reason, ChallengeServiceReason.UNKNOWN_FIELD.value)
        self.assertEqual(store.corrections, {})

    def test_wrong_or_oversized_payload_is_rejected_before_store(self):
        store = MemoryStore()
        bad_payloads = [
            ["not", "a", "mapping"],
            _correction(reason="x" * 8001),
            _correction(changed_fields={"blob": "x" * 40_000}),
        ]
        for payload in bad_payloads:
            receipt = submit_challenge(
                store,
                payload,
                launch_profile=_profile(ChallengeKind.CORRECTION),
                rate_state=RateLimitState(),
                clock=_clock,
            )
            self.assertEqual(receipt.state, ChallengeServiceState.NOT_RECEIVED)
        self.assertEqual(store.finding_reads, 0)
        self.assertEqual(store.corrections, {})

    def test_rate_quota_is_caller_supplied_and_fails_before_persistence(self):
        store = MemoryStore()
        receipt = submit_challenge(
            store,
            _correction(),
            launch_profile=_profile(ChallengeKind.CORRECTION, limit=1),
            rate_state=RateLimitState(submissions_in_window=1),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ChallengeServiceState.NOT_RECEIVED)
        self.assertEqual(receipt.reason, "QUOTA_EXCEEDED")
        self.assertEqual(store.finding_reads, 0)
        self.assertEqual(store.corrections, {})

    def test_missing_rate_state_fails_closed(self):
        receipt = submit_challenge(
            MemoryStore(),
            _correction(),
            launch_profile=_profile(ChallengeKind.CORRECTION),
            rate_state=None,
            clock=_clock,
        )
        self.assertEqual(receipt.reason, ChallengeServiceReason.RATE_DECISION_MISSING.value)

    def test_no_dns_fetch_provider_publication_or_finding_mutation(self):
        store = MemoryStore()
        with mock.patch.object(
            socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")
        ), mock.patch.object(
            socket, "create_connection", side_effect=AssertionError("network forbidden")
        ):
            receipt = submit_challenge(
                store,
                _correction(),
                launch_profile=_profile(ChallengeKind.CORRECTION),
                rate_state=RateLimitState(),
                clock=_clock,
            )
        self.assertEqual(receipt.state, ChallengeServiceState.REANALYSIS_PENDING_PRIVATE)
        self.assertEqual(store.publish_calls, 0)
        self.assertEqual(store.finding_mutations, 0)

    def test_private_reason_and_changed_fields_are_absent_from_ack_and_log_receipt(self):
        private_reason = "PRIVATE_REASON_SENTINEL with confidential detail"
        private_changed = {"private_note": "PRIVATE_CHANGED_FIELD_SENTINEL"}
        receipt = submit_challenge(
            MemoryStore(),
            _correction(reason=private_reason, changed_fields=private_changed),
            launch_profile=_profile(ChallengeKind.CORRECTION),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        rendered = json.dumps(
            {"ack": receipt.acknowledgement, "log": receipt.loggable_receipt},
            sort_keys=True,
        )
        self.assertNotIn(private_reason, rendered)
        self.assertNotIn("PRIVATE_CHANGED_FIELD_SENTINEL", rendered)
        self.assertTrue(receipt.is_bounded())

    def test_private_store_exception_is_redacted(self):
        receipt = submit_challenge(
            MemoryStore(fail_private=True),
            _correction(reason="PRIVATE_REASON_SENTINEL"),
            launch_profile=_profile(ChallengeKind.CORRECTION),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        rendered = json.dumps(
            {"ack": receipt.acknowledgement, "log": receipt.loggable_receipt},
            sort_keys=True,
        )
        self.assertEqual(receipt.reason, ChallengeServiceReason.CORRECTION_CHAIN_INVALID.value)
        self.assertNotIn("PRIVATE_STORE_DETAIL_SENTINEL", rendered)
        self.assertNotIn("PRIVATE_REASON_SENTINEL", rendered)
        self.assertTrue(receipt.is_bounded())

    def test_ack_never_claims_acceptance_approval_or_publication(self):
        receipts = [
            submit_challenge(
                MemoryStore(),
                payload,
                launch_profile=_profile(kind),
                rate_state=RateLimitState(),
                clock=_clock,
            )
            for payload, kind in (
                (_correction(), ChallengeKind.CORRECTION),
                (_takedown(), ChallengeKind.TAKEDOWN),
                (_appeal(), ChallengeKind.APPEAL),
            )
        ]
        for receipt in receipts:
            rendered = json.dumps(receipt.acknowledgement).lower()
            for forbidden in ("accepted", "approved", "published", "verified"):
                self.assertNotIn(forbidden, rendered)
            self.assertTrue(receipt.is_bounded())


if __name__ == "__main__":
    unittest.main()
