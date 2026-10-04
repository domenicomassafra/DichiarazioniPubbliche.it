import json
import tempfile
import unittest
from pathlib import Path

from dichiarazioni_pubbliche.timestamp_acceptance import (
    DEFAULT_AUDIT,
    DEFAULT_TRANSCRIPT,
    acceptance_summary,
    load_fixture_acceptance,
    parse_media_timestamp,
)


class TimestampAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture_acceptance(DEFAULT_AUDIT, DEFAULT_TRANSCRIPT)

    def test_strict_timestamp_parser(self):
        self.assertEqual(parse_media_timestamp("0:00"), 0)
        self.assertEqual(parse_media_timestamp("7:04"), 424_000)
        self.assertEqual(parse_media_timestamp("1:02:03.250"), 3_723_250)
        for invalid in (None, "", "-1:00", "0:60", "nope"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    parse_media_timestamp(invalid)

    def test_real_fixture_accepts_84_segments_and_36_claims(self):
        summary = acceptance_summary(self.fixture)
        self.assertEqual(summary["segment_count"], 84)
        self.assertEqual(summary["claim_count"], 36)
        self.assertEqual(summary["provider_call_count"], 0)
        self.assertEqual(summary["live_lane"], "BLOCKED_BY_DP_202")
        self.assertGreaterEqual(summary["claim_segment_edge_count"], 36)

    def test_every_claim_maps_timestamp_to_its_segment_range(self):
        for claim in self.fixture.claims:
            self.assertTrue(claim.segment_ids)
            self.assertGreaterEqual(claim.source_timestamp_ms, claim.start_ms - 500)
            self.assertLessEqual(claim.source_timestamp_ms, claim.end_ms + 500)
            self.assertGreaterEqual(claim.start_ms, 0)
            self.assertLessEqual(claim.end_ms, self.fixture.duration_ms)

    def test_inserted_clip_is_not_attributed_to_narrator(self):
        inserted = [s for s in self.fixture.segments if 414_000 <= s.start_ms <= 434_000]
        self.assertTrue(inserted)
        self.assertEqual({s.speaker for s in inserted}, {"Giorgia Meloni (inserted clip)"})

    def test_numeric_secondary_asr_claims_remain_identified(self):
        numeric = {c.fixture_claim_id for c in self.fixture.claims if c.numeric_sensitive}
        self.assertTrue({"C07", "C08", "C09"}.issubset(numeric))

    def test_missing_timestamp_is_not_defaulted_to_zero(self):
        original = json.loads(DEFAULT_AUDIT.read_text())
        original["claims"][1].pop("timestamp", None)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "audit.json"
            path.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, "TIMESTAMP_MISSING"):
                load_fixture_acceptance(path, DEFAULT_TRANSCRIPT)

    def test_out_of_window_timestamp_is_held(self):
        original = json.loads(DEFAULT_AUDIT.read_text())
        original["claims"][1]["timestamp"] = "7:20"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "audit.json"
            path.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, "TIMESTAMP_UNVERIFIED"):
                load_fixture_acceptance(path, DEFAULT_TRANSCRIPT)

    def test_claim_ids_are_stable_on_replay(self):
        replay = load_fixture_acceptance(DEFAULT_AUDIT, DEFAULT_TRANSCRIPT)
        self.assertEqual(
            [claim.claim_id for claim in self.fixture.claims],
            [claim.claim_id for claim in replay.claims],
        )


if __name__ == "__main__":
    unittest.main()
