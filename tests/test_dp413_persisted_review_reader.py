"""DP-413: durable model receipts cannot be replayed as stale public authority."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.autonomous_agent_review import OmniRouteAgentReview
from dichiarazioni_pubbliche.autonomous_publication import CHECKS, candidate_fingerprint
from dichiarazioni_pubbliche.public_statement_authority_common import (
    AUTHORITY_CHECKS,
)
from dichiarazioni_pubbliche.autonomous_review_reader import JournalReviewPacketReader
from dichiarazioni_pubbliche.autonomous_runner_v3 import SQLiteRunJournal
from tests.test_autonomous_publication import written_candidate


PRIMARY = "antigravity/gemini-3.8-flash-tiered"
SECOND = "antigravity/gemini-3.7-flash"


class PersistedReviewReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.journal = SQLiteRunJournal(Path(self.temporary.name) / "reviews.sqlite3")
        self.current = written_candidate()
        self.calls = []
        # Independent fake gateway-side observations, separate from the
        # SQLite journal. Only the fake HTTP transport populates this map.
        self.gateway_events = {}

    def read_candidate(self, record_id, version_id):
        if (self.current.record_id, self.current.record_version_id) == (record_id, version_id):
            return self.current
        return None

    def provider_witness(self, receipt):
        event = self.gateway_events.get(receipt.get("provider_request_id"))
        return event == {
            "requested_model": receipt.get("requested_model"),
            "returned_model": receipt.get("returned_model"),
            "prompt_sha256": receipt.get("prompt_sha256"),
            "evidence_sha256": receipt.get("evidence_sha256"),
            "usage": receipt.get("usage"),
        }

    def reader(self, *, authenticated=True):
        return JournalReviewPacketReader(
            journal=self.journal, read_current_candidate=self.read_candidate,
            verify_provider_execution=self.provider_witness if authenticated else None,
            primary_agent_id="agent:primary", primary_model_id=PRIMARY,
            independent_agent_id="agent:independent", independent_model_id=SECOND,
        )

    def response(self, _url, _headers, payload):
        self.calls.append(payload["model"])
        receipt_id = f"completion-{len(self.calls)}"
        user_data = json.loads(payload["messages"][1]["content"])
        authority = user_data.get("authority_decision")
        evidence_sha256 = user_data["evidence_sha256"]
        checks = CHECKS
        citations = {
            "PROVENANCE": [self.current.source_url, self.current.snapshot_url],
            "WORDING": [self.current.snapshot_url],
            "SPEAKER": [self.current.public_role_source_url],
            "PERSON": [self.current.public_role_source_url],
            "RIGHTS_PRIVACY": [
                self.current.rights_citation_url, self.current.privacy_citation_url,
            ],
        }
        if isinstance(authority, dict):
            checks = AUTHORITY_CHECKS
            decision = authority["decision"]
            citations["AUTHORITY_DECISION"] = [
                self.current.source_url, self.current.snapshot_url,
            ]
            if authority["authority_kind"] == "ATTRIBUTION":
                citations["AUTHORITY_DECISION"].extend([
                    decision["official_person_uri"], decision["public_role_source_url"],
                ])
        self.gateway_events[receipt_id] = {
            "requested_model": payload["model"],
            "returned_model": payload["model"],
            "prompt_sha256": hashlib.sha256(json.dumps(
                payload, sort_keys=True, ensure_ascii=False,
                separators=(",", ":"),
            ).encode()).hexdigest(),
            "evidence_sha256": evidence_sha256,
            "usage": {"prompt_tokens": 100, "completion_tokens": 31},
        }
        return 200, {
            "id": receipt_id,
            "model": payload["model"],
            "usage": {"prompt_tokens": 100, "completion_tokens": 31},
            "choices": [{"message": {"content": json.dumps({
                "evidence_sha256": evidence_sha256,
                "checked_stages": list(checks),
                "stage_citations": citations,
                "accepted": True,
            })}}],
        }

    def review(self, agent_id, model_id):
        return OmniRouteAgentReview(
            agent_id=agent_id, model_id=model_id,
            journal=self.journal, api_key="test-not-a-secret",
            subscription_gate=lambda model: model in {PRIMARY, SECOND},
            http_post=self.response,
        ).review(self.current, candidate_fingerprint(self.current))

    def review_authority(self, agent_id, model_id, authority_kind, decision):
        return OmniRouteAgentReview(
            agent_id=agent_id, model_id=model_id,
            journal=self.journal, api_key="test-not-a-secret",
            subscription_gate=lambda model: model in {PRIMARY, SECOND},
            http_post=self.response,
        ).review_authority(self.current, authority_kind, decision)

    def complete(self):
        self.review("agent:primary", PRIMARY)
        self.review("agent:independent", SECOND)

    def packet(self):
        return self.reader()(self.current.record_id, self.current.record_version_id)

    def test_two_actual_adapter_receipts_rehydrate_current_packet(self):
        self.assertIsNone(self.packet())
        self.review("agent:primary", PRIMARY)
        self.assertIsNone(self.packet())
        self.review("agent:independent", SECOND)
        proof = self.packet()
        self.assertIsNotNone(proof)
        self.assertEqual(proof.candidate, self.current)
        self.assertEqual(proof.primary.model_id, PRIMARY)
        self.assertEqual(proof.independent.model_id, SECOND)
        self.assertEqual(self.calls, [PRIMARY, SECOND])

    def test_authority_reviews_bind_the_exact_semantic_payload_and_provider_calls(self):
        decision = {
            "speech_act": "DIRECT_ASSERTION",
            "endorsed": True,
            "source_session_ref": "senato-session:2026-10-31",
        }
        self.review_authority("agent:primary", PRIMARY, "CONTEXT", decision)
        self.review_authority("agent:independent", SECOND, "CONTEXT", decision)
        packet = self.reader().authority_packet(
            self.current.record_id, self.current.record_version_id, "CONTEXT", decision,
        )
        self.assertIsNotNone(packet)
        self.assertEqual(packet.decision, decision)
        self.assertEqual(packet.primary.checked_stages, AUTHORITY_CHECKS)
        changed = {**decision, "speech_act": "IRONY", "endorsed": False}
        self.assertIsNone(self.reader().authority_packet(
            self.current.record_id, self.current.record_version_id, "CONTEXT", changed,
        ))
        self.assertEqual(self.calls, [PRIMARY, SECOND])

    def test_revoked_or_changed_original_does_not_replay_old_receipts(self):
        self.complete()
        self.assertIsNotNone(self.packet())
        original = self.current
        self.current = None
        self.assertIsNone(self.reader()(original.record_id, original.record_version_id))
        self.current = replace(original, source_version="updated-source")
        self.assertIsNone(self.packet())
        self.current = replace(original, privacy_cleared=False)
        self.assertIsNone(self.packet())

    def test_locally_forged_receipts_cannot_qualify_without_provider_authority(self):
        self.complete()
        record_id = self.current.record_id
        version_id = self.current.record_version_id
        # Journal-only data must fail, including when rows look complete.
        self.assertIsNone(self.reader(authenticated=False)(record_id, version_id))
        self.gateway_events.clear()  # Provider has no matching executions.
        self.assertIsNone(self.packet())

    def test_duplicate_or_mismatched_reviewer_receipts_fail_closed(self):
        self.complete()
        self.review("agent:primary", PRIMARY)
        self.assertIsNone(self.packet())

    def test_untrusted_receipt_metadata_cannot_grant_authority(self):
        self.complete()
        first = self.journal.review_executions(candidate_fingerprint(self.current))[0]
        for field, altered in (
            ("policy_version", "previous-policy"),
            ("source_sha256", "0" * 64),
            ("prompt_version", "unverified-prompt"),
            ("returned_model", "openrouter/paid-model"),
            ("accepted", False),
        ):
            with self.subTest(field=field):
                from dichiarazioni_pubbliche.autonomous_review_reader import (
                    JournalReviewPacketReader,
                )
                modified = {**first, field: altered}
                self.assertFalse(JournalReviewPacketReader._matches(
                    modified, self.current, candidate_fingerprint(self.current),
                    "agent:primary", PRIMARY,
                ))

    def test_non_independent_configuration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "NOT_INDEPENDENT"):
            JournalReviewPacketReader(
                journal=self.journal, read_current_candidate=self.read_candidate,
                verify_provider_execution=self.provider_witness,
                primary_agent_id="agent:primary", primary_model_id=PRIMARY,
                independent_agent_id="AGENT:PRIMARY", independent_model_id=SECOND,
            )
        with self.assertRaisesRegex(ValueError, "NOT_INDEPENDENT"):
            JournalReviewPacketReader(
                journal=self.journal, read_current_candidate=self.read_candidate,
                verify_provider_execution=self.provider_witness,
                primary_agent_id="agent:primary", primary_model_id=PRIMARY,
                independent_agent_id="agent:independent", independent_model_id=PRIMARY,
            )


if __name__ == "__main__":
    unittest.main()
