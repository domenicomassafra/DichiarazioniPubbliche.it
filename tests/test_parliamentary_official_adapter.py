from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.parliamentary_official_adapter import (  # noqa: E402
    normalize_parliamentary_official_record,
    normalize_parliamentary_official_records,
)
from tests.parliamentary_official_fixture import (  # noqa: E402
    parliamentary_official_fixture_records,
)


def fixture_records():
    return parliamentary_official_fixture_records()


class ParliamentaryOfficialAdapterTests(unittest.TestCase):
    def test_offline_fixture_preserves_two_official_speakers_without_cross_attribution(self):
        records = normalize_parliamentary_official_records(fixture_records())
        self.assertEqual(len(records), 2)
        by_statement = {row.statement_id: row for row in records}
        first = by_statement["camera:statement:2026-10-05:101:1"]
        second = by_statement["camera:statement:2026-10-05:101:2"]
        self.assertEqual(first.speaker.speaker_id, "camera:deputy:123")
        self.assertEqual(second.speaker.speaker_id, "camera:deputy:456")
        self.assertNotEqual(first.speaker.speaker_id, second.speaker.speaker_id)

    def test_platform_account_never_overrides_official_speaker(self):
        raw = copy.deepcopy(fixture_records()[1])
        raw["platform_author"] = "Completely Different Account"
        row = normalize_parliamentary_official_record(raw)
        self.assertEqual(row.speaker.speaker_id, "camera:deputy:456")
        self.assertEqual(row.speaker.speaker_name, "Anna Bianchi")

    def test_missing_official_speaker_fails_even_if_platform_author_exists(self):
        raw = copy.deepcopy(fixture_records()[0])
        del raw["speaker"]["id"]
        raw["platform_author"] = "Mario Rossi"
        with self.assertRaisesRegex(ValueError, "SPEAKER_ID_REQUIRED"):
            normalize_parliamentary_official_record(raw)

    def test_explicit_video_timing_is_preserved_without_inference(self):
        row = normalize_parliamentary_official_record(fixture_records()[0])
        self.assertEqual((row.video.start_ms, row.video.end_ms), (120000, 127500))
        raw = copy.deepcopy(fixture_records()[0])
        raw.pop("video")
        without = normalize_parliamentary_official_record(raw)
        self.assertIsNone(without.video)

    def test_video_range_must_be_explicit_and_complete(self):
        raw = copy.deepcopy(fixture_records()[0])
        raw["video"].pop("end_ms")
        with self.assertRaisesRegex(ValueError, "VIDEO_RANGE_INCOMPLETE"):
            normalize_parliamentary_official_record(raw)

    def test_official_transcript_stays_separate_from_platform_asr_variants(self):
        row = normalize_parliamentary_official_record(fixture_records()[0])
        self.assertEqual(
            row.transcript.variant_refs,
            ("platform-caption:camera-101", "asr:camera-101:whisper"),
        )
        self.assertEqual(row.transcript.statement_text, "Non aumenteremo le tasse.")

    def test_agenda_context_is_preserved_separately_from_statement(self):
        row = normalize_parliamentary_official_record(fixture_records()[0])
        self.assertEqual(row.session.agenda_item_id, "camera:agenda:2026-10-05:tax")
        self.assertEqual(row.session.agenda_label, "Interrogazioni a risposta immediata")
        self.assertNotIn(row.session.agenda_label, row.transcript.statement_text)

    def test_replay_identity_and_provenance_are_deterministic_and_exact_duplicates_dedupe(self):
        raw = fixture_records()[0]
        first = normalize_parliamentary_official_record(raw)
        second = normalize_parliamentary_official_record(copy.deepcopy(raw))
        self.assertEqual(first.record_id, second.record_id)
        self.assertEqual(first.provenance_id, second.provenance_id)
        self.assertEqual(len(normalize_parliamentary_official_records([raw, copy.deepcopy(raw)])), 1)

    def test_same_statement_id_with_changed_material_is_replay_conflict(self):
        raw = fixture_records()[0]
        changed = copy.deepcopy(raw)
        changed["video"]["end_ms"] = 127600
        with self.assertRaisesRegex(ValueError, "REPLAY_CONFLICT"):
            normalize_parliamentary_official_records([raw, changed])

    def test_chamber_mismatch_fails_closed(self):
        raw = copy.deepcopy(fixture_records()[0])
        raw["chamber"] = "SENATO"
        with self.assertRaisesRegex(ValueError, "CHAMBER_MISMATCH"):
            normalize_parliamentary_official_record(raw)

    def test_date_mismatch_fails_closed(self):
        raw = copy.deepcopy(fixture_records()[0])
        raw["statement"]["date"] = "2026-10-06"
        with self.assertRaisesRegex(ValueError, "STATEMENT_DATE_MISMATCH"):
            normalize_parliamentary_official_record(raw)

    def test_speaker_mismatch_fails_closed(self):
        raw = copy.deepcopy(fixture_records()[0])
        raw["statement"]["speaker_id"] = "camera:deputy:456"
        with self.assertRaisesRegex(ValueError, "STATEMENT_SPEAKER_MISMATCH"):
            normalize_parliamentary_official_record(raw)

    def test_statement_span_mismatch_fails_closed(self):
        raw = copy.deepcopy(fixture_records()[0])
        raw["statement"]["start_char"] = 14
        with self.assertRaisesRegex(ValueError, "STATEMENT_SPAN_MISMATCH"):
            normalize_parliamentary_official_record(raw)

    def test_http_and_wrong_chamber_urls_are_refused(self):
        raw = copy.deepcopy(fixture_records()[0])
        raw["transcript"]["url"] = "http://www.camera.it/unsafe"
        with self.assertRaisesRegex(ValueError, "HTTPS_REQUIRED"):
            normalize_parliamentary_official_record(raw)
        raw = copy.deepcopy(fixture_records()[0])
        raw["video"]["url"] = "https://www.senato.it/video/101"
        with self.assertRaisesRegex(ValueError, "CHAMBER_MISMATCH"):
            normalize_parliamentary_official_record(raw)

    def test_record_contract_has_no_publication_or_review_authority(self):
        row = normalize_parliamentary_official_record(fixture_records()[0])
        fields = set(row.__dataclass_fields__)
        self.assertTrue(
            {
                "publication_status",
                "publication_authorized",
                "approved",
                "review_status",
                "assessment",
                "verdict",
            }.isdisjoint(fields)
        )


if __name__ == "__main__":
    unittest.main()
