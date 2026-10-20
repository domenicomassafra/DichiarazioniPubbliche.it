import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.caption_adapter import (
    caption_stats,
    parse_chapters,
    parse_transcript_api_snippets,
    parse_youtube_json3,
)


class CaptionAdapterTests(unittest.TestCase):
    def test_transcript_api_manual_and_automatic_seconds_to_milliseconds(self):
        # Purely synthetic donor-shaped fixtures; no platform words or traffic.
        fixtures = (
            ([{"text": "Città &amp; scuola", "start": 0.125, "duration": 1.250},
              {"text": "Seconda frase", "start": 1.375, "duration": 2.0}],
             [(125, 1375, "Città & scuola"), (1375, 3375, "Seconda frase")]),
            ([{"text": "Primo auto", "start": 0.0025, "duration": 0.998}],
             [(3, 1001, "Primo auto")]),
        )
        for payload, expected in fixtures:
            with self.subTest(payload=payload):
                observed = parse_transcript_api_snippets(payload)
                self.assertEqual(
                    [(s.start_ms, s.end_ms, s.text) for s in observed], expected
                )

    def test_transcript_api_invalid_timing_fails_closed(self):
        valid = {"text": "frase", "start": 1, "duration": 1}
        for rows in (
            [], [{**valid, "start": -1}], [{**valid, "duration": 0}],
            [{**valid, "start": "NaN"}],
            [valid, {**valid, "start": 1.5}],
            [{**valid, "start": 2}, valid],
            [{**valid, "text": "  "}],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                parse_transcript_api_snippets(rows)

    def test_parse_youtube_json3_and_drop_exact_rolling_duplicate(self):
        payload = {
            "events": [
                {
                    "tStartMs": 1000,
                    "dDurationMs": 2000,
                    "segs": [{"utf8": "Il gettito è "}, {"utf8": "7,5 miliardi"}],
                },
                {
                    "tStartMs": 1500,
                    "dDurationMs": 2000,
                    "segs": [{"utf8": "Il gettito è 7,5 miliardi"}],
                },
                {
                    "tStartMs": 4000,
                    "dDurationMs": 1000,
                    "segs": [{"utf8": "poi cambia."}],
                },
            ]
        }
        rows = parse_youtube_json3(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].text, "Il gettito è 7,5 miliardi")
        self.assertEqual(rows[1].segment_index, 1)

    def test_caption_stats_marks_sensitive_numeric_segments(self):
        payload = {
            "events": [
                {
                    "tStartMs": 0,
                    "dDurationMs": 1000,
                    "segs": [{"utf8": "Parliamo del tema."}],
                },
                {
                    "tStartMs": 1000,
                    "dDurationMs": 1000,
                    "segs": [{"utf8": "Sono 2,3 miliardi."}],
                },
            ]
        }
        stats = caption_stats(parse_youtube_json3(payload))
        self.assertEqual(stats["segment_count"], 2)
        self.assertEqual(stats["sensitive_segment_count"], 1)

    def test_parse_pulp_style_chapters(self):
        description = """
Minutaggio:
0:00 introduzione ospite
14:45 Vannacci e ritorno del Nazionalismo
1:02:15 il giornalismo oggi
"""
        chapters = parse_chapters(description)
        self.assertEqual([row.start_seconds for row in chapters], [0, 885, 3735])
        self.assertEqual(chapters[-1].title, "il giornalismo oggi")


if __name__ == "__main__":
    unittest.main()
