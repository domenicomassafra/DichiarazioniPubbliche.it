"""Synthetic, non-real persons/acts: private documentary-role guard for DP-313."""

import dataclasses
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.procedural_document_roles import (  # noqa: E402
    AssertionKind,
    DocumentPerson,
    DocumentaryRole,
    ProceduralDocumentSource,
    ProceduralSpanAnnotation,
    ProceduralStatus,
    PrivacyClass,
    assess_procedural_independence,
    evaluate_procedural_document,
)

TEXT = (
    "Il testimone Ada riferisce: «Non ho visto Bruno».\n"
    "La procura allega che Bruno era presente.\n"
    "Il giudice dispone l'archiviazione per Carla."
)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source(text=TEXT, **changes):
    data = dict(
        capture_ref="capture:test-1",
        original_record_ref="origin:synthetic-1",
        family_ref="family:court-1",
        version_ref="document:v1",
        source_kind="COURT_ORDER",
        source_text=text,
        source_sha256=digest(text),
        jurisdiction_ref="court:fictional-it",
        issued_date="2026-01-10",
        effective_date="2026-01-10",
        document_author_ref="body:judge",
        reporting_body_ref="body:court",
        authenticity_review_ref="review:source-1",
        source_format="NATIVE_TEXT",
        version_current=True,
        page_ranges=((1, 0, len(text)),),
    )
    data.update(changes)
    return ProceduralDocumentSource(**data)


def people(*, bruno=PrivacyClass.PUBLIC_FIGURE, alias=()):
    return (
        DocumentPerson("person:ada", PrivacyClass.PUBLIC_FIGURE),
        DocumentPerson("person:bruno", bruno, tuple(alias)),
        DocumentPerson("person:carla", PrivacyClass.PUBLIC_FIGURE),
    )


def span(fragment, *, text=TEXT, kind=AssertionKind.TESTIMONY,
         role=DocumentaryRole.WITNESS, speaker="person:ada",
         subjects=("person:bruno",), status=ProceduralStatus.UNKNOWN, **changes):
    begin = text.index(fragment)
    data = dict(
        start_char=begin,
        end_char=begin + len(fragment),
        page_number=1,
        text_sha256=digest(fragment),
        annotation_review_ref="review:annotation-1",
        assertion_kind=kind,
        speaker_role=role,
        asserted_by_ref=speaker,
        subject_person_refs=subjects,
        procedural_party_refs=("person:bruno",),
        status=status,
        status_jurisdiction_ref="court:fictional-it",
        status_effective_date="2026-01-10",
        negation_polarity="NEGATED" if "Non " in fragment else "AFFIRMED",
        negation_review_ref="review:negation-1",
    )
    data.update(changes)
    return ProceduralSpanAnnotation(**data)


