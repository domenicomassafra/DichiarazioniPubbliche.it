from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from dichiarazioni_pubbliche.claim_contract import validate_atomic_claim
from dichiarazioni_pubbliche.quote_binding import verify_written_quote_binding
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.text_provenance import make_text_provenance_candidate


PROMOTION_VERSION = "claim-candidate-promotion-v1"
PROMOTION_CHANNELS = frozenset({"WRITTEN", "MEDIA"})
PROMOTABLE_CANDIDATE_STATES = frozenset({"CANDIDATE", "DUPLICATE"})


@dataclass(frozen=True)
class PromotionRequest:
    candidate_id: str
    provenance_channel: str
    actor_ref: str
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ValueError("PROMOTION_CANDIDATE_ID_REQUIRED")
        if self.provenance_channel not in PROMOTION_CHANNELS:
            raise ValueError("PROMOTION_CHANNEL_INVALID")
        if not isinstance(self.actor_ref, str) or not self.actor_ref.strip():
            raise ValueError("PROMOTION_ACTOR_REQUIRED")


@dataclass(frozen=True)
class PromotionReceipt:
    status: str
    reason_code: str
    candidate_id: str
    promotion_id: str | None = None
    target_claim_id: str | None = None
    action: str | None = None
    provenance_refs: tuple[str, ...] = ()
    replayed: bool = False

    @property
    def promoted(self) -> bool:
        return self.status == "PROMOTED"


def _digest(prefix: str, *parts: str) -> str:
    material = "\x1f".join(str(part).strip() for part in parts).encode("utf-8")
    return f"{prefix}:" + hashlib.sha256(material).hexdigest()


def deterministic_promotion_id(candidate_id: str) -> str:
    return _digest("claim-promotion", PROMOTION_VERSION, candidate_id)


def deterministic_promotion_key(candidate_id: str, channel: str) -> str:
    return _digest("claim-promotion-key", PROMOTION_VERSION, candidate_id, channel)


def deterministic_promoted_claim_id(candidate_id: str) -> str:
    return _digest("claim:promoted", PROMOTION_VERSION, candidate_id)


