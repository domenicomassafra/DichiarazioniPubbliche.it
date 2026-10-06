"""DP-302 runtime edge/service tests for private right-of-reply intake."""

from __future__ import annotations

import json
import socket
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.intake_policy import (  # noqa: E402
    RateLimitProfile,
    RateLimitState,
    RateScope,
    compute_request_fingerprint,
)
from dichiarazioni_pubbliche.right_of_reply_intake import (  # noqa: E402
    ReplayKind,
    RightOfReplyLaunchProfile,
    ServiceReason,
    ServiceState,
    submit_right_of_reply,
)


def _payload(**overrides):
    data = {
        "finding_id": "finding:demo:1",
        "body": "Replica privata documentata.",
        "submitter_name": "Persona privata",
        "submitter_role": "Portavoce",
        "evidence_urls": ["https://example.test/reply/reference"],
        "policy_version": "reply-intake-policy-v1",
        "request_fingerprint": "caller-idempotency-token",
    }
    data.update(overrides)
    return data


def _profile(*, limit=5, scope=RateScope.PER_FINDING):
    return RightOfReplyLaunchProfile(
        configured=True,
        enabled=True,
        rate_profile=RateLimitProfile(
            scope=scope,
            limit=limit,
            window_seconds=3600,
            configured=True,
        ),
    )


def _clock():
    return datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)


class MemoryStore:
    def __init__(self, *, reply_exists=False, followup_exists=False):
        self.reply_exists = reply_exists
        self.followup_exists = followup_exists
        self.replies = []
        self.followups = []
        self.attachments = []
        self.publish_calls = 0

    def finding_context(self, finding_id):
        if finding_id != "finding:demo:1":
            raise KeyError("unknown finding")
        return {
            "finding_id": finding_id,
            "claim_id": "claim:demo:1",
            "content_id": "content:demo:1",
            "publication_status": "PUBLISH",
        }

    def claim_context(self, claim_id):
        return {"claim_id": claim_id, "content_id": "content:demo:1"}

    def insert_right_of_reply(self, **kwargs):
        if self.reply_exists:
            return False
        self.reply_exists = True
        self.replies.append(kwargs)
        return True

    def enqueue_followup(self, **kwargs):
        job_id = "job:" + kwargs["variant"]
        if self.followup_exists:
            return job_id, False
        self.followup_exists = True
        self.followups.append(kwargs)
        return job_id, True

    def attach_reply_reanalysis_job(self, **kwargs):
        self.attachments.append(kwargs)
        return True

    def publish_right_of_reply_with_review(self, **kwargs):
        self.publish_calls += 1
        raise AssertionError("intake must never invoke publication")

    def fetch(self, *args, **kwargs):
        raise AssertionError("intake must never fetch")

    def call_provider(self, *args, **kwargs):
        raise AssertionError("intake must never invoke a provider")


class FailingPrivateStore(MemoryStore):
    def finding_context(self, finding_id):
        raise RuntimeError("PRIVATE_STORE_ERROR_SENTINEL")