class ProceduralDocumentRoleTests(unittest.TestCase):
    def test_witness_statement_in_judge_document_is_not_judge_endorsement(self):
        claim = span("Non ho visto Bruno")
        result = evaluate_procedural_document(source(), people(), (claim,))
        row = result.spans[0]
        self.assertEqual(row.state, "CANDIDATE_PRIVATE")
        self.assertEqual(row.speaker_role, DocumentaryRole.WITNESS)
        self.assertEqual(row.asserted_by_ref, "person:ada")
        self.assertEqual(row.document_author_ref, "body:judge")
        self.assertEqual(row.reporting_body_ref, "body:court")
        self.assertEqual(row.subject_person_refs, ("person:bruno",))
        self.assertEqual(row.assertion_kind, AssertionKind.TESTIMONY)
        self.assertEqual(row.underlying_fact_assessment, "NOT_EVALUATED")
        self.assertFalse(row.publication_authority)
        self.assertNotIn(TEXT, repr(result.to_metadata()))

    def test_allegation_and_court_disposition_do_not_establish_underlying_fact(self):
        accusation = span(
            "La procura allega che Bruno era presente.",
            kind=AssertionKind.ALLEGATION, role=DocumentaryRole.ALLEGATION,
            speaker="body:prosecutor", negation_polarity="AFFIRMED",
        )
        order = span(
            "Il giudice dispone l'archiviazione per Carla.",
            kind=AssertionKind.FINDING_ORDER, role=DocumentaryRole.COURT_DECISION,
            speaker="body:judge", subjects=("person:carla",),
            status=ProceduralStatus.DISMISSED, procedural_party_refs=("person:carla",),
        )
        result = evaluate_procedural_document(source(), people(), (accusation, order))
        self.assertEqual(result.state, "CANDIDATE_PRIVATE")
        self.assertEqual(result.spans[0].assertion_kind, AssertionKind.ALLEGATION)
        self.assertEqual(result.spans[1].status, ProceduralStatus.DISMISSED)
        self.assertEqual(result.spans[1].assertion_kind, AssertionKind.FINDING_ORDER)
        self.assertTrue(all(x.underlying_fact_assessment == "NOT_EVALUATED" for x in result.spans))

    def test_quoted_person_is_distinct_from_author_and_reporter(self):
        row = span(
            "Non ho visto Bruno", kind=AssertionKind.QUOTED_TEXT,
            role=DocumentaryRole.QUOTED, speaker="person:ada",
            quoted_author_ref="person:ada",
        )
        result = evaluate_procedural_document(source(), people(), (row,))
        self.assertEqual(result.spans[0].quoted_author_ref, "person:ada")
        self.assertNotEqual(result.spans[0].document_author_ref, "person:ada")

    def test_reporter_missing_quoted_author_cannot_claim_provenance(self):
        reported = span(
            "Non ho visto Bruno", kind=AssertionKind.QUOTED_TEXT,
            role=DocumentaryRole.REPORTER, speaker="body:reporter",
        )
        result = evaluate_procedural_document(source(), people(), (reported,))
        self.assertIn("QUOTED_AUTHOR_ATTRIBUTION_UNVERIFIED", result.spans[0].reason_codes)

    def test_reporter_named_quote_cannot_trust_an_unresolved_person_reference(self):
        quoted = span(
            "Non ho visto Bruno", kind=AssertionKind.QUOTED_TEXT,
            role=DocumentaryRole.REPORTER, speaker="body:reporter",
            quoted_author_ref="person:unregistered",
        )
        held = evaluate_procedural_document(source(), people(), (quoted,))
        self.assertEqual(held.state, "HOLD")
        self.assertIn("QUOTED_AUTHOR_IDENTITY_UNVERIFIED", held.spans[0].reason_codes)
        self.assertFalse(held.spans[0].publication_authority)

        known = evaluate_procedural_document(source(), people(), (
            dataclasses.replace(quoted, quoted_author_ref="person:ada"),
        ))
        self.assertEqual(known.spans[0].state, "CANDIDATE_PRIVATE")

    def test_mismatched_role_or_source_family_cannot_become_court_decision(self):
        row = span(
            "La procura allega che Bruno era presente.",
            kind=AssertionKind.FINDING_ORDER, role=DocumentaryRole.ALLEGATION,
            speaker="body:prosecutor",
        )
        held = evaluate_procedural_document(source(), people(), (row,))
        self.assertIn("ROLE_ASSERTION_KIND_MISMATCH", held.spans[0].reason_codes)
        fake_press = evaluate_procedural_document(
            source(source_kind="NEWS_REPORT"), people(), (
                span("Il giudice dispone l'archiviazione per Carla.",
                     kind=AssertionKind.FINDING_ORDER,
                     role=DocumentaryRole.COURT_DECISION, speaker="body:judge",
                     subjects=("person:carla",), procedural_party_refs=("person:carla",),
                     status=ProceduralStatus.DISMISSED),
            )
        )
        self.assertIn("NON_COURT_SOURCE_CANNOT_ATTEST_ORDER", fake_press.spans[0].reason_codes)

    def test_all_five_procedural_statuses_remain_distinct(self):
        scenarios = (
            ("Mario è indagato.", ProceduralStatus.INVESTIGATED),
            ("Mario è imputato.", ProceduralStatus.CHARGED),
            ("Mario è condannato.", ProceduralStatus.CONVICTED),
            ("Mario è assolto.", ProceduralStatus.ACQUITTED),
            ("Mario è archiviato.", ProceduralStatus.DISMISSED),
        )
        results = []
        for phrase, status in scenarios:
            with self.subTest(status=status):
                value = evaluate_procedural_document(
                    source(phrase),
                    (DocumentPerson("person:mario", PrivacyClass.PUBLIC_FIGURE),),
                    (span(phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
                          role=DocumentaryRole.AUTHOR, speaker="body:judge",
                          subjects=("person:mario",), procedural_party_refs=("person:mario",),
                          status=status, negation_polarity="AFFIRMED"),),
                )
                results.append(value.spans[0])
                self.assertEqual(value.spans[0].state, "CANDIDATE_PRIVATE")
                self.assertEqual(value.spans[0].status, status)
        self.assertEqual(len({x.status for x in results}), 5)

    def test_mislabeled_status_or_jurisdiction_effective_date_holds(self):
        phrase = "Mario è indagato."
        base = span(
            phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
            role=DocumentaryRole.AUTHOR, speaker="body:judge",
            subjects=("person:mario",), status=ProceduralStatus.CONVICTED,
            negation_polarity="AFFIRMED",
        )
        person = (DocumentPerson("person:mario", PrivacyClass.PUBLIC_FIGURE),)
        wrong = evaluate_procedural_document(source(phrase), person, (base,))
        self.assertIn("PROCEDURAL_STATUS_LEXICAL_CONFLICT", wrong.spans[0].reason_codes)
        for changes in (
            {"status_jurisdiction_ref": "court:other"},
            {"status_effective_date": "2027-01-01"},
        ):
            with self.subTest(changes=changes):
                held = evaluate_procedural_document(source(phrase), person, (dataclasses.replace(
                    base, status=ProceduralStatus.INVESTIGATED, **changes
                ),))
                self.assertEqual(held.state, "HOLD")

    def test_ocr_dropped_negation_and_name_or_date_mismatch_hold(self):
        original = "Non ho visto Bruno il 10/01/2026."
        for ocr in ("Ho visto Bruno il 10/01/2026.",
                    "Non ho visto Bruna il 10/01/2026.",
                    "Non ho visto Bruno il 11/01/2026."):
            with self.subTest(ocr=ocr):
                result = evaluate_procedural_document(
                    source(ocr, source_format="OCR"),
                    people(),
                    (span(ocr, text=ocr, ocr_original_excerpt=original,
                          ocr_original_review_ref="review:scan",
                          ocr_confidence=0.97,
                          negation_polarity="NEGATED" if ocr.startswith("Non") else "AFFIRMED"),),
                )
                self.assertIn("OCR_ORIGINAL_MISMATCH", result.spans[0].reason_codes)

    def test_ocr_requires_manual_original_comparison_without_magic_threshold(self):
        phrase = "Non ho visto Bruno"
        held = evaluate_procedural_document(
            source(phrase, source_format="OCR"), people(),
            (span(phrase, text=phrase, ocr_confidence=0.99),),
        )
        self.assertIn("OCR_ORIGINAL_COMPARISON_REQUIRED", held.spans[0].reason_codes)
        reviewed = evaluate_procedural_document(
            source(phrase, source_format="OCR"), people(),
            (span(phrase, text=phrase, ocr_confidence=0.35,
                  ocr_original_excerpt=phrase, ocr_original_review_ref="review:original"),),
        )
        self.assertEqual(reviewed.state, "CANDIDATE_PRIVATE")
        self.assertFalse(reviewed.spans[0].publication_authority)

    def test_ambiguous_alias_and_multiple_people_are_not_silently_resolved(self):
        phrase = "Mario Rossi è indagato."
        ambiguous = DocumentPerson(
            "person:mario-1", PrivacyClass.PUBLIC_FIGURE,
            ("person:mario-1", "person:mario-2"),
        )
        result = evaluate_procedural_document(
            source(phrase),
            (ambiguous, DocumentPerson("person:mario-2", PrivacyClass.PUBLIC_FIGURE)),
            (span(phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
                  role=DocumentaryRole.AUTHOR, speaker="body:judge",
                  subjects=("person:mario-1", "person:mario-2"),
                  procedural_party_refs=("person:mario-1", "person:mario-2"),
                  status=ProceduralStatus.INVESTIGATED, negation_polarity="AFFIRMED"),),
        )
        self.assertIn("PERSON_ALIAS_COLLISION", result.spans[0].reason_codes)
        self.assertEqual(result.spans[0].subject_person_refs, ("person:mario-1", "person:mario-2"))

    def test_minor_victim_incidental_and_private_person_hold_separately(self):
        for privacy in (
            PrivacyClass.MINOR, PrivacyClass.VICTIM, PrivacyClass.INCIDENTAL,
            PrivacyClass.PRIVATE_PERSON, PrivacyClass.UNKNOWN,
        ):
            with self.subTest(privacy=privacy):
                result = evaluate_procedural_document(
                    source(), people(bruno=privacy),
                    (span("Non ho visto Bruno"),),
                )
                self.assertEqual(result.state, "HOLD")
                self.assertIn("SUBJECT_PRIVACY_REVIEW_REQUIRED", result.spans[0].reason_codes)
                self.assertNotIn(TEXT, repr(result.to_metadata()))

    def test_private_minor_witness_or_quoted_author_is_not_exposed_as_safe(self):
        private_witness = (
            DocumentPerson("person:ada", PrivacyClass.MINOR),
            DocumentPerson("person:bruno", PrivacyClass.PUBLIC_FIGURE),
        )
        for claim in (
            span("Non ho visto Bruno"),
            span("Non ho visto Bruno", kind=AssertionKind.QUOTED_TEXT,
                 role=DocumentaryRole.QUOTED, quoted_author_ref="person:ada"),
        ):
            with self.subTest(role=claim.speaker_role):
                result = evaluate_procedural_document(source(), private_witness, (claim,))
                self.assertIn("SPEAKER_PRIVACY_REVIEW_REQUIRED", result.spans[0].reason_codes)
                self.assertEqual(result.state, "HOLD")

    def test_negated_conviction_does_not_become_positive_procedural_status(self):
        phrase = "Mario non è condannato."
        result = evaluate_procedural_document(
            source(phrase), (DocumentPerson("person:mario", PrivacyClass.PUBLIC_FIGURE),),
            (span(phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
                  role=DocumentaryRole.AUTHOR, speaker="body:judge",
                  subjects=("person:mario",), procedural_party_refs=("person:mario",),
                  status=ProceduralStatus.CONVICTED, negation_polarity="NEGATED"),),
        )
        self.assertEqual(result.state, "HOLD")
        self.assertIn("NEGATED_STATUS_NOT_ESTABLISHED", result.spans[0].reason_codes)
        self.assertEqual(result.spans[0].underlying_fact_assessment, "NOT_EVALUATED")

    def test_news_cannot_authoritatively_label_a_court_status(self):
        phrase = "Mario è condannato."
        result = evaluate_procedural_document(
            source(phrase, source_kind="NEWS_REPORT"),
            (DocumentPerson("person:mario", PrivacyClass.PUBLIC_FIGURE),),
            (span(phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
                  role=DocumentaryRole.AUTHOR, speaker="body:judge",
                  subjects=("person:mario",), procedural_party_refs=("person:mario",),
                  status=ProceduralStatus.CONVICTED, negation_polarity="AFFIRMED"),),
        )
        self.assertIn("SECONDARY_SOURCE_NOT_STATUS_AUTHORITY", result.spans[0].reason_codes)

    def test_witness_source_is_not_authority_for_conviction_status(self):
        phrase = "Mario è condannato."
        person_records = (
            DocumentPerson("person:ada", PrivacyClass.PUBLIC_FIGURE),
            DocumentPerson("person:mario", PrivacyClass.PUBLIC_FIGURE),
        )
        status_row = span(
            phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
            role=DocumentaryRole.AUTHOR, speaker="person:ada",
            subjects=("person:mario",), procedural_party_refs=("person:mario",),
            status=ProceduralStatus.CONVICTED, negation_polarity="AFFIRMED",
        )
        witness = evaluate_procedural_document(
            source(phrase, source_kind="WITNESS_STATEMENT",
                   document_author_ref="person:ada", reporting_body_ref="body:police"),
            person_records, (status_row,),
        )
        self.assertEqual(witness.state, "HOLD")
        self.assertIn("WITNESS_SOURCE_NOT_STATUS_AUTHORITY", witness.spans[0].reason_codes)

        court = evaluate_procedural_document(
            source(phrase), person_records,
            (dataclasses.replace(status_row, asserted_by_ref="body:judge"),),
        )
        self.assertEqual(court.spans[0].state, "CANDIDATE_PRIVATE")

    def test_embedded_witness_or_quote_cannot_attest_court_status(self):
        """A court order may quote a conviction allegation without ordering it."""
        phrase = "Mario è condannato."
        person_records = (
            DocumentPerson("person:ada", PrivacyClass.PUBLIC_FIGURE),
            DocumentPerson("person:mario", PrivacyClass.PUBLIC_FIGURE),
        )
        cases = (
            (AssertionKind.TESTIMONY, DocumentaryRole.WITNESS, "person:ada", None),
            (AssertionKind.QUOTED_TEXT, DocumentaryRole.REPORTER, "body:reporter", "person:ada"),
            (AssertionKind.ALLEGATION, DocumentaryRole.ALLEGATION, "body:prosecutor", None),
        )
        for kind, role, speaker, quoted_author in cases:
            with self.subTest(kind=kind, role=role):
                claim = span(
                    phrase, text=phrase, kind=kind, role=role, speaker=speaker,
                    subjects=("person:mario",),
                    procedural_party_refs=("person:mario",),
                    quoted_author_ref=quoted_author,
                    status=ProceduralStatus.CONVICTED,
                    negation_polarity="AFFIRMED",
                )
                result = evaluate_procedural_document(source(phrase), person_records, (claim,))
                self.assertEqual(result.state, "HOLD")
                self.assertIn("ASSERTION_ROLE_NOT_STATUS_AUTHORITY", result.spans[0].reason_codes)
                self.assertEqual(result.spans[0].underlying_fact_assessment, "NOT_EVALUATED")
                self.assertFalse(result.spans[0].publication_authority)
        institutional = span(
            phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
            role=DocumentaryRole.AUTHOR, speaker="body:judge",
            subjects=("person:mario",), procedural_party_refs=("person:mario",),
            status=ProceduralStatus.CONVICTED, negation_polarity="AFFIRMED",
        )
        held_only_when_quoted = evaluate_procedural_document(
            source(phrase), person_records, (institutional,)
        )
        self.assertEqual(held_only_when_quoted.state, "CANDIDATE_PRIVATE")
        self.assertFalse(held_only_when_quoted.publication_authority)

    def test_conflicting_status_words_do_not_become_single_definite_status(self):
        phrase = "Mario è indagato e imputato."
        result = evaluate_procedural_document(
            source(phrase),
            (DocumentPerson("person:mario", PrivacyClass.PUBLIC_FIGURE),),
            (span(phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
                  role=DocumentaryRole.AUTHOR, speaker="body:judge",
                  subjects=("person:mario",), procedural_party_refs=("person:mario",),
                  status=ProceduralStatus.CHARGED, negation_polarity="AFFIRMED"),),
        )
        self.assertIn("MULTIPLE_PROCEDURAL_STATUS_TERMS_UNRESOLVED", result.spans[0].reason_codes)

    def test_unsupported_procedural_language_holds_even_with_typed_annotation(self):
        phrase = "Mario è indagato."
        result = evaluate_procedural_document(
            source(phrase, language="de"),
            (DocumentPerson("person:mario", PrivacyClass.PUBLIC_FIGURE),),
            (span(phrase, text=phrase, kind=AssertionKind.INSTITUTIONAL_FACT,
                  role=DocumentaryRole.AUTHOR, speaker="body:judge",
                  subjects=("person:mario",), status=ProceduralStatus.INVESTIGATED,
                  negation_polarity="AFFIRMED"),),
        )
        self.assertIn("PROCEDURAL_LANGUAGE_UNCALIBRATED", result.spans[0].reason_codes)

    def test_review_and_original_selector_hash_mismatch_or_stale_version_holds(self):
        row = span("Non ho visto Bruno")
        for doc, annotation, code in (
            (source(), dataclasses.replace(row, text_sha256="a" * 64), "SPAN_HASH_MISMATCH"),
            (source(version_current=False, supersedes_version_ref="document:v0"), row,
             "DOCUMENT_CURRENTNESS_UNVERIFIED"),
            (source(authenticity_review_ref=None), row, "SOURCE_AUTHENTICITY_UNVERIFIED"),
            (source(), dataclasses.replace(row, annotation_review_ref=None),
             "ANNOTATION_REVIEW_UNVERIFIED"),
            (source(family_ref=""), row, "SOURCE_FAMILY_UNRESOLVED"),
            (source(original_record_ref=""), row, "SOURCE_ORIGIN_UNVERIFIED"),
            (source(appeal_state="PENDING"), row, "APPEAL_PENDING_NONFINAL"),
        ):
            with self.subTest(code=code):
                result = evaluate_procedural_document(doc, people(), (annotation,))
                self.assertIn(code, result.spans[0].reason_codes)

    def test_page_range_binding_rejects_mislabeled_and_cross_page_spans(self):
        row = span("Non ho visto Bruno")
        for doc, code in (
            (source(page_ranges=()), "PAGE_BOUNDARIES_UNVERIFIED"),
            (source(page_ranges=((2, 0, len(TEXT)),)), "PAGE_SPAN_BINDING_MISMATCH"),
            (source(page_ranges=((1, 0, 8), (2, 8, len(TEXT)))),
             "PAGE_SPAN_BINDING_MISMATCH"),
        ):
            with self.subTest(code=code):
                result = evaluate_procedural_document(doc, people(), (row,))
                self.assertIn(code, result.spans[0].reason_codes)

    def test_document_revision_changes_binding_and_replay_is_stable(self):
        one = evaluate_procedural_document(source(), people(), (span("Non ho visto Bruno"),))
        two = evaluate_procedural_document(
            source(version_ref="document:v2", supersedes_version_ref="document:v1"),
            people(), (span("Non ho visto Bruno"),),
        )
        self.assertNotEqual(one.binding_sha256, two.binding_sha256)
        self.assertEqual(one.binding_sha256, evaluate_procedural_document(
            source(), people(), (span("Non ho visto Bruno"),)
        ).binding_sha256)

    def test_distinct_pages_and_span_boundaries_required(self):
        row = span("Non ho visto Bruno")
        bad = evaluate_procedural_document(source(), people(), (dataclasses.replace(
            row, page_number=0
        ),))
        self.assertIn("PAGE_LOCATOR_INVALID", bad.spans[0].reason_codes)
        with self.assertRaisesRegex(ValueError, "SPAN_RANGE_INVALID"):
            evaluate_procedural_document(source(), people(), (
                dataclasses.replace(row, end_char=len(TEXT) + 1),
            ))

    def test_conflicting_denial_annotation_holds(self):
        held = evaluate_procedural_document(
            source(), people(), (span("Non ho visto Bruno", negation_polarity="AFFIRMED"),)
        )
        self.assertIn("NEGATION_POLARITY_CONFLICT", held.spans[0].reason_codes)


