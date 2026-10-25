"""Current private source-use proof shared by DP-418 write and receipt readback.

The archived Content/Capture rights flags are insufficient after a versioned
private rights revocation. This predicate requires an exact current Content/URL
grant for the operations used to produce and review a private Candidate.
"""

CURRENT_CANDIDATE_RIGHTS_SQL = """
EXISTS (
    SELECT 1 FROM private_source_rights_record rights
    WHERE rights.content_id=content.id
      AND rights.locator_kind='URL'
      AND rights.locator_value=content.canonical_url
      AND rights.evidence_id IS NULL AND rights.passage_id IS NULL
      AND rights.transcript_segment_id IS NULL
      AND rights.canonical_segment_id IS NULL
      AND rights.record_version='private-rights-record-v1'
      AND rights.record_visibility='PRIVATE'
      AND rights.rights_status='CLEARED'
      AND rights.rights_receipt_ref IS NOT NULL
      AND rights.rights_receipt_ref !~ '[[:space:]]'
      AND length(btrim(rights.reviewer_ref)) BETWEEN 1 AND 256
      AND rights.reviewed_at <= statement_timestamp()
      AND rights.expires_at > statement_timestamp()
      AND rights.permitted_uses @> ARRAY[
          'RESEARCH_CAPTURE_PRIVATE','OMNIROUTE_MODEL_EXTRACTION_PRIVATE'
      ]::text[]
      AND NOT EXISTS (
          SELECT 1 FROM private_source_rights_record successor
          WHERE successor.supersedes_id=rights.id
      )
)
""".strip()
