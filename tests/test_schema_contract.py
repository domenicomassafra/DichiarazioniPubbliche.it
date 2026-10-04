import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / "db" / "schema.v1.sql").read_text()

    def test_keeps_raw_and_canonical_transcripts_separate(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS content_locator", self.sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS transcript_variant", self.sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS transcript_segment", self.sql)
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS canonical_transcript_segment",
            self.sql,
        )
        self.assertIn("canonical_segment_candidate", self.sql)

    def test_transcript_uncertain_requires_publication_block(self):
        self.assertIn("TRANSCRIPT_UNCERTAIN", self.sql)
        self.assertIn("OR publication_blocked = true", self.sql)

    def test_schema_has_no_media_blob_column(self):
        forbidden = ("video_blob", "audio_blob", "media_blob", "bytea")
        lowered = self.sql.lower()
        for token in forbidden:
            self.assertNotIn(token, lowered)

    def test_right_of_reply_and_correction_are_first_class(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS right_of_reply", self.sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS correction", self.sql)
        self.assertIn("public_visibility", self.sql)
        self.assertIn("'PUBLISHED'", self.sql)
        self.assertIn("'RIGHT_OF_REPLY'", self.sql)
        self.assertIn("'CORRECTION'", self.sql)

    def test_speaker_identity_is_candidate_and_non_biometric(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS speaker_identity_candidate", self.sql)
        self.assertIn("MANUAL_REVIEW", self.sql)
        self.assertNotIn("VOICEPRINT", self.sql)
        self.assertNotIn("FACE_RECOGNITION", self.sql)

    def test_queue_has_lease_fields(self):
        self.assertIn("lease_owner", self.sql)
        self.assertIn("lease_until", self.sql)

    def test_provider_receipts_are_first_class(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS provider_receipt", self.sql)
        self.assertIn("estimated_cost_usd", self.sql)

    def test_claim_evidence_candidate_exists_before_finding(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS claim_evidence_candidate", self.sql)
        self.assertIn("relation_candidate", self.sql)
        self.assertIn("retrieval_version", self.sql)

    def test_verification_and_reanalysis_are_append_only_first_class_records(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS evidence_observation", self.sql)
        self.assertIn("status              text NOT NULL DEFAULT 'CANDIDATE'", self.sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS verification_run", self.sql)
        self.assertIn("verification_rule", self.sql)
        self.assertIn("observation_ids", self.sql)
        self.assertIn("verification_run_id", self.sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS claim_relation_candidate", self.sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS reanalysis_trigger", self.sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS review_event", self.sql)

    def test_reasoned_inference_is_private_first_class_candidate(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS inference_candidate", self.sql)
        self.assertIn("CHECK (publication_blocked = true)", self.sql)
        self.assertIn("'ABDUCTIVE_BEST_EXPLANATION'", self.sql)
        self.assertIn("'CRIMINAL_ALLEGATION'", self.sql)

    def test_text_claim_provenance_is_first_class_and_hash_bounded(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS claim_text_provenance", self.sql)
        self.assertIn("'TEXT_QUOTE_HASH'", self.sql)
        self.assertIn("'TEXT_POSITION_HASH'", self.sql)
        self.assertIn("quote_sha256 ~ '^[0-9a-f]{64}$'", self.sql)
        self.assertIn("'CLAIM_TEXT_PROVENANCE'", self.sql)

    def test_finding_assessment_uses_canonical_verification_vocabulary(self):
        block = self.sql[
            self.sql.index("CREATE TABLE IF NOT EXISTS finding") : self.sql.index(
                "CREATE TABLE IF NOT EXISTS correction", self.sql.index(
                    "CREATE TABLE IF NOT EXISTS finding"
                )
            )
        ]
        for assessment in (
            "SUPPORTED",
            "FACTUALLY_FALSE",
            "OUTDATED_DATA",
            "INSUFFICIENT_EVIDENCE",
            "UNRESOLVED",
        ):
            self.assertIn(f"'{assessment}'", block)
        for forbidden in (
            "NO_CONTRADICTION_ESTABLISHED",
            "PARTIALLY_SUPPORTED",
            "CONTRADICTED",
            "IMPRECISE",
        ):
            self.assertNotIn(forbidden, block)

    def test_finding_vocabulary_migration_does_not_rewrite_existing_rows(self):
        migration = (
            ROOT
            / "db"
            / "migrations"
            / "20260925-add-finding-assessment-vocabulary.sql"
        ).read_text()
        self.assertIn("DROP CONSTRAINT IF EXISTS finding_assessment_check", migration)
        self.assertIn("ADD CONSTRAINT finding_assessment_check", migration)
        self.assertNotIn("UPDATE finding", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS claim_type_version", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS assessment_version", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS publication_status_version", migration)


class RoleIntervalSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (ROOT / "db" / "schema.v1.sql").read_text()
        cls.migration = (
            ROOT
            / "db"
            / "migrations"
            / "20260925-add-role-interval-organizations.sql"
        ).read_text()

    @staticmethod
    def _block(sql, table):
        start = sql.index("CREATE TABLE IF NOT EXISTS " + table)
        end = sql.index(");", start)
        return sql[start:end]

    def test_organization_and_role_interval_are_additive_tables(self):
        for source in (self.sql, self.migration):
            self.assertIn("CREATE TABLE IF NOT EXISTS organization", source)
            self.assertIn("CREATE TABLE IF NOT EXISTS person_role_interval", source)

    def test_role_interval_requires_start_and_allows_open_end(self):
        block = self._block(self.sql, "person_role_interval")
        self.assertIn("start_date          date NOT NULL", block)
        self.assertIn("end_date            date", block)
        self.assertIn("CHECK (end_date IS NULL OR end_date >= start_date)", block)

    def test_role_interval_overlap_is_excluded(self):
        block = self._block(self.sql, "person_role_interval")
        self.assertIn("CONSTRAINT person_role_interval_overlap_excl", block)
        self.assertIn("EXCLUDE USING gist", block)
        self.assertIn(
            "daterange(start_date, end_date, '[)'::text) WITH &&", block
        )
        self.assertIn("WHERE (status = 'ACTIVE')", block)

    def test_role_interval_uses_half_open_adjacency_friendly_bounds(self):
        # [start_date, end_date): ranges touch only at the boundary, so
        # adjacent intervals for the same person+org+role may share a date.
        block = self._block(self.sql, "person_role_interval")
        self.assertIn("daterange(start_date, end_date, '[)'::text)", block)
        self.assertNotIn("daterange(start_date, end_date, '[]'::text)", block)

    def test_public_role_claim_requires_provenance(self):
        block = self._block(self.sql, "person_role_interval")
        self.assertIn("source_ref          jsonb", block)
        self.assertIn("is_public_role      boolean NOT NULL DEFAULT true", block)
        self.assertIn("CHECK (is_public_role = false OR source_ref IS NOT NULL)", block)

    def test_role_interval_supports_correction_supersession_lineage(self):
        block = self._block(self.sql, "person_role_interval")
        self.assertIn("status              text NOT NULL DEFAULT 'ACTIVE'", block)
        self.assertIn(
            "supersedes_id       text REFERENCES person_role_interval(id)", block
        )
        self.assertIn("CHECK (status IN ('ACTIVE', 'SUPERSEDED'))", block)
        self.assertIn("CHECK (supersedes_id IS NULL OR supersedes_id <> id)", block)

    def test_role_interval_has_no_person_score_or_ranking(self):
        block = self._block(self.sql, "person_role_interval")
        lowered = block.lower()
        for token in ("score", "reliability", "ranking", "fitness", "truthfulness"):
            self.assertNotIn(token, lowered)

    def test_time_specific_role_lookup_exists(self):
        for source in (self.sql, self.migration):
            self.assertIn("CREATE OR REPLACE FUNCTION person_role_interval_at", source)
            self.assertIn("status = 'ACTIVE'", source)
            self.assertIn("end_date IS NULL OR at_date < end_date", source)

    def test_time_lookup_uses_half_open_exclusive_end(self):
        # Half-open [start_date, end_date): at_date == end_date is NOT a hit.
        for source in (self.sql, self.migration):
            self.assertIn("end_date IS NULL OR at_date < end_date", source)
            self.assertNotIn("end_date IS NULL OR at_date <= end_date", source)

    def test_public_role_legacy_compatibility_is_documented(self):
        for source in (self.sql, self.migration):
            self.assertIn("COMMENT ON COLUMN person.public_role", source)
            self.assertIn("legacy timeless", source.lower())
            self.assertIn("person_role_interval", source)

    def test_migration_is_replay_idempotent(self):
        lowered = self.migration.lower()
        for marker in (
            "create extension if not exists btree_gist",
            "create table if not exists organization",
            "create table if not exists person_role_interval",
            "create index if not exists person_role_interval_person_idx",
            "create index if not exists person_role_interval_org_idx",
            "create or replace function person_role_interval_at",
        ):
            self.assertIn(marker, lowered)
        for forbidden in (
            "add column",
            "drop table",
            "drop column",
        ):
            self.assertNotIn(forbidden, lowered)
        self.assertIn(
            "drop constraint if exists review_event_entity_type_check",
            lowered,
        )
        self.assertIn("'person_role_interval'", lowered)


if __name__ == "__main__":
    unittest.main()
