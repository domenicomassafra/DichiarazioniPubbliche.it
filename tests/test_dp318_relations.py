"""DP-318 private, provenance-bound Statement relation hypotheses (not public edges)."""

import dataclasses
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.context_integrity import assess_speech_act_context  # noqa: E402
from dichiarazioni_pubbliche.domain_vocabulary import RelationCandidateType  # noqa: E402
from dichiarazioni_pubbliche.relation_runtime import (  # noqa: E402
    ScopedStatementRelationInput,
    StatementRelationKind,
    StatementRelationScope,
    StructuredClaimRelationInput,
    classify_relation,
    evaluate_scoped_statement_relation,
)
from dichiarazioni_pubbliche.relation_policy import (  # noqa: E402
    StatementRelationPreflight,
    StatementRelationPreflightState,
    evaluate_statement_relation_preflight,
)


def context(person="person:a", *, speech="Secondo me la misura è utile.", language="it"):
    return assess_speech_act_context(
        source_text=speech, source_sha256=hashlib.sha256(speech.encode()).hexdigest(),
        quote_start=0, quote_end=len(speech), turn_start=0, turn_end=len(speech),
        utterer_id=person, turn_speaker_ids=(person,), source_part_ref="capture:part",
        turn_complete=True, language=language,
    )


SCOPE = StatementRelationScope(
    jurisdiction_ref="jurisdiction:it",
    subject_ref="measure:1",
    period_start="2025-01-01",
    period_end="2025-12-31",
    modality="ASSERTED",
    condition_ref="NONE",
    location_ref="location:it",
)


def statement(identifier="statement:a", *, person="person:a", date="2025-01-01",
              position="SUPPORT", speech_act=None, **changes):
    payload = dict(
        statement_id=identifier,
        person_id=person,
        statement_date=date,
        proposition_key="p:measure-useful",
        equivalence_review_ref="verified-equivalence:case-1",
        statement_kind="OPINION",
        position=position,
        scope=SCOPE,
        speech_act=speech_act or context(
            person, speech=(
                "Secondo me la misura è dannosa."
                if position == "OPPOSE"
                else "Secondo me la misura è utile."
            )
        ),
    )
    payload.update(changes)
    return ScopedStatementRelationInput(**payload)


