import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.corpus_search import (  # noqa: E402
    CORPUS_SEARCH_SQL_V1,
    SEARCH_CONTRACT_VERSION,
    SEARCH_RESULT_KINDS,
    TRIGRAM_PLAN_PROBE_SQL_V1,
    CorpusSearchRequest,
    CorpusSearchResult,
    result_ids,
)
from dichiarazioni_pubbliche.corpus_search_benchmark import load_fixture  # noqa: E402


class CorpusSearchContractTests(unittest.TestCase):
    def test_request_is_versioned_bounded_and_rejects_unknown_kinds(self):
        request = CorpusSearchRequest(
            query="DNA unghie Sempio",
            kinds=("ATOMIC_CLAIM", "CONTENT"),
            person_id="person:roberta-bruzzone",
            limit=25,
        )
        self.assertEqual(request.contract_version, SEARCH_CONTRACT_VERSION)
        self.assertEqual(json.loads(request.variables()["kinds"]), ["ATOMIC_CLAIM", "CONTENT"])
        with self.assertRaisesRegex(ValueError, "SEARCH_KIND_INVALID"):
            CorpusSearchRequest(query="x", kinds=("UNKNOWN",))
        with self.assertRaisesRegex(ValueError, "SEARCH_LIMIT_OUT_OF_RANGE"):
            CorpusSearchRequest(query="x", limit=101)
        with self.assertRaisesRegex(ValueError, "SEARCH_QUERY_REQUIRED"):
            CorpusSearchRequest(query="   ")

    def test_request_datetime_requires_timezone(self):
        with self.assertRaisesRegex(ValueError, "TIMEZONE_REQUIRED"):
            CorpusSearchRequest(query="x", from_at="2026-01-01T00:00:00")
        request = CorpusSearchRequest(query="x", from_at="2026-01-01T00:00:00+01:00")
        self.assertEqual(request.variables()["from_at"], "2026-01-01T00:00:00+01:00")

    def test_result_parser_preserves_jump_and_filter_fields(self):
        result = CorpusSearchResult.from_dict(
            {
                "kind": "ATOMIC_CLAIM",
                "id": "claim:1",
                "label": "claim text",
                "snippet": "claim text",
                "content_id": "content:1",
                "passage_id": "canonical-segment:1",
                "source_id": "source:1",
                "person_id": "person:1",
                "topic_id": None,
                "event_id": None,
                "event_at": "2026-01-01T00:00:00+00:00",
                "status": "ATOMIC",
                "claim_type": "HISTORICAL_CLAIM",
                "check_worthy": True,
                "lexical_score": 0.2,
                "trigram_score": 0.8,
            }
        )
        self.assertEqual(result.content_id, "content:1")
        self.assertEqual(result.passage_id, "canonical-segment:1")
        self.assertGreater(result.score, result.lexical_score)
        self.assertEqual(result_ids([result]), ("claim:1",))

    def test_sql_spans_all_required_private_result_families(self):
        for kind in SEARCH_RESULT_KINDS:
            self.assertIn(f"'{kind}'", CORPUS_SEARCH_SQL_V1)
        for table in (
            "content_item", "passage", "statement_candidate", "claim_candidate",
            "atomic_claim", "person", "organization", "topic", "event", "research_collection",
        ):
            self.assertIn(table, CORPUS_SEARCH_SQL_V1)

    def test_sql_has_structured_filters_and_only_approved_entity_relations(self):
        for variable in (
            "collection_id", "person_id", "topic_id", "event_id", "source_id", "content_id",
            "status", "claim_type", "check_worthy", "from_at", "to_at",
        ):
            self.assertIn(f":'{variable}'", CORPUS_SEARCH_SQL_V1)
        self.assertIn("erc.status='APPROVED'", CORPUS_SEARCH_SQL_V1)
        self.assertIn("rcc.status='INCLUDED'", CORPUS_SEARCH_SQL_V1)

    def test_collection_scoped_speakers_require_exact_historical_claim_membership(self):
        # Before DP-214's first persisted collection, collection-scoped search
        # lost the two PERSON baseline cases: PERSON rows have no content_id.
        # The fix must bind a real existing historical speaker to an included
        # collection Content, not expose arbitrary people or model candidates.
        self.assertIn("h.kind='PERSON' AND h.person_id IS NOT NULL", CORPUS_SEARCH_SQL_V1)
        self.assertIn("JOIN atomic_claim ac ON ac.content_id=rcc.content_id", CORPUS_SEARCH_SQL_V1)
        self.assertIn("ac.speaker_person_id=h.person_id", CORPUS_SEARCH_SQL_V1)
        self.assertIn("rcc.collection_id=:'collection_id'", CORPUS_SEARCH_SQL_V1)
        self.assertIn("rcc.status='INCLUDED'", CORPUS_SEARCH_SQL_V1)
        self.assertIn("h.kind='COLLECTION' AND h.id=:'collection_id'", CORPUS_SEARCH_SQL_V1)
        self.assertNotIn("h.kind='ORGANIZATION' AND h.id=:'collection_id'", CORPUS_SEARCH_SQL_V1)

    def test_sql_is_provider_free_and_similarity_is_retrieval_only(self):
        lowered = CORPUS_SEARCH_SQL_V1.lower()
        self.assertNotIn("http://", lowered)
        self.assertNotIn("https://", lowered)
        self.assertNotIn("embedding", lowered)
        self.assertNotIn("provider_receipt", lowered)
        self.assertNotIn("verification_run", lowered)
        self.assertNotIn("finding", lowered)
        self.assertNotIn("review_event", lowered)
        self.assertIn("websearch_to_tsquery('italian'", lowered)
        self.assertIn("word_similarity", lowered)
        self.assertIn("<%", CORPUS_SEARCH_SQL_V1)

    def test_trigram_plan_probe_forces_index_eligible_path(self):
        self.assertIn("SET enable_seqscan=off", TRIGRAM_PLAN_PROBE_SQL_V1)
        self.assertIn("<% normalized_claim", TRIGRAM_PLAN_PROBE_SQL_V1)
        self.assertIn("word_similarity", TRIGRAM_PLAN_PROBE_SQL_V1)
        self.assertIn("RESET enable_seqscan", TRIGRAM_PLAN_PROBE_SQL_V1)

    def test_versioned_benchmark_contains_real_and_typo_queries(self):
        version, top_k, minimum, cases = load_fixture()
        self.assertEqual(version, "corpus-search-benchmark-v1")
        self.assertEqual(top_k, 5)
        self.assertGreaterEqual(minimum, 0.9)
        self.assertGreaterEqual(len(cases), 10)
        typo = [c for c in cases if c.requires_trigram]
        self.assertGreaterEqual(len(typo), 2)
        all_expected = {x for case in cases for x in case.expected_any_ids}
        self.assertIn("person:roberta-bruzzone", all_expected)
        self.assertTrue(any(x.startswith("claim:garlasco:") for x in all_expected))


if __name__ == "__main__":
    unittest.main()
