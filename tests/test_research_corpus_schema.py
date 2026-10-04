import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ResearchCorpusSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT / "db" / "migrations" / "20260929-add-research-corpus-core.sql"
        ).read_text()

    def test_schema_and_migration_have_same_core_tables(self):
        tables = (
            "content_capture",
            "research_collection",
            "research_collection_content",
            "passage",
            "statement_candidate",
            "statement_candidate_passage",
            "claim_candidate",
        )
        for table in tables:
            marker = f"CREATE TABLE IF NOT EXISTS {table}"
            with self.subTest(table=table):
                self.assertIn(marker, self.schema)
                self.assertIn(marker, self.migration)

    def test_content_identity_is_separate_from_immutable_versions(self):
        for sql in (self.schema, self.migration):
            self.assertIn("content_id          text NOT NULL REFERENCES content_item(id)", sql)
            self.assertIn("content_sha256      text NOT NULL", sql)
            self.assertIn("UNIQUE (content_id, content_sha256)", sql)
            self.assertIn("content_sha256 ~ '^[0-9a-f]{64}$'", sql)

    def test_passage_has_exactly_one_source_and_same_content_foreign_keys(self):
        for sql in (self.schema, self.migration):
            self.assertIn(
                "CHECK ((capture_id IS NOT NULL)::integer + (canonical_segment_id IS NOT NULL)::integer = 1)",
                sql,
            )
            self.assertIn(
                "FOREIGN KEY (capture_id, content_id) REFERENCES content_capture(id, content_id)",
                sql,
            )
            self.assertIn(
                "FOREIGN KEY (canonical_segment_id, content_id) REFERENCES canonical_transcript_segment(id, content_id)",
                sql,
            )

    def test_statement_passage_links_cannot_cross_content(self):
        for sql in (self.schema, self.migration):
            self.assertIn(
                "FOREIGN KEY (statement_candidate_id, content_id) REFERENCES statement_candidate(id, content_id)",
                sql,
            )
            self.assertIn(
                "FOREIGN KEY (passage_id, content_id) REFERENCES passage(id, content_id)",
                sql,
            )

    def test_claim_candidate_uses_canonical_taxonomy_and_promotion_state(self):
        for sql in (self.schema, self.migration):
            start = sql.index("CREATE TABLE IF NOT EXISTS claim_candidate")
            end = sql.index(");", start)
            block = sql[start:end]
            self.assertIn("proposed_claim_type IN (", block)
            self.assertIn("'VALUE_JUDGMENT'", block)
            self.assertIn("claim_type_version = 'atomic-claim-v1'", block)
            self.assertIn("OR check_worthy = false", block)
            self.assertIn(
                "CHECK ((status = 'PROMOTED') = (promoted_claim_id IS NOT NULL))",
                block,
            )

    def test_candidates_are_reviewable_but_have_no_publication_column(self):
        for sql in (self.schema, self.migration):
            for table in ("statement_candidate", "claim_candidate"):
                start = sql.index(f"CREATE TABLE IF NOT EXISTS {table}")
                end = sql.index(");", start)
                block = sql[start:end].lower()
                self.assertNotIn("publication_status", block)
                self.assertNotIn("publishable", block)
            self.assertIn("'STATEMENT_CANDIDATE'", sql)
            self.assertIn("'CLAIM_CANDIDATE'", sql)

    def test_migration_is_additive_and_replay_safe(self):
        lowered = self.migration.lower()
        self.assertIn("begin;", lowered)
        self.assertIn("commit;", lowered)
        self.assertIn("create table if not exists", lowered)
        self.assertIn("create index if not exists", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("drop column", lowered)
        self.assertNotIn("update content_item", lowered)
        self.assertNotIn("update atomic_claim", lowered)
        # The only intentional DROP is the replace-in-place enum-like review constraint.
        self.assertIn("drop constraint if exists review_event_entity_type_check", lowered)

    def test_public_projection_does_not_read_private_corpus_tables(self):
        projection = (ROOT / "poc" / "dichiarazioni_pubbliche" / "public_projection.py").read_text()
        for table in (
            "content_capture",
            "research_collection",
            "passage",
            "statement_candidate",
            "claim_candidate",
        ):
            self.assertNotIn(f"FROM {table}", projection)
            self.assertNotIn(f"JOIN {table}", projection)

    def test_restore_drill_includes_corpus_tables(self):
        restore = (
            ROOT / "poc" / "dichiarazioni_pubbliche" / "ops" / "restore_verify.py"
        ).read_text()
        for table in (
            "content_capture",
            "research_collection",
            "research_collection_content",
            "passage",
            "statement_candidate",
            "statement_candidate_passage",
            "claim_candidate",
        ):
            self.assertIn(f'"{table}"', restore)


if __name__ == "__main__":
    unittest.main()