class DP318ScopedStatementTests(unittest.TestCase):
    def test_different_people_opposite_position_is_divergence_not_position_change(self):
        result = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", person="person:b",
                                   date="2025-06-01", position="OPPOSE")
        )
        self.assertEqual(result.kind, StatementRelationKind.CROSS_PERSON_DIVERGENCE)
        self.assertEqual(result.person_cardinality, 2)
        self.assertEqual(result.state, "CANDIDATE_PRIVATE")
        self.assertFalse(result.review_authority)
        self.assertFalse(result.publication_authority)

    def test_same_person_opposite_across_statement_dates_is_position_change_candidate(self):
        result = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", date="2025-06-01", position="OPPOSE")
        )
        self.assertEqual(result.kind, StatementRelationKind.SAME_PERSON_POSITION_CHANGE_CANDIDATE)
        self.assertEqual(result.person_cardinality, 1)

    def test_same_person_opposite_same_date_is_contradiction_candidate_not_lie(self):
        result = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", date="2025-01-01", position="OPPOSE")
        )
        self.assertEqual(result.kind, StatementRelationKind.SAME_PERSON_CONTRADICTION_CANDIDATE)
        self.assertNotIn("lie", repr(result).lower())
        self.assertFalse(result.publication_authority)

    def test_retrospective_continuity_does_not_become_simple_position_change(self):
        result = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", date="2025-06-01",
                                   position="OPPOSE", asserts_past_continuity=True)
        )
        self.assertEqual(result.kind, StatementRelationKind.SAME_PERSON_CONTRADICTION_CANDIDATE)
        self.assertIn("RETROSPECTIVE_CONTINUITY_CANDIDATE", result.rationale_codes)

    def test_same_person_and_cross_person_agreement_are_distinct(self):
        same = evaluate_scoped_statement_relation(statement(), statement("statement:b"))
        cross = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", person="person:b")
        )
        self.assertEqual(same.kind, StatementRelationKind.SAME_PERSON_REAFFIRMATION)
        self.assertEqual(cross.kind, StatementRelationKind.CROSS_PERSON_AGREEMENT)

    def test_unreviewed_equivalence_topic_or_homonym_does_not_form_relation(self):
        for changes in (
            {"equivalence_review_ref": None},
            {"equivalence_review_ref": "review:other"},
            {"proposition_key": "p:different"},
            {"proposition_key": None},
            {"person_id": ""},
            {"equivalence_review_ref": "UNKNOWN"},
        ):
            with self.subTest(changes=changes):
                result = evaluate_scoped_statement_relation(
                    statement(), statement("statement:b", **changes)
                )
                self.assertEqual(result.kind, StatementRelationKind.HOLD)
                self.assertEqual(result.state, "HOLD")

    def test_placeholder_person_ids_cannot_assert_same_person_contradiction(self):
        # The speech-act preflight binds to the supplied utterer string; that
        # cryptographic binding does not establish a resolved human identity.
        for unresolved in ("UNKNOWN", "person:unknown", "person:unresolved", "person:"):
            with self.subTest(unresolved=unresolved):
                result = evaluate_scoped_statement_relation(
                    statement(person=unresolved),
                    statement("statement:b", person=unresolved, position="OPPOSE"),
                )
                self.assertEqual(result.kind, StatementRelationKind.HOLD)
                self.assertEqual(result.person_cardinality, 0)
                self.assertIn("PERSON_ID_UNVERIFIED", result.rationale_codes)

    def test_placeholder_person_ids_cannot_assert_cross_person_divergence(self):
        result = evaluate_scoped_statement_relation(
            statement(person="person:unknown"),
            statement("statement:b", person="person:b", position="OPPOSE"),
        )
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertEqual(result.person_cardinality, 0)
        self.assertIn("PERSON_ID_UNVERIFIED", result.rationale_codes)

    def test_incompatible_jurisdiction_period_condition_or_modality_holds(self):
        for changes in (
            {"jurisdiction_ref": "jurisdiction:de"},
            {"subject_ref": "measure:2"},
            {"period_start": "2026-01-01", "period_end": "2026-12-31"},
            {"condition_ref": "IF_PRICES_FALL"},
            {"modality": "CONDITIONAL"},
            {"location_ref": "location:de"},
            {"qualifier_ref": "UNDER_EXCEPTIONS"},
            {"jurisdiction_ref": "UNKNOWN"},
            {"location_ref": "UNSPECIFIED"},
        ):
            with self.subTest(changes=changes):
                result = evaluate_scoped_statement_relation(
                    statement(), statement("statement:b", scope=dataclasses.replace(SCOPE, **changes))
                )
                self.assertEqual(result.kind, StatementRelationKind.HOLD)
                self.assertEqual(result.state, "HOLD")

    def test_report_quotation_criticised_source_question_and_unknown_stance_hold(self):
        cases = (
            ("Secondo Ada, «Io sostengo che la misura sia utile».", "it"),
            ("Critico lo slogan «Io sostengo che la misura sia utile».", "it"),
            ("Recito «Io sostengo che la misura sia utile».", "it"),
            ("Sostieni che la misura sia utile?", "it"),
            ("Die Maßnahme ist hilfreich.", "de"),
            ("Io sostengo che la misura sia utile.", "xx"),
        )
        for text, language in cases:
            with self.subTest(text=text):
                candidate = statement(
                    "statement:b", person="person:b",
                    speech_act=context("person:b", speech=text, language=language),
                )
                result = evaluate_scoped_statement_relation(statement(), candidate)
                self.assertEqual(result.kind, StatementRelationKind.HOLD)
                self.assertFalse(result.publication_authority)

    def test_denial_of_saying_is_not_denial_of_endorsement_or_truth(self):
        for denial in ("DENIAL_OF_SAYING", "DENIAL_OF_ENDORSEMENT",
                       "NEGATIVE_FACTUAL_CLAIM", "UNKNOWN"):
            with self.subTest(denial=denial):
                result = evaluate_scoped_statement_relation(
                    statement(), statement("statement:b", denial_kind=denial)
                )
                self.assertEqual(result.kind, StatementRelationKind.HOLD)
                self.assertIn("DENIAL_ROLE_UNRESOLVED", result.rationale_codes)

        for words in (
            "Non ho mai detto che la misura sia utile.",
            "Non sostengo che la misura sia utile.",
            "Io sostengo che la misura non sia utile.",
        ):
            with self.subTest(words=words):
                result = evaluate_scoped_statement_relation(
                    statement(),
                    statement(
                        "statement:b", person="person:b",
                        speech_act=context("person:b", speech=words),
                        denial_kind="DENIAL_OF_SAYING",
                    ),
                )
                self.assertEqual(result.kind, StatementRelationKind.HOLD)
                self.assertNotIn("FACTUALLY_FALSE", repr(result))

    def test_identical_source_words_with_forged_opposite_position_hold(self):
        same_words = context("person:b")
        result = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", person="person:b",
                                   position="OPPOSE", speech_act=same_words)
        )
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertIn(
            "IDENTICAL_QUOTATION_OPPOSITE_POSITION_UNSUPPORTED", result.rationale_codes
        )

    def test_tampered_speech_act_stance_or_hash_is_held(self):
        original = context("person:b")
        for tamper in (
            {"stance": "REFUTE"},
            {"source_sha256": "f" * 64},
            {"quoted_author_id": "person:historic"},
        ):
            with self.subTest(tamper=tamper):
                receipt = dataclasses.replace(original, **tamper)
                result = evaluate_scoped_statement_relation(
                    statement(), statement("statement:b", person="person:b",
                                           speech_act=receipt)
                )
                self.assertEqual(result.kind, StatementRelationKind.HOLD)
                self.assertIn("SPEECH_ACT_BINDING_TAMPERED", result.rationale_codes)

    def test_proposition_scope_unknown_cannot_become_same_take(self):
        result = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", position="UNKNOWN")
        )
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertIn("POSITION_NOT_REVIEWED", result.rationale_codes)

    def test_factual_statement_candidate_keeps_finding_requirement(self):
        first = statement(
            statement_kind="FACTUAL",
            speech_act=context(speech="Io sostengo che la misura sia utile."),
        )
        second = statement(
            "statement:b", person="person:b", statement_kind="FACTUAL",
            speech_act=context("person:b", speech="Io sostengo che la misura sia utile."),
        )
        result = evaluate_scoped_statement_relation(first, second)
        self.assertEqual(result.kind, StatementRelationKind.CROSS_PERSON_AGREEMENT)
        self.assertTrue(result.finding_required)

    def test_person_binding_to_utterer_ref_is_required(self):
        result = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", person="person:b",
                                   speech_act=context("person:c"))
        )
        self.assertEqual(result.kind, StatementRelationKind.HOLD)
        self.assertIn("PERSON_UTTERER_MISMATCH", result.rationale_codes)

    def test_statement_kind_factual_vs_opinion_not_automatically_equivalent(self):
        result = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", statement_kind="FACTUAL")
        )
        self.assertEqual(result.kind, StatementRelationKind.HOLD)

    def test_stale_source_or_context_receipt_changes_identity_of_candidate(self):
        other_source = context(speech="Io sostengo che il nuovo piano sia utile.")
        first = evaluate_scoped_statement_relation(statement(), statement("statement:b"))
        updated = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", speech_act=other_source)
        )
        self.assertNotEqual(first.binding_sha256, updated.binding_sha256)
        self.assertNotEqual(first.source_context_bindings, updated.source_context_bindings)
        self.assertEqual(
            first.binding_sha256,
            evaluate_scoped_statement_relation(statement(), statement("statement:b")).binding_sha256
        )

    def test_date_order_and_input_symmetry_canonicalized(self):
        earlier, later = statement(), statement("statement:b", date="2025-06-01", position="OPPOSE")
        forward = evaluate_scoped_statement_relation(earlier, later)
        backward = evaluate_scoped_statement_relation(later, earlier)
        self.assertEqual(forward, backward)
        self.assertEqual(forward.subject_statement_id, earlier.statement_id)
        self.assertEqual(forward.object_statement_id, later.statement_id)

    def test_invalid_dates_scope_reversed_and_self_are_refused(self):
        with self.assertRaisesRegex(ValueError, "RELATION_SELF_REFUSED"):
            evaluate_scoped_statement_relation(statement(), statement())
        with self.assertRaisesRegex(ValueError, "DATE_INVALID"):
            evaluate_scoped_statement_relation(statement(), statement("statement:b", date="2025-02-30"))
        with self.assertRaisesRegex(ValueError, "SCOPE_INVALID"):
            evaluate_scoped_statement_relation(
                statement(),
                statement("statement:b", scope=dataclasses.replace(
                    SCOPE, period_start="2026-01-01", period_end="2025-01-01"
                )),
            )

    def test_legacy_typed_identity_known_cross_person_never_position_change(self):
        prior = StructuredClaimRelationInput(
            claim_id="a", statement_date="2025-01-01",
            proposition_key="p", stance="support", person_id="person:a",
        )
        later = StructuredClaimRelationInput(
            claim_id="b", statement_date="2025-06-01",
            proposition_key="p", stance="oppose", person_id="person:b",
        )
        result = classify_relation(prior, later)
        self.assertNotIn(result.relation_type, (
            RelationCandidateType.POSITION_CHANGE_CANDIDATE,
            RelationCandidateType.CONTRADICTION_CANDIDATE,
        ))
        self.assertIn("CROSS_PERSON", " ".join(result.rationale_codes))

    def test_legacy_identity_partial_refuses_position_change_without_breaking_signature(self):
        left = StructuredClaimRelationInput(
            claim_id="a", statement_date="2025-01-01",
            proposition_key="p", stance="support", person_id="person:a",
        )
        right = StructuredClaimRelationInput(
            claim_id="b", statement_date="2025-06-01",
            proposition_key="p", stance="oppose",
        )
        result = classify_relation(left, right)
        self.assertEqual(result.relation_type, RelationCandidateType.SAME_PROPOSITION)
        self.assertIn("PERSON_ID_INCOMPLETE_NO_POSITION_CHANGE", result.rationale_codes)

    def test_legacy_explicit_unresolved_person_cannot_be_position_change(self):
        for unresolved in ("UNKNOWN", "person:unknown", "person:unresolved", ""):
            with self.subTest(unresolved=unresolved):
                result = classify_relation(
                    StructuredClaimRelationInput(
                        claim_id="a", statement_date="2025-01-01",
                        proposition_key="p", stance="support", person_id=unresolved,
                    ),
                    StructuredClaimRelationInput(
                        claim_id="b", statement_date="2025-06-01",
                        proposition_key="p", stance="oppose", person_id=unresolved,
                    ),
                )
                self.assertEqual(result.relation_type, RelationCandidateType.SAME_PROPOSITION)
                self.assertIn("PERSON_ID_UNVERIFIED_NO_POSITION_CHANGE", result.rationale_codes)


