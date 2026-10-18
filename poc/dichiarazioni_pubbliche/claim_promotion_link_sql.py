"""SQL authority for linking an approved duplicate extraction.

Executed by ClaimPromotionStore after its source-bound preflight.
"""

_LINK_EXISTING_SQL = r"""
WITH lock_row AS (
    SELECT pg_advisory_xact_lock(hashtextextended(:'candidate_id', 0))
), candidate AS (
    SELECT cc.*, sc.id AS statement_id, sc.status AS statement_status,
           sc.speaker_person_id, sc.statement_text_hash,
           sc.metadata AS statement_metadata
    FROM claim_candidate cc
    JOIN statement_candidate sc
      ON sc.id=cc.statement_candidate_id AND sc.content_id=cc.content_id
    CROSS JOIN lock_row
    WHERE cc.id=:'candidate_id'
      AND cc.status IN ('CANDIDATE','DUPLICATE')
      AND cc.metadata->>'speech_mode'='DIRECT_UTTERANCE'
      AND ((cc.metadata->'speech_act_context' IS NULL AND sc.metadata->'speech_act_context' IS NULL)
           OR (cc.metadata#>>'{speech_act_context,speech_act}' IN ('ASSERTION','OPINION')
               AND cc.metadata#>>'{speech_act_context,state}'='CANDIDATE_PRIVATE'
               AND cc.metadata#>>'{speech_act_context,stance}'='ENDORSE'
               AND cc.metadata#>>'{speech_act_context,utterer_id}'=sc.speaker_person_id
               AND cc.metadata#>>'{speech_act_context,quote_sha256}'=sc.statement_text_hash
               AND cc.metadata#>>'{speech_act_context,source_part_ref}'=cc.metadata->>'parent_passage_id'
               AND cc.metadata#>>'{speech_act_context,source_sha256}'=cc.metadata#>>'{context_integrity,source_sha256}'
               AND cc.metadata->'speech_act_context'=sc.metadata->'speech_act_context'
               AND EXISTS (
                   SELECT 1 FROM passage source_parent
                   LEFT JOIN canonical_transcript_segment source_segment
                     ON source_segment.id=source_parent.canonical_segment_id
                    AND source_segment.content_id=source_parent.content_id
                   WHERE source_parent.id=cc.metadata->>'parent_passage_id'
                     AND source_parent.content_id=cc.content_id
                     AND encode(sha256(convert_to(
                         COALESCE(source_parent.private_text, source_segment.canonical_text),
                         'UTF8')), 'hex')=cc.metadata#>>'{speech_act_context,source_sha256}'
               )))
      AND cc.metadata#>>'{context_integrity,state}' IN ('CLEAR_AUTOMATIC','APPROVED_CURATED')
      AND cc.metadata#>>'{wording,source_occurrence,wording_type}'='VERBATIM_ORIGINAL'
      AND cc.metadata#>>'{wording,normalized_claim,wording_type}'='PARAPHRASE'
      AND sc.status='APPROVED'
      AND sc.speaker_person_id IS NOT NULL
      AND (
          SELECT r.action FROM review_event r
          WHERE r.entity_type='CLAIM_CANDIDATE' AND r.entity_id=cc.id
          ORDER BY r.created_at DESC, r.id DESC LIMIT 1
      ) = 'APPROVED'
      AND (
          SELECT r.action FROM review_event r
          WHERE r.entity_type='STATEMENT_CANDIDATE' AND r.entity_id=sc.id
          ORDER BY r.created_at DESC, r.id DESC LIMIT 1
      ) = 'APPROVED'
      AND (SELECT count(*) FROM statement_candidate_passage x WHERE x.statement_candidate_id=sc.id)=1
    FOR UPDATE OF cc
), valid_provenance AS (
    SELECT c.id
    FROM candidate c
    JOIN statement_candidate_passage link ON link.statement_candidate_id=c.statement_id
    JOIN passage p ON p.id=link.passage_id AND p.content_id=c.content_id
    LEFT JOIN content_capture cap ON cap.id=p.capture_id AND cap.content_id=p.content_id
    LEFT JOIN canonical_transcript_segment seg ON seg.id=p.canonical_segment_id AND seg.content_id=p.content_id
    WHERE
      (
        :'provenance_channel'='WRITTEN'
        AND p.capture_id IS NOT NULL
        AND cap.status IN ('CAPTURED','PURGED_BODY')
        AND cap.hold_status='NONE'
      ) OR (
        :'provenance_channel'='MEDIA'
        AND p.canonical_segment_id IS NOT NULL
        AND seg.transcript_status='RESOLVED'
        AND seg.publication_blocked=false
        AND seg.speaker_person_id=c.speaker_person_id
        AND CASE
            WHEN jsonb_typeof(
                c.statement_metadata->'quote_local_start_char'
            ) = 'number'
             AND jsonb_typeof(
                c.statement_metadata->'quote_local_end_char'
             ) = 'number'
             AND (c.statement_metadata->>'quote_local_start_char')::numeric >= 0
             AND (c.statement_metadata->>'quote_local_start_char')::numeric =
                 trunc((c.statement_metadata->>'quote_local_start_char')::numeric)
             AND (c.statement_metadata->>'quote_local_end_char')::numeric =
                 trunc((c.statement_metadata->>'quote_local_end_char')::numeric)
             AND (c.statement_metadata->>'quote_local_end_char')::numeric >
                 (c.statement_metadata->>'quote_local_start_char')::numeric
             AND (c.statement_metadata->>'quote_local_end_char')::numeric <=
                 char_length(seg.canonical_text)
            THEN encode(
                sha256(
                    convert_to(
                        substring(
                            seg.canonical_text
                            FROM (
                                (c.statement_metadata->>'quote_local_start_char')::numeric
                                + 1
                            )::integer
                            FOR (
                                (c.statement_metadata->>'quote_local_end_char')::numeric
                                - (c.statement_metadata->>'quote_local_start_char')::numeric
                            )::integer
                        ),
                        'UTF8'
                    )
                ),
                'hex'
            ) = c.statement_text_hash
            ELSE false
        END
        AND c.metadata#>'{context_integrity,quote_start}' =
            c.statement_metadata->'quote_local_start_char'
        AND c.metadata#>'{context_integrity,quote_end}' =
            c.statement_metadata->'quote_local_end_char'
        AND c.metadata#>>'{context_integrity,quote_sha256}' = c.statement_text_hash
        AND EXISTS (
            SELECT 1
            FROM canonical_segment_candidate media_candidate_link
            JOIN transcript_segment media_candidate_segment
              ON media_candidate_segment.id =
                 media_candidate_link.transcript_segment_id
            JOIN transcript_variant media_candidate_variant
              ON media_candidate_variant.id = media_candidate_segment.variant_id
            WHERE media_candidate_link.canonical_segment_id = seg.id
              AND (
                  upper(media_candidate_variant.source_kind) = 'OFFICIAL_TRANSCRIPT'
                  OR EXISTS (
                      SELECT 1
                      FROM transcript_verbatim_review_event verbatim_review
                      WHERE verbatim_review.content_id = seg.content_id
                        AND verbatim_review.source_variant_id = media_candidate_variant.id
                        AND verbatim_review.source_segment_id = media_candidate_segment.id
                        AND verbatim_review.decision = 'APPROVED'
                        AND verbatim_review.source_variant_sha256 =
                            media_candidate_variant.raw_text_sha256
                        AND verbatim_review.source_segment_sha256 = encode(
                            sha256(convert_to(media_candidate_segment.text, 'UTF8')), 'hex'
                        )
                        AND verbatim_review.reviewed_text_sha256 = encode(
                            sha256(convert_to(seg.canonical_text, 'UTF8')), 'hex'
                        )
                        AND verbatim_review.start_ms <= seg.start_ms
                        AND verbatim_review.end_ms >= seg.end_ms
                  )
              )
        )
      )
), target_valid AS (
    SELECT ac.id
    FROM candidate c
    JOIN atomic_claim ac ON ac.id=:'target_claim_id'
    WHERE EXISTS (
        SELECT 1
        FROM proposition_cluster_member source
        JOIN proposition_cluster cluster ON cluster.id=source.cluster_id AND cluster.status='APPROVED'
        JOIN proposition_cluster_member target
          ON target.cluster_id=cluster.id
         AND target.atomic_claim_id=ac.id
         AND target.member_type='ATOMIC_CLAIM'
         AND target.status='APPROVED'
         AND target.match_class = 'DUPLICATE_EXTRACTION'
        WHERE source.claim_candidate_id=c.id
          AND source.member_type='CLAIM_CANDIDATE'
          AND source.status='APPROVED'
          AND source.match_class = 'DUPLICATE_EXTRACTION'
      )
), receipt AS (
    INSERT INTO claim_candidate_promotion (
        id, claim_candidate_id, target_claim_id, action, provenance_channel,
        promotion_version, idempotency_key, provenance_refs, actor_ref, reason, metadata
    )
    SELECT :'promotion_id', c.id, t.id, 'LINKED_EXISTING', :'provenance_channel',
           'claim-candidate-promotion-v1', :'idempotency_key', :'provenance_refs'::jsonb,
           :'actor_ref', NULLIF(:'reason',''), :'metadata'::jsonb
    FROM candidate c JOIN valid_provenance vp ON vp.id=c.id CROSS JOIN target_valid t
    ON CONFLICT (claim_candidate_id, promotion_version) DO NOTHING
    RETURNING id, claim_candidate_id, target_claim_id
), updated AS (
    UPDATE claim_candidate cc
    SET status='PROMOTED', promoted_claim_id=receipt.target_claim_id
    FROM receipt
    WHERE cc.id=receipt.claim_candidate_id
    RETURNING cc.id
)
SELECT CASE
    WHEN EXISTS(SELECT 1 FROM updated) THEN 'LINKED_EXISTING'
    ELSE 'CONFLICT'
END;
""".strip()
