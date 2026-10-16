"""DP-440 synthetic opt-in citation-bound synopsis, never real editorial approval."""

from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.public_projection import build_public_projection  # noqa: E402
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256  # noqa: E402
from dichiarazioni_pubbliche.public_synopsis_v3 import (  # noqa: E402
    ApprovedTopicIntersection,
    ReviewedSynopsisSentence,
    prepare_public_synopsis,
)
from test_dp435_public_statement_seam import IsolatedStatementSource, STAMP  # noqa: E402


NOW = datetime(2026, 10, 11, 16, tzinfo=timezone.utc)


def bundle(two_sources=True):
    source = IsolatedStatementSource()
    value = build_public_projection(source, generated_at=STAMP, include_public_statements=True)
    if two_sources:
        second = copy.deepcopy(value["statements"][0])
        second.update({
            "statement_id": "statement:2", "version_id": "statement-version:2",
            "content_id": "content:2", "source_url": "https://example.test/second",
            "source_title": "Seconda fonte sintetica", "source_version": "source-version:2",
            "source_sha256": "a" * 64, "statement_date": "2026-10-09",
            "review_provenance": {key: f"review:{key}:2" for key in second["review_provenance"]},
        })
        value["statements"].append(second)
        value["dataset_sha256"] = projection_dataset_sha256(value)
    return value


def intersection(value, **overrides):
    keys = tuple((row["statement_id"], row["version_id"]) for row in value["statements"])
    lineages = tuple((*key, f"original-lineage:{i}") for i, key in enumerate(keys))
    return replace(ApprovedTopicIntersection(
        person_id="person:1", topic_id="topic:official-test",
        dataset_sha256=value["dataset_sha256"], statement_versions=keys,
        statement_lineages=lineages,
        review_event_id="review:topic:1", status="APPROVED",
        currentness_attestation_id="attested:snapshot:1",
        currentness_attested_at="2026-10-11T13:00:00+00:00",
        currentness_valid_until="2026-10-12T13:00:00+00:00",
    ), **overrides)


def sentence(value, index=0, **overrides):
    record = value["statements"][index]
    return replace(ReviewedSynopsisSentence(
        text="Nel corpus raccolto appare una posizione dichiarata in una fonte delimitata.",
        source_statement_versions=((record["statement_id"], record["version_id"]),),
        source_quote_sha256=(record["quote_sha256"],),
        review_event_id="review:summary:1", kind="REVIEWED_DESCRIPTIVE_SUMMARY",
    ), **overrides)


def prepare(value=None, proof=None, sentences=None, **extra):
    value = value or bundle()
    note = extra.pop("coverage_note", "Nel corpus raccolto, soltanto due fonti sintetiche verificate; copertura non esaustiva.")
    return prepare_public_synopsis(
        bundle=value, intersection=proof or intersection(value),
        reviewed_sentences=sentences if sentences is not None else (
            sentence(value), sentence(value, 1, review_event_id="review:summary:2")
        ),
        current_public_dataset_sha256=value["dataset_sha256"],
        coverage_note=note,
        now=extra.pop("now", NOW), **extra,
    )


