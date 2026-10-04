import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CorpusSearchSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (ROOT / "db" / "migrations" / "20260929-add-corpus-search.sql").read_text()

    def test_fresh_schema_and_migration_enable_pg_trgm(self):
        self.assertIn("CREATE EXTENSION IF NOT EXISTS pg_trgm", self.schema)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS pg_trgm", self.migration)

    def test_existing_table_indexes_are_concurrent_in_migration(self):
        self.assertNotIn("BEGIN;", self.migration)
        self.assertNotIn("COMMIT;", self.migration)
        self.assertIn("CREATE INDEX CONCURRENTLY IF NOT EXISTS", self.migration)
        self.assertNotIn("CREATE INDEX IF NOT EXISTS content_item_search_fts_idx", self.migration)

    def test_required_fts_and_trigram_indexes_exist(self):
        index_names = (
            "content_item_search_fts_idx", "content_item_title_trgm_idx",
            "passage_search_fts_idx", "passage_text_trgm_idx",
            "statement_candidate_search_fts_idx", "statement_candidate_text_trgm_idx",
            "claim_candidate_search_fts_idx", "claim_candidate_text_trgm_idx",
            "atomic_claim_search_fts_idx", "atomic_claim_text_trgm_idx",
            "research_collection_search_fts_idx", "research_collection_name_trgm_idx",
            "person_alias_trgm_idx", "organization_alias_trgm_idx", "topic_alias_trgm_idx", "event_alias_trgm_idx",
            "person_name_trgm_idx", "organization_name_trgm_idx",
            "topic_search_fts_idx", "topic_name_trgm_idx", "event_search_fts_idx", "event_name_trgm_idx",
        )
        for index in index_names:
            self.assertIn(index, self.schema)
            self.assertIn(index, self.migration)

    def test_italian_fts_is_explicit(self):
        self.assertGreaterEqual(self.schema.count("to_tsvector('italian'"), 7)
        self.assertGreaterEqual(self.migration.count("to_tsvector('italian'"), 7)

    def test_no_new_search_service_or_vector_extension(self):
        lowered = (self.schema + self.migration).lower()
        self.assertNotIn("create extension if not exists vector", lowered)
        self.assertNotIn(" vector(", lowered)
        self.assertNotIn("elasticsearch", lowered)
        self.assertNotIn("opensearch", lowered)


if __name__ == "__main__":
    unittest.main()
