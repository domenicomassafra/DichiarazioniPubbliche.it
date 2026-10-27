"""DP-413B: live gateway response binding and persisted review execution identity."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.autonomous_agent_review import OmniRouteAgentReview
from dichiarazioni_pubbliche.autonomous_publication import candidate_fingerprint, CHECKS
from dichiarazioni_pubbliche.autonomous_runner_v3 import SQLiteRunJournal, PersistentRunner
from dichiarazioni_pubbliche.autonomous_operations import AutonomousOperations
from tests.test_autonomous_operations import Capture, Challenge, Surface
from tests.test_autonomous_publication import candidate

MODEL = "antigravity/gemini-3.8-flash-tiered"


class GatewayReviewTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = SQLiteRunJournal(Path(self.temp.name) / "journal.sqlite3")
        self.item = candidate()
        self.binding = candidate_fingerprint(self.item)
        self.calls = []

    def fake_post(self, url, headers, payload):
        self.calls.append((url, headers, payload))
        return 200, {
            "id": f"completion-{len(self.calls)}", "model": MODEL,
            "usage": {"prompt_tokens": 200, "completion_tokens": 40},
            "choices": [{"message": {"content": json.dumps({
                "evidence_sha256": self.binding, "checked_stages": list(CHECKS),
                "stage_citations": {
                    "PROVENANCE": [self.item.source_url, self.item.snapshot_url],
                    "WORDING": [self.item.snapshot_url],
                    "SPEAKER": [self.item.public_role_source_url],
                    "PERSON": [self.item.public_role_source_url],
                    "RIGHTS_PRIVACY": [
                        self.item.rights_citation_url, self.item.privacy_citation_url,
                    ],
                },
                "accepted": True,
            })}}],
        }

    def reviewer(self, agent_id, *, gate=lambda: True, post=None):
        return OmniRouteAgentReview(
            agent_id=agent_id, api_key="fake-test-token",
            subscription_gate=gate, journal=self.journal,
            http_post=post or self.fake_post,
        )

    def test_two_distinct_gateway_completions_same_approved_model_keep_public_hold(self):
        first = self.reviewer("agent:primary")
        second = self.reviewer("agent:independent")
        surface = Surface()
        operation = AutonomousOperations(
            capture=Capture(self.item), challenge=Challenge(),
            first=first, second=second, public_surface=surface,
            journal=self.journal,
        )
        result = PersistentRunner(operation, self.journal).run(
            self.item.record_id, now=datetime(2026, 10, 26, tzinfo=timezone.utc),
        )
        self.assertEqual(result.disposition, "HOLD")
        self.assertIn("INDEPENDENT_REVIEW", result.reason_codes)
        self.assertFalse(surface.visible)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.journal.review_executions(self.binding)), 2)
        self.assertEqual(
            [event.disposition for event in self.journal.events(self.item.record_id)],
            ["HOLD"],
        )

    def test_two_agent_calls_have_separate_durable_actual_response_ids(self):
        one = self.reviewer("agent:primary").review(self.item, self.binding)
        two = self.reviewer("agent:independent").review(self.item, self.binding)
        self.assertTrue(one.accepted and two.accepted)
        self.assertEqual((one.agent_id, two.agent_id),
                         ("agent:primary", "agent:independent"))
        self.assertEqual([r["provider_request_id"] for r in
                          self.journal.review_executions(self.binding)],
                         ["completion-1", "completion-2"])
        self.assertEqual(len(self.calls), 2)
        for url, headers, payload in self.calls:
            self.assertEqual(url, "http://127.0.0.1:20128/v1/chat/completions")
            self.assertEqual(payload["model"], MODEL)
            self.assertIn("Authorization", headers)

    def test_missing_real_subscription_admission_never_calls_gateway(self):
        with self.assertRaisesRegex(RuntimeError, "SUBSCRIPTION"):
            self.reviewer("agent:first", gate=lambda: False).review(self.item, self.binding)
        self.assertEqual(self.calls, [])

    def test_fail_on_stale_evidence_without_model_work(self):
        with self.assertRaisesRegex(ValueError, "STALE"):
            self.reviewer("agent:first").review(self.item, "0" * 64)
        self.assertEqual(self.calls, [])

    def test_substituted_model_is_not_a_valid_review(self):
        def substitute(*args):
            status, response = self.fake_post(*args)
            response["model"] = "provider:paid-fallback"
            return status, response

        with self.assertRaisesRegex(RuntimeError, "MODEL_SUBSTITUTED"):
            self.reviewer("agent:first", post=substitute).review(self.item, self.binding)
        self.assertEqual(self.journal.review_executions(self.binding), ())

    def test_exhausted_quota_is_not_retried_or_approved(self):
        def exhausted(*args):
            self.calls.append(args)
            return 429, {"error": {"code": "quota_exhausted"}}

        with self.assertRaisesRegex(RuntimeError, "HTTP_429"):
            self.reviewer("agent:first", post=exhausted).review(self.item, self.binding)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.journal.review_executions(self.binding), ())

    def test_model_accept_without_canonical_rights_citation_remains_hold(self):
        def omit_rights(*args):
            status, response = self.fake_post(*args)
            verdict = json.loads(response["choices"][0]["message"]["content"])
            verdict["stage_citations"]["RIGHTS_PRIVACY"] = []
            response["choices"][0]["message"]["content"] = json.dumps(verdict)
            return status, response

        result = self.reviewer("agent:first", post=omit_rights).review(
            self.item, self.binding,
        )
        self.assertFalse(result.accepted)
        self.assertFalse(self.journal.review_executions(self.binding)[0]["accepted"])

    def test_replayed_provider_completion_id_is_rejected(self):
        def replay(*args):
            status, response = self.fake_post(*args)
            response["id"] = "replayed-provider-id"
            return status, response

        self.reviewer("agent:first", post=replay).review(self.item, self.binding)
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            self.reviewer("agent:second", post=replay).review(self.item, self.binding)
        self.assertEqual(len(self.journal.review_executions(self.binding)), 1)