class DP318PolicyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.candidate = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", person="person:b")
        )

    def test_opinions_require_no_finding_but_still_cannot_publish_from_preflight(self):
        decision = evaluate_statement_relation_preflight(
            StatementRelationPreflight(
                relation=self.candidate, endpoint_public_statement_versions=("v1:a", "v1:b"),
                source_context_current=True, person_identity_current=True,
                corrections_current=True, rights_current=True,
                relation_review_event_ref="review:event-1",
            )
        )
        self.assertEqual(decision.state, StatementRelationPreflightState.PRIVATE_HANDOFF)
        self.assertFalse(decision.finding_required)
        self.assertFalse(decision.publication_authority)

    def test_missing_public_statement_review_binding_rights_and_correction_hold(self):
        valid = StatementRelationPreflight(
            relation=self.candidate, endpoint_public_statement_versions=("v1:a", "v1:b"),
            source_context_current=True, person_identity_current=True,
            corrections_current=True, rights_current=True,
            relation_review_event_ref="review:event-1",
        )
        for patch in (
            {"endpoint_public_statement_versions": ("v1:a", "")},
            {"source_context_current": False},
            {"person_identity_current": False},
            {"corrections_current": False},
            {"rights_current": False},
            {"relation_review_event_ref": None},
        ):
            with self.subTest(patch=patch):
                state = evaluate_statement_relation_preflight(dataclasses.replace(valid, **patch))
                self.assertEqual(state.state, StatementRelationPreflightState.HOLD)
                self.assertFalse(state.publication_authority)

    def test_held_semantics_cannot_be_rehabilitated_by_pretend_approval(self):
        held = evaluate_scoped_statement_relation(
            statement(), statement("statement:b", person="person:b", position="UNKNOWN")
        )
        result = evaluate_statement_relation_preflight(
            StatementRelationPreflight(
                relation=held, endpoint_public_statement_versions=("v1:a", "v1:b"),
                source_context_current=True, person_identity_current=True,
                corrections_current=True, rights_current=True,
                relation_review_event_ref="review:event-forged",
            )
        )
        self.assertEqual(result.state, StatementRelationPreflightState.HOLD)
        self.assertFalse(result.publication_authority)


if __name__ == "__main__":
    unittest.main()
