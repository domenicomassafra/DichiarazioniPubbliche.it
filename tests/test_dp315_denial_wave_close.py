"""DP-315 adversarial replay tests against the exported private evaluator.

The source, attribution and review metadata below are entirely synthetic.
"""

import sys
import unittest
from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.denial_prior_utterance import (  # noqa: E402
    DenialTarget,
    PriorOccurrence,
    evaluate_denial,
)


def utc(year: int) -> datetime:
    return datetime(year, 5, 1, 10, tzinfo=timezone.utc)


def denial(predicate: str = "NEVER_UTTERED") -> DenialTarget:
    return DenialTarget(
        denial_id="denial:synth", person_id="person:synth",
        source_version_id="denial:v1", source_sha256="a" * 64,
        review_event_id="review:denial", uttered_at=utc(2026),
        target_quote_sha256="b" * 64,
        target_proposition_sha256="c" * 64,
        predicate=predicate, quantifier="NEVER", scope="PUBLIC",
        from_at=None, through_at=None,
    )


def occurrence(occurrence_id: str, source: str, year: int = 2024) -> PriorOccurrence:
    return PriorOccurrence(
        occurrence_id=occurrence_id, source_version_id=source,
        source_sha256="d" * 64, quote_sha256="b" * 64,
        proposition_sha256="c" * 64, spoken_at=utc(year),
        utterer_person_id="person:synth", quoted_person_id=None,
        speech_act="ASSERTION", endorsed=True,
        publication_scope="PUBLIC", review_event_id="review:prior",
    )


def evaluate(rows: tuple[PriorOccurrence, ...], predicate: str = "NEVER_UTTERED"):
    versions = {"denial:v1": "a" * 64}
    versions.update({row.source_version_id: row.source_sha256 for row in rows})
    return evaluate_denial(denial(predicate), rows, current_source_versions=versions)


class DenialAdversarialReplayTests(unittest.TestCase):
    def test_mutated_prior_after_receipt_snapshot_cannot_certify_refutation(self):
        # Frozen dataclasses still have a mutable __dict__ and can be subclassed.
        # A caller-controlled typed occurrence must not be re-read for a
        # counterexample after its independently hashed receipt snapshot.
        class SwitchingPrior(PriorOccurrence):
            def __getattribute__(self, name):
                state = object.__getattribute__(self, "__dict__")
                if state.get("_armed") and name == state["_switch_field"]:
                    state["_reads"] += 1
                    return state["_first"] if state["_reads"] == 1 else state["_later"]
                return super().__getattribute__(name)

        source = replace(occurrence("occ:mutable", "source:mutable:v1"),
                         endorsed=False)
        for field, first, later in (
            ("status", "REVOKED", "CURRENT"),
            ("speech_act", "REPORTED_QUOTE", "ASSERTION"),
        ):
            with self.subTest(field=field):
                row = SwitchingPrior(**{
                    item.name: getattr(source, item.name)
                    for item in fields(PriorOccurrence)
                })
                state = vars(row)
                state.update(_switch_field=field, _first=first, _later=later,
                             _reads=0, _armed=True)
                expected = evaluate((replace(source, **{field: first}),))
                # The quoted case is not an endorsement; the revoked case
                # cannot reappear as CURRENT while the hashed receipt says revoked.
                actual = evaluate((row,))
                self.assertEqual(actual.denial_factual_status,
                                 "CHECKED_INSUFFICIENT_EVIDENCE")
                # Context-only occurrences remain listed as reviewed matches,
                # while a revoked one cannot be a matched occurrence.
                if field == "status":
                    self.assertEqual(actual.matched_occurrence_ids, ())
                self.assertEqual(actual, expected)

    def test_two_independent_approved_counterexamples_both_survive_any_order(self):
        alpha = occurrence("occ:alpha", "source:alpha:v1", 2022)
        beta = occurrence("occ:beta", "source:beta:v1", 2024)
        forward = evaluate((alpha, beta))
        reverse = evaluate((beta, alpha))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward.denial_factual_status, "REFUTED_WITH_COUNTEREXAMPLE")
        self.assertEqual(forward.matched_occurrence_ids, ("occ:alpha", "occ:beta"))
        self.assertEqual(forward.relation_status, "PRIVATE_RELATION_CANDIDATE")
        self.assertFalse(forward.publication_authority)

    def test_contextual_only_match_does_not_erase_attested_refutation(self):
        direct = occurrence("occ:direct", "source:direct:v1")
        quotation = replace(
            occurrence("occ:quote", "source:quote:v1", 2023),
            speech_act="REPORTED_QUOTE", endorsed=False,
        )
        forward = evaluate((direct, quotation), "NEVER_ENDORSED")
        reverse = evaluate((quotation, direct), "NEVER_ENDORSED")
        self.assertEqual(forward, reverse)
        self.assertEqual(forward.matched_occurrence_ids, ("occ:direct", "occ:quote"))
        self.assertEqual(forward.prior_authenticity, "REVIEWED_ORIGINAL_UTTERANCE")
        self.assertEqual(forward.prior_endorsement, "REVIEWED_ENDORSED")
        self.assertEqual(forward.reason_code, "DENIAL_ATTESTED_PRIOR_ENDORSEMENT")

    def test_revoked_and_current_same_id_cannot_certify_a_prior_counterexample(self):
        active = occurrence("occ:shared", "source:shared:v1")
        revoked = replace(active, status="REVOKED")
        forward = evaluate((active, revoked))
        reverse = evaluate((revoked, active))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertEqual(forward.relation_status, "PRIVATE_HOLD")
        self.assertEqual(forward.matched_occurrence_ids, ())
        self.assertEqual(forward.reason_code, "DENIAL_CONFLICTING_OCCURRENCE_PROVENANCE")

    def test_discordant_approval_identity_same_id_cannot_certify_counterexample(self):
        original = occurrence("occ:shared", "source:shared:v1")
        alternate = replace(original, review_event_id="review:contradictory")
        for rows in ((original, alternate), (alternate, original)):
            with self.subTest(rows=rows):
                result = evaluate(rows, "NEVER_ENDORSED")
                self.assertEqual(result.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertEqual(result.matched_occurrence_ids, ())
                self.assertEqual(result.reason_code, "DENIAL_CONFLICTING_OCCURRENCE_PROVENANCE")

    def test_idempotent_exact_duplicate_keeps_one_provenance_relation(self):
        original = occurrence("occ:shared", "source:shared:v1")
        result = evaluate((original, original))
        self.assertEqual(result.denial_factual_status, "REFUTED_WITH_COUNTEREXAMPLE")
        self.assertEqual(result.matched_occurrence_ids, ("occ:shared",))

    def test_conflicting_id_does_not_hide_independent_approved_occurrence(self):
        disputed = occurrence("occ:disputed", "source:disputed:v1")
        independent = occurrence("occ:independent", "source:independent:v1", 2022)
        rows = (disputed, independent, replace(disputed, status="REVOKED"))
        forward = evaluate(rows)
        reverse = evaluate(rows[::-1])
        self.assertEqual(forward, reverse)
        self.assertEqual(forward.denial_factual_status, "REFUTED_WITH_COUNTEREXAMPLE")
        self.assertEqual(forward.matched_occurrence_ids, ("occ:independent",))
        self.assertFalse(forward.publication_authority)


if __name__ == "__main__":
    unittest.main()
