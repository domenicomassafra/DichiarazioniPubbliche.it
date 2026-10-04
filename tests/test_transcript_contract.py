import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.transcript_contract import (
    TranscriptCandidate,
    TranscriptStatus,
    reconcile_candidates,
)


def candidate(candidate_id: str, text: str) -> TranscriptCandidate:
    return TranscriptCandidate(
        candidate_id=candidate_id,
        provider_id=candidate_id,
        text=text,
        start_ms=98000,
        end_ms=125000,
        source_kind="asr",
    )


class TranscriptContractTests(unittest.TestCase):
    def test_identical_candidates_resolve(self):
        result = reconcile_candidates(
            (
                candidate("a", "Il gettito è 7,5 miliardi."),
                candidate("b", "Il gettito è 7,5 miliardi."),
            )
        )
        self.assertEqual(result.status, TranscriptStatus.RESOLVED)
        self.assertFalse(result.publication_blocked)

    def test_single_sensitive_candidate_is_not_publication_grade(self):
        result = reconcile_candidates(
            (
                TranscriptCandidate(
                    candidate_id="platform-caption",
                    provider_id="youtube",
                    text="Il costo è 10 milioni di euro.",
                    start_ms=0,
                    end_ms=2000,
                    source_kind="YOUTUBE_AUTO_CAPTION",
                ),
            )
        )
        self.assertEqual(result.status, TranscriptStatus.TRANSCRIPT_UNCERTAIN)
        self.assertTrue(result.publication_blocked)

    def test_numeric_disagreement_blocks_publication(self):
        result = reconcile_candidates(
            (
                candidate("a", "Il gettito è 7 miliardi."),
                candidate("b", "Il gettito è 7,5 miliardi."),
            )
        )
        self.assertEqual(result.status, TranscriptStatus.TRANSCRIPT_UNCERTAIN)
        self.assertTrue(result.publication_blocked)

    def test_negation_disagreement_blocks_publication(self):
        result = reconcile_candidates(
            (
                candidate("a", "Il governo abolirà il bollo."),
                candidate("b", "Il governo non abolirà il bollo."),
            )
        )
        self.assertEqual(result.status, TranscriptStatus.TRANSCRIPT_UNCERTAIN)
        self.assertTrue(result.publication_blocked)

    def test_gazetteer_name_presence_is_sensitive(self):
        result = reconcile_candidates(
            (
                candidate("a", "Ne ha parlato Tajani."),
                candidate("b", "Ne ha parlato Salvini."),
            ),
            gazetteer_terms=("Tajani", "Salvini"),
        )
        self.assertEqual(result.status, TranscriptStatus.TRANSCRIPT_UNCERTAIN)
        self.assertTrue(result.publication_blocked)

    def test_harmless_wording_difference_is_not_silently_rewritten(self):
        result = reconcile_candidates(
            (
                candidate("a", "Questa misura vale soltanto nel 2027."),
                candidate("b", "Questa misura si applica soltanto nel 2027."),
            )
        )
        self.assertEqual(result.status, TranscriptStatus.CANDIDATE_DISAGREEMENT)
        self.assertEqual(result.canonical_text, "Questa misura vale soltanto nel 2027.")
        self.assertFalse(result.publication_blocked)


if __name__ == "__main__":
    unittest.main()
