"""DP-315 conservative offline denial checks. All people/source data synthetic."""

import sys
import hashlib
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.denial_prior_utterance import (  # noqa: E402
    DenialTarget, PriorOccurrence, evaluate_denial,
)
from dichiarazioni_pubbliche.context_integrity import assess_speech_act_context  # noqa: E402

YEAR = lambda year: datetime(year, 10, 10, 10, tzinfo=timezone.utc)
SHA = "a" * 64
Q = "b" * 64
P = "c" * 64


def target(**changes):
    return replace(DenialTarget(
        denial_id="denial:demo", person_id="person:demo", source_version_id="source:later:v1",
        source_sha256="d" * 64, review_event_id="review:later:1", uttered_at=YEAR(2026),
        target_quote_sha256=Q, target_proposition_sha256=P, predicate="NEVER_UTTERED",
        quantifier="NEVER", scope="PUBLIC", from_at=None, through_at=None,
    ), **changes)


def prior(**changes):
    return replace(PriorOccurrence(
        occurrence_id="occurrence:demo", source_version_id="source:prior:v1",
        source_sha256=SHA, quote_sha256=Q, proposition_sha256=P,
        spoken_at=YEAR(2024), utterer_person_id="person:demo",
        quoted_person_id=None, speech_act="ASSERTION", endorsed=True,
        publication_scope="PUBLIC", review_event_id="review:prior:1",
    ), **changes)


def assess(t=None, rows=None, versions=None):
    return evaluate_denial(
        t or target(), (prior(),) if rows is None else rows,
        current_source_versions=versions if versions is not None else {
            "source:later:v1": "d" * 64, "source:prior:v1": SHA,
        },
    )


