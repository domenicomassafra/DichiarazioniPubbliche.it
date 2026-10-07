import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.citation_assurance import assertion_text_sha256  # noqa: E402
from dichiarazioni_pubbliche.context_integrity import (  # noqa: E402
    assess_structured_context_integrity,
)
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    PublicProjectionStore,
    build_public_projection,
    dossier_jsonld,
    projection_jsonld,
    render_dossier_html,
    write_public_bundle,
)
from dichiarazioni_pubbliche.wording_contract import (  # noqa: E402
    WordingType,
    make_summary_wording,
    make_translation_wording,
    wording_contract_metadata,
)


class FakeSource:
    def __init__(self, rows):
        self.rows = rows

    def projectable_findings(self):
        return self.rows


class FakeContentSource(FakeSource):
    def __init__(self, rows, contents):
        super().__init__(rows)
        self.contents = contents

    def projectable_contents(self):
        return self.contents


def valid_public_attribution_input():
    mention = "Persona A"
    return {
        "speaker_candidates": [
            {
                "id": "speaker-candidate:a",
                "content_id": "content:a",
                "person_id": "person:a",
                "start_ms": 0,
                "end_ms": 1000,
                "speaker_label": "PRIVATE_ALIAS_SPEAKER",
                "attribution_method": "MANUAL_REVIEW",
                "attribution_version": "speaker-attribution-v1",
                "source_ref": {"private_feature": "speaker-source-ref"},
                "confidence": 0.9999,
                "status": "APPROVED",
                "review_event_ids": ["review:speaker-a"],
            }
        ],
        "resolution_candidates": [
            {
                "id": "resolution:a",
                "content_id": "content:a",
                "passage_id": "passage:a",
                "mention_text": mention,
                "mention_text_sha256": hashlib.sha256(mention.encode()).hexdigest(),
                "entity_type": "PERSON",
                "target_id": "person:a",
                "resolution_method": "MANUAL_REVIEW",
                "resolution_version": "entity-resolution-v1",
                "supporting_features": [
                    {"code": "IDENTIFIER_ID", "value": "identifier:person-a"},
                    {"code": "KNOWN_ALIAS", "value": "PRIVATE_ALIAS_RESOLUTION"},
                ],
                "contradicting_features": [],
                "retrieval_score": 0.987654,
                "status": "APPROVED",
                "review_event_ids": ["review:resolution-a"],
            }
        ],
        "identifiers": [
            {
                "id": "identifier:person-a",
                "entity_type": "PERSON",
                "entity_id": "person:a",
                "identifier_kind": "OFFICIAL_PERSON_ID",
                "identifier_value": "PRIVATE_IDENTIFIER_VALUE",
                "authority": "OFFICIAL_REGISTER",
                "identifier_version": "entity-identifier-v1",
                "source_ref": {"private_identifier_source": "must-not-escape"},
                "status": "ACTIVE",
                "supersedes_id": None,
            }
        ],
        "role_intervals": [
            {
                "id": "role:a",
                "person_id": "person:a",
                "organization_id": "org:a",
                "organization_name": "Organization A",
                "role": "Member",
                "start_date": "2026-01-01",
                "end_date": None,
                "source_ref": {"private_role_source": "must-not-escape"},
                "status": "ACTIVE",
                "review_event_ids": ["review:role-a"],
            }
        ],
    }


def valid_row():
    rationale = "Supported by the approved record."
    normalized_claim = "Il valore è 10."
    source_wording = "Il valore dichiarato nella fonte è 10."
    quote_sha256 = hashlib.sha256(source_wording.encode("utf-8")).hexdigest()
    return {
        "finding_id": "finding:a",
        "claim_id": "claim:a",
        "assessment": "SUPPORTED",
        "rationale": rationale,
        "finding_assertion_sha256": assertion_text_sha256(rationale),
        "publication_status": "PUBLISH",
        "policy_version": "policy-v1",
        "verification_run_id": "verification:a",
        "created_at": "2026-09-22T10:00:00+00:00",
        "published_at": "2026-09-22T10:05:00+00:00",
        "publication_review_ids": ["review:finding-a"],
        "supersedes_id": None,
        "normalized_claim": normalized_claim,
        "source_occurrence_quote_sha256": quote_sha256,
        "wording": wording_contract_metadata(
            occurrence_id="statement:a",
            source_text_sha256=quote_sha256,
            normalized_claim=normalized_claim,
            language="it",
            derivation_version="candidate-extraction-v1",
            source_provenance={
                "selector_type": "MEDIA_SEGMENT_REF",
                "canonical_segment_id": "segment:a",
                "quote_local_start_char": 0,
                "quote_local_end_char": len(normalized_claim),
            },
        ),
        "claim_type": "NUMERIC_STATISTIC",
        "temporal_scope": {
            "statement_date": "2026-09-21",
            "valid_from": None,
            "valid_until": None,
        },
        "check_worthy": True,
        "content_id": "content:a",
        "source_url": "https://example.test/source",
        "source_title": "Source",
        "source_published_at": "2026-09-21T10:00:00+00:00",
        "speaker": {
            "id": "person:a",
            "name": "Persona <A>",
            "public_role": "Public role",
            "public_roles": [
                {
                    "organization_id": "org:a",
                    "organization_name": "Organization A",
                    "role": "Member",
                    "start_date": "2026-01-01",
                    "end_date": None,
                    "review_event_ids": ["review:role-a"],
                }
            ],
        },
        "source_segments": [
            {
                "segment_id": "segment:a",
                "segment_index": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "transcript_candidates": [
                    {
                        "segment_id": "segment:raw-a",
                        "variant_id": "transcript:a",
                        "provider_id": "youtube",
                        "source_kind": "PLATFORM_CAPTION",
                        "transcript_sha256": "b" * 64,
                    }
                ],
            }
        ],
        "evidence": [
            {
                "id": "evidence:a",
                "url": "https://example.test/evidence",
                "publisher": "Authority",
                "source_type": "PRIMARY_OFFICIAL",
                "publication_date": "2026-09-01",
                "observed_at": "2026-09-22T10:00:00+00:00",
                "content_sha256": "a" * 64,
                "reference_period": "2026",
                "rights_status": "UNKNOWN",
                "relation": "VERIFICATION_INPUT",
                "verification_observation_ids": ["evidence-observation:a"],
                "evidence_review_ids": ["review:evidence-a"],
                "observation_review_ids": ["review:observation-a"],
                "excerpt": "must never escape",
            }
        ],
        "existing_factchecks": [],
        "corrections": [],
        "rights_of_reply": [],
        "speaker_provenance": [
            {
                "candidate_id": "speaker-candidate:a",
                "review_event_ids": ["review:speaker-a"],
            }
        ],
        "public_attribution_input": valid_public_attribution_input(),
        "raw_text": "must never escape",
    }


