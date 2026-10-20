"""DP-239: double AI meaning assurance cannot grant public authority."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.multilingual_derivation import build_private_translation  # noqa: E402
from dichiarazioni_pubbliche.multilingual_ai_review import (  # noqa: E402
    AITranslationReview, evaluate_ai_translation_reviews,
)
from tests.test_dp239_multilingual_derivation import written_fixture  # noqa: E402


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def reviews(derivation):
    def one(stage: str, provider: str, model: str):
        return AITranslationReview(
            reviewer_id=stage, provider_id=provider, model_id=model,
            model_version="1", prompt_sha256=digest(stage + "-prompt"),
            config_sha256=digest(stage + "-config"),
            response_sha256=digest(stage + "-output"),
            translation_id=derivation.id,
            original_quote_sha256=derivation.original.quote_sha256,
            source_version_sha256=derivation.original.source_version_sha256,
            translated_text_sha256=derivation.translated_text_sha256,
            source_language=derivation.original.language,
            target_language=derivation.target_language,
            rights_receipt_sha256=digest("synthetic-unlicensed-rights"),
            license_ref="synthetic:license-not-cleared",
            observed_at="2026-10-19T12:00:00+00:00",
            retention_until="2026-11-19T12:00:00+00:00",
            verdict="FAITHFUL", meaning_risks=(),
        )
    return (one("ai-primary", "review-provider-a", "model-a"),
            one("ai-independent", "review-provider-b", "model-b"))


NOW = lambda: datetime(2026, 10, 20, tzinfo=timezone.utc)


def assess(translation, evidence, **kwargs):
    return evaluate_ai_translation_reviews(
        translation, evidence, now=NOW(),
        independent_receipt_check=lambda _: True,
        rights_receipt_check=lambda _: True,
        **kwargs,
    )


class DoubleAIReviewTests(unittest.TestCase):
    def setUp(self):
        self.translation = build_private_translation(**written_fixture())
        self.evidence = reviews(self.translation)

    def test_two_distinct_attested_models_are_only_private_contract_evidence(self):
        result = assess(self.translation, self.evidence)
        self.assertEqual(result.status, "CONTRACT_ONLY_PRIVATE_HOLD")
        self.assertTrue(result.double_review_complete)
        self.assertFalse(result.release_eligible)
        self.assertFalse(result.publication_authority)
        self.assertEqual(result.translation_id, self.translation.id)
        self.assertEqual(result.review_receipt_sha256,
                         assess(self.translation, self.evidence).review_receipt_sha256)

    def test_external_attestation_and_rights_required(self):
        without_attestor = evaluate_ai_translation_reviews(
            self.translation, self.evidence, now=NOW(),
            rights_receipt_check=lambda _: True,
        )
        self.assertEqual(without_attestor.status, "BLOCKED_EXTERNAL_REVIEW_ATTESTATION")
        self.assertFalse(without_attestor.double_review_complete)
        without_rights = evaluate_ai_translation_reviews(
            self.translation, self.evidence, now=NOW(),
            independent_receipt_check=lambda _: True,
        )
        self.assertEqual(without_rights.status, "BLOCKED_SOURCE_RIGHTS_RECEIPT")
        self.assertFalse(without_rights.double_review_complete)

    def test_identity_and_hash_replay_do_not_count(self):
        first, second = self.evidence
        for alteration in (
            replace(second, provider_id=first.provider_id),
            replace(second, model_id=first.model_id),
            replace(second, reviewer_id=first.reviewer_id),
            replace(second, response_sha256=first.response_sha256),
            replace(second, provider_id=self.translation.provider_id),
            replace(second, model_id=self.translation.model_id),
        ):
            with self.subTest(alteration=alteration):
                result = assess(self.translation, (first, alteration))
                self.assertEqual(result.status, "BLOCKED_REVIEW_INDEPENDENCE")
                self.assertFalse(result.double_review_complete)
        for alteration in (
            replace(second, translated_text_sha256=digest("modified-translation")),
            replace(second, source_version_sha256=digest("modified-source")),
            replace(second, translation_id="translation:another-version"),
            replace(second, original_quote_sha256=digest("wrong-quote")),
        ):
            with self.subTest(alteration=alteration):
                self.assertEqual(
                    assess(self.translation, (first, alteration)).status,
                    "BLOCKED_REVIEW_SOURCE_BINDING",
                )

    def test_disagreement_high_risk_and_expired_retention_hold(self):
        first, second = self.evidence
        disagreement = assess(self.translation, (
            first, replace(second, verdict="MISMATCH",
                           meaning_risks=("NEGATION_MISMATCH",)),
        ))
        self.assertEqual(disagreement.status, "HELD_REVIEW_DISAGREEMENT")
        self.assertIn("NEGATION_MISMATCH", disagreement.meaning_risks)
        high_risk = assess(self.translation, (
            replace(first, verdict="MISMATCH", meaning_risks=("DATE_MISMATCH",)),
            replace(second, verdict="MISMATCH", meaning_risks=("DATE_MISMATCH",)),
        ))
        self.assertEqual(high_risk.status, "HELD_MEANING_RISK")
        expired = assess(self.translation, (
            first, replace(second, retention_until="2026-10-19T12:00:00+00:00"),
        ))
        self.assertEqual(expired.status, "BLOCKED_REVIEW_RETENTION")

    def test_unsupported_and_mixed_languages_fail_closed(self):
        base = self.translation
        other = replace(base, original=replace(base.original, language="ru-RU"))
        self.assertEqual(assess(other, reviews(other)).status, "UNSUPPORTED_LANGUAGE_PAIR")
        mixed = replace(base, original=replace(base.original, language_origin="MIXED_DECLARED"))
        self.assertEqual(assess(mixed, reviews(mixed)).status, "UNSUPPORTED_LANGUAGE_PAIR")
        self.assertEqual(assess(base, ()).status, "BLOCKED_TWO_AI_REVIEWS_REQUIRED")

    def test_invalid_ai_risk_payload_is_blocked_without_exception(self):
        first, second = self.evidence
        malformed = replace(second, meaning_risks=({"not": "hashable"},))
        self.assertEqual(
            assess(self.translation, (first, malformed)).status,
            "BLOCKED_REVIEW_EVIDENCE_INVALID",
        )

    def test_revocation_during_ai_attestation_suppresses_all_private_text(self):
        from dichiarazioni_pubbliche.private_multilingual_view import read_private_multilingual_view
        from tests.test_dp239_gold_view import private_records, source_rights

        row = written_fixture()
        draft = build_private_translation(**row)
        guard = source_rights(row)
        record = guard.read_current(guard.subject)

        def revoke_before_return(_):
            guard.read_current = lambda subject: replace(record, rights_status="REVOKED")
            return True

        view = read_private_multilingual_view(
            row["passage"].id,
            originals_by_passage=private_records(row),
            current_versions_by_content={
                row["capture"].content_id: row["capture"].content_sha256,
            },
            rights_guard=guard,
            translation=draft,
            ai_reviews=reviews(draft),
            ai_review_clock=NOW(),
            independent_receipt_check=revoke_before_return,
            rights_receipt_check=lambda _: True,
        )
        self.assertEqual(view.status, "BLOCKED")
        self.assertIsNone(view.original_text)
        self.assertIsNone(view.translated_text)
        self.assertIsNone(view.source_url)

    def test_private_reader_exposes_review_status_only_as_held_metadata(self):
        from dichiarazioni_pubbliche.private_multilingual_view import read_private_multilingual_view
        from tests.test_dp239_gold_view import private_records, source_rights

        row = written_fixture()
        draft = build_private_translation(**row)
        view = read_private_multilingual_view(
            row["passage"].id,
            originals_by_passage=private_records(row),
            current_versions_by_content={
                row["capture"].content_id: row["capture"].content_sha256,
            },
            rights_guard=source_rights(row), translation=draft,
            ai_reviews=reviews(draft), ai_review_clock=NOW(),
            independent_receipt_check=lambda _: True,
            rights_receipt_check=lambda _: True,
        )
        self.assertEqual(view.status, "CURRENT_HELD")
        self.assertEqual(view.ai_meaning_assurance_status, "CONTRACT_ONLY_PRIVATE_HOLD")
        self.assertEqual(view.translated_text, draft.translated_text)
        self.assertEqual(view.original_text, draft.original.source_text)
        self.assertNotEqual(view.original_text, view.translated_text)
        self.assertFalse(view.translation_reviewed)
        self.assertFalse(view.public_quote_eligible)


if __name__ == "__main__":
    unittest.main()
