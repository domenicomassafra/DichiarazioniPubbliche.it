import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.linked_data import (  # noqa: E402
    projection_linked_data_receipt,
    projection_ntriples,
    public_resource_uri,
    topic_public_uri,
)
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    build_public_projection,
    dossier_jsonld,
)
from dichiarazioni_pubbliche.public_schema import projection_dataset_sha256  # noqa: E402
from dichiarazioni_pubbliche.wording_contract import (  # noqa: E402
    WordingType,
    make_summary_wording,
    make_translation_wording,
)
from tests.test_public_projection import (  # noqa: E402
    FakeContentSource,
    FakeSource,
    reset_row_wording,
    valid_content_row,
    valid_row,
)


class LinkedDataTests(unittest.TestCase):
    def payload(self):
        return build_public_projection(FakeSource([valid_row()]))

    def test_stable_resource_uri_is_https_and_kind_scoped(self):
        self.assertEqual(
            public_resource_uri("person", "person:a"),
            "https://dichiarazionipubbliche.it/id/person/person%3Aa",
        )
        self.assertNotEqual(
            public_resource_uri("person", "same"),
            public_resource_uri("finding", "same"),
        )

    def test_claimreview_and_rdf_share_statement_and_finding_identities(self):
        payload = self.payload()
        dossier = payload["dossiers"][0]
        graph = dossier_jsonld(dossier)
        triples = projection_ntriples(payload)
        finding_uri = public_resource_uri("finding", dossier["finding_id"])
        statement_uri = public_resource_uri("statement", dossier["claim_id"])
        self.assertEqual(graph["@id"], finding_uri)
        self.assertEqual(graph["itemReviewed"]["@id"], statement_uri)
        self.assertIn(f"<{finding_uri}>", triples)
        self.assertIn(f"<{statement_uri}>", triples)

    def test_export_is_deterministic_and_projection_fingerprinted(self):
        payload = self.payload()
        first = projection_ntriples(payload)
        second = projection_ntriples(copy.deepcopy(payload))
        self.assertEqual(first, second)
        receipt = projection_linked_data_receipt(payload)
        self.assertEqual(receipt["projection_fingerprint"], payload["dataset_sha256"])
        self.assertGreater(receipt["triple_count"], 0)

    def test_export_contains_no_private_transcript_or_review_fields(self):
        payload = self.payload()
        encoded = projection_ntriples(payload)
        forbidden = (
            "transcript_sha256",
            "variant_id",
            "review_event_ids",
            "publication_review_ids",
            "source_ref",
            "quote_sha256",
        )
        for token in forbidden:
            self.assertNotIn(token, encoded)

    def test_rdf_wording_metadata_distinguishes_source_and_derived_without_text_leak(self):
        row = valid_row()
        occurrence_id = f"statement:{row['claim_id']}"
        summary_text = "Sintesi editoriale privata."
        translation_text = "The value is 10."
        summary = make_summary_wording(
            occurrence_id=occurrence_id,
            summary=summary_text,
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_version="test-v1",
        )
        translation = make_translation_wording(
            occurrence_id=occurrence_id,
            source_text=row["normalized_claim"],
            translated_text=translation_text,
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            source_language="it",
            target_language="en",
            method="HUMAN",
            derivation_version="test-v1",
            human_reviewed=True,
        )
        reset_row_wording(row, representations=(summary, translation))
        encoded = projection_ntriples(build_public_projection(FakeSource([row])))
        occurrence_uri = public_resource_uri("occurrence", occurrence_id)
        self.assertIn(f"<{occurrence_uri}>", encoded)
        self.assertIn('"VERBATIM_ORIGINAL"', encoded)
        self.assertIn('"PARAPHRASE"', encoded)
        self.assertIn('"SUMMARY"', encoded)
        self.assertIn('"TRANSLATION"', encoded)
        self.assertIn('"HUMAN_REVIEWED"', encoded)
        self.assertIn('"DERIVED_REPRESENTATION"', encoded)
        self.assertIn('"false"', encoded)
        self.assertNotIn(summary_text, encoded)
        self.assertNotIn(translation_text, encoded)

    def test_zero_finding_public_content_is_present_in_linked_data(self):
        payload = build_public_projection(
            FakeContentSource([], [valid_content_row()])
        )
        encoded = projection_ntriples(payload)
        content_uri = public_resource_uri("content", "content:a")
        self.assertIn(f"<{content_uri}>", encoded)
        self.assertIn('"Source"', encoded)
        self.assertIn('"VIDEO"', encoded)
        self.assertNotIn("review:content-a", encoded)
        self.assertNotIn("private_capture_path", encoded)

    def test_approved_public_media_metadata_is_linked_without_private_state(self):
        payload = build_public_projection(
            FakeContentSource(
                [],
                [
                    valid_content_row(
                        public_media_url="https://media.example.test/embed/1",
                        media_policy_version="public-media-v1",
                    )
                ],
            )
        )
        encoded = projection_ntriples(payload)
        self.assertIn("https://media.example.test/embed/1", encoded)
        self.assertIn('"public-media-v1"', encoded)

    def test_no_person_score_or_ranking_is_exported(self):
        encoded = projection_ntriples(self.payload()).lower()
        for token in ("person_score", "truth_score", "trust_score", "ranking", "leaderboard"):
            self.assertNotIn(token, encoded)

    def test_finding_supersession_uses_prov_revision_relation(self):
        row = valid_row()
        row["supersedes_id"] = "finding:old"
        payload = build_public_projection(FakeSource([row]))
        encoded = projection_ntriples(payload)
        self.assertIn(
            "<http://www.w3.org/ns/prov#wasRevisionOf>",
            encoded,
        )
        self.assertIn(
            f"<{public_resource_uri('finding', 'finding:old')}>",
            encoded,
        )

    def test_topic_uses_canonical_public_topic_uri(self):
        payload = self.payload()
        dossier = payload["dossiers"][0]
        payload["topics"] = [
            {
                "topic_id": "topic:a",
                "slug": "tema-a",
                "canonical_name": "Tema A",
                "scope_text": "Ambito A",
                "entity_version": "knowledge-entity-v1",
                "review_event_ids": ["review:topic:a"],
                "memberships": [
                    {
                        "membership_id": "membership:a",
                        "claim_id": dossier["claim_id"],
                        "finding_ids": [dossier["finding_id"]],
                        "review_event_ids": ["review:membership:a"],
                        "source_resolution_candidate_id": None,
                    }
                ],
            }
        ]
        payload["dataset_sha256"] = projection_dataset_sha256(payload)
        encoded = projection_ntriples(payload)
        self.assertIn(f"<{topic_public_uri('tema-a')}>", encoded)


if __name__ == "__main__":
    unittest.main()
