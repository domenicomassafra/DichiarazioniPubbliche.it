import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.remote_asr import (  # noqa: E402
    AsrRequestRejected,
    GroqUrlTranscriber,
    parse_groq_verbose_response,
)


class RemoteAsrTests(unittest.TestCase):
    def test_verbose_response_requires_timestamped_segments(self):
        with self.assertRaises(AsrRequestRejected):
            parse_groq_verbose_response(
                {"text": "ciao"},
                provider_id="groq-whisper-large-v3-turbo",
                model_id="whisper-large-v3-turbo",
            )

    def test_verbose_response_normalizes_segments(self):
        result = parse_groq_verbose_response(
            {
                "text": "Ciao mondo",
                "language": "it",
                "duration": 2.5,
                "segments": [
                    {"start": 0.0, "end": 1.1, "text": "Ciao"},
                    {"start": 1.1, "end": 2.5, "text": "mondo"},
                ],
                "x_groq": {"id": "req-test"},
            },
            provider_id="groq-whisper-large-v3-turbo",
            model_id="whisper-large-v3-turbo",
        )
        self.assertEqual(result.request_id, "req-test")
        self.assertEqual(result.segments[1].start_ms, 1100)
        self.assertEqual(result.duration_seconds, 2.5)

    def test_groq_4xx_does_not_persist_upstream_error_body_in_exception(self):
        body = b'{"error":"signed-url=https://secret.example/token?key=abc"}'
        error = urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            400,
            "bad request",
            {},
            io.BytesIO(body),
        )
        transcriber = GroqUrlTranscriber("test-key")
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(
                AsrRequestRejected,
                r"^GROQ_REQUEST_REJECTED:400$",
            ) as caught:
                transcriber.transcribe_url("https://media.example/audio.mp3")
        self.assertNotIn("secret.example", str(caught.exception))
        self.assertNotIn("key=abc", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