class ThreeTrackDenialTests(unittest.TestCase):
    def test_optional_original_context_binding_prevents_reported_words_from_refuting_denial(self):
        words = "Io sostengo che il piano funziona"
        quote_hash = hashlib.sha256(words.encode()).hexdigest()
        def case(text, quoted_author_id=None):
            source_hash = hashlib.sha256(text.encode()).hexdigest()
            index = text.index(words)
            context = assess_speech_act_context(
                source_text=text, source_sha256=source_hash,
                quote_start=index, quote_end=index + len(words),
                turn_start=0, turn_end=len(text),
                utterer_id="person:demo", turn_speaker_ids=("person:demo",),
                quoted_author_id=quoted_author_id,
                source_part_ref="source:prior:v1", turn_complete=True,
                language="it",
            ).to_metadata()
            occurrence = prior(source_sha256=source_hash, quote_sha256=quote_hash)
            versions = {"source:later:v1": "d" * 64, "source:prior:v1": source_hash}
            return context, occurrence, versions

        direct_context, direct_row, direct_versions = case(words)
        later = target(target_quote_sha256=quote_hash)
        confirmed = evaluate_denial(
            later, (direct_row,), current_source_versions=direct_versions,
            prior_source_context={direct_row.occurrence_id: (words, direct_context)},
        )
        self.assertEqual(confirmed.denial_factual_status, "REFUTED_WITH_COUNTEREXAMPLE")
        self.assertFalse(confirmed.publication_authority)

        reported = f"Secondo Luca, «{words}»."
        reported_context, reported_row, reported_versions = case(reported, "person:luca")
        # A caller can mislabel reported words as direct and add a fictitious
        # review event. Without checking the original source this falsely
        # becomes a private counterexample.
        self.assertEqual(
            evaluate_denial(later, (reported_row,),
                            current_source_versions=reported_versions).denial_factual_status,
            "REFUTED_WITH_COUNTEREXAMPLE",
        )
        guarded = evaluate_denial(
            later, (reported_row,), current_source_versions=reported_versions,
            prior_source_context={reported_row.occurrence_id: (reported, reported_context)},
        )
        self.assertEqual(guarded.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertEqual(guarded.relation_status, "PRIVATE_HOLD")
        self.assertEqual(guarded.reason_code, "DENIAL_PRIOR_CONTEXT_UNVERIFIED")
        self.assertNotEqual(confirmed.receipt_sha256, guarded.receipt_sha256)

        for supplied in ({}, {direct_row.occurrence_id: (words + " alterato", direct_context)}):
            with self.subTest(supplied=supplied):
                held = evaluate_denial(
                    later, (direct_row,), current_source_versions=direct_versions,
                    prior_source_context=supplied,
                )
                self.assertEqual(held.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertEqual(held.reason_code, "DENIAL_PRIOR_CONTEXT_UNVERIFIED")
                self.assertNotEqual(held.receipt_sha256, confirmed.receipt_sha256)
        with self.assertRaisesRegex(ValueError, "DENIAL_CONTEXT_INPUT_INVALID"):
            evaluate_denial(
                later, (direct_row,), current_source_versions=direct_versions,
                prior_source_context={"occurrence:unrelated": (words, direct_context)},
            )

    def test_prior_same_person_original_refutes_never_uttered_only_privately(self):
        row = assess()
        self.assertEqual(row.denial_factual_status, "REFUTED_WITH_COUNTEREXAMPLE")
        self.assertEqual(row.prior_authenticity, "REVIEWED_ORIGINAL_UTTERANCE")
        self.assertEqual(row.relation_status, "PRIVATE_RELATION_CANDIDATE")
        self.assertEqual(row.matched_occurrence_ids, ("occurrence:demo",))
        self.assertEqual(row.prior_proposition_truth, "NOT_EVALUATED")
        self.assertFalse(row.publication_authority)
        self.assertEqual(row, assess(), "stable source replay must be deterministic")

    def test_never_endorsed_requires_actual_attested_endorsement(self):
        t = target(predicate="NEVER_ENDORSED")
        self.assertEqual(assess(t).denial_factual_status, "REFUTED_WITH_COUNTEREXAMPLE")
        undecided = assess(t, rows=(prior(endorsed=False),))
        self.assertEqual(undecided.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
        self.assertEqual(undecided.relation_status, "PRIVATE_HOLD")

    def test_quoted_criticism_or_ironized_words_not_prior_direct_position(self):
        for act in ("REPORTED_QUOTE", "CRITICISM", "IRONY", "QUESTION", "PERFORMANCE"):
            with self.subTest(act=act):
                row = assess(target(predicate="NEVER_ENDORSED"), rows=(prior(speech_act=act, endorsed=False),))
                self.assertEqual(row.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertEqual(row.relation_status, "PRIVATE_HOLD")
                self.assertEqual(row.prior_endorsement, "NOT_ESTABLISHED")

    def test_never_meant_cannot_be_refuted_from_words_even_if_endorsed(self):
        row = assess(target(predicate="NEVER_MEANT"))
        self.assertEqual(row.reason_code, "DENIAL_INNER_INTENT_UNVERIFIABLE")
        self.assertEqual(row.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")

    def test_no_match_or_incomplete_corpus_is_not_universal_supported(self):
        for rows in ((), (prior(quote_sha256="9" * 64),)):
            with self.subTest(rows=rows):
                row = assess(rows=rows)
                self.assertEqual(row.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertNotIn("SUPPORTED", str(row))

    def test_wrong_speaker_time_private_scope_and_target_window_hold(self):
        scenarios = [
            (target(), prior(utterer_person_id="person:other")),
            (target(), prior(spoken_at=YEAR(2027))),
            (target(), prior(publication_scope="PRIVATE")),
            (target(from_at=YEAR(2025)), prior()),
            (target(through_at=YEAR(2023)), prior()),
            (target(), prior(quoted_person_id="person:other")),
        ]
        for t, original in scenarios:
            with self.subTest(t=t, original=original):
                row = assess(t, rows=(original,))
                self.assertEqual(row.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertFalse(row.publication_authority)

    def test_stale_prior_source_or_review_never_becomes_counterexample(self):
        for item in (prior(status="SUPERSEDED"), prior(status="REVOKED"), prior(review_event_id=None)):
            with self.subTest(item=item):
                self.assertEqual(assess(rows=(item,)).denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
        versions = {"source:later:v1": "d" * 64, "source:prior:v1": "0" * 64}
        self.assertEqual(assess(versions=versions).reason_code, "DENIAL_PRIOR_SOURCE_HASH_STALE_OR_UNKNOWN")
        self.assertNotEqual(assess().receipt_sha256, assess(versions=versions).receipt_sha256)

    def test_later_denial_source_stale_cannot_be_refuted(self):
        versions = {"source:later:v1": "0" * 64, "source:prior:v1": SHA}
        row = assess(versions=versions)
        self.assertEqual(row.reason_code, "DENIAL_TARGET_SOURCE_STALE_OR_UNKNOWN")
        self.assertEqual(row.denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")

    def test_person_quote_and_proposition_changes_invalidate_receipt(self):
        initial = assess()
        for changed in (
            target(person_id="person:other"),
            target(target_quote_sha256="f" * 64),
            target(target_proposition_sha256="f" * 64),
        ):
            with self.subTest(changed=changed):
                self.assertEqual(assess(changed).denial_factual_status, "CHECKED_INSUFFICIENT_EVIDENCE")
                self.assertNotEqual(initial.receipt_sha256, assess(changed).receipt_sha256)

    def test_review_time_scope_and_prior_provenance_mutations_stale_denial_receipt(self):
        original = assess()
        # A still-matching occurrence may be reviewed anew or may occupy a
        # different period. Identical outcome text must not reuse its old
        # integrity fingerprint under materially different approved inputs.
        for t, rows in (
            (target(review_event_id="review:later:2"), (prior(),)),
            (target(from_at=YEAR(2023)), (prior(),)),
            (target(through_at=YEAR(2025)), (prior(),)),
            (target(), (prior(review_event_id="review:prior:2"),)),
            (target(), (prior(spoken_at=YEAR(2023)),)),
            (target(), (prior(speech_act="OPINION"),)),
        ):
            with self.subTest(target=t, rows=rows):
                after = assess(t, rows=rows)
                self.assertEqual(after.denial_factual_status, original.denial_factual_status)
                self.assertNotEqual(after.receipt_sha256, original.receipt_sha256)

    def test_invalid_predicate_or_malformed_quoted_endorsement_denied(self):
        with self.assertRaisesRegex(ValueError, "SCOPE_OR_PREDICATE"):
            target(predicate="NEVER_LIED")
        with self.assertRaisesRegex(ValueError, "FALSE_ENDORSEMENT"):
            prior(speech_act="REPORTED_QUOTE", endorsed=True)
        with self.assertRaisesRegex(ValueError, "FALSE_ENDORSEMENT"):
            prior(speech_act="PERFORMANCE", endorsed=True)
        with self.assertRaisesRegex(ValueError, "AWARE_TIME"):
            prior(spoken_at=datetime(2024, 10, 10))


if __name__ == "__main__":
    unittest.main()
