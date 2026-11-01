"""DP-468 semantic decisions stay bound to independently witnessed reviews."""

from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dp468_authority_support import AuthorityFixture
from dichiarazioni_pubbliche.public_statement_authority import (
    JournalAuthorityReviewPacketReader, PublicStatementAuthorityReader,
    PublicStatementChallengeStore,
)
from dichiarazioni_pubbliche.public_statement_authority_common import _digest
from dichiarazioni_pubbliche.public_statement_authority_policy import _authority_event_material


def rehash_event(row):
    row["decision_id"] = "public-statement-decision:" + _digest({
        "statement_id": row["statement_id"],
        "version_id": row["version_id"],
        "authority_kind": row["authority_kind"],
        "status": row["status"],
        "binding": row["binding"],
        "payload": row["payload"],
        "review_event_id": row["review_event_id"],
    })
    integrity = _digest(_authority_event_material(row))
    row["integrity_sha256"] = integrity
    row["event_id"] = "public-statement-authority:" + integrity


class PublicStatementAuthoritySemanticReviewTests(AuthorityFixture):
    def test_source_reader_rehydrates_current_decision_specific_review_packets(self):
        self.append_all()
        review_packets = JournalAuthorityReviewPacketReader(
            authority_store=self.store,
            read_authority_review_packet=lambda _statement, _version, kind, decision: (
                self.authority_packets.get(kind)
                if self.authority_packets.get(kind) is not None
                and dict(self.authority_packets[kind].decision) == dict(decision)
                else None
            ),
        )
        reader = PublicStatementAuthorityReader(
            authority_store=self.store,
            challenge_store=PublicStatementChallengeStore(store=self.db),
            read_current_binding=lambda _statement, _version: self.binding,
            read_current_autonomous_evidence=lambda _statement, _version: self.packet,
            read_current_authority_reviews=review_packets,
            processing_family_approved=lambda: True,
            verify_authority_review=self.verify,
        )
        result = reader.statement_publication_attestations(
            self.binding["statement_id"], self.binding["version_id"],
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["context"]["speech_act"], "DIRECT_ASSERTION")

    def test_local_model_claim_without_actual_provider_receipt_is_rejected(self):
        payload = {
            "speaker_name": self.binding["speaker_name"],
            "official_person_uri": "https://www.senato.it/leg/19/assemblea/",
            "public_role_source_url": "https://www.senato.it/leg/19/assemblea/",
        }
        valid_packet = self.authority_packet("ATTRIBUTION", payload)
        invalid = replace(
            valid_packet.primary,
            provider=None, provider_request_id=None, returned_model=None,
            prompt_sha256=None, usage=None,
        )
        with self.assertRaisesRegex(ValueError, "DP468_MODEL_REVIEW_RECEIPT_INVALID"):
            self.append(
                "ATTRIBUTION", payload,
                authority_review_packet=replace(valid_packet, primary=invalid),
            )

    def test_changed_context_payload_cannot_reuse_accepted_reviews_on_append(self):
        original = {
            "speech_act": "DIRECT_ASSERTION", "endorsed": True,
            "source_session_ref": "senato-session:2026-10-31",
        }
        packet = self.authority_packet("CONTEXT", original)
        changed = {**original, "speech_act": "IRONY", "endorsed": False}
        with self.assertRaisesRegex(ValueError, "DP468_AUTHORITY_REVIEW_DECISION_MISMATCH"):
            self.append("CONTEXT", changed, authority_review_packet=packet)
        self.assertEqual(self.db.authority_events, [])

    def test_changed_attribution_identity_cannot_reuse_accepted_reviews_on_append(self):
        original = {
            "speaker_name": self.binding["speaker_name"],
            "official_person_uri": "https://www.senato.it/leg/19/assemblea/",
            "public_role_source_url": "https://www.senato.it/leg/19/assemblea/",
        }
        packet = self.authority_packet("ATTRIBUTION", original)
        changed = {**original, "speaker_name": "Un'altra persona"}
        with self.assertRaisesRegex(ValueError, "DP468_AUTHORITY_REVIEW_DECISION_MISMATCH"):
            self.append("ATTRIBUTION", changed, authority_review_packet=packet)
        self.assertEqual(self.db.authority_events, [])

    def test_changed_context_payload_fails_on_replay_even_with_rehashed_ledger(self):
        self.append_all()
        row = next(event for event in self.db.authority_events if event["authority_kind"] == "CONTEXT")
        row["payload"]["speech_act"] = "IRONY"
        row["payload"]["endorsed"] = False
        rehash_event(row)
        self.assertIsNone(self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            authority_review_packets=self.authority_packets,
            verify_authority_review=self.verify, now=self.now,
        ))

    def test_changed_attribution_identity_fails_on_replay_even_with_rehashed_ledger(self):
        self.append_all()
        row = next(event for event in self.db.authority_events if event["authority_kind"] == "ATTRIBUTION")
        row["payload"]["speaker_name"] = "Un'altra persona"
        rehash_event(row)
        self.assertIsNone(self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            authority_review_packets=self.authority_packets,
            verify_authority_review=self.verify, now=self.now,
        ))


if __name__ == "__main__":
    unittest.main()
