"""Private DP-312 probe at the official AKN importer and speech-act seams."""

import hashlib
import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.dp331_private_speech_probe import probe_private_speech
from dichiarazioni_pubbliche.senato_akoma_stenographic import import_senato_akoma_stenographic
from tests.test_senato_akoma_stenographic import URL, blob_sha, fixture


def source(text: bytes = b"Un dato: <i>zero</i>."):
    raw = fixture().replace(b"Un dato: <i>zero</i>.", text)
    return import_senato_akoma_stenographic(
        raw, source_raw_url=URL, expected_blob_sha1=blob_sha(raw)
    )


class PrivateSpeechProbeTests(unittest.TestCase):
    def test_official_role_is_a_candidate_and_unreviewed_utterance_stays_held(self):
        imported = source(b"Sostengo questo piano.")
        receipt = probe_private_speech(imported, ordinal=1)
        self.assertEqual(receipt["speech_id"], imported.speeches[1].speech_id)
        self.assertEqual(receipt["utterer_candidate"], imported.speeches[1].official_person_uri)
        self.assertEqual(receipt["source_role_label"], "POTENTI")
        self.assertIsNone(receipt["quoted_author_candidate"])
        self.assertIsNone(receipt["source_author_candidate"])
        self.assertEqual(receipt["speech_act"], "ASSERTION")
        self.assertEqual(receipt["decision"], "HOLD")
        self.assertIn("TURN_COMPLETENESS_UNVERIFIED", receipt["signals"])
        self.assertFalse(receipt["attribution_approved"])
        self.assertFalse(receipt["extraction_authorized"])
        self.assertFalse(receipt["publication_authorized"])
        self.assertNotIn(imported.speeches[1].review_text, repr(receipt))
        self.assertEqual(receipt, probe_private_speech(imported, ordinal=1))

    def test_german_derived_negative_contrast_is_held_without_invented_speaker(self):
        imported = source(b"Sostengo questo piano.")
        receipt = probe_private_speech(
            imported, ordinal=1, german_draft="Ich unterstütze nichts davon.",
            italian_quote_span=(0, len("Sostengo questo piano.")),
        )
        german = receipt["german_draft"]
        self.assertEqual(german["language"], "de")
        self.assertEqual(german["decision"], "HOLD")
        self.assertEqual(german["stance"], "UNKNOWN")
        self.assertIn("NEGATION_SCOPE_UNRESOLVED", german["signals"])
        self.assertIn("UTTERER_PROVENANCE_REQUIRED", german["signals"])
        self.assertEqual(german["translation_review"], "NEEDS_REVIEW")
        self.assertFalse(german["source_wording_approved"])
        self.assertNotEqual(german["context_binding"], receipt["context_binding"])
        self.assertIn("NEGATION_CHANGED", german["translation_risks"])
        self.assertIn("MACHINE_TRANSLATION_REQUIRES_REVIEW", german["translation_risks"])

    def test_italian_quote_span_and_ai_german_question_remain_separate(self):
        text = "Secondo Ada, «Il parere è quindi favorevole?»"
        quote = "Il parere è quindi favorevole?"
        start = text.index(quote)
        receipt = probe_private_speech(
            source(text.encode("utf-8")), ordinal=1,
            italian_quote_span=(start, start + len(quote)),
            german_draft="Ist die Stellungnahme also positiv?",
        )
        german = receipt["german_draft"]
        self.assertEqual(receipt["speech_act"], "REPORT")
        self.assertEqual(receipt["stance"], "NON_COMMITTAL")
        self.assertIsNone(receipt["quoted_author_candidate"])
        self.assertEqual(german["source_quote_start"], start)
        self.assertEqual(german["source_quote_end"], start + len(quote))
        self.assertEqual(
            german["source_quote_sha256"], hashlib.sha256(quote.encode()).hexdigest()
        )
        self.assertEqual(german["speech_act"], "QUESTION")
        self.assertEqual(german["stance"], "NON_COMMITTAL")
        self.assertEqual(german["wording_type"], "TRANSLATION")
        self.assertEqual(german["representation_role"], "DERIVED_REPRESENTATION")
        self.assertEqual(german["translation_method"], "MACHINE")
        self.assertEqual(german["translation_review"], "NEEDS_REVIEW")
        self.assertIn("MACHINE_TRANSLATION_REQUIRES_REVIEW", german["translation_risks"])
        self.assertNotIn("NEGATION_CHANGED", german["translation_risks"])
        self.assertFalse(german["source_wording_approved"])
        self.assertFalse(receipt["attribution_approved"])
        negated = probe_private_speech(
            source(text.encode("utf-8")), ordinal=1,
            italian_quote_span=(start, start + len(quote)),
            german_draft="Ist die Stellungnahme also nicht positiv?",
        )["german_draft"]
        self.assertIn("NEGATION_CHANGED", negated["translation_risks"])
        self.assertEqual(negated["speech_act"], "QUESTION")
        self.assertEqual(negated["decision"], "HOLD")
        self.assertNotEqual(negated["translation_sha256"], german["translation_sha256"])

    def test_german_draft_requires_source_span_with_valid_exact_offsets(self):
        imported = source(b"Sostengo questo piano.")
        for span in (None, (0, 100), (0, 0), (True, 4), (5, 3)):
            with self.subTest(span=span), self.assertRaisesRegex(
                ValueError, "DP331_ITALIAN_QUOTE_SPAN_INVALID"
            ):
                probe_private_speech(
                    imported, ordinal=1, italian_quote_span=span,
                    german_draft="Ich unterstütze diesen Plan.",
                )
        with self.assertRaisesRegex(ValueError, "DP331_ITALIAN_QUOTE_SPAN_REQUIRES_DRAFT"):
            probe_private_speech(imported, ordinal=1, italian_quote_span=(0, 9))

    def test_report_and_ambiguity_do_not_become_author_endorsement(self):
        imported = source("Secondo Ada, «Io sostengo questo piano».".encode("utf-8"))
        receipt = probe_private_speech(imported, ordinal=1)
        self.assertEqual(receipt["speech_act"], "REPORT")
        self.assertEqual(receipt["stance"], "NON_COMMITTAL")
        self.assertIsNone(receipt["quoted_author_candidate"])
        self.assertEqual(receipt["decision"], "HOLD")

    def test_unverified_speaker_or_wrong_ordinal_cannot_be_probed(self):
        imported = source()
        for ordinal in (-1, 2, 100):
            with self.subTest(ordinal=ordinal), self.assertRaisesRegex(
                ValueError, "DP331_SPEECH_NOT_AVAILABLE"
            ):
                probe_private_speech(imported, ordinal=ordinal)

    def test_changed_source_bytes_invalidate_prior_speech_receipt(self):
        imported = source()
        first, second = imported.speeches
        corrupted = replace(
            imported, speeches=(first, replace(second, review_text=second.review_text + " X"))
        )
        with self.assertRaisesRegex(ValueError, "DP331_SPEECH_SOURCE_HASH_MISMATCH"):
            probe_private_speech(corrupted, ordinal=1)

    def test_revision_of_another_turn_changes_occurrence_binding(self):
        before = source()
        raw = fixture().replace(b"<b>inizia</b>", b"<b>termina</b>")
        after = import_senato_akoma_stenographic(
            raw, source_raw_url=URL, expected_blob_sha1=blob_sha(raw)
        )
        first = probe_private_speech(before, ordinal=1)
        revised = probe_private_speech(after, ordinal=1)
        self.assertEqual(first["context_binding"], revised["context_binding"])
        self.assertNotEqual(
            first["source_revision_binding"], revised["source_revision_binding"]
        )


if __name__ == "__main__":
    unittest.main()
