"""Read-only CURRENT metadata rights predicate for a persisted Discovery Hit.

This is evidence that a private registry entry covers DISCOVER_METADATA only.
It cannot authorize capture, review actions, extraction or publication. We
require one unsuperseded exact Content/URL/Source-family rights record.
"""

SOURCE_METADATA_RIGHTS_CURRENT_SQL = """
COALESCE((
    SELECT COUNT(*) = 1 AND BOOL_AND(
        rr.rights_status = 'CLEARED'
        AND rr.record_visibility = 'PRIVATE'
        AND rr.record_version = 'private-rights-record-v1'
        AND rr.rights_receipt_ref IS NOT NULL
        AND rr.rights_receipt_ref !~ '[[:space:]]'
        AND length(btrim(rr.reviewer_ref)) BETWEEN 1 AND 256
        AND rr.reviewed_at IS NOT NULL
        AND rr.reviewed_at <= statement_timestamp()
        AND rr.expires_at IS NOT NULL
        AND rr.expires_at > statement_timestamp()
        AND length(btrim(rr.policy_version)) > 0
        AND rr.permitted_uses @> ARRAY['DISCOVER_METADATA']::text[]
        AND hit.source_id IS NOT NULL
        AND hit.source_id = content.source_id
        AND content.canonical_url = hit.canonical_url
    )
    FROM private_source_rights_record rr
    WHERE rr.content_id = content.id
      AND rr.source_family = hit.source_family
      AND rr.locator_kind = 'URL'
      AND rr.locator_value = hit.canonical_url
      AND rr.evidence_id IS NULL
      AND rr.passage_id IS NULL
      AND rr.transcript_segment_id IS NULL
      AND rr.canonical_segment_id IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM private_source_rights_record next
          WHERE next.supersedes_id = rr.id
      )
), false)
""".strip()
