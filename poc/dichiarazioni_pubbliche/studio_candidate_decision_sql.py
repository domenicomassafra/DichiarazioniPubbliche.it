"""DP-418 PostgreSQL rights-locked decision write and historical readback SQL."""

from dichiarazioni_pubbliche.studio_candidate_rights_sql import CURRENT_CANDIDATE_RIGHTS_SQL


_WRITE_SQL = f"""
BEGIN;
SET LOCAL lock_timeout = '2000ms';
SET LOCAL statement_timeout = '5000ms';
SELECT pg_advisory_xact_lock(hashtextextended(:'candidate_id', 418));
-- Lock all mutable source/run rows. A second SQL statement observes the
-- committed state after any concurrent rights writer holding these locks.
WITH locked AS (
    SELECT c.id FROM claim_candidate c
    JOIN statement_candidate s ON s.id=c.statement_candidate_id AND s.content_id=c.content_id
    JOIN statement_candidate_passage edge ON edge.statement_candidate_id=s.id
        AND edge.content_id=s.content_id
    JOIN passage p ON p.id=edge.passage_id AND p.content_id=edge.content_id
    JOIN content_capture cap ON cap.id=p.capture_id AND cap.content_id=p.content_id
    JOIN content_item content ON content.id=c.content_id
    JOIN candidate_match_run run ON run.claim_candidate_id=c.id
    WHERE c.id=:'candidate_id' AND run.id=:'run_id'
      AND p.id=:'passage_id' AND cap.id=:'capture_id'
    FOR UPDATE OF c, s, edge, p, cap, content, run
) SELECT count(*) FROM locked;
-- Match results are mutable independent rows; freeze their dispositions and
-- targets until this transaction completes. The Run row lock also blocks a
-- new result FK insert while this decision is evaluated.
WITH locked_results AS (
    SELECT id FROM candidate_match_result WHERE run_id=:'run_id' FOR UPDATE
) SELECT count(*) FROM locked_results;
-- The rights registry is append-only. Lock the current parent row so an
-- incoming successor (whose FK requires KEY SHARE) cannot revoke it between
-- checking permission and committing a reviewer decision.
WITH locked_rights AS (
    SELECT rights.id FROM private_source_rights_record rights
    JOIN claim_candidate candidate ON candidate.content_id=rights.content_id
    JOIN content_item content ON content.id=candidate.content_id
    WHERE candidate.id=:'candidate_id'
      AND rights.locator_kind='URL'
      AND rights.locator_value=content.canonical_url
      AND NOT EXISTS (
          SELECT 1 FROM private_source_rights_record successor
          WHERE successor.supersedes_id=rights.id
      )
    FOR UPDATE OF rights
) SELECT count(*) FROM locked_rights;
WITH lineage AS (
    SELECT c.id
    FROM claim_candidate c
    JOIN statement_candidate s ON s.id=c.statement_candidate_id AND s.content_id=c.content_id
    JOIN statement_candidate_passage edge ON edge.statement_candidate_id=s.id
        AND edge.content_id=s.content_id
    JOIN passage p ON p.id=edge.passage_id AND p.content_id=edge.content_id
    JOIN content_capture cap ON cap.id=p.capture_id AND cap.content_id=p.content_id
    JOIN content_item content ON content.id=c.content_id
    JOIN candidate_match_run run ON run.claim_candidate_id=c.id
    WHERE c.id=:'candidate_id' AND c.status='CANDIDATE'
      AND s.status IN ('CANDIDATE','APPROVED')
      AND c.metadata->>'parent_passage_id'=p.id
      AND p.selector_type IN ('TEXT_POSITION','PAGE_RANGE')
      AND p.id=:'passage_id' AND cap.id=:'capture_id'
      AND cap.content_sha256=:'capture_sha256'
      AND content.rights_status='CLEARED' AND cap.rights_status='CLEARED'
      AND {CURRENT_CANDIDATE_RIGHTS_SQL}
      AND cap.hold_status='NONE' AND cap.status='CAPTURED'
      AND run.id=:'run_id' AND run.status='COMPLETED'
      AND run.input_fingerprint=:'input_fingerprint'
      AND run.matching_version='candidate-matching-v1'
      AND run.result_count=(SELECT count(*) FROM candidate_match_result r
                            WHERE r.run_id=run.id)
      AND NOT EXISTS(SELECT 1 FROM candidate_match_result invalid
                     WHERE invalid.run_id=run.id AND (
                         invalid.status <> 'CANDIDATE' OR
                         invalid.matching_version <> run.matching_version))
      AND (:'decision' <> 'REVIEW_CREATE' OR NOT EXISTS(
            SELECT 1 FROM candidate_match_result duplicate
            WHERE duplicate.run_id=run.id AND duplicate.status='CANDIDATE'
              AND duplicate.match_class IN ('DUPLICATE_EXTRACTION','SAME_PROPOSITION')))
      AND (:'decision' <> 'REVIEW_LINK' OR EXISTS(
            SELECT 1 FROM candidate_match_result reviewed
            WHERE reviewed.run_id=run.id AND reviewed.status='CANDIDATE'
              AND reviewed.target_type='CLAIM_CANDIDATE'
              AND reviewed.target_claim_candidate_id=:'target_id'
              AND reviewed.match_class='DUPLICATE_EXTRACTION'
              AND reviewed.matching_version=run.matching_version))
      AND NOT EXISTS (
          SELECT 1 FROM content_capture newer WHERE newer.content_id=c.content_id
            AND (newer.observed_at, newer.id) > (cap.observed_at, cap.id))
), latest AS (
    SELECT COALESCE(MAX(revision),0) AS revision FROM dp418_candidate_decision
    WHERE candidate_id=:'candidate_id'
), previous AS (
    SELECT * FROM dp418_candidate_decision WHERE request_key=:'request_key'
), inserted AS (
    INSERT INTO dp418_candidate_decision (
      receipt_id,candidate_id,run_id,passage_id,capture_id,capture_sha256,
      input_fingerprint,request_key,revision,expected_revision,decision,actor_ref,
      payload_sha256,authority_receipt_id,authority_event_sha256,receipt_sha256,
      target_type,target_id)
    SELECT :'receipt_id', :'candidate_id', :'run_id', :'passage_id', :'capture_id',
      :'capture_sha256', :'input_fingerprint', :'request_key', latest.revision+1,
      :'expected_revision'::bigint, :'decision', :'actor_ref', :'payload_sha256',
      :'authority_receipt_id', :'authority_event_sha256', :'receipt_sha256',
      :'target_type', :'target_id'
    FROM lineage, latest WHERE latest.revision=:'expected_revision'::bigint
      AND NOT EXISTS(SELECT 1 FROM previous)
    ON CONFLICT DO NOTHING RETURNING revision, receipt_sha256
)
SELECT json_build_object(
  'result_code', CASE
    WHEN NOT EXISTS (SELECT 1 FROM lineage) THEN 'HELD_SOURCE'
    WHEN EXISTS(SELECT 1 FROM previous WHERE payload_sha256=:'payload_sha256'
        AND authority_receipt_id=:'authority_receipt_id'
        AND authority_event_sha256=:'authority_event_sha256'
        AND receipt_sha256=:'receipt_sha256') THEN 'REPLAY'
    WHEN EXISTS(SELECT 1 FROM previous) THEN 'IDEMPOTENCY_CONFLICT'
    WHEN EXISTS(SELECT 1 FROM inserted) THEN 'CREATED'
    ELSE 'REVISION_CONFLICT'
  END,
  'revision', COALESCE((SELECT revision FROM inserted),
       (SELECT revision FROM previous), (SELECT revision FROM latest)),
  -- Only an exact successful CREATE/REPLAY may return an attested receipt.
  -- A revoked source can have historical decisions, but a new request or
  -- replay while held must not echo the *historical* receipt as if current.
  -- Likewise an idempotency conflict must not disclose someone else's SHA.
  'receipt_sha256', CASE
    WHEN NOT EXISTS(SELECT 1 FROM lineage) THEN NULL
    WHEN EXISTS(SELECT 1 FROM inserted) THEN
       (SELECT receipt_sha256 FROM inserted)
    WHEN EXISTS(SELECT 1 FROM previous
         WHERE payload_sha256=:'payload_sha256'
           AND authority_receipt_id=:'authority_receipt_id'
           AND authority_event_sha256=:'authority_event_sha256'
           AND receipt_sha256=:'receipt_sha256') THEN
       (SELECT receipt_sha256 FROM previous)
    ELSE NULL
  END
)::text;
COMMIT;
"""