def valid_existing_factcheck_metadata():
    return {
        "lineage_id": "factcheck-lineage:abc",
        "version_id": "factcheck-version:def",
        "source_version": "claimreview-v1",
        "version_state": "CURRENT",
        "provider_id": "google-factcheck-tools",
        "review_url": "https://factcheck.example/reviews/claim-123",
        "review_publisher_name": "Example Fact Check",
        "review_publisher_site": "factcheck.example",
        "review_date": "2026-09-02",
        "persistence_version": "existing-factcheck-mirror-v1",
    }


def reset_row_wording(
    row: dict,
    *,
    source_text_sha256: str | None = None,
    representations=(),
):
    normalized_claim = str(row["normalized_claim"])
    quote_sha256 = source_text_sha256 or hashlib.sha256(
        f"Fonte distinta per {row['claim_id']}: {normalized_claim}".encode("utf-8")
    ).hexdigest()
    row["source_occurrence_quote_sha256"] = quote_sha256
    row["wording"] = wording_contract_metadata(
        occurrence_id=f"statement:{row['claim_id']}",
        source_text_sha256=quote_sha256,
        normalized_claim=normalized_claim,
        language="it",
        derivation_version="candidate-extraction-v1",
        representations=representations,
    )
    return row


def valid_content_row(**overrides):
    row = {
        "content_id": "content:a",
        "slug": "content-a",
        "url": "https://example.test/source",
        "title": "Source",
        "published_at": "2026-09-21T10:00:00+00:00",
        "content_kind": "VIDEO",
        "duration_ms": 180000,
        "public_media_url": None,
        "media_policy_version": None,
        "publication_version": "public-content-v1",
        "review_event_ids": ["review:content-a"],
        "private_capture_path": "/private/must-not-escape",
    }
    row.update(overrides)
    return row


