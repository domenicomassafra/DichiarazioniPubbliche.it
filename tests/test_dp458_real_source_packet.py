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


if __name__ == "__main__":
    unittest.main()
