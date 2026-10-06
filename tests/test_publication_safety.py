import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.publication_safety import (  # noqa: E402
    ProofState,
    PublicationSafetyInput,
    WordingMode,
    evaluate_publication_safety,
    receipt_is_current,
    required_proofs,
)


def complete(**overrides):
    values = dict(
        wording_mode=WordingMode.PARAPHRASE,
        media_quote=False,
        source_identity=ProofState.PASSED,
        exact_wording=ProofState.NOT_APPLICABLE,
        transcript_verbatim=ProofState.NOT_APPLICABLE,
        speaker_span=ProofState.PASSED,
        speech_origin=ProofState.PASSED,
        context_integrity=ProofState.PASSED,
        wording_integrity=ProofState.PASSED,
        identity_integrity=ProofState.PASSED,
        translation_review=ProofState.NOT_APPLICABLE,
        evidence_suitability=ProofState.PASSED,
        citation_assurance=ProofState.PASSED,
        privacy=ProofState.PASSED,
        rights=ProofState.PASSED,
        verification_review=ProofState.PASSED,
        finding_review=ProofState.PASSED,
        challenge_hold=ProofState.PASSED,
        load_bearing_refs={
            "source_sha256": "a" * 64,
            "finding_review": "review:finding:1",
            "policy_version": "policy-v1",
        },
    )
    values.update(overrides)
    return PublicationSafetyInput(**values)


class PublicationSafetyTests(unittest.TestCase):
    def test_complete_paraphrase_is_eligible_without_quote_authority(self):
        result = evaluate_publication_safety(complete())
        self.assertTrue(result.eligible)
        self.assertNotIn("exact_wording", result.required_proofs)
        self.assertNotIn("transcript_verbatim", result.required_proofs)
        self.assertFalse(hasattr(result, "score"))

    def test_direct_media_quote_requires_exact_wording_and_verbatim_transcript(self):
        value = complete(
            wording_mode=WordingMode.DIRECT_QUOTE,
            media_quote=True,
            exact_wording=ProofState.MISSING,
            transcript_verbatim=ProofState.STALE,
        )
        result = evaluate_publication_safety(value)
        self.assertFalse(result.eligible)
        self.assertIn("MISSING_EXACT_WORDING", result.reason_codes)
        self.assertIn("STALE_TRANSCRIPT_VERBATIM", result.reason_codes)

    def test_translation_requires_review_but_not_direct_quote_proof(self):
        result = evaluate_publication_safety(
            complete(
                wording_mode=WordingMode.TRANSLATION,
                translation_review=ProofState.MISSING,
            )
        )
        self.assertFalse(result.eligible)
        self.assertIn("translation_review", result.required_proofs)
        self.assertNotIn("exact_wording", result.required_proofs)
        self.assertIn("MISSING_TRANSLATION_REVIEW", result.reason_codes)

    def test_truth_verification_cannot_compensate_for_bad_attribution(self):
        for field in ("speaker_span", "speech_origin", "context_integrity", "identity_integrity"):
            with self.subTest(field=field):
                result = evaluate_publication_safety(
                    complete(**{field: ProofState.MISSING})
                )
                self.assertFalse(result.eligible)
                self.assertIn(f"MISSING_{field.upper()}", result.reason_codes)

    def test_attribution_cannot_compensate_for_unsuitable_or_uncited_evidence(self):
        unsuitable = evaluate_publication_safety(
            complete(evidence_suitability=ProofState.HOLD)
        )
        self.assertFalse(unsuitable.eligible)
        self.assertIn("HOLD_EVIDENCE_SUITABILITY", unsuitable.reason_codes)
        uncited = evaluate_publication_safety(
            complete(citation_assurance=ProofState.MISSING)
        )
        self.assertFalse(uncited.eligible)
        self.assertIn("MISSING_CITATION_ASSURANCE", uncited.reason_codes)

    def test_privacy_rights_and_challenge_holds_dominate(self):
        for field in ("privacy", "rights", "challenge_hold"):
            with self.subTest(field=field):
                result = evaluate_publication_safety(
                    complete(**{field: ProofState.HOLD})
                )
                self.assertEqual(result.disposition, "POLICY_HOLD")
                self.assertIn(f"HOLD_{field.upper()}", result.reason_codes)

    def test_stale_load_bearing_proof_blocks_even_with_finding_review(self):
        result = evaluate_publication_safety(
            complete(source_identity=ProofState.STALE)
        )
        self.assertEqual(result.disposition, "STALE")
        self.assertIn("STALE_SOURCE_IDENTITY", result.reason_codes)

    def test_receipt_binding_changes_when_any_load_bearing_reference_changes(self):
        original = complete()
        result = evaluate_publication_safety(original)
        self.assertTrue(receipt_is_current(result, original.load_bearing_refs))
        for key in original.load_bearing_refs:
            with self.subTest(key=key):
                changed = dict(original.load_bearing_refs)
                changed[key] += ":changed"
                self.assertFalse(receipt_is_current(result, changed))

    def test_missing_load_bearing_refs_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "LOAD_BEARING_REFS_REQUIRED"):
            evaluate_publication_safety(complete(load_bearing_refs={}))

    def test_required_proof_matrix_is_deterministic(self):
        direct = required_proofs(WordingMode.DIRECT_QUOTE, media_quote=True)
        paraphrase = required_proofs(WordingMode.PARAPHRASE, media_quote=False)
        translation = required_proofs(WordingMode.TRANSLATION, media_quote=False)
        self.assertIn("exact_wording", direct)
        self.assertIn("transcript_verbatim", direct)
        self.assertNotIn("exact_wording", paraphrase)
        self.assertIn("translation_review", translation)
        self.assertEqual(direct, required_proofs(WordingMode.DIRECT_QUOTE, media_quote=True))


if __name__ == "__main__":
    unittest.main()
