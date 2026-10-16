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


def _attested_private_speech(person: str, words: str, *, part="capture:part1"):
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
        source_part_ref=part,
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

    def test_same_capture_quote_span_two_people_cannot_assert_cross_person_agreement(self):
        # Two identities cannot each claim to have uttered the exact same
        # immutable captured span, even with internally consistent lexical receipts.
        self.assertNotEqual(self.left.person_id, self.right.person_id)
        self.assertEqual(self.left.speech_act.source_sha256, self.right.speech_act.source_sha256)
        self.assertEqual(self.left.speech_act.source_part_ref, self.right.speech_act.source_part_ref)
        self.assertNotEqual(self.left.speech_act.binding_sha256, self.right.speech_act.binding_sha256)
        result = evaluate_scoped_statement_relation(self.left, self.right)
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertIn("IDENTICAL_SOURCE_SPAN_REUSED", result.rationale_codes)
        self.assertEqual(result.state, "HOLD")
        self.assertFalse(result.publication_authority)

        independent = _statement(
            "statement:two", "person:two", "Io sostengo che la misura sia utile.",
            speech_act=_attested_private_speech(
                "person:two", "Io sostengo che la misura sia utile.",
                part="capture:independent-other-person",
            ),
        )
        safe = evaluate_scoped_statement_relation(self.left, independent)
        self.assertEqual(safe.kind, StatementRelationKind.CROSS_PERSON_AGREEMENT)
        self.assertEqual(safe.state, "CANDIDATE_PRIVATE")
        self.assertFalse(safe.publication_authority)

    def test_same_day_statement_alias_cannot_count_single_capture_as_reaffirmation(self):
        alias = dataclasses.replace(self.left, statement_id="statement:same-day-alias")
        result = evaluate_scoped_statement_relation(self.left, alias)
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertIn("IDENTICAL_SOURCE_SPAN_REUSED", result.rationale_codes)
        self.assertFalse(result.review_authority)

        independent_speech = _attested_private_speech(
            "person:one", "Io sostengo che la misura sia utile.",
            part="capture:independent-same-day",
        )
        safe = evaluate_scoped_statement_relation(
            self.left, dataclasses.replace(alias, speech_act=independent_speech)
        )
        self.assertEqual(safe.kind, StatementRelationKind.SAME_PERSON_REAFFIRMATION)
        self.assertEqual(safe.state, "CANDIDATE_PRIVATE")

    def test_same_capture_part_across_source_revisions_must_hold(self):
        # An immutable Capture part cannot simultaneously have two different
        # source hashes. Comparing two revisions as independent utterances
        # could assert cross-person agreement or longitudinal reaffirmation.
        updated_speech = _attested_private_speech(
            "person:two", "Io sostengo che questa misura sia utile.",
            part=self.left.speech_act.source_part_ref,
        )
        self.assertNotEqual(
            updated_speech.source_sha256, self.left.speech_act.source_sha256
        )
        self.assertEqual(updated_speech.state, "CANDIDATE_PRIVATE")
        incompatible = _statement(
            "statement:updated", "person:two",
            "Io sostengo che questa misura sia utile.", speech_act=updated_speech,
        )
        result = evaluate_scoped_statement_relation(self.left, incompatible)
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertIn("SOURCE_PART_REVISION_CONFLICT", result.rationale_codes)
        self.assertFalse(result.publication_authority)

        same_person_revision = _attested_private_speech(
            "person:one", "Io sostengo che questa misura sia utile.",
            part=self.left.speech_act.source_part_ref,
        )
        own_result = evaluate_scoped_statement_relation(
            self.left,
            dataclasses.replace(
                incompatible, person_id="person:one", statement_date="2025-07-01",
                speech_act=same_person_revision,
            ),
        )
        self.assertEqual(own_result.kind, StatementRelationKind.HOLD)
        self.assertIn("SOURCE_PART_REVISION_CONFLICT", own_result.rationale_codes)

        # A distinct capture part remains a private candidate, even when the
        # two receipts contain different exact words.
        separate_part = _attested_private_speech(
            "person:two", "Io sostengo che questa misura sia utile.",
            part="capture:independent-updated",
        )
        eligible = evaluate_scoped_statement_relation(
            self.left, dataclasses.replace(incompatible, speech_act=separate_part)
        )
        self.assertEqual(eligible.kind, StatementRelationKind.CROSS_PERSON_AGREEMENT)
        self.assertFalse(eligible.publication_authority)

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
