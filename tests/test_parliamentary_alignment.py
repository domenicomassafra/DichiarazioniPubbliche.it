import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.parliamentary_alignment import (  # noqa: E402
    MediaSegment,
    ParliamentaryIntervention,
    align_parliamentary_intervention,
)


def intervention(**overrides):
    values = {
        "intervention_id": "camera:intervention:1",
        "session_id": "camera:session:1",
        "official_speaker_ref": "camera:deputy:123",
        "official_speaker_name": "Mario Rossi",
        "transcript_text": "Non aumenteremo le tasse.",
        "source_url": "https://www.camera.it/example",
        "source_version": "camera-record-v1",
        "speaker_person_id": "person:mario-rossi",
        "speaker_resolution_approved": True,
    }
    values.update(overrides)
    return ParliamentaryIntervention(**values)


class ParliamentaryAlignmentTests(unittest.TestCase):
    def test_official_timing_is_direct_locator(self):
        result = align_parliamentary_intervention(
            intervention(official_start_ms=1000, official_end_ms=3500)
        )
        self.assertTrue(result.direct_official)
        self.assertEqual(result.method, "OFFICIAL_MEDIA_RANGE")
        self.assertEqual((result.start_ms, result.end_ms), (1000, 3500))

    def test_unapproved_speaker_keeps_official_locator_but_holds_attribution(self):
        result = align_parliamentary_intervention(
            intervention(
                speaker_person_id=None,
                speaker_resolution_approved=False,
                official_start_ms=1000,
                official_end_ms=3500,
            )
        )
        self.assertEqual(result.status, "ATTRIBUTION_HOLD")
        self.assertIn("SPEAKER_RESOLUTION_NOT_APPROVED", result.blockers)
        self.assertIsNone(result.speaker_person_id)

    def test_exact_text_alignment_is_only_review_candidate(self):
        result = align_parliamentary_intervention(
            intervention(),
            [
                MediaSegment("s1", 1000, 2000, "Non aumenteremo", "media-v1"),
                MediaSegment("s2", 2000, 3000, "le tasse.", "media-v1"),
            ],
        )
        self.assertEqual(result.status, "REVIEW_CANDIDATE")
        self.assertEqual(result.segment_ids, ("s1", "s2"))
        self.assertIn("TEXT_ALIGNMENT_REQUIRES_REVIEW", result.blockers)

    def test_repeated_identical_text_is_ambiguous(self):
        result = align_parliamentary_intervention(
            intervention(transcript_text="Grazie."),
            [
                MediaSegment("s1", 1000, 1500, "Grazie.", "media-v1"),
                MediaSegment("s2", 3000, 3500, "Grazie.", "media-v1"),
            ],
        )
        self.assertEqual(result.status, "UNRESOLVED")
        self.assertIn("AMBIGUOUS_TEXT_ALIGNMENT", result.blockers)

    def test_no_match_never_invents_timestamp(self):
        result = align_parliamentary_intervention(
            intervention(),
            [MediaSegment("s1", 1000, 2000, "Testo differente.", "media-v1")],
        )
        self.assertEqual(result.status, "UNRESOLVED")
        self.assertIsNone(result.start_ms)
        self.assertIsNone(result.end_ms)
        self.assertIn("NO_TEXT_ALIGNMENT", result.blockers)


if __name__ == "__main__":
    unittest.main()
