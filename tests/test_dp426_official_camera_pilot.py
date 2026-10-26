"""DP-420A: original Camera text is the only source of private passages."""
from __future__ import annotations

import hashlib
import unittest

from dichiarazioni_pubbliche.garlasco_camera_pilot import (
    CAMERA_SOURCES, CameraSpeechParser, pinned_excerpt,
)
from dichiarazioni_pubbliche.source_watcher import FetchedBytes


class CameraGarlascoPilotTests(unittest.TestCase):
    def fetched(self, body: str) -> FetchedBytes:
        encoded = body.encode()
        return FetchedBytes(body=encoded, final_url=CAMERA_SOURCES[0]["url"],
                            status_code=200, media_type="text/html", charset="utf-8",
                            content_length=len(encoded))

    def test_exact_official_speech_becomes_one_verifiable_passage(self):
        source = CAMERA_SOURCES[0]
        body = (f"<p>VITTORIA BALDINO (M5S). Testo reale.</p>"
                f"<p>{source['excerpt']}</p>")
        result = CameraSpeechParser(source).parse(self.fetched(body))
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(len(result.spans), 1)
        self.assertEqual(result.spans[0].text, source["excerpt"])
        self.assertEqual(result.canonical_text[result.spans[0].start_char:
                                                result.spans[0].end_char], source["excerpt"])
        self.assertEqual(result.spans[0].text_sha256,
                         hashlib.sha256(source["excerpt"].encode()).hexdigest())

    def test_missing_speaker_and_changed_quote_fail_closed(self):
        source = CAMERA_SOURCES[0]
        self.assertEqual(CameraSpeechParser(source).parse(
            self.fetched(f"<p>{source['excerpt']}</p>")).status, "FAILED")
        self.assertEqual(CameraSpeechParser(source).parse(
            self.fetched(f"<p>{source['speaker']}</p><p>{source['excerpt'][:-3]}</p>")
        ).status, "FAILED")

    def test_duplicate_quotation_rejected(self):
        source = CAMERA_SOURCES[0]
        body = f"<p>{source['speaker']} {source['excerpt']} {source['excerpt']}</p>"
        self.assertEqual(CameraSpeechParser(source).parse(self.fetched(body)).status, "FAILED")

    def test_intervening_different_speaker_is_not_attributed_to_original(self):
        source = CAMERA_SOURCES[0]
        speaker = source["speaker"]
        excerpt = source["excerpt"]
        body = (
            f"<p>{speaker} Inizio intervento.</p>"
            "<p>CARLO ROSSI (PD-IDP). Intervento differente.</p>"
            f"<p>{excerpt}</p>"
        )
        result = CameraSpeechParser(source).parse(self.fetched(body))
        self.assertEqual(result.status, "FAILED")

    def test_pinned_excerpt_requires_exact_single_source_occurrence(self):
        source = CAMERA_SOURCES[1]
        self.assertEqual(pinned_excerpt(source, source["speaker"] + " " + source["excerpt"]),
                         source["excerpt"])
        with self.assertRaises(ValueError):
            pinned_excerpt(source, source["excerpt"])


if __name__ == "__main__":
    unittest.main()