class PublicProjectionTests(unittest.TestCase):
    def test_discontinuous_public_source_discloses_omissions_without_source_body(self):
        source_text = "Prima clausola. Materiale omesso. Seconda clausola."
        first = source_text.index("Prima clausola.")
        first_end = first + len("Prima clausola.")
        second = source_text.index("Seconda clausola.")
        second_end = second + len("Seconda clausola.")
        assessment = assess_structured_context_integrity(
            source_text=source_text,
            source_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
            spans=((first, first_end), (second, second_end)),
            speaker_refs=("person:a", "person:a"),
            source_part_refs=("part:a", "part:a"),
        ).to_metadata()
        assessment["state"] = "APPROVED_CURATED"
        row = valid_row()
        row["context_integrity"] = assessment

        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 1)
        disclosure = payload["dossiers"][0]["wording"]["source_span_disclosure"]
        self.assertEqual(disclosure["omission_count"], 1)
        self.assertEqual(disclosure["omission_marker"], " […] ")
        self.assertEqual(
            [(span["start_char"], span["end_char"]) for span in disclosure["spans"]],
            [(first, first_end), (second, second_end)],
        )
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(source_text, encoded)
        self.assertNotIn("Materiale omesso", encoded)

        dossier = payload["dossiers"][0]
        html = render_dossier_html(dossier)
        jsonld = json.dumps(dossier_jsonld(dossier), ensure_ascii=False)
        self.assertIn("Omissioni dichiarate: 1", html)
        self.assertIn("[…]", html)
        self.assertIn("omissionMarker", jsonld)
        self.assertIn("[…]", jsonld)
        self.assertNotIn("Materiale omesso", html)
        self.assertNotIn("Materiale omesso", jsonld)

    def test_discontinuous_public_source_cannot_cross_speaker_or_montage_boundary(self):
        source_text = "Clausola uno. Intermezzo. Clausola due."
        spans = ((0, len("Clausola uno.")), (source_text.index("Clausola due."), len(source_text)))
        source_sha = hashlib.sha256(source_text.encode()).hexdigest()
        cases = (
            dict(speaker_refs=("person:a", "person:b"), source_part_refs=("part:a", "part:a")),
            dict(speaker_refs=("person:a", "person:a"), source_part_refs=("part:a", "part:b")),
        )
        for refs in cases:
            with self.subTest(refs=refs):
                assessment = assess_structured_context_integrity(
                    source_text=source_text,
                    source_sha256=source_sha,
                    spans=spans,
                    **refs,
                ).to_metadata()
                assessment["state"] = "APPROVED_CURATED"
                row = valid_row()
                row["context_integrity"] = assessment
                payload = build_public_projection(FakeSource([row]))
                self.assertEqual(payload["dossier_count"], 0)
                self.assertEqual(payload["omitted_count"], 1)

    def test_discontinuous_public_source_omits_stale_structured_binding(self):
        source_text = "Prima clausola. Materiale omesso. Seconda clausola."
        second = source_text.index("Seconda clausola.")
        assessment = assess_structured_context_integrity(
            source_text=source_text,
            source_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
            spans=((0, len("Prima clausola.")), (second, len(source_text))),
            speaker_refs=("person:a", "person:a"),
            source_part_refs=("part:a", "part:a"),
        ).to_metadata()
        assessment["state"] = "APPROVED_CURATED"
        assessment["spans"][1]["start_char"] = second + 1
        row = valid_row()
        row["context_integrity"] = assessment

        payload = build_public_projection(FakeSource([row]))

        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

    def test_first_class_content_can_publish_with_zero_findings(self):
        payload = build_public_projection(
            FakeContentSource([], [valid_content_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        self.assertEqual(payload["dossiers"], [])
        self.assertEqual(len(payload["contents"]), 1)
        content = payload["contents"][0]
        self.assertEqual(content["content_id"], "content:a")
        self.assertEqual(content["finding_ids"], [])
        self.assertNotIn("private_capture_path", content)

    def test_first_class_content_membership_comes_only_from_projectable_findings(self):
        row = valid_row()
        payload = build_public_projection(
            FakeContentSource([row], [valid_content_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        self.assertEqual(payload["contents"][0]["finding_ids"], ["finding:a"])

        held = valid_row()
        held["publication_status"] = "POLICY_HOLD"
        payload = build_public_projection(
            FakeContentSource([held], [valid_content_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        self.assertEqual(payload["contents"][0]["finding_ids"], [])

    def test_content_collects_multiple_public_findings_for_same_source(self):
        first = valid_row()
        second = valid_row()
        second["finding_id"] = "finding:b"
        second["claim_id"] = "claim:b"
        second["normalized_claim"] = "Il valore è 11."
        reset_row_wording(second)
        payload = build_public_projection(
            FakeContentSource([first, second], [valid_content_row()])
        )
        self.assertEqual(
            payload["contents"][0]["finding_ids"],
            ["finding:a", "finding:b"],
        )

    def test_similar_content_titles_keep_distinct_reviewed_identity_and_slug(self):
        payload = build_public_projection(
            FakeContentSource(
                [],
                [
                    valid_content_row(title="Intervista serale", slug="intervista-serale-a"),
                    valid_content_row(
                        content_id="content:b",
                        title="Intervista serale",
                        slug="intervista-serale-b",
                        url="https://example.test/source-b",
                        review_event_ids=["review:content-b"],
                    ),
                ],
            )
        )
        self.assertEqual(
            [(item["content_id"], item["slug"]) for item in payload["contents"]],
            [
                ("content:a", "intervista-serale-a"),
                ("content:b", "intervista-serale-b"),
            ],
        )

    def test_content_membership_and_fingerprint_change_when_finding_is_held(self):
        published = valid_row()
        first = build_public_projection(
            FakeContentSource([published], [valid_content_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        held = valid_row()
        held["publication_status"] = "POLICY_HOLD"
        second = build_public_projection(
            FakeContentSource([held], [valid_content_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        self.assertEqual(first["contents"][0]["finding_ids"], ["finding:a"])
        self.assertEqual(second["contents"][0]["finding_ids"], [])
        self.assertNotEqual(first["dataset_sha256"], second["dataset_sha256"])

    def test_content_media_url_requires_explicit_reviewed_policy_metadata(self):
        unsafe = valid_content_row(
            public_media_url="https://media.example.test/embed/1",
            media_policy_version=None,
        )
        payload = build_public_projection(FakeContentSource([], [unsafe]))
        self.assertEqual(payload["contents"], [])

        approved = valid_content_row(
            public_media_url="https://media.example.test/embed/1",
            media_policy_version="public-media-v1",
        )
        payload = build_public_projection(FakeContentSource([], [approved]))
        self.assertEqual(
            payload["contents"][0]["public_media_url"],
            "https://media.example.test/embed/1",
        )

    def test_dataset_fingerprint_includes_first_class_contents(self):
        first = build_public_projection(
            FakeContentSource([], [valid_content_row(title="Source A")]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        second = build_public_projection(
            FakeContentSource([], [valid_content_row(title="Source B")]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        self.assertNotEqual(first["dataset_sha256"], second["dataset_sha256"])

    def test_content_store_requires_approved_candidate_and_latest_review(self):
        class CaptureStore(PublicProjectionStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return "[]"

        store = CaptureStore()
        self.assertEqual(store.projectable_contents(), [])
        self.assertIn("content_publication_candidate", store.sql)
        self.assertIn("candidate.status = 'APPROVED'", store.sql)
        self.assertIn("'CONTENT_PUBLICATION_CANDIDATE'", store.sql)
        self.assertIn("ORDER BY review.created_at DESC", store.sql)

    def approved_relation(self, **overrides):
        relation = {
            "id": "relation:a",
            "relation_type": "POSITION_CHANGE_CANDIDATE",
            "relation_version": "claim-relation-v1",
            "status": "APPROVED",
            "role": "SUBJECT",
            "related_claim_id": "claim:b",
            "related_claim": "Il valore è 20.",
            "related_statement_date": "2026-08-01",
            "rationale_codes": ["SAME_PROPOSITION_OPPOSITE_STANCE"],
            "review_event_id": "review:relation-a",
        }
        relation.update(overrides)
        return relation

    def test_source_methodology_is_bounded_to_public_safe_fields(self):
        row = valid_row()
        row["source_methodology"] = {
            "assessment": "SUFFICIENT_FOR_RULE",
            "assessment_version": "evidence-set-assessment-v1",
            "requirement_profile_version": "evidence-requirements-v1",
            "rationale_codes": ["EVIDENCE_REQUIREMENTS_SATISFIED"],
            "coverage_need_candidates": [{"private": "must not escape"}],
            "rejected_evidence": [{"private_note": "must not escape"}],
        }
        payload = build_public_projection(FakeSource([row]))
        methodology = payload["dossiers"][0]["source_methodology"]
        self.assertEqual(methodology["assessment"], "SUFFICIENT_FOR_RULE")
        self.assertEqual(
            methodology["rationale_codes"], ["EVIDENCE_REQUIREMENTS_SATISFIED"]
        )
        self.assertNotIn("coverage_need_candidates", methodology)
        self.assertNotIn("rejected_evidence", methodology)

    def test_legacy_dossier_omits_absent_source_methodology(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        self.assertNotIn("source_methodology", payload["dossiers"][0])

    def test_approved_relation_requires_one_review_event_and_publishes(self):
        row = valid_row()
        row["relations"] = [self.approved_relation()]
        payload = build_public_projection(FakeSource([row]))
        relations = payload["dossiers"][0]["relations"]
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["review_event_id"], "review:relation-a")
        self.assertEqual(
            relations[0]["relation_type"], "POSITION_CHANGE_CANDIDATE"
        )
        self.assertEqual(relations[0]["status"], "APPROVED")
        self.assertEqual(relations[0]["related_claim_id"], "claim:b")

    def test_unreviewed_or_malformed_relation_is_omitted_fail_closed(self):
        for broken in (
            self.approved_relation(review_event_id=None),
            self.approved_relation(relation_type="PUBLISHED_CONTRADICTION"),
            self.approved_relation(related_claim_id=""),
            self.approved_relation(related_claim=None),
        ):
            row = valid_row()
            row["relations"] = [broken]
            payload = build_public_projection(FakeSource([row]))
            self.assertEqual(payload["dossiers"], [])
            self.assertEqual(payload["omitted_count"], 1)

    def test_relation_never_carries_intent_or_person_aggregate(self):
        row = valid_row()
        row["relations"] = [self.approved_relation()]
        payload = build_public_projection(FakeSource([row]))
        encoded = json.dumps(
            payload["dossiers"][0]["relations"], ensure_ascii=False
        ).lower()
        for token in (
            "intent",
            "deliberate",
            "falsehood",
            "reliability",
            "score",
        ):
            self.assertNotIn(token, encoded)

    def test_sql_projection_requires_fresh_review_after_transcript_change(self):
        class CaptureStore(PublicProjectionStore):
            def __init__(self):
                self.sql = ""

            def run(self, sql, **variables):
                self.sql = sql
                return "[]"

        store = CaptureStore()
        self.assertEqual(store.projectable_findings(), [])
        self.assertIn("freshness_review.created_at >=", store.sql)
        self.assertIn("segment.updated_at", store.sql)
        self.assertIn("trigger.status = 'PROCESSED'", store.sql)
        self.assertIn("'OFFICIAL_TRANSCRIPT'", store.sql)
        self.assertIn("transcript_verbatim_review_event", store.sql)
        self.assertIn("verbatim_review.source_variant_sha256", store.sql)
        self.assertIn("verbatim_review.source_segment_sha256", store.sql)
        self.assertIn("verbatim_review.reviewed_text_sha256", store.sql)
        self.assertIn("'MANUAL_REVIEW'", store.sql)
        self.assertIn("'TRANSCRIPT_LABEL'", store.sql)
        self.assertIn("'OFFICIAL_RECORD'", store.sql)
        self.assertIn("claim.metadata->>'speech_mode'", store.sql)
        self.assertIn("'DIRECT_UTTERANCE'", store.sql)
        self.assertIn("claim.metadata#>>'{context_integrity,state}'", store.sql)
        self.assertIn("'CLEAR_AUTOMATIC'", store.sql)
        self.assertIn("'APPROVED_CURATED'", store.sql)
        self.assertNotIn("claim_candidate_promotion", store.sql)
        self.assertNotIn("FROM claim_candidate ", store.sql)
        self.assertNotIn("FROM statement_candidate ", store.sql)
        self.assertNotIn("FROM passage ", store.sql)
        self.assertIn(
            "claim.metadata#>'{context_integrity,quote_start}'",
            store.sql,
        )
        self.assertIn(
            "claim.metadata#>'{context_integrity,quote_end}'",
            store.sql,
        )
        self.assertIn(
            "claim.metadata#>>'{context_integrity,quote_sha256}'",
            store.sql,
        )
        self.assertIn("segment.canonical_text", store.sql)
        self.assertIn("char_length(segment.canonical_text)", store.sql)
        self.assertIn("substring(", store.sql)
        self.assertIn("sha256(", store.sql)
        self.assertIn(
            "candidate_link.canonical_segment_id =",
            store.sql,
        )
        self.assertIn("'CLAIM_TEXT_PROVENANCE'", store.sql)
        self.assertIn("FROM claim_text_provenance provenance", store.sql)
        self.assertIn("FROM finding_assertion assertion", store.sql)
        self.assertIn("FROM finding_assertion_citation citation", store.sql)
        self.assertIn("assertion.assertion_text = finding.rationale", store.sql)
        self.assertIn("AS finding_assertion_sha256", store.sql)
        self.assertIn(
            "citation.relation =\n                                        assertion.required_relation",
            store.sql,
        )

    def test_projection_exposes_no_raw_transcript_or_evidence_excerpt(self):
        payload = build_public_projection(
            FakeSource([valid_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["dossier_count"], 1)
        self.assertNotIn("must never escape", encoded)
        self.assertNotIn("excerpt", encoded)
        self.assertNotIn("raw_text", encoded)
        self.assertFalse(payload["methodology"]["aggregate_person_score"])

    def test_existing_factcheck_public_surface_is_metadata_link_only(self):
        row = valid_row()
        row["existing_factchecks"] = [valid_existing_factcheck_metadata()]
        payload = build_public_projection(FakeSource([row]))
        factchecks = payload["dossiers"][0]["existing_factchecks"]
        self.assertEqual(factchecks, [valid_existing_factcheck_metadata()])
        encoded = json.dumps(factchecks, sort_keys=True)
        for forbidden in (
            "claim_text",
            "textual_rating",
            "review_title",
            "claimant",
            "provider_receipt",
            "normalized_record",
            "rights_status",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_existing_factcheck_public_surface_rejects_unapproved_shape_or_url(self):
        row = valid_row()
        unsafe = valid_existing_factcheck_metadata()
        unsafe["textual_rating"] = "False"
        row["existing_factchecks"] = [unsafe]
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

        row = valid_row()
        unsafe = valid_existing_factcheck_metadata()
        unsafe["review_url"] = "https://user:secret@factcheck.example/review"
        row["existing_factchecks"] = [unsafe]
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

    def test_public_attribution_gate_emits_only_stable_identity_and_statement_time_role(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        self.assertEqual(payload["dossier_count"], 1)
        self.assertEqual(payload["omitted_count"], 0)
        dossier = payload["dossiers"][0]
        self.assertEqual(dossier["speaker"]["id"], "person:a")
        self.assertEqual(dossier["speaker"]["public_role"], "Member")
        self.assertEqual(
            dossier["speaker"]["public_roles"],
            [
                {
                    "organization_id": "org:a",
                    "organization_name": "Organization A",
                    "role": "Member",
                    "start_date": "2026-01-01",
                    "end_date": None,
                    "review_event_ids": ["review:role-a"],
                }
            ],
        )
        self.assertEqual(
            dossier["speaker"]["provenance"],
            [
                {
                    "candidate_id": "speaker-candidate:a",
                    "review_event_ids": ["review:speaker-a"],
                    "provenance_kind": "TIMED_SPEAKER",
                    "attribution_method": "MANUAL_REVIEW",
                }
            ],
        )
        self.assertNotIn("confidence", dossier["speaker"]["provenance"][0])
        self.assertNotIn("source_ref", dossier["speaker"]["provenance"][0])

        public_bytes = "\n".join(
            (
                json.dumps(payload, ensure_ascii=False),
                render_dossier_html(dossier),
                json.dumps(dossier_jsonld(dossier), ensure_ascii=False),
            )
        )
        for private_value in (
            "PRIVATE_ALIAS_SPEAKER",
            "PRIVATE_ALIAS_RESOLUTION",
            "PRIVATE_IDENTIFIER_VALUE",
            "speaker-source-ref",
            "private_identifier_source",
            "private_role_source",
            "supporting_features",
            "contradicting_features",
            "retrieval_score",
            '"confidence"',
            "public_attribution_input",
        ):
            self.assertNotIn(private_value, public_bytes)

    def test_public_attribution_gate_omits_direct_person_link_tamper(self):
        row = valid_row()
        row["speaker"]["id"] = "person:tampered"
        row["speaker"]["name"] = "Persona Tampered"
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

    def test_public_attribution_gate_omits_private_resolution_contradiction(self):
        row = valid_row()
        row["public_attribution_input"]["resolution_candidates"][0][
            "contradicting_features"
        ] = [{"code": "DATE_ROLE_CONFLICT", "value": "private-conflict"}]
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

    def test_public_attribution_gate_omits_stale_role_but_keeps_person(self):
        row = valid_row()
        row["public_attribution_input"]["role_intervals"][0]["end_date"] = "2026-01-01"
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 1)
        speaker = payload["dossiers"][0]["speaker"]
        self.assertEqual(speaker["id"], "person:a")
        self.assertIsNone(speaker["public_role"])
        self.assertEqual(speaker["public_roles"], [])

    def test_public_wording_metadata_is_bounded_and_private_free(self):
        row = valid_row()
        summary_text = "Sintesi editoriale da non pubblicare come testo derivato."
        translation_text = "The value is 10."
        summary = make_summary_wording(
            occurrence_id=f"statement:{row['claim_id']}",
            summary=summary_text,
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_version="test-v1",
            author_ref="private-editor:must-not-escape",
        )
        translation = make_translation_wording(
            occurrence_id=f"statement:{row['claim_id']}",
            source_text=row["normalized_claim"],
            translated_text=translation_text,
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            source_language="it",
            target_language="en",
            method="HUMAN",
            derivation_version="test-v1",
            human_reviewed=True,
            reviewer_ref="private-reviewer:must-not-escape",
        )
        reset_row_wording(row, representations=(summary, translation))
        payload = build_public_projection(FakeSource([row]))
        wording = payload["dossiers"][0]["wording"]
        self.assertEqual(
            wording["source_occurrence"]["wording_type"],
            "VERBATIM_ORIGINAL",
        )
        self.assertTrue(wording["source_occurrence"]["direct_quote_eligible"])
        self.assertEqual(wording["normalized_claim"]["wording_type"], "PARAPHRASE")
        self.assertFalse(wording["normalized_claim"]["direct_quote_eligible"])
        self.assertEqual(
            [item["wording_type"] for item in wording["representations"]],
            ["SUMMARY", "TRANSLATION"],
        )
        self.assertTrue(
            all(
                item["direct_quote_eligible"] is False
                for item in wording["representations"]
            )
        )
        self.assertEqual(
            wording["representations"][1]["review_state"],
            "HUMAN_REVIEWED",
        )
        self.assertEqual(
            wording["representations"][1]["source_language"],
            "it",
        )
        self.assertEqual(wording["representations"][1]["language"], "en")
        self.assertEqual(
            wording["public_provenance"]["segment_ids"],
            ["segment:a"],
        )
        encoded = json.dumps(wording, ensure_ascii=False)
        for forbidden in (
            summary_text,
            translation_text,
            "private-editor",
            "private-reviewer",
            "capture_id",
            "passage_id",
            "private_text",
            "raw_text",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_public_claim_cannot_copy_private_source_or_derived_wording_body(self):
        source_copy = valid_row()
        exact_source_hash = hashlib.sha256(
            source_copy["normalized_claim"].encode("utf-8")
        ).hexdigest()
        reset_row_wording(source_copy, source_text_sha256=exact_source_hash)
        payload = build_public_projection(FakeSource([source_copy]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

        derived_copy = valid_row()
        summary = make_summary_wording(
            occurrence_id=f"statement:{derived_copy['claim_id']}",
            summary=derived_copy["normalized_claim"],
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_version="test-v1",
        )
        reset_row_wording(derived_copy, representations=(summary,))
        payload = build_public_projection(FakeSource([derived_copy]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

        translated_copy = valid_row()
        translation = make_translation_wording(
            occurrence_id=f"statement:{translated_copy['claim_id']}",
            source_text="The source wording is distinct.",
            translated_text=translated_copy["normalized_claim"],
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            source_language="en",
            target_language="it",
            method="HUMAN",
            derivation_version="test-v1",
            human_reviewed=True,
        )
        reset_row_wording(
            translated_copy,
            source_text_sha256=hashlib.sha256(
                b"The source wording is distinct."
            ).hexdigest(),
            representations=(translation,),
        )
        payload = build_public_projection(FakeSource([translated_copy]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

    def test_derived_wording_cannot_gain_direct_quote_authority(self):
        row = valid_row()
        summary = make_summary_wording(
            occurrence_id=f"statement:{row['claim_id']}",
            summary="Sintesi editoriale.",
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_version="test-v1",
        )
        reset_row_wording(row, representations=(summary,))
        row["wording"]["representations"][0]["direct_quote_eligible"] = True
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossiers"], [])
        self.assertEqual(payload["omitted_count"], 1)

    def test_rationale_assertion_hash_mismatch_is_omitted_fail_closed(self):
        row = valid_row()
        row["finding_assertion_sha256"] = "0" * 64
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)

    def test_public_claim_contract_is_bounded_and_private_free(self):
        payload = build_public_projection(
            FakeSource([valid_row()]),
            generated_at="2026-09-22T12:00:00+00:00",
        )
        contract = payload["dossiers"][0]["claim_contract"]
        self.assertEqual(contract["version"], 1)
        self.assertEqual(contract["temporal_scope"]["statement_date"], "2026-09-21")
        self.assertTrue(contract["check_worthy"])
        self.assertTrue(contract["speaker_approval_required"])
        self.assertEqual(contract["source_segment_ids"], ["segment:a"])
        self.assertNotIn("metadata", contract)

    def test_unapproved_status_or_unsafe_url_is_omitted(self):
        row = valid_row()
        row["publication_status"] = "POLICY_HOLD"
        unsafe = valid_row()
        unsafe["finding_id"] = "finding:b"
        unsafe["claim_id"] = "claim:b"
        unsafe["source_url"] = "javascript:alert(1)"
        payload = build_public_projection(FakeSource([row, unsafe]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 2)

    def test_speaker_requires_provenance(self):
        row = valid_row()
        row["speaker_provenance"] = []
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)

    def test_public_roles_require_approval_and_do_not_expose_source_refs(self):
        row = valid_row()
        row["speaker"]["public_roles"][0]["review_event_ids"] = []
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossiers"][0]["speaker"]["public_roles"], [])
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("source_ref", encoded)
        self.assertEqual(
            payload["dossiers"][0]["speaker"]["public_role"],
            None,
        )

        approved = valid_row()
        graph = dossier_jsonld(
            build_public_projection(FakeSource([approved]))["dossiers"][0]
        )
        self.assertEqual(
            graph["itemReviewed"]["author"]["worksFor"],
            [
                {
                    "@type": "Organization",
                    "id": "https://dichiarazionipubbliche.it/id/organization/org%3Aa",
                    "name": "Organization A",
                }
            ],
        )

    def test_transcript_candidate_provenance_is_required(self):
        row = valid_row()
        row["source_segments"][0]["transcript_candidates"] = []
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)

    def test_approved_text_provenance_can_replace_timed_segments(self):
        row = valid_row()
        row["source_segments"] = []
        row["speaker_provenance"] = []
        reset_row_wording(row, source_text_sha256="c" * 64)
        row["source_text_provenance"] = [
            {
                "id": "text-provenance:a",
                "selector_type": "TEXT_QUOTE_HASH",
                "quote_sha256": row["source_occurrence_quote_sha256"],
                "source_sha256": "d" * 64,
                "start_char": None,
                "end_char": None,
                "attribution_method": "SOURCE_QUOTE",
                "attribution_version": "text-source-provenance-v1",
                "review_event_ids": ["review:text-provenance-a"],
                "source_ref": {"raw": "must never escape"},
            }
        ]
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 1)
        dossier = payload["dossiers"][0]
        self.assertEqual(dossier["source"]["segments"], [])
        self.assertEqual(
            dossier["claim_contract"]["source_text_provenance_ids"],
            ["text-provenance:a"],
        )
        self.assertEqual(
            dossier["speaker"]["provenance"][0]["provenance_kind"],
            "TEXT_ATTRIBUTION",
        )
        encoded = json.dumps(dossier, ensure_ascii=False)
        self.assertNotIn("must never escape", encoded)
        self.assertNotIn("source_ref", encoded)

    def test_text_provenance_without_review_fails_closed(self):
        row = valid_row()
        row["source_segments"] = []
        row["speaker_provenance"] = []
        row["source_text_provenance"] = [
            {
                "id": "text-provenance:a",
                "selector_type": "TEXT_QUOTE_HASH",
                "quote_sha256": "c" * 64,
                "source_sha256": None,
                "start_char": None,
                "end_char": None,
                "attribution_method": "SOURCE_QUOTE",
                "attribution_version": "text-source-provenance-v1",
                "review_event_ids": [],
            }
        ]
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)

    def test_review_ledger_provenance_is_required(self):
        row = valid_row()
        row["evidence"][0]["evidence_review_ids"] = []
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)

    def test_speaker_is_required_for_public_projection(self):
        row = valid_row()
        row["speaker"] = None
        payload = build_public_projection(FakeSource([row]))
        self.assertEqual(payload["dossier_count"], 0)

    def test_html_escapes_claim_and_speaker(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        dossier = payload["dossiers"][0]
        dossier["claim"] = "<script>alert(1)</script>"
        rendered = render_dossier_html(dossier)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("Persona &lt;A&gt;", rendered)
        self.assertIn('type="application/ld+json"', rendered)
        self.assertIn('data-wording-type="PARAPHRASE"', rendered)
        self.assertIn('data-direct-quote-eligible="false"', rendered)
        self.assertNotIn("<blockquote", rendered)

    def test_jsonld_claimreview_has_no_numeric_person_score(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        graph = dossier_jsonld(payload["dossiers"][0])
        encoded = json.dumps(graph, ensure_ascii=False)
        self.assertEqual(graph["@type"], "ClaimReview")
        self.assertEqual(graph["itemReviewed"]["@type"], "Claim")
        self.assertEqual(graph["datePublished"], "2026-09-22T10:05:00+00:00")
        self.assertEqual(
            graph["reviewRating"]["alternateName"],
            "SUPPORTED",
        )
        self.assertNotIn("ratingValue", encoded)
        self.assertNotIn("bestRating", encoded)
        self.assertNotIn("worstRating", encoded)
        self.assertNotIn("reliability", encoded.lower())
        properties = {
            item["name"]: item["value"]
            for item in graph["itemReviewed"]["additionalProperty"]
        }
        self.assertEqual(properties["wordingType"], "PARAPHRASE")
        self.assertFalse(properties["directQuoteEligible"])
        source = graph["itemReviewed"]["isBasedOn"]
        source_properties = {
            item["name"]: item["value"]
            for item in source["additionalProperty"]
        }
        self.assertEqual(source_properties["wordingType"], "VERBATIM_ORIGINAL")
        self.assertTrue(source_properties["directQuoteEligible"])
        self.assertNotIn("text", source)

    def test_jsonld_rejects_unknown_or_non_public_assessment(self):
        for assessment in (
            "INSUFFICIENT_EVIDENCE",
            "UNRESOLVED",
            "PARTIALLY_SUPPORTED",
        ):
            row = valid_row()
            row["assessment"] = assessment
            payload = build_public_projection(FakeSource([row]))
            self.assertEqual(payload["dossiers"], [])
            self.assertEqual(payload["omitted_count"], 1)

    def test_projection_jsonld_is_itemlist(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        graph = projection_jsonld(payload)
        self.assertEqual(graph["@type"], "ItemList")
        self.assertEqual(graph["numberOfItems"], 1)
        self.assertEqual(
            graph["itemListElement"][0]["item"]["@type"],
            "ClaimReview",
        )

    def test_public_correction_keeps_both_finding_ids(self):
        row = valid_row()
        row["corrections"] = [
            {
                "id": "correction:a",
                "finding_id": "finding:new",
                "previous_finding_id": "finding:a",
                "reason": "Updated evidence.",
                "changed_fields": {"assessment": ["A", "B"]},
                "created_at": "2026-09-22T12:00:00+00:00",
                "publication_review_approved": True,
            }
        ]
        payload = build_public_projection(FakeSource([row]))
        correction = payload["dossiers"][0]["corrections"][0]
        self.assertEqual(correction["finding_id"], "finding:new")
        self.assertEqual(correction["previous_finding_id"], "finding:a")

    def test_unreviewed_reply_and_correction_never_escape_projection(self):
        row = valid_row()
        row["rights_of_reply"] = [
            {
                "id": "reply:a",
                "submitter_name": "Persona",
                "submitter_role": "Ruolo",
                "submitted_at": "2026-09-22T12:00:00+00:00",
                "body": "Replica privata.",
                "evidence_urls": ["https://example.test/reply"],
                "status": "PUBLISHED",
                "publication_review_approved": False,
            },
            {
                "id": "reply:b",
                "submitter_name": "Persona",
                "submitter_role": "Ruolo",
                "submitted_at": "2026-09-22T12:00:00+00:00",
                "body": "Replica non pubblicata.",
                "evidence_urls": [],
                "status": "UNDER_REVIEW",
                "publication_review_approved": True,
            },
        ]
        row["corrections"] = [
            {
                "id": "correction:a",
                "finding_id": "finding:new",
                "previous_finding_id": "finding:a",
                "reason": "Private correction.",
                "changed_fields": {},
                "created_at": "2026-09-22T12:00:00+00:00",
                "publication_review_approved": False,
            }
        ]
        dossier = build_public_projection(FakeSource([row]))["dossiers"][0]
        self.assertEqual(dossier["rights_of_reply"], [])
        self.assertEqual(dossier["corrections"], [])

    def test_reviewed_published_reply_is_projected(self):
        row = valid_row()
        row["rights_of_reply"] = [
            {
                "id": "reply:a",
                "submitter_name": "Persona",
                "submitter_role": "Ruolo",
                "submitted_at": "2026-09-22T12:00:00+00:00",
                "body": "Replica pubblicabile.",
                "evidence_urls": ["https://example.test/reply"],
                "status": "PUBLISHED",
                "publication_review_approved": True,
            }
        ]
        dossier = build_public_projection(FakeSource([row]))["dossiers"][0]
        self.assertEqual(len(dossier["rights_of_reply"]), 1)
        self.assertEqual(dossier["rights_of_reply"][0]["id"], "reply:a")

    def test_public_bundle_writes_only_projection_files(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_public_bundle(root, payload)
            self.assertTrue((root / "index.json").is_file())
            self.assertTrue((root / "index.jsonld").is_file())
            self.assertTrue((root / "index.nt").is_file())
            self.assertTrue((root / "linked-data-receipt.json").is_file())
            self.assertEqual(len(list((root / "claims").glob("*.json"))), 1)
            self.assertEqual(len(list((root / "claims").glob("*.html"))), 1)
            self.assertEqual(len(list((root / "claims").glob("*.jsonld"))), 1)
            text = (root / "index.json").read_text()
            self.assertNotIn("must never escape", text)
            linked = (root / "index.nt").read_text()
            self.assertNotIn("transcript_sha256", linked)
            receipt = json.loads((root / "linked-data-receipt.json").read_text())
            self.assertEqual(
                receipt["projection_fingerprint"],
                payload["dataset_sha256"],
            )
            self.assertGreater(receipt["triple_count"], 0)

    def test_multiple_finding_versions_of_same_claim_do_not_overwrite(self):
        old = valid_row()
        old["finding_id"] = "finding:old"
        old["publication_status"] = "CORRECTED"
        current = valid_row()
        current["finding_id"] = "finding:new"
        current["supersedes_id"] = "finding:old"
        payload = build_public_projection(FakeSource([old, current]))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_public_bundle(root, payload)
            self.assertEqual(len(list((root / "claims").glob("*.json"))), 2)
            self.assertEqual(len(list((root / "claims").glob("*.html"))), 2)
            self.assertEqual(len(list((root / "claims").glob("*.jsonld"))), 2)

    def test_public_bundle_removes_stale_projection_files(self):
        payload = build_public_projection(FakeSource([valid_row()]))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale = root / "claims" / "stale.json"
            stale.parent.mkdir(parents=True)
            stale.write_text('{"old":true}')
            (root / "claims" / "stale.html").write_text("old")
            (root / "claims" / "stale.jsonld").write_text("{}")
            (root / "claims" / "keep.txt").write_text("not projection-owned")
            (root / "index.nt").write_text("<old> <old> <old> .\n")
            (root / "linked-data-receipt.json").write_text('{"old":true}')
            write_public_bundle(root, payload)
            self.assertFalse(stale.exists())
            self.assertFalse((root / "claims" / "stale.html").exists())
            self.assertFalse((root / "claims" / "stale.jsonld").exists())
            self.assertTrue((root / "claims" / "keep.txt").exists())
            self.assertNotIn(
                "<old>",
                (root / "index.nt").read_text(),
            )
            self.assertNotIn(
                '"old"',
                (root / "linked-data-receipt.json").read_text(),
            )

    def test_dossier_contract_violation_is_omitted_fail_closed(self):
        invalid_row = valid_row()
        # Inject an unapproved claim_type that violates canonical vocabulary
        invalid_row["claim_type"] = "INVALID_TYPE"
        payload = build_public_projection(FakeSource([invalid_row]))
        self.assertEqual(payload["dossier_count"], 0)
        self.assertEqual(payload["omitted_count"], 1)
        self.assertEqual(payload["dossiers"], [])


if __name__ == "__main__":
    unittest.main()
