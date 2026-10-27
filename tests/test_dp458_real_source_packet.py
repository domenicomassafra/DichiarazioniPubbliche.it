"""DP-458: protect verified EU AVS cue minute and private-only scope."""
from __future__ import annotations

import unittest

from tools import dp458_real_source_packet as packet


class DP458RealSourcePacketTests(unittest.TestCase):
    def test_cue_12_preserves_hours_minutes_seconds(self):
        self.assertEqual(packet.vtt_timestamp_ms("00:01:14.669"), 74669)
        self.assertEqual(packet.vtt_timestamp_ms("00:01:18.940"), 78940)
        self.assertEqual((packet.START, packet.END), (74669, 78940))
        self.assertEqual(packet.END - packet.START, 4271)
        self.assertEqual(packet.VERSION, "dp458-original-source-v2")

    def test_old_seconds_only_extraction_does_not_match_real_cue(self):
        self.assertNotEqual(packet.START, 14669)
        self.assertNotEqual(packet.END, 18940)
        self.assertEqual(packet.vtt_timestamp_ms("00:00:14.669"), 14669)

    def test_invalid_cue_formats_are_not_silently_accepted(self):
        for bad in ("01:14.669", "00:61:14.669", "00:01:61.000",
                    "00:01:14", "-00:01:14.669", "00:01:14.66"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                packet.vtt_timestamp_ms(bad)

    def test_private_use_and_source_revision_are_pinned(self):
        self.assertEqual(packet.CANDIDATE, "statement:dp458:I-293056:cue12")
        self.assertEqual(packet.CANONICAL, "canonical:dp458:I-293056:cue12")
        self.assertEqual(
            packet.ORIGINAL_SHA,
            "225b145412687af1ac0fa7a5f03a010541fcf8cd81be3494418f59614ec57593",
        )
        self.assertEqual(
            packet.VTT_SHA,
            "2de8e201c68ede5735330bfa9f48b87da0ebdddca679f71ffd6be3d0aa58c2de",
        )
        self.assertEqual(packet.sha(packet.QUOTE),
                         "5678722cae3853f90810d5825d8b5a1f1b17592245a3650b179ff67afd840a96")
        self.assertIn("PLAYBACK", packet.USES)
        self.assertIn("ASR_MEDIA", packet.USES)
        self.assertNotIn("EXCERPT_PUBLIC", packet.USES)



    def test_full_persisted_chain_rejects_any_text_or_speaker_drift(self):
        row = {
            "quote": packet.QUOTE, "sha": packet.sha(packet.QUOTE),
            "start": packet.START, "end": packet.END,
            "raw_start": packet.START, "raw_end": packet.END,
            "candidate_version": packet.VERSION,
            "status": "TRANSCRIPT_UNCERTAIN", "blocked": True,
            "candidate_status": "HELD",
            "raw_text": packet.QUOTE, "canonical_text": packet.QUOTE,
            "speaker_id": packet.PERSON, "variant_text": packet.QUOTE,
            "variant_sha": packet.sha(packet.QUOTE),
            "variant_vtt_sha": packet.VTT_SHA,
        }
        packet.verify_source_chain(row)
        for field, bad in (
            ("raw_text", "Not the publisher cue"),
            ("canonical_text", "Not the publisher cue"),
            ("speaker_id", "person:wrong-speaker"),
            ("variant_text", "Tampered source caption"),
            ("variant_sha", "0" * 64),
            ("variant_vtt_sha", "0" * 64),
            ("start", 14669), ("blocked", False),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                RuntimeError, "DP458_STATEMENT_READBACK_FAILED"
            ):
                packet.verify_source_chain({**row, field: bad})

    def test_real_vtt_bytes_hash_and_cue_must_match(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from tools.dp458_cue_correction import CAPTION_NAME, pinned_caption
        raw = (
            "WEBVTT\\n\\n12\\n00:01:14.669 --> 00:01:18.940\\n"
            + packet.QUOTE + "\\n"
        ).replace("\\n", "\n").encode()
        with tempfile.TemporaryDirectory() as temporary:
            location = Path(temporary) / CAPTION_NAME
            location.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            pinned_caption(Path(temporary), expected_sha=digest,
                           expected_start=packet.START, expected_end=packet.END,
                           exact_quote=packet.QUOTE)
            for kwargs in (
                {"expected_sha": "0" * 64},
                {"expected_start": 14669},
                {"exact_quote": "Another transcript"},
            ):
                options = dict(expected_sha=digest, expected_start=packet.START,
                               expected_end=packet.END, exact_quote=packet.QUOTE)
                options.update(kwargs)
                with self.assertRaises(RuntimeError):
                    pinned_caption(Path(temporary), **options)
            location.write_bytes(raw.replace(b"more", b"less"))
            with self.assertRaisesRegex(RuntimeError, "DP458_VTT_VERSION_CHANGED"):
                pinned_caption(Path(temporary), expected_sha=digest,
                               expected_start=packet.START, expected_end=packet.END,
                               exact_quote=packet.QUOTE)

    def test_cas_updates_both_timestamps_in_one_postgres_statement(self):
        import json
        from tools.dp458_cue_correction import correct_persisted_cue
        class FakeStore:
            commands = []
            def run(self, sql, **params):
                self.commands.append(sql)
                if "SELECT json_build_object" in sql:
                    return json.dumps({
                        "hash": packet.sha(packet.QUOTE), "candidate_status": "HELD",
                        "transcript": "TRANSCRIPT_UNCERTAIN", "blocked": True,
                        "binding_count": 0, "start": 14669, "end": 18940,
                        "raw_start": 14669, "raw_end": 18940,
                    })
                return ""
        store=FakeStore()
        correct_persisted_cue(
            store, canonical=packet.CANONICAL, segment=packet.SEGMENT,
            candidate=packet.CANDIDATE, passage=packet.PASSAGE,
            exact_quote_sha=packet.sha(packet.QUOTE),
            start=packet.START, end=packet.END, vtt_sha=packet.VTT_SHA,
            version=packet.VERSION,
        )
        atomic = [sql for sql in store.commands if "DO $dp458$" in sql]
        self.assertEqual(len(atomic), 1)
        self.assertIn("UPDATE canonical_transcript_segment", atomic[0])
        self.assertIn("UPDATE transcript_segment", atomic[0])
        self.assertIn("RAISE EXCEPTION 'DP458_VTT_TIMING_CAS_FAILED'", atomic[0])
        self.assertFalse(any(
            "UPDATE canonical_transcript_segment" in sql and "DO $dp458$" not in sql
            for sql in store.commands
        ))

if __name__ == "__main__":
    unittest.main()