class ProceduralIndependenceTests(unittest.TestCase):
    def test_two_republishers_one_family_not_two_independent_confirmation(self):
        versions = (
            source(capture_ref="capture:official", source_kind="COURT_ORDER"),
            source(capture_ref="capture:mirror", source_kind="NEWS_REPORT",
                   version_ref="document:mirror"),
        )
        groups = assess_procedural_independence(versions)
        self.assertEqual(groups.observed_family_count, 1)
        self.assertEqual(groups.independent_evidence_proven, 0)
        self.assertEqual(groups.groups[0][1], ("capture:mirror", "capture:official"))

    def test_same_origin_or_bytes_claimed_as_different_families_is_held(self):
        result = assess_procedural_independence((
            source(), source(capture_ref="capture:copy", family_ref="family:fake"),
        ))
        self.assertEqual(result.state, "HOLD")
        self.assertIn("CROSS_FAMILY_ORIGIN_CONFLICT", result.reason_codes)
        self.assertEqual(result.independent_evidence_proven, 0)

    def test_family_unknown_stays_held_not_independent(self):
        group = assess_procedural_independence((source(family_ref=""),))
        self.assertEqual(group.state, "HOLD")
        self.assertEqual(group.independent_evidence_proven, 0)


if __name__ == "__main__":
    unittest.main()
