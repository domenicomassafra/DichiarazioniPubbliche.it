"""DP-239 offline source-version and adversarial de→it translation holds."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.corpus_repository import ContentCaptureRecord, PassageRecord  # noqa: E402
from dichiarazioni_pubbliche.multilingual_derivation import (  # noqa: E402
    ActorAnchor, CodeSwitchSpan, build_private_translation, recheck_private_translation,
)
from dichiarazioni_pubbliche.original_source_resolver import (  # noqa: E402
    ExactSourceLocator, ObservedMediaSegment,
)
from dichiarazioni_pubbliche.wording_contract import (  # noqa: E402
    TranslationReviewState, WordingType, assert_direct_quote_eligible,
)


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def written_fixture(text: str = "Anna muss Bruno nicht am 10.11.2026 vor Gericht sehen.") -> dict:
    body = text.encode("utf-8")
    capture = ContentCaptureRecord(
        id="capture:de-v1", content_id="content:history-1",
        observed_at="2026-10-11T00:00:00+00:00",
        final_url="https://example.test/de-original", media_type="text/plain",
        content_sha256=sha(body), retrieval_method="FIXTURE", retrieval_version="fixture-v1",
        parser_method="NATIVE_DOCUMENT_TEXT", parser_version="document-native-text-v1",
        body_ref="private:fixture", rights_status="CLEARED",
        metadata={"parse_status": "SUCCEEDED"},
    )
    passage = PassageRecord(
        id="passage:de-v1", content_id=capture.content_id,
        capture_id=capture.id, selector_type="TEXT_POSITION",
        start_char=0, end_char=len(text), private_text=text,
        text_sha256=sha(text), extraction_method=capture.parser_method,
        extraction_version=capture.parser_version, language="de-Latn-DE",
    )
    locator = ExactSourceLocator(
        content_id=capture.content_id, capture_id=capture.id,
        passage_id=passage.id, selector_type=passage.selector_type,
        quote_start=0, quote_end=len(text), quote_sha256=sha(text),
        capture_sha256=sha(body),
    )
    return {
        "locator": locator, "passage": passage, "capture": capture,
        "source_body": body, "canonical_text": text, "source_text": text,
        "source_language": "de-Latn-DE", "target_language": "it-IT",
        "language_origin": "SOURCE_DECLARED",
        "translated_text": "Anna non deve vedere Bruno in tribunale il 10/11/2026.",
        "source_wording_type": WordingType.VERBATIM_ORIGINAL,
        "actor_anchors": (ActorAnchor("person:anna", "Anna"), ActorAnchor("person:bruno", "Bruno")),
        "provider_id": "OFFLINE_SYNTHETIC_FIXTURE", "model_id": "fixture-translation",
        "model_version": "frozen-v1", "prompt_sha256": sha("fixture prompt"),
        "config_sha256": sha("fixture config"), "derivation_version": "translation-v1",
    }


def build(**updates):
    data = written_fixture()
    if "source_text" in updates:
        text = updates.pop("source_text")
        data = written_fixture(text)
    data.update(updates)
    return build_private_translation(**data)


class DP239TranslationTests(unittest.TestCase):
    def test_original_and_translation_are_distinct_immutable_versions(self):
        row = written_fixture()
        old_original = row["source_text"]
        first = build_private_translation(**row)
        second = build_private_translation(**row)
        self.assertEqual(first, second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.original.source_text, old_original)
        self.assertEqual(first.original.quote_sha256, sha(old_original))
        self.assertEqual(first.original.source_version_sha256, sha(old_original.encode()))
        self.assertEqual(first.original.locator_fingerprint, second.original.locator_fingerprint)
        self.assertEqual(first.original.extraction_version, "document-native-text-v1")
        self.assertIsNone(first.original.original_charset)
        self.assertEqual(first.translated_text_sha256, sha(row["translated_text"]))
        self.assertNotEqual(first.translated_text_sha256, first.original.quote_sha256)
        self.assertEqual(first.wording.wording_type, WordingType.TRANSLATION)
        self.assertEqual(first.wording.source_wording_type, WordingType.VERBATIM_ORIGINAL)
        self.assertEqual(first.wording.source_language, "de-Latn-DE")
        self.assertEqual(first.wording.language, "it-IT")
        self.assertFalse(first.public_quote_eligible)
        self.assertFalse(first.wording.direct_quote_eligible)
        self.assertEqual(first.review_state, TranslationReviewState.NEEDS_REVIEW)
        self.assertEqual(first.status, "HELD")
        self.assertEqual(first.method, "MACHINE")
        self.assertIn("INDEPENDENT_MEANING_ASSURANCE_REQUIRED", first.signal_codes)
        self.assertIn("SOURCE_LANGUAGE_IDENTIFICATION_UNVERIFIED", first.signal_codes)
        self.assertIn("DERIVATIVE_USE_RIGHTS_UNVERIFIED", first.signal_codes)
        self.assertEqual(first.original.speaker_binding_state, "UNVERIFIED")
        with self.assertRaisesRegex(ValueError, "WORDING_DIRECT_QUOTE_FORBIDDEN"):
            assert_direct_quote_eligible(first.wording)
        revision = build_private_translation(**{**row, "translated_text": row["translated_text"].replace("Anna", "Anja")})
        self.assertNotEqual(first.id, revision.id)
        self.assertEqual(first.original, revision.original)
        changed_config = build_private_translation(**{**row, "config_sha256": sha("reconfigured")})
        self.assertNotEqual(first.id, changed_config.id)
        self.assertEqual(first.original, changed_config.original)

    def test_source_version_selector_hash_and_parser_are_bound_fail_closed(self):
        data = written_fixture()
        for modification in (
            {"source_body": b"malicious new version"},
            {"canonical_text": "Anna muss Bruno gehen."},
            {"passage": replace(data["passage"], private_text="Anna anders")},
            {"passage": replace(data["passage"], extraction_version="unreviewed-v2")},
            {"locator": replace(data["locator"], quote_sha256=sha("forged"))},
            {"locator": replace(data["locator"], capture_sha256=sha("changed"))},
            {"capture": replace(data["capture"], content_sha256=sha("changed"))},
            {"current_source_sha256": sha("new source")},
        ):
            with self.subTest(modification=list(modification)):
                with self.assertRaisesRegex(ValueError, "DP239_ORIGINAL_LOCATOR_"):
                    build_private_translation(**{**data, **modification})

    def test_explicit_recheck_detects_stale_current_source_without_mutating_original(self):
        data = written_fixture()
        derivative = build_private_translation(**data)
        keys = {k: data[k] for k in ("locator", "passage", "capture", "source_body", "canonical_text")}
        current = recheck_private_translation(derivative, **keys)
        stale = recheck_private_translation(derivative, **keys, current_source_sha256=sha("new source bytes"))
        self.assertEqual(current.status, "CURRENT")
        self.assertEqual(stale.status, "STALE")
        self.assertEqual(stale.reason_codes, ("LOCATOR_NEWER_SOURCE_VERSION",))
        self.assertEqual(derivative.original.source_version_sha256, data["capture"].content_sha256)
        forged = recheck_private_translation(derivative, **{**keys, "locator": replace(data["locator"], passage_id="wrong")})
        self.assertEqual(forged.status, "BLOCKED")
        altered_extraction = recheck_private_translation(
            derivative, **{**keys, "passage": replace(data["passage"], extraction_version="rewritten-parser")},
        )
        self.assertEqual(altered_extraction.status, "BLOCKED")

    def test_recheck_cannot_mask_rebound_original_as_stale_source(self):
        data = written_fixture()
        derivative = build_private_translation(**data)
        new_passage = replace(data["passage"], id="passage:other")
        new_locator = replace(data["locator"], passage_id=new_passage.id)
        result = recheck_private_translation(
            derivative, locator=new_locator, passage=new_passage,
            capture=data["capture"], source_body=data["source_body"],
            canonical_text=data["canonical_text"],
            current_source_sha256=sha("new current source"),
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.reason_codes, ("TRANSLATION_ORIGINAL_BINDING_CHANGED",))

    def test_german_italian_adversarial_regressions_are_explicit_warnings(self):
        cases = (
            ("Anna hat nicht gestanden.", "Anna ha confessato.", "NEGATION_MISMATCH"),
            ("Anna zahlte 12 Euro.", "Anna ha pagato 21 euro.", "NUMBER_MISMATCH"),
            ("Anna sprach am 10.11.2026.", "Anna ha parlato il 11/11/2026.", "DATE_MISMATCH"),
            ("Anna beschuldigte Bruno.", "Marco ha accusato Bruno.", "ACTOR_ANCHOR_CHANGED"),
            ("Anna beschuldigte Bruno.", "Bruno ha accusato Anna.", "ACTOR_ORDER_CHANGED"),
            ("Anna muss gehen.", "Anna può andare.", "MODALITY_MISMATCH"),
            ("Anna wurde freigesprochen.", "Anna è stata condannata.", "JUDICIAL_STATUS_MISMATCH"),
            ('Anna sagte: „Bruno kommt.“', "Anna arriva con Bruno.", "REPORTED_SPEECH_MISMATCH"),
            ('Anna sagte: „Bruno kommt.“', "Anna ha detto che Bruno arriva.", "QUOTE_MARKER_MISMATCH"),
        )
        for index, (original, italian, expected) in enumerate(cases):
            with self.subTest(case=index, expected=expected):
                row = written_fixture(original)
                row["translated_text"] = italian
                row["actor_anchors"] = tuple(
                    ActorAnchor(f"person:{name.lower()}", name)
                    for name in ("Anna", "Bruno") if name in original
                )
                derived = build_private_translation(**row)
                self.assertIn(expected, derived.signal_codes)
                self.assertEqual(derived.status, "HELD")
                self.assertFalse(derived.public_quote_eligible)

    def test_negation_date_number_modality_and_status_matching_are_only_lexical(self):
        row = written_fixture()
        derived = build_private_translation(**row)
        for mismatch in ("NEGATION_MISMATCH", "DATE_MISMATCH", "NUMBER_MISMATCH",
                         "MODALITY_MISMATCH", "JUDICIAL_STATUS_MISMATCH"):
            self.assertNotIn(mismatch, derived.signal_codes)
        self.assertIn("NEGATION_SCOPE_UNVERIFIED", derived.signal_codes)
        self.assertIn("ACTOR_GRAMMATICAL_ROLE_UNVERIFIED", derived.signal_codes)
        self.assertEqual(derived.review_state, TranslationReviewState.NEEDS_REVIEW)

    def test_german_italian_number_check_preserves_sign_and_decimal_magnitude(self):
        cases = (
            ("Anna zahlte -12 Euro.", "Anna ha pagato 12 euro.", True),
            ("Anna zahlte 1.200 Euro.", "Anna ha pagato 12,00 euro.", True),
            ("Anna zahlte 1.200 Euro.", "Anna ha pagato 1200 euro.", False),
            ("Anna zahlte 1,20 Euro.", "Anna ha pagato 1,2 euro.", False),
            ("Anna zahlte -12% Zinsen.", "Anna ha pagato 12% interessi.", True),
        )
        for original, translated, mismatch in cases:
            with self.subTest(original=original, translated=translated):
                row = written_fixture(original)
                row["translated_text"] = translated
                row["actor_anchors"] = (ActorAnchor("person:anna", "Anna"),)
                derivative = build_private_translation(**row)
                self.assertEqual("NUMBER_MISMATCH" in derivative.signal_codes, mismatch)
                self.assertEqual(derivative.status, "HELD")
        ambiguous = build(
            source_text="Anna zahlte 1.20 Euro.",
            translated_text="Anna ha pagato 1,20 euro.",
            actor_anchors=(ActorAnchor("person:anna", "Anna"),),
        )
        self.assertIn("NUMBER_UNPARSED_OR_AMBIGUOUS", ambiguous.signal_codes)

    def test_named_month_date_and_unmapped_semantics_are_held(self):
        row = written_fixture("Anna sprach am 4. Mai 2026.")
        row["translated_text"] = "Anna ha parlato il 4 maggio 2026."
        row["actor_anchors"] = (ActorAnchor("person:anna", "Anna"),)
        derived = build_private_translation(**row)
        self.assertIn("DATE_UNPARSED_OR_AMBIGUOUS", derived.signal_codes)
        self.assertEqual(derived.status, "HELD")

    def test_bcp47_script_claims_are_checked_and_never_language_detection(self):
        row = written_fixture()
        row["source_language"] = "de-Cyrl-DE"
        row["passage"] = replace(row["passage"], language="de-Cyrl-DE")
        derived = build_private_translation(**row)
        self.assertIn("SOURCE_SCRIPT_MISMATCH", derived.signal_codes)
        self.assertIn("LANGUAGE_PAIR_RISK_RULE_UNAVAILABLE", derived.signal_codes)
        row = written_fixture()
        row["target_language"] = "it-Cyrl-IT"
        derived = build_private_translation(**row)
        self.assertIn("TARGET_SCRIPT_MISMATCH", derived.signal_codes)
        self.assertEqual(derived.review_state, TranslationReviewState.NEEDS_REVIEW)

    def test_reported_quote_provenance_cannot_be_upgraded_to_own_words(self):
        row = written_fixture('Anna sagte: „Bruno hat nicht gesprochen.“')
        row["translated_text"] = 'Anna ha detto: «Bruno non ha parlato.»'
        row["source_wording_type"] = WordingType.REPORTED_QUOTE
        row["actor_anchors"] = (ActorAnchor("person:anna", "Anna"), ActorAnchor("person:bruno", "Bruno"))
        translated = build_private_translation(**row)
        self.assertEqual(translated.wording.source_wording_type, WordingType.REPORTED_QUOTE)
        self.assertIn("QUOTED_SPEAKER_ENDORSEMENT_UNVERIFIED", translated.signal_codes)
        self.assertNotIn("QUOTE_MARKER_MISMATCH", translated.signal_codes)

    def test_unknown_or_unsupported_language_is_private_held_with_explicit_state(self):
        pairs = (
            {"source_language": "und", "passage": replace(written_fixture()["passage"], language="und"),
             "language_origin": "UNKNOWN"},
            {"source_language": "de-Latn-DE", "language_origin": "INFERRED_UNREVIEWED"},
            {"source_language": "de-Latn-DE", "target_language": "fr-FR"},
        )
        for item in pairs:
            with self.subTest(item=item):
                row = written_fixture()
                row.update(item)
                translated = build_private_translation(**row)
                self.assertEqual(translated.status, "HELD")
                self.assertIn("LANGUAGE_PAIR_RISK_RULE_UNAVAILABLE", translated.signal_codes)
                self.assertFalse(translated.public_quote_eligible)

    def test_explicit_code_switch_and_script_mismatch_hold_without_guessing_italian(self):
        original = "Anna sagte nein. Poi Marco rispose."
        row = written_fixture(original)
        row["translated_text"] = "Anna ha detto no. Poi Marco rispose."
        row["actor_anchors"] = ()
        row["language_origin"] = "MIXED_DECLARED"
        middle = original.index(" Poi")
        row["code_switch_spans"] = (
            CodeSwitchSpan(0, middle, "de-DE"),
            CodeSwitchSpan(middle, len(original), "it-IT"),
        )
        derived = build_private_translation(**row)
        self.assertIn("CODE_SWITCH_UNRESOLVED", derived.signal_codes)
        self.assertIn("LANGUAGE_PAIR_RISK_RULE_UNAVAILABLE", derived.signal_codes)
        row["code_switch_spans"] = (CodeSwitchSpan(0, middle + 3, "de"),)
        with self.assertRaisesRegex(ValueError, "DP239_CODE_SWITCH_DISCONTINUOUS"):
            build_private_translation(**row)
        cyrillic = written_fixture("Анна muss nicht gehen.")
        cyrillic["translated_text"] = "Anna non deve andare."
        cyrillic["actor_anchors"] = ()
        with self.assertRaisesRegex(ValueError, "DP239_PASSAGE_LANGUAGE_CONFLICT"):
            build_private_translation(**{**cyrillic, "source_language": "ru"})
        derived = build_private_translation(**cyrillic)
        self.assertIn("SCRIPT_UNKNOWN_OR_MIXED", derived.signal_codes)
        self.assertIn("SOURCE_SCRIPT_MISMATCH", derived.signal_codes)

    def test_invalid_bcp47_and_actor_anchor_hold(self):
        row = written_fixture()
        for new_value in ("de_XX", "x", "de-DE-invalid-verylongvariant", "de-Latn-"):
            with self.subTest(language=new_value):
                with self.assertRaisesRegex(ValueError, "DP239_SOURCE_LANGUAGE_BCP47_INVALID"):
                    build_private_translation(**{**row, "source_language": new_value})
        for anchors in (
            (ActorAnchor("person:duplicate", "Anna"), ActorAnchor("person:duplicate", "Bruno")),
            (ActorAnchor("person:absent", "Claudia"),),
        ):
            with self.subTest(anchors=anchors):
                with self.assertRaisesRegex(ValueError, "DP239_(?:SOURCE_)?ACTOR_ANCHOR_"):
                    build_private_translation(**{**row, "actor_anchors": anchors})

    def test_translated_text_and_config_cannot_upgrade_to_fake_review(self):
        row = written_fixture()
        with self.assertRaises(TypeError):
            build_private_translation(**row, human_reviewed=True)
        with self.assertRaises(TypeError):
            build_private_translation(**row, reviewer_ref="fake:review")
        with self.assertRaisesRegex(ValueError, "DP239_PROMPT_SHA256_INVALID"):
            build_private_translation(**{**row, "prompt_sha256": "invalid"})
        with self.assertRaisesRegex(ValueError, "DP239_TEXT_INVALID_OR_OVERSIZE"):
            build_private_translation(**{**row, "translated_text": "t" * 8193})

    def test_media_variant_version_and_speaker_locked_without_fabricated_attribution(self):
        segment_text = "Anna sagte nicht zu."
        variant_text = "Intro. " + segment_text + " Ende."
        segment = ObservedMediaSegment(
            content_id="content:media", canonical_segment_id="canonical:1",
            transcript_variant_id="transcript:v3", transcript_variant_sha256=sha(variant_text),
            source_segment_id="segment:s3", source_segment_sha256=sha(segment_text),
            variant_text=variant_text, segment_text=segment_text,
            variant_start_char=7, variant_end_char=7 + len(segment_text),
            start_ms=1000, end_ms=2400, speaker_person_id="person:anna",
        )
        passage = PassageRecord(
            id="passage:media", content_id=segment.content_id,
            selector_type="MEDIA_SEGMENT_REF", canonical_segment_id=segment.canonical_segment_id,
            private_text=segment_text, text_sha256=sha(segment_text),
            extraction_method="TRANSCRIPT", extraction_version="transcript-v3", language="de",
        )
        locator = ExactSourceLocator(
            content_id=segment.content_id, passage_id=passage.id,
            selector_type="MEDIA_SEGMENT_REF", quote_start=0,
            quote_end=len(segment_text), quote_sha256=sha(segment_text),
            canonical_segment_id=segment.canonical_segment_id,
            transcript_variant_id=segment.transcript_variant_id,
            transcript_variant_sha256=segment.transcript_variant_sha256,
            source_segment_id=segment.source_segment_id,
            source_segment_sha256=segment.source_segment_sha256,
            start_ms=1000, end_ms=2400, speaker_person_id=segment.speaker_person_id,
        )
        row = written_fixture()
        row.update(locator=locator, passage=passage, capture=None,
                   source_body=None, canonical_text=None, media_segment=segment,
                   source_text=segment_text, source_language="de", translated_text="Anna non ha acconsentito.",
                   actor_anchors=(ActorAnchor("person:anna", "Anna"),))
        derivative = build_private_translation(**row)
        self.assertEqual(derivative.original.speaker_person_id, "person:anna")
        self.assertIn("SPEAKER_REVIEW_AUTHORITY_UNVERIFIED", derivative.signal_codes)
        with self.assertRaisesRegex(ValueError, "DP239_ORIGINAL_LOCATOR_LOCATOR_MEDIA_SPEAKER_MISMATCH"):
            build_private_translation(**{**row, "locator": replace(locator, speaker_person_id="person:other")})
        with self.assertRaisesRegex(ValueError, "DP239_ORIGINAL_LOCATOR_LOCATOR_MEDIA_VERSION_MISMATCH"):
            build_private_translation(**{**row, "media_segment": replace(segment, transcript_variant_sha256=sha("new"))})


if __name__ == "__main__":
    unittest.main()
