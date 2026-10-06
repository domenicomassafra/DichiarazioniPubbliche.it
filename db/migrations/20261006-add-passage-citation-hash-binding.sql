BEGIN;

ALTER TABLE finding_assertion_citation
    ADD COLUMN IF NOT EXISTS passage_text_sha256 text,
    ADD COLUMN IF NOT EXISTS source_content_sha256 text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'finding_assertion_citation_passage_hash_format'
          AND conrelid = 'finding_assertion_citation'::regclass
    ) THEN
        ALTER TABLE finding_assertion_citation
            ADD CONSTRAINT finding_assertion_citation_passage_hash_format
            CHECK (
                passage_text_sha256 IS NULL
                OR passage_text_sha256 ~ '^[0-9a-f]{64}$'
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'finding_assertion_citation_source_hash_format'
          AND conrelid = 'finding_assertion_citation'::regclass
    ) THEN
        ALTER TABLE finding_assertion_citation
            ADD CONSTRAINT finding_assertion_citation_source_hash_format
            CHECK (
                source_content_sha256 IS NULL
                OR source_content_sha256 ~ '^[0-9a-f]{64}$'
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'finding_assertion_citation_passage_hash_pair'
          AND conrelid = 'finding_assertion_citation'::regclass
    ) THEN
        ALTER TABLE finding_assertion_citation
            ADD CONSTRAINT finding_assertion_citation_passage_hash_pair
            CHECK (
                (passage_text_sha256 IS NULL) =
                (source_content_sha256 IS NULL)
            );
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS finding_assertion_citation_passage_idx
    ON finding_assertion_citation(passage_id)
    WHERE passage_id IS NOT NULL;

CREATE OR REPLACE FUNCTION finding_assertion_passage_binding_valid(
    p_citation_id text
) RETURNS boolean
LANGUAGE sql STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM finding_assertion_citation citation
        JOIN finding_assertion assertion
          ON assertion.id = citation.assertion_id
        JOIN finding_evidence source_link
          ON source_link.finding_id = assertion.finding_id
         AND source_link.evidence_id = citation.evidence_id
        JOIN evidence cited_evidence
          ON cited_evidence.id = citation.evidence_id
        JOIN passage cited_passage
          ON cited_passage.id = citation.passage_id
        JOIN content_capture cited_capture
          ON cited_capture.id = cited_passage.capture_id
         AND cited_capture.content_id = cited_passage.content_id
        WHERE
            citation.id = p_citation_id
            AND citation.observation_id IS NULL
            AND citation.passage_id IS NOT NULL
            AND citation.passage_text_sha256 ~ '^[0-9a-f]{64}$'
            AND citation.source_content_sha256 ~ '^[0-9a-f]{64}$'
            AND citation.relation = assertion.required_relation
            AND cited_passage.text_sha256 = citation.passage_text_sha256
            AND cited_capture.content_sha256 = citation.source_content_sha256
            AND cited_evidence.content_sha256 = citation.source_content_sha256
            AND (
                cited_passage.private_text IS NULL
                OR encode(
                    sha256(convert_to(cited_passage.private_text, 'UTF8')),
                    'hex'
                ) = cited_passage.text_sha256
            )
            AND NOT EXISTS (
                SELECT 1
                FROM evidence_observation structured_observation
                WHERE structured_observation.evidence_id = citation.evidence_id
            )
    );
$$;

COMMIT;
