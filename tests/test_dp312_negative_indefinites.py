"""Prevent source-bound EN/DE negative indefinite utterances from endorsing."""

import hashlib
import unittest

from dichiarazioni_pubbliche.context_integrity import assess_speech_act_context


class NegativeIndefiniteSpeechActTests(unittest.TestCase):
    def test_negative_indefinites_hold_and_preserve_exact_source_binding(self):
        # Support verbs followed by negated targets are not endorsements.
        for source, language in (
            ("I support nothing in this proposal.", "en"),
            ("Ich unterstütze nichts davon.", "de"),
        ):
            with self.subTest(source=source):
                result = assess_speech_act_context(
                    source_text=source,
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    quote_start=0, quote_end=len(source),
                    turn_start=0, turn_end=len(source),
                    utterer_id="person:a", turn_speaker_ids=("person:a",),
                    source_part_ref="part:a", turn_complete=True,
                    language=language,
                )
                self.assertEqual(result.state, "HOLD_FOR_CONTEXT")
                self.assertEqual(result.stance, "UNKNOWN")
                self.assertIn("NEGATION_SCOPE_UNRESOLVED", result.signal_codes)
                self.assertFalse(result.publication_authority)
                replay = result.to_metadata()
                self.assertEqual(replay["source_sha256"], hashlib.sha256(source.encode()).hexdigest())