PROMOTION_CONTEXT_SQL_V1 = r"""
WITH candidate AS (
    SELECT
        cc.id AS candidate_id,
        cc.status AS candidate_status,
        cc.content_id,
        cc.normalized_claim,
        cc.proposed_claim_type,
        cc.claim_type_version,
        cc.temporal_scope,
        cc.check_worthy,
        cc.extraction_model,
        cc.extraction_version,
        cc.metadata AS candidate_metadata,
        cc.promoted_claim_id,
        sc.id AS statement_candidate_id,
        sc.status AS statement_status,
        sc.speaker_person_id,
        sc.statement_text_hash,
        sc.statement_at,
        sc.attribution_method,
        content.canonical_url,
        content.title,
        content.published_at,
        person.is_public_figure
    FROM claim_candidate cc
    JOIN statement_candidate sc
      ON sc.id = cc.statement_candidate_id AND sc.content_id = cc.content_id
    JOIN content_item content ON content.id = cc.content_id
    LEFT JOIN person ON person.id = sc.speaker_person_id
    WHERE cc.id = :'candidate_id'
), passage_rows AS (
    SELECT
        p.id AS passage_id,
        p.selector_type,
        p.start_char,
        p.end_char,
        p.page_start,
        p.page_end,
        p.text_sha256,
        p.private_text,
        p.capture_id,
        capture.content_sha256 AS capture_sha256,
        capture.final_url AS capture_final_url,
        capture.status AS capture_status,
        capture.hold_status AS capture_hold_status,
        p.canonical_segment_id,
        segment.transcript_status AS segment_status,
        segment.publication_blocked AS segment_publication_blocked,
        segment.speaker_person_id AS segment_speaker_person_id,
        (
            SELECT CASE
                WHEN bool_or(upper(variant.source_kind)='HUMAN_AUDIO_VERIFIED')
                    THEN 'HUMAN_AUDIO_VERIFIED'
                WHEN bool_or(upper(variant.source_kind)='OFFICIAL_TRANSCRIPT')
                    THEN 'OFFICIAL_TRANSCRIPT'
                WHEN count(*) > 1
                    THEN 'MULTI_ASR_AGREEMENT'
                WHEN bool_or(
                    variant.is_platform_caption
                    OR upper(variant.source_kind) IN (
                        'PLATFORM_CAPTION','YOUTUBE_AUTO_CAPTION'
                    )
                )
                    THEN 'PLATFORM_CAPTION'
                WHEN count(*) = 1
                    THEN 'SINGLE_ASR'
                ELSE 'UNVERIFIED'
            END
            FROM canonical_segment_candidate candidate_link
            JOIN transcript_segment candidate_segment
              ON candidate_segment.id = candidate_link.transcript_segment_id
            JOIN transcript_variant variant
              ON variant.id = candidate_segment.variant_id
            WHERE candidate_link.canonical_segment_id = segment.id
        ) AS segment_verbatim_method,
        EXISTS (
            SELECT 1
            FROM speaker_identity_candidate speaker
            WHERE
                speaker.content_id = segment.content_id
                AND speaker.person_id = c.speaker_person_id
                AND speaker.status = 'APPROVED'
                AND speaker.attribution_method IN (
                    'MANUAL_REVIEW',
                    'TRANSCRIPT_LABEL',
                    'OFFICIAL_RECORD'
                )
                AND segment.start_ms >= speaker.start_ms
                AND segment.end_ms <= speaker.end_ms
                AND EXISTS (
                    SELECT 1
                    FROM review_event speaker_review
                    WHERE
                        speaker_review.entity_type =
                            'SPEAKER_IDENTITY_CANDIDATE'
                        AND speaker_review.entity_id = speaker.id
                        AND speaker_review.action = 'APPROVED'
                )
        ) AS segment_speaker_provenance_ok
    FROM candidate c
    JOIN statement_candidate_passage link
      ON link.statement_candidate_id = c.statement_candidate_id
     AND link.content_id = c.content_id
    JOIN passage p ON p.id = link.passage_id AND p.content_id = c.content_id
    LEFT JOIN content_capture capture
      ON capture.id = p.capture_id AND capture.content_id = p.content_id
    LEFT JOIN canonical_transcript_segment segment
      ON segment.id = p.canonical_segment_id AND segment.content_id = p.content_id
), passage_summary AS (
    SELECT
        count(*)::integer AS passage_count,
        count(*) FILTER (WHERE capture_id IS NOT NULL)::integer AS written_count,
        count(*) FILTER (WHERE canonical_segment_id IS NOT NULL)::integer AS media_count,
        COALESCE(jsonb_agg(
            jsonb_build_object(
                'passage_id', passage_id,
                'selector_type', selector_type,
                'start_char', start_char,
                'end_char', end_char,
                'page_start', page_start,
                'page_end', page_end,
                'text_sha256', text_sha256,
                'private_text', private_text,
                'capture_id', capture_id,
                'capture_sha256', capture_sha256,
                'capture_final_url', capture_final_url,
                'capture_status', capture_status,
                'capture_hold_status', capture_hold_status,
                'canonical_segment_id', canonical_segment_id,
                'segment_status', segment_status,
                'segment_publication_blocked', segment_publication_blocked,
                'segment_speaker_person_id', segment_speaker_person_id,
                'segment_verbatim_method', segment_verbatim_method,
                'segment_speaker_provenance_ok', segment_speaker_provenance_ok
            ) ORDER BY passage_id
        ), '[]'::jsonb) AS passages
    FROM passage_rows
), exact_targets AS (
    SELECT ac.id
    FROM candidate c
    JOIN atomic_claim ac
      ON ac.content_id = c.content_id
     AND ac.speaker_person_id IS NOT DISTINCT FROM c.speaker_person_id
     AND ac.normalized_claim = c.normalized_claim
     AND ac.claim_type = c.proposed_claim_type
     AND ac.claim_type_version = c.claim_type_version
     AND ac.temporal_scope = c.temporal_scope
     AND ac.check_worthy = c.check_worthy
), approved_cluster_targets AS (
    SELECT DISTINCT target.atomic_claim_id AS id
    FROM candidate c
    JOIN proposition_cluster_member source
      ON source.claim_candidate_id = c.candidate_id
     AND source.member_type = 'CLAIM_CANDIDATE'
     AND source.status = 'APPROVED'
     AND source.match_class IN ('DUPLICATE_EXTRACTION', 'SAME_PROPOSITION')
    JOIN proposition_cluster cluster
      ON cluster.id = source.cluster_id AND cluster.status = 'APPROVED'
    JOIN proposition_cluster_member target
      ON target.cluster_id = cluster.id
     AND target.member_type = 'ATOMIC_CLAIM'
     AND target.status = 'APPROVED'
     AND target.match_class IN ('DUPLICATE_EXTRACTION', 'SAME_PROPOSITION')
), targets AS (
    SELECT id FROM exact_targets
    UNION
    SELECT id FROM approved_cluster_targets
), existing_promotion AS (
    SELECT
        promotion.id,
        promotion.target_claim_id,
        promotion.action,
        promotion.provenance_channel,
        promotion.provenance_refs,
        promotion.idempotency_key
    FROM claim_candidate_promotion promotion
    WHERE promotion.claim_candidate_id = :'candidate_id'
      AND promotion.promotion_version = 'claim-candidate-promotion-v1'
)
SELECT COALESCE((
    SELECT json_build_object(
        'candidate_id', c.candidate_id,
        'candidate_status', c.candidate_status,
        'content_id', c.content_id,
        'normalized_claim', c.normalized_claim,
        'proposed_claim_type', c.proposed_claim_type,
        'claim_type_version', c.claim_type_version,
        'temporal_scope', c.temporal_scope,
        'check_worthy', c.check_worthy,
        'extraction_model', c.extraction_model,
        'extraction_version', c.extraction_version,
        'candidate_metadata', c.candidate_metadata,
        'promoted_claim_id', c.promoted_claim_id,
        'statement_candidate_id', c.statement_candidate_id,
        'statement_status', c.statement_status,
        'statement_reviewed', EXISTS (
            SELECT 1 FROM review_event r
            WHERE r.entity_type='STATEMENT_CANDIDATE'
              AND r.entity_id=c.statement_candidate_id
              AND r.action='APPROVED'
        ),
        'claim_candidate_reviewed', EXISTS (
            SELECT 1 FROM review_event r
            WHERE r.entity_type='CLAIM_CANDIDATE'
              AND r.entity_id=c.candidate_id
              AND r.action='APPROVED'
        ),
        'speaker_person_id', c.speaker_person_id,
        'speaker_is_public', COALESCE(c.is_public_figure, false),
        'statement_text_hash', c.statement_text_hash,
        'statement_at', c.statement_at,
        'attribution_method', c.attribution_method,
        'canonical_url', c.canonical_url,
        'title', c.title,
        'published_at', c.published_at,
        'passage_count', ps.passage_count,
        'written_count', ps.written_count,
        'media_count', ps.media_count,
        'passages', ps.passages,
        'duplicate_target_ids', COALESCE((SELECT jsonb_agg(id ORDER BY id) FROM targets), '[]'::jsonb),
        'existing_promotion', (SELECT row_to_json(ep) FROM existing_promotion ep LIMIT 1)
    )
    FROM candidate c CROSS JOIN passage_summary ps
)::text, '');
""".strip()


