import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.citation_assurance import assertion_text_sha256  # noqa: E402
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    PublicProjectionStore,
    build_public_projection,
    dossier_jsonld,
    projection_jsonld,
    render_dossier_html,
    write_public_bundle,
)


class FakeSource:
    def __init__(self, rows):
        self.rows = rows

    def projectable_findings(self):
        return self.rows


def valid_row():
    rationale = "Supported by the approved record."
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
        "normalized_claim": "Il valore è 10.",
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
        "corrections": [],
        "rights_of_reply": [],
        "speaker_provenance": [
            {
                "candidate_id": "speaker-candidate:a",
                "review_event_ids": ["review:speaker-a"],
            }
        ],
        "raw_text": "must never escape",
    }


class PublicProjectionTests(unittest.TestCase):
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
        self.assertIn("'HUMAN_AUDIO_VERIFIED'", store.sql)
        self.assertIn("'MANUAL_REVIEW'", store.sql)
        self.assertIn("'TRANSCRIPT_LABEL'", store.sql)
        self.assertIn("'OFFICIAL_RECORD'", store.sql)
        self.assertIn("claim.metadata->>'speech_mode'", store.sql)
        self.assertIn("'DIRECT_UTTERANCE'", store.sql)
        self.assertIn("claim.metadata#>>'{context_integrity,state}'", store.sql)
        self.assertIn("'CLEAR_AUTOMATIC'", store.sql)
        self.assertIn("'APPROVED_CURATED'", store.sql)
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
        row["source_text_provenance"] = [
            {
                "id": "text-provenance:a",
                "selector_type": "TEXT_QUOTE_HASH",
                "quote_sha256": "c" * 64,
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
