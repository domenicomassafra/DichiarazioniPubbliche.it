-- DP-116: PostgreSQL-first private corpus search baseline.
-- Intentionally no BEGIN/COMMIT: CREATE INDEX CONCURRENTLY cannot run inside a transaction.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS content_item_search_fts_idx
    ON content_item USING gin (
        to_tsvector('italian', coalesce(title, '') || ' ' || coalesce(description, ''))
    );
CREATE INDEX CONCURRENTLY IF NOT EXISTS content_item_title_trgm_idx
    ON content_item USING gin (title gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS passage_search_fts_idx
    ON passage USING gin (to_tsvector('italian', coalesce(private_text, '')));
CREATE INDEX CONCURRENTLY IF NOT EXISTS passage_text_trgm_idx
    ON passage USING gin (private_text gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS statement_candidate_search_fts_idx
    ON statement_candidate USING gin (to_tsvector('italian', normalized_statement));
CREATE INDEX CONCURRENTLY IF NOT EXISTS statement_candidate_text_trgm_idx
    ON statement_candidate USING gin (normalized_statement gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS claim_candidate_search_fts_idx
    ON claim_candidate USING gin (to_tsvector('italian', normalized_claim));
CREATE INDEX CONCURRENTLY IF NOT EXISTS claim_candidate_text_trgm_idx
    ON claim_candidate USING gin (normalized_claim gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS atomic_claim_search_fts_idx
    ON atomic_claim USING gin (to_tsvector('italian', normalized_claim));
CREATE INDEX CONCURRENTLY IF NOT EXISTS atomic_claim_text_trgm_idx
    ON atomic_claim USING gin (normalized_claim gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS research_collection_search_fts_idx
    ON research_collection USING gin (
        to_tsvector('italian', name || ' ' || scope_text)
    );
CREATE INDEX CONCURRENTLY IF NOT EXISTS research_collection_name_trgm_idx
    ON research_collection USING gin (name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS person_alias_trgm_idx
    ON person_alias USING gin (alias gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS organization_alias_trgm_idx
    ON organization_alias USING gin (alias gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS topic_alias_trgm_idx
    ON topic_alias USING gin (alias gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS event_alias_trgm_idx
    ON event_alias USING gin (alias gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS person_name_trgm_idx
    ON person USING gin (canonical_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS organization_name_trgm_idx
    ON organization USING gin (canonical_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS topic_search_fts_idx
    ON topic USING gin (to_tsvector('italian', canonical_name || ' ' || scope_text));
CREATE INDEX CONCURRENTLY IF NOT EXISTS topic_name_trgm_idx
    ON topic USING gin (canonical_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS event_search_fts_idx
    ON event USING gin (to_tsvector('italian', canonical_name || ' ' || scope_text));
CREATE INDEX CONCURRENTLY IF NOT EXISTS event_name_trgm_idx
    ON event USING gin (canonical_name gin_trgm_ops);
