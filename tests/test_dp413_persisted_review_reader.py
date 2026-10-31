"""DP-413: durable model receipts cannot be replayed as stale public authority."""

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.autonomous_agent_review import OmniRouteAgentReview
from dichiarazioni_pubbliche.autonomous_publication import CHECKS, candidate_fingerprint
from dichiarazioni_pubbliche.autonomous_review_reader import JournalReviewPacketReader
from dichiarazioni_pubbliche.autonomous_runner_v3 import SQLiteRunJournal
from tests.test_autonomous_publication import candidate


PRIMARY = "antigravity/gemini-3.8-flash-tiered"
SECOND = "antigravity/gemini-3.7-flash"


class PersistedReviewReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.journal = SQLiteRunJournal(Path(self.temporary.name) / "reviews.sqlite3")
        self.current = candidate()
        self.calls = []

    def read_candidate(self, record_id, version_id):
        if (self.current.record_id, self.current.record_version_id) == (record_id, version_id):
            return self.current
        return None

    def reader(self):
        return JournalReviewPacketReader(
            journal=self.journal, read_current_candidate=self.read_candidate,
            primary_agent_id="agent:primary", primary_model_id=PRIMARY,
            independent_agent_id="agent:independent", independent_model_id=SECOND,
        )

    def response(self, _url, _headers, payload):
        self.calls.append(payload["model"])
        return 200, {
            "id": f"completion-{len(self.calls)}",
            "model": payload["model"],
            "usage": {"prompt_tokens": 100, "completion_tokens": 31},
            "choices": [{"message": {"content": json.dumps({
                "evidence_sha256": candidate_fingerprint(self.current),
                "checked_stages": list(CHECKS),
                "stage_citations": {
                    "PROVENANCE": [self.current.source_url, self.current.snapshot_url],
                    "WORDING": [self.current.snapshot_url],
                    "SPEAKER": [self.current.public_role_source_url],
                    "PERSON": [self.current.public_role_source_url],
                    "RIGHTS_PRIVACY": [
                        self.current.rights_citation_url, self.current.privacy_citation_url,
                    ],
                },
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
                primary_agent_id="agent:primary", primary_model_id=PRIMARY,
                independent_agent_id="AGENT:PRIMARY", independent_model_id=SECOND,
            )
        with self.assertRaisesRegex(ValueError, "NOT_INDEPENDENT"):
            JournalReviewPacketReader(
                journal=self.journal, read_current_candidate=self.read_candidate,
                primary_agent_id="agent:primary", primary_model_id=PRIMARY,
                independent_agent_id="agent:independent", independent_model_id=PRIMARY,
            )


if __name__ == "__main__":
    unittest.main()