class PublicSynopsisContractTests(unittest.TestCase):
    def test_two_sources_sentence_level_exact_citations_and_zero_model_calls(self):
        result = prepare()
        self.assertEqual(result.status, "READY_READ_MODEL")
        self.assertEqual(len(result.sentences), 2)
        self.assertTrue(all(len(s["citations"]) == 1 for s in result.sentences))
        self.assertTrue(all(s["citations"][0]["quote_sha256"] for s in result.sentences))
        self.assertEqual(result.provider_calls, 0)
        self.assertEqual(result, prepare())
        self.assertIsNone(result.sentences[0].get("person_truth_score"))

    def test_snapshot_date_is_pinned_to_source_projection_not_reader_clock(self):
        value = bundle()
        self.assertEqual(value["generated_at"], STAMP)
        first = prepare(value)
        later = prepare(value, now=datetime(2026, 10, 11, 17, tzinfo=timezone.utc))
        self.assertEqual((first.status, later.status),
                         ("READY_READ_MODEL", "READY_READ_MODEL"))
        self.assertEqual(first.snapshot_at, STAMP)
        self.assertEqual(later.snapshot_at, STAMP)
        self.assertEqual(first, later)
        self.assertEqual(first.fingerprint, later.fingerprint)

    def test_sparse_source_withholds_not_hallucinates_coverage(self):
        value = bundle(two_sources=False)
        result = prepare(value, sentences=(sentence(value),))
        self.assertEqual(result.status, "WITHHELD")
        self.assertEqual(result.reason_code, "SYNOPSIS_TOO_FEW_PUBLISHED_SOURCES")
        self.assertFalse(result.sentences)

    def test_duplicate_mirror_lineages_cannot_fabricate_independent_sources(self):
        value = bundle()
        proof = intersection(value)
        proof = replace(proof, statement_lineages=(
            (*proof.statement_versions[0], "lineage:same"),
            (*proof.statement_versions[1], "lineage:same"),
        ))
        self.assertEqual(prepare(value, proof=proof).reason_code, "SYNOPSIS_TOO_FEW_PUBLISHED_SOURCES")

    def test_two_statements_on_same_content_or_locator_are_not_two_sources(self):
        for shared_field in ("content_id", "source_url"):
            with self.subTest(shared_field=shared_field):
                value = bundle()
                # Distinct approved lineage labels cannot turn two excerpts of
                # the same Content/locator into independent public sources.
                value["statements"][1][shared_field] = value["statements"][0][shared_field]
                value["dataset_sha256"] = projection_dataset_sha256(value)
                result = prepare(value)
                self.assertEqual(result.status, "WITHHELD")
                self.assertEqual(result.reason_code, "SYNOPSIS_TOO_FEW_PUBLISHED_SOURCES")

    def test_rehosted_identical_source_bytes_do_not_count_as_independent(self):
        value = bundle()
        # Both Statement records claim distinct Content IDs, HTTPS URLs and
        # externally reviewed lineage labels; one source file was mirrored.
        # Two URL hosts must not count as two independent corroborating texts.
        value["statements"][1]["source_sha256"] = value["statements"][0]["source_sha256"]
        value["dataset_sha256"] = projection_dataset_sha256(value)
        result = prepare(value)
        self.assertEqual(result.status, "WITHHELD")
        self.assertEqual(result.reason_code, "SYNOPSIS_TOO_FEW_PUBLISHED_SOURCES")

    def test_currentness_must_not_precede_snapshot_or_cited_source_dates(self):
        future_bundle = bundle()
        future_bundle["generated_at"] = "2026-10-12T16:00:00+00:00"
        future_bundle["dataset_sha256"] = projection_dataset_sha256(future_bundle)
        result = prepare(future_bundle)
        self.assertEqual(result.status, "WITHHELD")
        self.assertEqual(result.reason_code, "SYNOPSIS_SNAPSHOT_IN_FUTURE")

        future_statement = bundle()
        future_statement["statements"][1]["statement_date"] = "2026-10-12"
        future_statement["dataset_sha256"] = projection_dataset_sha256(future_statement)
        result = prepare(future_statement)
        self.assertEqual(result.status, "WITHHELD")
        self.assertEqual(result.reason_code, "SYNOPSIS_CITATION_IN_FUTURE")

    def test_currentness_attestation_has_a_bounded_period_after_snapshot(self):
        value = bundle()
        result = prepare(value, proof=intersection(
            value, currentness_valid_until="2026-10-11T15:59:59+00:00"))
        self.assertEqual(result.status, "WITHHELD")
        self.assertEqual(result.reason_code, "SYNOPSIS_CURRENTNESS_ATTESTATION_EXPIRED")

        result = prepare(value, proof=intersection(
            value, currentness_attested_at="2026-10-11T11:59:59+00:00"))
        self.assertEqual(result.status, "WITHHELD")
        self.assertEqual(result.reason_code, "SYNOPSIS_CURRENTNESS_ATTESTATION_STALE")

        result = prepare(value, proof=intersection(
            value, currentness_attested_at="2026-10-11T17:00:00+00:00"))
        self.assertEqual(result.status, "WITHHELD")
        self.assertEqual(result.reason_code, "SYNOPSIS_CURRENTNESS_ATTESTATION_IN_FUTURE")

        result = prepare(value, proof=intersection(
            value, currentness_valid_until="2026-10-12T00:00:00"))
        self.assertEqual(result.status, "WITHHELD")
        self.assertEqual(result.reason_code, "SYNOPSIS_CURRENTNESS_ATTESTATION_INVALID")

    def test_changed_dataset_and_unapproved_topic_permission_hold(self):
        value = bundle()
        self.assertEqual(prepare(value, proof=intersection(value, status="REVOKED")).status, "WITHHELD")
        self.assertEqual(prepare(value, proof=intersection(value, dataset_sha256="0" * 64)).reason_code,
                         "SYNOPSIS_STALE_OR_UNAPPROVED_SNAPSHOT")
        result = prepare_public_synopsis(
            bundle=value, intersection=intersection(value), reviewed_sentences=(sentence(value),),
            current_public_dataset_sha256="0" * 64, coverage_note="corpus delimitato", now=NOW,
        )
        self.assertEqual(result.reason_code, "SYNOPSIS_STALE_OR_UNAPPROVED_SNAPSHOT")

    def test_wrong_person_or_missing_topic_membership_fails_closed(self):
        value = bundle()
        first = sentence(value)
        bad_proof = intersection(value, person_id="person:other")
        self.assertEqual(prepare(value, proof=bad_proof).reason_code, "SYNOPSIS_CITATION_NOT_PUBLIC_MEMBERSHIP")
        missing_proof = intersection(value, statement_versions=(("statement:unknown", "version:unknown"),),
                                     statement_lineages=(("statement:unknown", "version:unknown", "lineage:unknown"),))
        self.assertEqual(prepare(value, proof=missing_proof, sentences=(first,)).reason_code,
                         "SYNOPSIS_CITATION_NOT_PUBLIC_MEMBERSHIP")

    def test_wrong_quote_hash_and_repeat_citation_review_hold(self):
        value = bundle()
        self.assertEqual(prepare(value, sentences=(sentence(value, source_quote_sha256=("f" * 64,)),)).reason_code,
                         "SYNOPSIS_ORIGINAL_QUOTE_CHANGED")
        self.assertEqual(prepare(value, sentences=(sentence(value), sentence(value))).reason_code,
                         "SYNOPSIS_SENTENCE_PROVENANCE_INVALID")

    def test_topic_membership_or_currentness_event_cannot_review_synopsis_sentence(self):
        value = bundle()
        proof = intersection(value)
        # Approval of membership/currentness is not an independent editorial
        # sentence review even when the public Statement citations are valid.
        for reused in (proof.review_event_id, proof.currentness_attestation_id):
            with self.subTest(reused=reused):
                sentences = (
                    sentence(value, review_event_id=reused),
                    sentence(value, 1, review_event_id="review:summary:separate"),
                )
                result = prepare(value, proof=proof, sentences=sentences)
                self.assertEqual(result.status, "WITHHELD")
                self.assertEqual(result.reason_code, "SYNOPSIS_SENTENCE_PROVENANCE_INVALID")
        self.assertEqual(prepare(value, proof=proof).status, "READY_READ_MODEL")

    def test_later_private_source_locator_mutation_cannot_rewrite_citation(self):
        value = bundle()
        public_read = prepare(value)
        self.assertEqual(public_read.status, "READY_READ_MODEL")
        frozen_fingerprint = public_read.fingerprint
        citation_locator = copy.deepcopy(public_read.sentences[0]["citations"][0]["locator"])
        value["statements"][0]["locator"]["start_char"] += 10
        self.assertEqual(public_read.sentences[0]["citations"][0]["locator"], citation_locator)
        self.assertEqual(public_read.fingerprint, frozen_fingerprint)

    def test_quoted_criticism_not_turned_into_stance(self):
        value = bundle()
        value["statements"][0]["speech_act"] = "REPORTED_QUOTE"
        value["statements"][0]["endorsed"] = False
        value["dataset_sha256"] = projection_dataset_sha256(value)
        self.assertEqual(prepare(value).reason_code, "SYNOPSIS_REPORTED_SPEECH_NOT_ENDORSEMENT")
        first = sentence(value, kind="SOURCE_LIST_ONLY")
        second = sentence(value, 1, review_event_id="review:summary:2")
        self.assertEqual(prepare(value, sentences=(first, second)).status, "READY_READ_MODEL")

    def test_no_unreviewed_generation_or_original_quote_disguised_as_summary(self):
        value = bundle()
        original = value["statements"][0]["original_text"]
        self.assertEqual(prepare(value, sentences=(sentence(value, text="La fonte dice: " + original),)).reason_code,
                         "SYNOPSIS_VERBATIM_IN_SYNTHESIS")
        self.assertEqual(prepare(value, sentences=(sentence(value, review_event_id=""),)).status, "WITHHELD")

    def test_bad_coverage_note_and_non_verbatim_v2_bundle_rejected(self):
        value = bundle()
        self.assertEqual(prepare(value, coverage_note="Risultati completi di ogni dichiarazione").status, "WITHHELD")
        value["schema_version"] = "dichiarazioni-pubbliche-public-v2"
        with self.assertRaises(Exception):
            prepare(value)


if __name__ == "__main__":
    unittest.main()
