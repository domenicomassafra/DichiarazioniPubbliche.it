"""Adversarial DP-318 cases against the real private Statement relation seam."""

import dataclasses
import hashlib
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.context_integrity import assess_speech_act_context  # noqa: E402
from dichiarazioni_pubbliche.relation_runtime import (  # noqa: E402
    ScopedStatementRelationInput,
    StatementRelationKind,
    StatementRelationScope,
    evaluate_scoped_statement_relation,
)


_SCOPE = StatementRelationScope(
    jurisdiction_ref="jurisdiction:it",
    subject_ref="measure:1",
    period_start="2025-01-01",
    period_end="2025-12-31",
    modality="ASSERTED",
    condition_ref="NONE",
    location_ref="location:it",
)


def _attested_private_speech(person: str, words: str):
    """Produce a self-consistent real lexical receipt, not a forged hash."""
    return assess_speech_act_context(
        source_text=words,
        source_sha256=hashlib.sha256(words.encode("utf-8")).hexdigest(),
        quote_start=0,
        quote_end=len(words),
        turn_start=0,
        turn_end=len(words),
        utterer_id=person,
        language="it",
        turn_speaker_ids=(person,),
        source_part_ref="capture:part1",
        turn_complete=True,
    )


def _statement(identifier: str, person: str, words: str, *, day="2025-02-01", **kwargs):
    payload = dict(
        statement_id=identifier,
        person_id=person,
        statement_date=day,
        proposition_key="proposition:measure-effect",
        equivalence_review_ref="equivalence:case-7",
        statement_kind="FACTUAL",
        position="SUPPORT",
        scope=_SCOPE,
        speech_act=_attested_private_speech(person, words),
    )
    payload.update(kwargs)
    return ScopedStatementRelationInput(**payload)


class DP318RelationWaveCloseTests(unittest.TestCase):
    def setUp(self):
        self.left = _statement(
            "statement:one", "person:one", "Io sostengo che la misura sia utile."
        )
        self.right = _statement(
            "statement:two", "person:two", "Io sostengo che la misura sia utile."
        )

    def test_real_negated_utterance_cannot_be_asserted_same_take(self):
        negated = _statement(
            "statement:two", "person:two", "Io sostengo che non sia utile."
        )
        self.assertEqual(self.left.speech_act.polarity, "POSITIVE")
        self.assertEqual(negated.speech_act.polarity, "NEGATED")
        self.assertEqual(self.left.speech_act.state, "CANDIDATE_PRIVATE")
        self.assertEqual(negated.speech_act.state, "CANDIDATE_PRIVATE")
        result = evaluate_scoped_statement_relation(self.left, negated)
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertIn("SPEECH_ACT_POLARITY_MISMATCH", result.rationale_codes)
        self.assertFalse(result.publication_authority)

    def test_unresolved_namespace_refs_cannot_attest_equivalence(self):
        for field, values in (
            ("equivalence_review_ref", ("review:unknown", "review:unresolved", "review:")),
            ("proposition_key", ("proposition:unknown", "proposition:unresolved", "proposition:")),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    pair = (
                        dataclasses.replace(self.left, **{field: value}),
                        dataclasses.replace(self.right, **{field: value}),
                    )
                    result = evaluate_scoped_statement_relation(*pair)
                    self.assertEqual(result.kind, StatementRelationKind.HOLD)
                    self.assertIn(
                        "PROPOSITION_EQUIVALENCE_UNVERIFIED"
                        if field == "proposition_key"
                        else "EQUIVALENCE_REVIEW_REF_UNVERIFIED",
                        result.rationale_codes,
                    )

    def test_unresolved_namespaced_scope_cannot_be_asserted_same_take(self):
        for field, value in (
            ("jurisdiction_ref", "jurisdiction:unknown"),
            ("subject_ref", "subject:unresolved"),
            ("location_ref", "location:unspecified"),
            ("qualifier_ref", "qualifier:unknown"),
        ):
            with self.subTest(field=field):
                scope = dataclasses.replace(_SCOPE, **{field: value})
                result = evaluate_scoped_statement_relation(
                    dataclasses.replace(self.left, scope=scope),
                    dataclasses.replace(self.right, scope=scope),
                )
                self.assertEqual(result.kind, StatementRelationKind.HOLD)
                self.assertIn("CONDITIONAL_OR_UNKNOWN_SCOPE", result.rationale_codes)

    def test_same_capture_quote_span_two_ids_is_not_two_independent_utterances(self):
        # Two records for the exact same captured utterance must not create
        # fictitious longitudinal reaffirmation merely by changing Statement ID/date.
        repeated = dataclasses.replace(
            self.left, statement_id="statement:alias", statement_date="2025-07-01"
        )
        result = evaluate_scoped_statement_relation(self.left, repeated)
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertIn("IDENTICAL_SOURCE_SPAN_REUSED", result.rationale_codes)
        self.assertFalse(result.review_authority)

    def test_distinct_capture_quote_spans_remain_private_relation_candidates(self):
        # Two independent captured speeches on separate source-part references
        # are not suppressed because their original words happen to match.
        words = "Io sostengo che la misura sia utile."
        # Use the assessor for both independent receipts, preserving a real hash.
        later_receipt = assess_speech_act_context(
            source_text=words,
            source_sha256=hashlib.sha256(words.encode()).hexdigest(),
            quote_start=0, quote_end=len(words), turn_start=0,
            turn_end=len(words), utterer_id="person:one", language="it",
            turn_speaker_ids=("person:one",), source_part_ref="capture:part2",
            turn_complete=True,
        )
        result = evaluate_scoped_statement_relation(
            self.left,
            dataclasses.replace(
                self.left, statement_id="statement:new-speech",
                statement_date="2025-07-01", speech_act=later_receipt,
            ),
        )
        self.assertEqual(result.kind, StatementRelationKind.SAME_PERSON_REAFFIRMATION)
        self.assertEqual(result.state, "CANDIDATE_PRIVATE")
        self.assertFalse(result.publication_authority)


if __name__ == "__main__":
    unittest.main()