class RightOfReplyIntakeRuntimeTests(unittest.TestCase):
    def test_disabled_without_explicit_launch_profile(self):
        store = MemoryStore()
        receipt = submit_right_of_reply(store, _payload(), clock=_clock)
        self.assertEqual(receipt.state, ServiceState.NOT_RECEIVED)
        self.assertEqual(receipt.reason, "LAUNCH_PROFILE_MISSING")
        self.assertEqual(store.replies, [])
        self.assertEqual(store.followups, [])

    def test_valid_submission_uses_private_persistence_path_only(self):
        store = MemoryStore()
        receipt = submit_right_of_reply(
            store,
            _payload(),
            launch_profile=_profile(),
            rate_state=RateLimitState(submissions_in_window=1),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ServiceState.RECEIVED_PRIVATE)
        self.assertEqual(receipt.replay, ReplayKind.NONE)
        self.assertTrue(receipt.created)
        self.assertTrue(receipt.is_bounded())
        self.assertEqual(len(store.replies), 1)
        self.assertEqual(store.replies[0]["body"], "Replica privata documentata.")
        self.assertEqual(len(store.followups), 1)
        self.assertEqual(store.followups[0]["job_type"], "REGISTER_REANALYSIS")
        self.assertEqual(store.followups[0]["payload"]["trigger_type"], "RIGHT_OF_REPLY")
        self.assertEqual(store.publish_calls, 0)
        ack_text = json.dumps(receipt.acknowledgement).lower()
        self.assertNotIn("accepted", ack_text)
        self.assertNotIn("published", ack_text)

    def test_invalid_payload_is_rejected_before_store_use(self):
        store = MemoryStore()
        receipt = submit_right_of_reply(
            store,
            _payload(body=""),
            launch_profile=_profile(),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ServiceState.NOT_RECEIVED)
        self.assertEqual(receipt.reason, "BODY_EMPTY")
        self.assertEqual(store.replies, [])
        self.assertEqual(store.followups, [])

    def test_quarantined_payload_is_not_persisted_by_this_adapter(self):
        store = MemoryStore()
        receipt = submit_right_of_reply(
            store,
            _payload(body="Contattami a private@example.test per i dettagli."),
            launch_profile=_profile(),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ServiceState.NOT_RECEIVED)
        self.assertEqual(receipt.reason, "DISCLOSED_PRIVATE_CONTACT")
        self.assertEqual(store.replies, [])
        self.assertEqual(store.followups, [])

    def test_quota_decision_blocks_before_persistence(self):
        store = MemoryStore()
        receipt = submit_right_of_reply(
            store,
            _payload(),
            launch_profile=_profile(limit=2, scope=RateScope.GLOBAL),
            rate_state=RateLimitState(submissions_in_window=2),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ServiceState.NOT_RECEIVED)
        self.assertEqual(receipt.reason, "QUOTA_EXCEEDED")
        self.assertEqual(store.replies, [])

    def test_rate_decision_can_defer_without_persistence(self):
        store = MemoryStore()
        receipt = submit_right_of_reply(
            store,
            _payload(),
            launch_profile=_profile(limit=2),
            rate_state=RateLimitState(submissions_in_window=2),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ServiceState.DEFERRED)
        self.assertEqual(receipt.reason, "RATE_LIMIT_EXCEEDED")
        self.assertEqual(store.replies, [])

    def test_missing_caller_rate_state_fails_closed(self):
        store = MemoryStore()
        receipt = submit_right_of_reply(
            store,
            _payload(),
            launch_profile=_profile(),
            rate_state=None,
            clock=_clock,
        )
        self.assertEqual(receipt.reason, ServiceReason.RATE_DECISION_MISSING.value)
        self.assertEqual(store.replies, [])

    def test_no_dns_network_fetch_or_provider_is_invoked(self):
        store = MemoryStore()
        with mock.patch.object(
            socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")
        ), mock.patch.object(
            socket, "create_connection", side_effect=AssertionError("network forbidden")
        ):
            receipt = submit_right_of_reply(
                store,
                _payload(evidence_urls=["https://example.test/never-fetched"]),
                launch_profile=_profile(),
                rate_state=RateLimitState(),
                clock=_clock,
            )
        self.assertEqual(receipt.state, ServiceState.RECEIVED_PRIVATE)
        self.assertEqual(store.publish_calls, 0)

    def test_duplicate_replay_returns_same_receipt_without_second_trigger(self):
        store = MemoryStore()
        kwargs = dict(
            launch_profile=_profile(),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        first = submit_right_of_reply(store, _payload(), **kwargs)
        second = submit_right_of_reply(store, _payload(), **kwargs)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual(second.replay, ReplayKind.DUPLICATE)
        self.assertFalse(second.created)
        self.assertEqual(len(store.replies), 1)
        self.assertEqual(len(store.followups), 1)

    def test_concurrent_replay_is_distinguished_from_completed_duplicate(self):
        store = MemoryStore(reply_exists=True, followup_exists=False)
        receipt = submit_right_of_reply(
            store,
            _payload(),
            launch_profile=_profile(),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ServiceState.RECEIVED_PRIVATE)
        self.assertEqual(receipt.replay, ReplayKind.CONCURRENT)
        self.assertFalse(receipt.created)
        self.assertEqual(len(store.followups), 1)

    def test_canonical_fingerprint_is_stable_but_never_logged(self):
        payload = _payload(request_fingerprint="PRIVATE_FINGERPRINT_SENTINEL")
        expected = compute_request_fingerprint(
            finding_id=payload["finding_id"],
            body=payload["body"],
            submitter_name=payload["submitter_name"],
            submitter_role=payload["submitter_role"],
            evidence_urls=tuple(payload["evidence_urls"]),
        )
        self.assertEqual(len(expected), 64)
        receipt = submit_right_of_reply(
            MemoryStore(),
            payload,
            launch_profile=_profile(),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        rendered = json.dumps(
            {"ack": receipt.acknowledgement, "log": receipt.loggable_receipt},
            sort_keys=True,
        )
        self.assertNotIn(expected, rendered)
        self.assertNotIn("PRIVATE_FINGERPRINT_SENTINEL", rendered)

    def test_private_body_identity_and_secret_reference_never_enter_ack_or_log_receipt(self):
        private_body = "PRIVATE_BODY_SENTINEL secret material"
        private_name = "PRIVATE_NAME_SENTINEL"
        private_url = "https://example.test/PRIVATE_REFERENCE_SENTINEL"
        receipt = submit_right_of_reply(
            MemoryStore(),
            _payload(
                body=private_body,
                submitter_name=private_name,
                evidence_urls=[private_url],
            ),
            launch_profile=_profile(),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        rendered = json.dumps(
            {"ack": receipt.acknowledgement, "log": receipt.loggable_receipt},
            sort_keys=True,
        )
        for private_value in (private_body, private_name, private_url):
            self.assertNotIn(private_value, rendered)
        self.assertTrue(receipt.is_bounded())

    def test_private_persistence_error_is_reduced_to_generic_receipt(self):
        receipt = submit_right_of_reply(
            FailingPrivateStore(),
            _payload(body="PRIVATE_BODY_SENTINEL"),
            launch_profile=_profile(),
            rate_state=RateLimitState(),
            clock=_clock,
        )
        self.assertEqual(receipt.state, ServiceState.NOT_RECEIVED)
        self.assertEqual(receipt.reason, ServiceReason.PERSISTENCE_ERROR.value)
        rendered = json.dumps(
            {"ack": receipt.acknowledgement, "log": receipt.loggable_receipt},
            sort_keys=True,
        )
        self.assertNotIn("PRIVATE_STORE_ERROR_SENTINEL", rendered)
        self.assertNotIn("PRIVATE_BODY_SENTINEL", rendered)
        self.assertTrue(receipt.is_bounded())


if __name__ == "__main__":
    unittest.main()