READBACK_SQL = f"""
            BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
            SELECT json_build_object(
                'candidate_id',receipt.candidate_id,
                'run_id',receipt.run_id,'passage_id',receipt.passage_id,
                'capture_id',receipt.capture_id,'request_key',receipt.request_key,
                'decision',receipt.decision,'revision',receipt.revision,
                'receipt_sha256',receipt.receipt_sha256,
                'source_current',(
                   content.rights_status='CLEARED'
                   AND capture.rights_status='CLEARED'
                   AND {CURRENT_CANDIDATE_RIGHTS_SQL}
                   AND capture.status='CAPTURED' AND capture.hold_status='NONE'
                   AND NOT EXISTS (
                     SELECT 1 FROM content_capture newer
                     WHERE newer.content_id=content.id AND
                       (newer.observed_at,newer.id)>(capture.observed_at,capture.id)
                   )
                )
            )::text
            FROM dp418_candidate_decision receipt
            JOIN claim_candidate candidate ON candidate.id=receipt.candidate_id
            JOIN statement_candidate statement ON statement.id=candidate.statement_candidate_id
              AND statement.content_id=candidate.content_id
            JOIN statement_candidate_passage binding
              ON binding.statement_candidate_id=statement.id
              AND binding.content_id=statement.content_id
              AND binding.passage_id=receipt.passage_id
            JOIN passage passage ON passage.id=binding.passage_id
              AND passage.content_id=statement.content_id
              AND passage.capture_id=receipt.capture_id
            JOIN content_capture capture ON capture.id=receipt.capture_id
              AND capture.content_id=passage.content_id
            JOIN content_item content ON content.id=capture.content_id
            JOIN candidate_match_run run ON run.id=receipt.run_id
              AND run.claim_candidate_id=candidate.id
            WHERE receipt.candidate_id=:'candidate_id'
              AND receipt.run_id=:'run_id'
              AND receipt.passage_id=:'passage_id'
              AND receipt.capture_id=:'capture_id'
              AND receipt.request_key=:'request_key'
              AND capture.content_sha256=receipt.capture_sha256
            LIMIT 1;
            COMMIT;
        """
