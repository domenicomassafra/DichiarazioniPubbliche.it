"""DP #413: public auto-acceptance policy, independent review, and HOLD retry."""

from dataclasses import replace
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.autonomous_publication import (  # noqa: E402
    AutonomousCandidate,
    AgentReview,
    SpeakerSignal,
    candidate_fingerprint,
    evaluate_autonomous_publication,
)


def candidate() -> AutonomousCandidate:
    return AutonomousCandidate(
        record_id="finding:413",
        record_version_id="finding-version:1",
        source_version="source-version:1",
        rights_attestation_sha256="d" * 64,
        source_url="https://example.org/original-video",
        source_kind="TIMED",
        snapshot_url="https://archive.example.org/20261025/original-video",
        snapshot_sha256="a" * 64,
        source_text_sha256="c" * 64,
        captured_at="2026-10-25T16:00:00+00:00",
        segment_start=21,
        segment_end=25,
        quote="La misura è stata approvata oggi.",
        transcript_segment="La misura è stata approvata oggi.",
        alignment_confidence=0.98,
        speaker_id="person:123",
        speaker_signals=(
            SpeakerSignal("official_channel", "https://example.org/official"),
            SpeakerSignal("diarization", "sha256:" + "b" * 64),
        ),
        public_role_source_url="https://www.wikidata.org/wiki/Q12345",
        public_context_source_url=None,
        person_is_minor=False,
        sensitive_third_party_data=False,
        privacy_cleared=True,
        privacy_citation_url="https://www.garanteprivacy.it/",
        rights_cleared=True,
        rights_citation_url="https://www.normattiva.it/",
        source_length_chars=800,
        contains_editorial_judgment=False,
    )


def reviews(item: AutonomousCandidate) -> tuple[AgentReview, AgentReview]:
    binding = candidate_fingerprint(item)
    stages = ("PROVENANCE", "WORDING", "SPEAKER", "PERSON", "RIGHTS_PRIVACY")
    return (
        AgentReview("agent:primary", "gemini:flash", binding, stages, True),
        AgentReview("agent:independent", "local:reviewer", binding, stages, True),
    )


class AutonomousPublicationTests(unittest.TestCase):
    def test_valid_quote_is_eligible_after_two_models_recheck_same_evidence(self):
        item = candidate()
        result = evaluate_autonomous_publication(item, *reviews(item))
        self.assertEqual(result.disposition, "PUBLISH")
        self.assertEqual(result.reason_codes, ())

    def test_provenance_missing_hash_public_url_or_timestamps_holds(self):
        for update in (
            {"source_url": "http://127.0.0.1/private"},
            {"snapshot_sha256": "missing"},
            {"source_text_sha256": "missing"},
            {"captured_at": "not-a-date"},
            {"segment_end": 21},
        ):
            with self.subTest(update=update):
                item = replace(candidate(), **update)
                self.assertEqual(
                    evaluate_autonomous_publication(item, *reviews(item)).disposition,
                    "HOLD",
                )

    def test_altered_quote_and_weak_alignment_hold(self):
        for update in (
            {"quote": "La misura è stata respinta oggi."},
            {"alignment_confidence": 0.91},
            {"alignment_confidence": True},
        ):
            item = replace(candidate(), **update)
            result = evaluate_autonomous_publication(item, *reviews(item))
            self.assertIn("WORDING", result.reason_codes)

    def test_single_source_of_speaker_claim_is_insufficient(self):
        item = replace(
            candidate(),
            speaker_signals=(
                SpeakerSignal("official_channel", "https://example.org/channel"),
                SpeakerSignal("source_title", "https://example.org/title"),
            ),
        )
        result = evaluate_autonomous_publication(item, *reviews(item))
        self.assertIn("SPEAKER", result.reason_codes)
        same_upload = replace(
            item,
            speaker_signals=(
                SpeakerSignal("official_channel", "https://example.org/channel"),
                SpeakerSignal("source_caption", "https://example.org/captions"),
            ),
        )
        self.assertIn(
            "SPEAKER",
            evaluate_autonomous_publication(same_upload, *reviews(same_upload)).reason_codes,
        )

    def test_minor_sensitive_data_and_uncleared_rights_hold(self):
        for update, reason in (
            ({"person_is_minor": True}, "PERSON"),
            ({"sensitive_third_party_data": True}, "RIGHTS_PRIVACY"),
            ({"rights_cleared": False}, "RIGHTS_PRIVACY"),
            ({"contains_editorial_judgment": True}, "RIGHTS_PRIVACY"),
            ({"source_length_chars": 0}, "RIGHTS_PRIVACY"),
            ({"source_length_chars": True}, "RIGHTS_PRIVACY"),
        ):
            item = replace(candidate(), **update)
            self.assertIn(
                reason,
                evaluate_autonomous_publication(item, *reviews(item)).reason_codes,
            )

    def test_different_people_without_authority_need_public_context_evidence(self):
        item = replace(candidate(), public_role_source_url=None)
        self.assertIn(
            "PERSON", evaluate_autonomous_publication(item, *reviews(item)).reason_codes
        )
        item = replace(item, public_context_source_url="https://example.org/tv-broadcast")
        self.assertEqual(
            evaluate_autonomous_publication(item, *reviews(item)).disposition, "PUBLISH"
        )

    def test_models_must_disagree_never_publish_or_use_same_model(self):
        item = candidate()
        first, second = reviews(item)
        self.assertIn(
            "INDEPENDENT_REVIEW",
            evaluate_autonomous_publication(
                item, first, replace(second, model_id=first.model_id)
            ).reason_codes,
        )
        self.assertIn(
            "INDEPENDENT_REVIEW",
            evaluate_autonomous_publication(
                item, first, replace(second, accepted=False)
            ).reason_codes,
        )
        self.assertIn(
            "INDEPENDENT_REVIEW",
            evaluate_autonomous_publication(
                item, first, replace(second, model_id=first.model_id.upper())
            ).reason_codes,
        )

    def test_rights_dispute_holds_immediately_then_old_reviews_cannot_unhold(self):
        item = candidate()
        first, second = reviews(item)
        self.assertIn(
            "CHALLENGE_HOLD",
            evaluate_autonomous_publication(
                item, first, second, active_challenge=True
            ).reason_codes,
        )
        revised = replace(item, snapshot_sha256="c" * 64)
        self.assertIn(
            "INDEPENDENT_REVIEW",
            evaluate_autonomous_publication(revised, first, second).reason_codes,
        )
        self.assertEqual(
            evaluate_autonomous_publication(revised, *reviews(revised)).disposition,
            "PUBLISH",
        )

    def test_review_fingerprint_expires_on_version_or_rights_change(self):
        item = candidate()
        old_reviews = reviews(item)
        for changed in (
            {"record_version_id": "finding-version:2"},
            {"source_version": "source-version:2"},
            {"rights_attestation_sha256": "e" * 64},
        ):
            with self.subTest(changed=changed):
                current = replace(item, **changed)
                self.assertIn(
                    "INDEPENDENT_REVIEW",
                    evaluate_autonomous_publication(current, *old_reviews).reason_codes,
                )


if __name__ == "__main__":
    unittest.main()
