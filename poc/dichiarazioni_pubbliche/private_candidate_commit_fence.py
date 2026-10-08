"""Additional SQL-snapshot fence for operator-only private Candidate persistence.

The read-time rights/ingestion gates remain mandatory. This SQL provides a
same-statement second check so revoked/paused records observed *at commit
snapshot* cannot insert candidates, receipts or a COMPLETED extraction run.
It cannot serialize against an external append-only revocation writer that
doesn't take a compatible transaction lock: do not call this a global
revocation atomicity guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass

from dichiarazioni_pubbliche.discovery_provenance import valid_discovery_hit_groups_sql
from dichiarazioni_pubbliche.ingestion_relevance import (
    canonical_content_url,
    content_relevance_binding_sha256,
)


@dataclass(frozen=True)
class PrivateCandidateCommitFence:
    collection_id: str
    content_id: str
    capture_id: str
    passage_id: str
    passage_sha256: str
    canonical_url: str
    source_family: str
    rights_record_id: str

    def sql_parameters(self) -> dict[str, str]:
        from re import fullmatch
        for value in (self.collection_id, self.content_id, self.capture_id,
                      self.passage_id, self.source_family, self.rights_record_id):
            if not isinstance(value, str) or not fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}", value):
                raise ValueError("PRIVATE_CANDIDATE_COMMIT_FENCE_ID_INVALID")
        if not isinstance(self.passage_sha256, str) or not fullmatch(r"[0-9a-f]{64}", self.passage_sha256):
            raise ValueError("PRIVATE_CANDIDATE_COMMIT_FENCE_HASH_INVALID")
        if not isinstance(self.canonical_url, str) or canonical_content_url(self.canonical_url) != self.canonical_url:
            raise ValueError("PRIVATE_CANDIDATE_COMMIT_FENCE_URL_INVALID")
        return {
            "fence_collection_id": self.collection_id,
            "fence_content_id": self.content_id,
            "fence_capture_id": self.capture_id,
            "fence_passage_id": self.passage_id,
            "fence_passage_sha256": self.passage_sha256,
            "fence_canonical_url": self.canonical_url,
            "fence_source_family": self.source_family,
            "fence_rights_record_id": self.rights_record_id,
            "fence_relevance_binding_sha256": content_relevance_binding_sha256(
                self.content_id, self.canonical_url
            ),
        }


_VALID_DISCOVERY = valid_discovery_hit_groups_sql(
    collection_id_sql="collection.id",
    content_id_sql="content.id",
    canonical_url_sql="content.canonical_url",
)

# Compiles inside a WITH clause. Parameter values are always passed to psql
# via quoted bind substitutions; no caller-supplied SQL is interpolated.
PRIVATE_CANDIDATE_COMMIT_AUTHORITY_CTE = f"""
commit_authority AS MATERIALIZED (
    SELECT 1 AS allowed
    FROM content_item content
    JOIN research_collection_content member
      ON member.content_id=content.id
     AND member.collection_id=:'fence_collection_id'
     AND member.status='INCLUDED'
     AND member.metadata->'capture_authorized'='true'::jsonb
    JOIN research_collection collection
      ON collection.id=member.collection_id AND collection.status='ACTIVE'
    JOIN content_capture capture
      ON capture.content_id=content.id
     AND capture.id=:'fence_capture_id'
     AND capture.status='CAPTURED'
     AND capture.rights_status='CLEARED'
     AND capture.hold_status='NONE'
     AND capture.body_ref IS NOT NULL
     AND capture.retention_class IN ('EPHEMERAL','DURABLE_PRIVATE','DURABLE_PROVENANCE')
    JOIN passage source_passage
      ON source_passage.content_id=content.id
     AND source_passage.id=:'fence_passage_id'
     AND source_passage.capture_id=capture.id
     AND source_passage.text_sha256=:'fence_passage_sha256'
    JOIN private_source_rights_record rights
      ON rights.id=:'fence_rights_record_id'
     AND rights.content_id=content.id
     AND rights.locator_kind='URL'
     AND rights.locator_value=content.canonical_url
     AND rights.source_family=:'fence_source_family'
     AND rights.rights_status='CLEARED'
     AND rights.record_version='private-rights-record-v1'
     AND rights.record_visibility='PRIVATE'
     AND rights.rights_receipt_ref IS NOT NULL
     AND rights.reviewer_ref IS NOT NULL
     AND rights.reviewed_at <= statement_timestamp()
     AND (rights.expires_at IS NULL OR rights.expires_at > statement_timestamp())
     AND rights.evidence_id IS NULL
     AND rights.passage_id IS NULL
     AND rights.transcript_segment_id IS NULL
     AND rights.canonical_segment_id IS NULL
     AND rights.permitted_uses @> ARRAY[
         'RESEARCH_CAPTURE_PRIVATE','OMNIROUTE_MODEL_EXTRACTION_PRIVATE'
     ]::text[]
    WHERE content.id=:'fence_content_id'
      AND content.canonical_url=:'fence_canonical_url'
      AND content.rights_status='CLEARED'
      AND NOT EXISTS (
          SELECT 1 FROM private_source_rights_record superseding
          WHERE superseding.supersedes_id=rights.id
      )
      AND EXISTS (
          SELECT 1 FROM privacy_ingestion_relevance_authority relevance
          WHERE relevance.content_ref=content.id
            AND relevance.content_binding_sha256=:'fence_relevance_binding_sha256'
            AND relevance.contract_version='privacy-ingestion-relevance-v1'
            AND relevance.binding_version='content-acquisition-binding-v1'
            AND relevance.privacy_policy_version='privacy-minimization-v1'
            AND relevance.record_visibility='PRIVATE'
            AND NOT EXISTS (
                SELECT 1 FROM privacy_ingestion_relevance_authority successor
                WHERE successor.supersedes_authority_id=relevance.authority_id
            )
      )
      AND EXISTS (
          SELECT 1 FROM ({_VALID_DISCOVERY}) provenance
          WHERE provenance.source_family=:'fence_source_family'
            AND provenance.hit_count > 0
      )
      AND NOT EXISTS (
          SELECT 1 FROM research_collection_content other_member
          JOIN research_collection other_collection
            ON other_collection.id=other_member.collection_id
          WHERE other_member.content_id=content.id
            AND (other_collection.status<>'ACTIVE'
                 OR other_member.status<>'INCLUDED'
                 OR other_member.metadata->'capture_authorized' IS DISTINCT FROM 'true'::jsonb)
      )
    LIMIT 1
)
""".strip()