_LINK_EXISTING_SQL = r"""
WITH lock_row AS (
    SELECT pg_advisory_xact_lock(hashtextextended(:'candidate_id', 0))
), candidate AS (
    SELECT cc.*, sc.id AS statement_id, sc.status AS statement_status, sc.speaker_person_id
    FROM claim_candidate cc
    JOIN statement_candidate sc
      ON sc.id=cc.statement_candidate_id AND sc.content_id=cc.content_id
    CROSS JOIN lock_row
    WHERE cc.id=:'candidate_id'
      AND cc.status IN ('CANDIDATE','DUPLICATE')
      AND sc.status='APPROVED'
      AND sc.speaker_person_id IS NOT NULL
      AND EXISTS (
          SELECT 1 FROM review_event r
          WHERE r.entity_type='CLAIM_CANDIDATE' AND r.entity_id=cc.id AND r.action='APPROVED'
      )
      AND EXISTS (
          SELECT 1 FROM review_event r
          WHERE r.entity_type='STATEMENT_CANDIDATE' AND r.entity_id=sc.id AND r.action='APPROVED'
      )
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
      )
), target_valid AS (
    SELECT ac.id
    FROM candidate c
    JOIN atomic_claim ac ON ac.id=:'target_claim_id'
    WHERE
      (
        ac.content_id=c.content_id
        AND ac.speaker_person_id IS NOT DISTINCT FROM c.speaker_person_id
        AND ac.normalized_claim=c.normalized_claim
        AND ac.claim_type=c.proposed_claim_type
        AND ac.claim_type_version=c.claim_type_version
        AND ac.temporal_scope=c.temporal_scope
        AND ac.check_worthy=c.check_worthy
      )
      OR EXISTS (
        SELECT 1
        FROM proposition_cluster_member source
        JOIN proposition_cluster cluster ON cluster.id=source.cluster_id AND cluster.status='APPROVED'
        JOIN proposition_cluster_member target
          ON target.cluster_id=cluster.id
         AND target.atomic_claim_id=ac.id
         AND target.member_type='ATOMIC_CLAIM'
         AND target.status='APPROVED'
         AND target.match_class IN ('DUPLICATE_EXTRACTION','SAME_PROPOSITION')
        WHERE source.claim_candidate_id=c.id
          AND source.member_type='CLAIM_CANDIDATE'
          AND source.status='APPROVED'
          AND source.match_class IN ('DUPLICATE_EXTRACTION','SAME_PROPOSITION')
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


_PROMOTE_WRITTEN_NEW_SQL = r"""
WITH lock_row AS (
    SELECT pg_advisory_xact_lock(hashtextextended(:'candidate_id', 0))
), candidate AS (
    SELECT cc.*, sc.id AS statement_id, sc.status AS statement_status,
           sc.speaker_person_id, sc.statement_text_hash,
           content.canonical_url, content.title, content.published_at
    FROM claim_candidate cc
    JOIN statement_candidate sc
      ON sc.id=cc.statement_candidate_id AND sc.content_id=cc.content_id
    JOIN content_item content ON content.id=cc.content_id
    CROSS JOIN lock_row
    WHERE cc.id=:'candidate_id'
      AND cc.status IN ('CANDIDATE','DUPLICATE')
      AND sc.status='APPROVED'
      AND sc.speaker_person_id IS NOT NULL
      AND EXISTS (SELECT 1 FROM person p WHERE p.id=sc.speaker_person_id AND p.is_public_figure=true)
      AND EXISTS (
          SELECT 1 FROM review_event r
          WHERE r.entity_type='CLAIM_CANDIDATE' AND r.entity_id=cc.id AND r.action='APPROVED'
      )
      AND EXISTS (
          SELECT 1 FROM review_event r
          WHERE r.entity_type='STATEMENT_CANDIDATE' AND r.entity_id=sc.id AND r.action='APPROVED'
      )
      AND (SELECT count(*) FROM statement_candidate_passage x WHERE x.statement_candidate_id=sc.id)=1
    FOR UPDATE OF cc
), written AS (
    SELECT c.*, p.id AS passage_id, p.selector_type AS passage_selector_type,
           p.start_char, p.end_char, cap.id AS capture_id,
           cap.content_sha256 AS source_sha256, cap.final_url
    FROM candidate c
    JOIN statement_candidate_passage link ON link.statement_candidate_id=c.statement_id
    JOIN passage p ON p.id=link.passage_id AND p.content_id=c.content_id
    JOIN content_capture cap ON cap.id=p.capture_id AND cap.content_id=p.content_id
    WHERE cap.status IN ('CAPTURED','PURGED_BODY') AND cap.hold_status='NONE'
), duplicate_targets AS (
    SELECT ac.id
    FROM written c
    JOIN atomic_claim ac
      ON ac.content_id=c.content_id
     AND ac.speaker_person_id IS NOT DISTINCT FROM c.speaker_person_id
     AND ac.normalized_claim=c.normalized_claim
     AND ac.claim_type=c.proposed_claim_type
     AND ac.claim_type_version=c.claim_type_version
     AND ac.temporal_scope=c.temporal_scope
     AND ac.check_worthy=c.check_worthy
    UNION
    SELECT target.atomic_claim_id
    FROM written c
    JOIN proposition_cluster_member source
      ON source.claim_candidate_id=c.id AND source.status='APPROVED'
     AND source.match_class IN ('DUPLICATE_EXTRACTION','SAME_PROPOSITION')
    JOIN proposition_cluster cluster ON cluster.id=source.cluster_id AND cluster.status='APPROVED'
    JOIN proposition_cluster_member target
      ON target.cluster_id=cluster.id AND target.member_type='ATOMIC_CLAIM'
     AND target.status='APPROVED'
     AND target.match_class IN ('DUPLICATE_EXTRACTION','SAME_PROPOSITION')
), eligible AS (
    SELECT * FROM written WHERE NOT EXISTS (SELECT 1 FROM duplicate_targets)
), claim_insert AS (
    INSERT INTO atomic_claim (
        id, content_id, speaker_person_id, normalized_claim, claim_type, claim_type_version,
        temporal_scope, check_worthy, extraction_model, extraction_version, metadata
    )
    SELECT :'target_claim_id', content_id, speaker_person_id, normalized_claim,
           proposed_claim_type, claim_type_version, temporal_scope, check_worthy,
           extraction_model, extraction_version,
           metadata || jsonb_build_object(
               'promoted_from_claim_candidate', id,
               'promotion_version', 'claim-candidate-promotion-v1'
           )
    FROM eligible
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), provenance_review AS (
    INSERT INTO review_event (id, entity_type, entity_id, action, actor_ref, reason, metadata)
    SELECT :'provenance_review_id', 'CLAIM_TEXT_PROVENANCE', :'provenance_id', 'APPROVED',
           :'actor_ref', NULLIF(:'reason',''),
           jsonb_build_object('claim_candidate_id', eligible.id, 'promotion_id', :'promotion_id')
    FROM eligible JOIN claim_insert ON true
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), provenance_insert AS (
    INSERT INTO claim_text_provenance (
        id, claim_id, content_id, person_id, selector_type, quote_sha256, source_sha256,
        start_char, end_char, attribution_method, attribution_version, source_ref, status, metadata
    )
    SELECT :'provenance_id', claim_insert.id, eligible.content_id, eligible.speaker_person_id,
           :'selector_type', eligible.statement_text_hash, eligible.source_sha256,
           NULLIF(:'start_char','')::integer, NULLIF(:'end_char','')::integer,
           'SOURCE_QUOTE', 'text-source-provenance-v1', :'source_ref'::jsonb, 'APPROVED',
           jsonb_build_object('claim_candidate_id', eligible.id, 'promotion_id', :'promotion_id')
    FROM eligible JOIN claim_insert ON true JOIN provenance_review ON true
    ON CONFLICT (id) DO NOTHING
    RETURNING id, claim_id
), receipt AS (
    INSERT INTO claim_candidate_promotion (
        id, claim_candidate_id, target_claim_id, action, provenance_channel,
        promotion_version, idempotency_key, provenance_refs, actor_ref, reason, metadata
    )
    SELECT :'promotion_id', eligible.id, claim_insert.id, 'CREATED', 'WRITTEN',
           'claim-candidate-promotion-v1', :'idempotency_key', jsonb_build_array(provenance_insert.id),
           :'actor_ref', NULLIF(:'reason',''), :'metadata'::jsonb
    FROM eligible JOIN claim_insert ON true JOIN provenance_insert ON provenance_insert.claim_id=claim_insert.id
    ON CONFLICT (claim_candidate_id, promotion_version) DO NOTHING
    RETURNING id, claim_candidate_id, target_claim_id
), updated AS (
    UPDATE claim_candidate cc
    SET status='PROMOTED', promoted_claim_id=receipt.target_claim_id
    FROM receipt
    WHERE cc.id=receipt.claim_candidate_id
    RETURNING cc.id
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM updated) THEN 'CREATED' ELSE 'CONFLICT' END;
""".strip()


_PROMOTE_MEDIA_NEW_SQL = r"""
WITH lock_row AS (
    SELECT pg_advisory_xact_lock(hashtextextended(:'candidate_id', 0))
), candidate AS (
    SELECT cc.*, sc.id AS statement_id, sc.status AS statement_status, sc.speaker_person_id
    FROM claim_candidate cc
    JOIN statement_candidate sc
      ON sc.id=cc.statement_candidate_id AND sc.content_id=cc.content_id
    CROSS JOIN lock_row
    WHERE cc.id=:'candidate_id'
      AND cc.status IN ('CANDIDATE','DUPLICATE')
      AND sc.status='APPROVED'
      AND sc.speaker_person_id IS NOT NULL
      AND EXISTS (SELECT 1 FROM person p WHERE p.id=sc.speaker_person_id AND p.is_public_figure=true)
      AND EXISTS (
          SELECT 1 FROM review_event r
          WHERE r.entity_type='CLAIM_CANDIDATE' AND r.entity_id=cc.id AND r.action='APPROVED'
      )
      AND EXISTS (
          SELECT 1 FROM review_event r
          WHERE r.entity_type='STATEMENT_CANDIDATE' AND r.entity_id=sc.id AND r.action='APPROVED'
      )
      AND (SELECT count(*) FROM statement_candidate_passage x WHERE x.statement_candidate_id=sc.id)=1
    FOR UPDATE OF cc
), media AS (
    SELECT c.*, p.id AS passage_id, p.canonical_segment_id
    FROM candidate c
    JOIN statement_candidate_passage link ON link.statement_candidate_id=c.statement_id
    JOIN passage p ON p.id=link.passage_id AND p.content_id=c.content_id
    JOIN canonical_transcript_segment seg
      ON seg.id=p.canonical_segment_id AND seg.content_id=p.content_id
    WHERE seg.transcript_status='RESOLVED'
      AND seg.publication_blocked=false
      AND seg.speaker_person_id=c.speaker_person_id
), duplicate_targets AS (
    SELECT ac.id
    FROM media c
    JOIN atomic_claim ac
      ON ac.content_id=c.content_id
     AND ac.speaker_person_id IS NOT DISTINCT FROM c.speaker_person_id
     AND ac.normalized_claim=c.normalized_claim
     AND ac.claim_type=c.proposed_claim_type
     AND ac.claim_type_version=c.claim_type_version
     AND ac.temporal_scope=c.temporal_scope
     AND ac.check_worthy=c.check_worthy
    UNION
    SELECT target.atomic_claim_id
    FROM media c
    JOIN proposition_cluster_member source
      ON source.claim_candidate_id=c.id AND source.status='APPROVED'
     AND source.match_class IN ('DUPLICATE_EXTRACTION','SAME_PROPOSITION')
    JOIN proposition_cluster cluster ON cluster.id=source.cluster_id AND cluster.status='APPROVED'
    JOIN proposition_cluster_member target
      ON target.cluster_id=cluster.id AND target.member_type='ATOMIC_CLAIM'
     AND target.status='APPROVED'
     AND target.match_class IN ('DUPLICATE_EXTRACTION','SAME_PROPOSITION')
), eligible AS (
    SELECT * FROM media WHERE NOT EXISTS (SELECT 1 FROM duplicate_targets)
), claim_insert AS (
    INSERT INTO atomic_claim (
        id, content_id, speaker_person_id, normalized_claim, claim_type, claim_type_version,
        temporal_scope, check_worthy, extraction_model, extraction_version, metadata
    )
    SELECT :'target_claim_id', content_id, speaker_person_id, normalized_claim,
           proposed_claim_type, claim_type_version, temporal_scope, check_worthy,
           extraction_model, extraction_version,
           metadata || jsonb_build_object(
               'promoted_from_claim_candidate', id,
               'promotion_version', 'claim-candidate-promotion-v1'
           )
    FROM eligible
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), segment_link AS (
    INSERT INTO claim_segment (claim_id, segment_id)
    SELECT claim_insert.id, eligible.canonical_segment_id
    FROM eligible JOIN claim_insert ON true
    ON CONFLICT DO NOTHING
    RETURNING claim_id, segment_id
), receipt AS (
    INSERT INTO claim_candidate_promotion (
        id, claim_candidate_id, target_claim_id, action, provenance_channel,
        promotion_version, idempotency_key, provenance_refs, actor_ref, reason, metadata
    )
    SELECT :'promotion_id', eligible.id, claim_insert.id, 'CREATED', 'MEDIA',
           'claim-candidate-promotion-v1', :'idempotency_key', jsonb_build_array(segment_link.segment_id),
           :'actor_ref', NULLIF(:'reason',''), :'metadata'::jsonb
    FROM eligible JOIN claim_insert ON true JOIN segment_link ON segment_link.claim_id=claim_insert.id
    ON CONFLICT (claim_candidate_id, promotion_version) DO NOTHING
    RETURNING id, claim_candidate_id, target_claim_id
), updated AS (
    UPDATE claim_candidate cc
    SET status='PROMOTED', promoted_claim_id=receipt.target_claim_id
    FROM receipt
    WHERE cc.id=receipt.claim_candidate_id
    RETURNING cc.id
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM updated) THEN 'CREATED' ELSE 'CONFLICT' END;
""".strip()


class ClaimPromotionStore(PsqlRuntime):
    def context(self, candidate_id: str) -> dict[str, Any] | None:
        raw = self.run(PROMOTION_CONTEXT_SQL_V1, candidate_id=candidate_id)
        if not raw:
            return None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError("PROMOTION_CONTEXT_INVALID")
        return parsed

    def link_existing(self, **variables: object) -> str:
        return self.run(_LINK_EXISTING_SQL, **variables)

    def create_written(self, **variables: object) -> str:
        return self.run(_PROMOTE_WRITTEN_NEW_SQL, **variables)

    def create_media(self, **variables: object) -> str:
        return self.run(_PROMOTE_MEDIA_NEW_SQL, **variables)


def _blocked(request: PromotionRequest, code: str) -> PromotionReceipt:
    return PromotionReceipt(
        status="BLOCKED",
        reason_code=code,
        candidate_id=request.candidate_id,
    )


def _existing_receipt(request: PromotionRequest, raw: Mapping[str, Any]) -> PromotionReceipt:
    refs = raw.get("provenance_refs") or []
    return PromotionReceipt(
        status="PROMOTED",
        reason_code="PROMOTION_REPLAYED",
        candidate_id=request.candidate_id,
        promotion_id=str(raw.get("id") or "") or None,
        target_claim_id=str(raw.get("target_claim_id") or "") or None,
        action=str(raw.get("action") or "") or None,
        provenance_refs=tuple(str(x) for x in refs),
        replayed=True,
    )


def promote_claim_candidate(
    store: ClaimPromotionStore,
    request: PromotionRequest,
) -> PromotionReceipt:
    context = store.context(request.candidate_id)
    if context is None:
        return _blocked(request, "PROMOTION_CANDIDATE_NOT_FOUND")

    existing = context.get("existing_promotion")
    if isinstance(existing, Mapping):
        return _existing_receipt(request, existing)

    state = str(context.get("candidate_status") or "")
    if state == "PROMOTED":
        return _blocked(request, "PROMOTION_LEDGER_MISSING")
    if state not in PROMOTABLE_CANDIDATE_STATES:
        return _blocked(request, "PROMOTION_CANDIDATE_STATE_BLOCKED")
    if not bool(context.get("claim_candidate_reviewed")):
        return _blocked(request, "PROMOTION_CLAIM_CANDIDATE_NOT_REVIEWED")
    if str(context.get("statement_status") or "") != "APPROVED" or not bool(
        context.get("statement_reviewed")
    ):
        return _blocked(request, "PROMOTION_STATEMENT_NOT_REVIEWED")
    speaker_id = str(context.get("speaker_person_id") or "").strip()
    if not speaker_id or not bool(context.get("speaker_is_public")):
        return _blocked(request, "PROMOTION_ATTRIBUTION_MISSING")

    passages = context.get("passages") or []
    if not isinstance(passages, list) or not passages:
        return _blocked(request, "PROMOTION_PROVENANCE_MISSING")
    if int(context.get("passage_count") or 0) != 1 or len(passages) != 1:
        return _blocked(request, "PROMOTION_PROVENANCE_NOT_ATOMIC")
    passage = passages[0]
    if not isinstance(passage, Mapping):
        return _blocked(request, "PROMOTION_PROVENANCE_INVALID")

    if request.provenance_channel == "WRITTEN":
        if int(context.get("written_count") or 0) != 1 or passage.get("capture_id") is None:
            return _blocked(request, "PROMOTION_CHANNEL_MISMATCH")
        if str(passage.get("capture_hold_status") or "") != "NONE":
            return _blocked(request, "PROMOTION_CAPTURE_HOLD")
        if str(passage.get("capture_status") or "") not in {"CAPTURED", "PURGED_BODY"}:
            return _blocked(request, "PROMOTION_CAPTURE_UNUSABLE")
        try:
            quote_binding = verify_written_quote_binding(
                statement_text_sha256=str(context.get("statement_text_hash") or ""),
                passage_text_sha256=str(passage.get("text_sha256") or ""),
                private_text=str(passage.get("private_text") or ""),
                selector_type=str(passage.get("selector_type") or ""),
                start_char=passage.get("start_char"),
                end_char=passage.get("end_char"),
                source_sha256=str(passage.get("capture_sha256") or ""),
            )
        except (TypeError, ValueError):
            return _blocked(request, "PROMOTION_QUOTE_BINDING_INVALID")
        if not quote_binding.verified:
            return _blocked(request, f"PROMOTION_{quote_binding.reason_code}")
    else:
        if int(context.get("media_count") or 0) != 1 or passage.get("canonical_segment_id") is None:
            return _blocked(request, "PROMOTION_CHANNEL_MISMATCH")
        if (
            str(passage.get("segment_status") or "") != "RESOLVED"
            or bool(passage.get("segment_publication_blocked"))
            or str(passage.get("segment_speaker_person_id") or "") != speaker_id
        ):
            return _blocked(request, "PROMOTION_MEDIA_PROVENANCE_UNRESOLVED")
        if str(passage.get("segment_verbatim_method") or "") not in {
            "OFFICIAL_TRANSCRIPT",
            "HUMAN_AUDIO_VERIFIED",
        }:
            return _blocked(request, "PROMOTION_MEDIA_VERBATIM_NOT_ELIGIBLE")
        if passage.get("segment_speaker_provenance_ok") is not True:
            return _blocked(request, "PROMOTION_MEDIA_SPEAKER_PROOF_MISSING")

    duplicate_ids = tuple(str(x) for x in (context.get("duplicate_target_ids") or []))
    if len(set(duplicate_ids)) > 1:
        return _blocked(request, "PROMOTION_AMBIGUOUS_DUPLICATE")

    promotion_id = deterministic_promotion_id(request.candidate_id)
    idempotency_key = deterministic_promotion_key(
        request.candidate_id, request.provenance_channel
    )
    metadata = {
        "promotion_version": PROMOTION_VERSION,
        "claim_candidate_id": request.candidate_id,
    }
    if request.provenance_channel == "WRITTEN":
        metadata["quote_binding_version"] = quote_binding.version
        metadata["quote_binding_reason"] = quote_binding.reason_code
    provenance_refs: tuple[str, ...]

    if duplicate_ids:
        target_claim_id = duplicate_ids[0]
        provenance_refs = (
            str(passage.get("passage_id") or passage.get("canonical_segment_id") or ""),
        )
        state = store.link_existing(
            candidate_id=request.candidate_id,
            target_claim_id=target_claim_id,
            provenance_channel=request.provenance_channel,
            promotion_id=promotion_id,
            idempotency_key=idempotency_key,
            provenance_refs=json.dumps(list(provenance_refs), separators=(",", ":")),
            actor_ref=request.actor_ref,
            reason=request.reason or "",
            metadata=json.dumps(metadata, separators=(",", ":")),
        )
        if state != "LINKED_EXISTING":
            return _blocked(request, "PROMOTION_CONCURRENT_CONFLICT")
        return PromotionReceipt(
            status="PROMOTED",
            reason_code="PROMOTION_LINKED_EXISTING",
            candidate_id=request.candidate_id,
            promotion_id=promotion_id,
            target_claim_id=target_claim_id,
            action="LINKED_EXISTING",
            provenance_refs=provenance_refs,
        )

    target_claim_id = deterministic_promoted_claim_id(request.candidate_id)
    temporal_scope = context.get("temporal_scope") or {}
    if not isinstance(temporal_scope, Mapping):
        return _blocked(request, "PROMOTION_TEMPORAL_SCOPE_INVALID")
    candidate_metadata = context.get("candidate_metadata") or {}
    if not isinstance(candidate_metadata, Mapping):
        return _blocked(request, "PROMOTION_METADATA_INVALID")

    if request.provenance_channel == "WRITTEN":
        selector_type = (
            "TEXT_POSITION_HASH"
            if str(passage.get("selector_type") or "") == "TEXT_POSITION"
            else "TEXT_QUOTE_HASH"
        )
        start_char = passage.get("start_char") if selector_type == "TEXT_POSITION_HASH" else None
        end_char = passage.get("end_char") if selector_type == "TEXT_POSITION_HASH" else None
        source_ref = {
            "url": str(context.get("canonical_url") or ""),
            "title": context.get("title"),
            "published_at": context.get("published_at"),
            "capture_id": passage.get("capture_id"),
            "passage_id": passage.get("passage_id"),
            "final_url": passage.get("capture_final_url"),
        }
        provenance = make_text_provenance_candidate(
            claim_id=target_claim_id,
            content_id=str(context["content_id"]),
            person_id=speaker_id,
            selector_type=selector_type,
            quote_sha256=str(context.get("statement_text_hash") or ""),
            source_sha256=str(passage.get("capture_sha256") or ""),
            start_char=None if start_char is None else int(start_char),
            end_char=None if end_char is None else int(end_char),
            attribution_method="SOURCE_QUOTE",
            source_ref=source_ref,
        )
        validate_atomic_claim(
            claim_id=target_claim_id,
            content_id=str(context["content_id"]),
            normalized_claim=str(context["normalized_claim"]),
            claim_type=str(context["proposed_claim_type"]),
            statement_date=(temporal_scope.get("statement_date") if temporal_scope else None),
            valid_from=(temporal_scope.get("valid_from") if temporal_scope else None),
            valid_until=(temporal_scope.get("valid_until") if temporal_scope else None),
            check_worthy=bool(context["check_worthy"]),
            source_text_provenance_ids=(provenance.candidate_id,),
            metadata=dict(candidate_metadata),
        )
        provenance_review_id = _digest(
            "review",
            "CLAIM_TEXT_PROVENANCE",
            provenance.candidate_id,
            "APPROVED",
            request.actor_ref,
            request.reason or "",
        )
        state = store.create_written(
            candidate_id=request.candidate_id,
            target_claim_id=target_claim_id,
            promotion_id=promotion_id,
            idempotency_key=idempotency_key,
            provenance_id=provenance.candidate_id,
            provenance_review_id=provenance_review_id,
            selector_type=provenance.selector_type,
            start_char="" if provenance.start_char is None else provenance.start_char,
            end_char="" if provenance.end_char is None else provenance.end_char,
            source_ref=json.dumps(source_ref, ensure_ascii=False, separators=(",", ":")),
            actor_ref=request.actor_ref,
            reason=request.reason or "",
            metadata=json.dumps(metadata, separators=(",", ":")),
        )
        if state != "CREATED":
            return _blocked(request, "PROMOTION_CONCURRENT_DUPLICATE_OR_CONFLICT")
        provenance_refs = (provenance.candidate_id,)
    else:
        segment_id = str(passage["canonical_segment_id"])
        validate_atomic_claim(
            claim_id=target_claim_id,
            content_id=str(context["content_id"]),
            normalized_claim=str(context["normalized_claim"]),
            claim_type=str(context["proposed_claim_type"]),
            statement_date=(temporal_scope.get("statement_date") if temporal_scope else None),
            valid_from=(temporal_scope.get("valid_from") if temporal_scope else None),
            valid_until=(temporal_scope.get("valid_until") if temporal_scope else None),
            check_worthy=bool(context["check_worthy"]),
            source_segment_ids=(segment_id,),
            metadata=dict(candidate_metadata),
        )
        state = store.create_media(
            candidate_id=request.candidate_id,
            target_claim_id=target_claim_id,
            promotion_id=promotion_id,
            idempotency_key=idempotency_key,
            actor_ref=request.actor_ref,
            reason=request.reason or "",
            metadata=json.dumps(metadata, separators=(",", ":")),
        )
        if state != "CREATED":
            return _blocked(request, "PROMOTION_CONCURRENT_DUPLICATE_OR_CONFLICT")
        provenance_refs = (segment_id,)

    return PromotionReceipt(
        status="PROMOTED",
        reason_code="PROMOTION_CREATED",
        candidate_id=request.candidate_id,
        promotion_id=promotion_id,
        target_claim_id=target_claim_id,
        action="CREATED",
        provenance_refs=provenance_refs,
    )


__all__ = [
    "ClaimPromotionStore",
    "PROMOTION_CHANNELS",
    "PROMOTION_CONTEXT_SQL_V1",
    "PROMOTION_VERSION",
    "PromotionReceipt",
    "PromotionRequest",
    "deterministic_promoted_claim_id",
    "deterministic_promotion_id",
    "deterministic_promotion_key",
    "promote_claim_candidate",
]
