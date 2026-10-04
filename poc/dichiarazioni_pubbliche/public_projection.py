from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.domain_vocabulary import (
    ClaimType,
    FindingPublicationStatus,
    RelationCandidateType,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_FINDING_STATUSES,
    PUBLIC_SCHEMA_VERSION,
    validate_dossier,
    validate_public_bundle,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.text_provenance import (
    ALLOWED_ATTRIBUTION_METHODS as TEXT_ATTRIBUTION_METHODS,
    ALLOWED_SELECTOR_TYPES as TEXT_SELECTOR_TYPES,
    TEXT_PROVENANCE_VERSION,
)



class ProjectionSource(Protocol):
    def projectable_findings(self) -> list[dict[str, Any]]: ...


class PublicProjectionStore(PsqlRuntime):
    def projectable_findings(self) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(row_data ORDER BY created_at, finding_id)::text, '[]')
            FROM (
                SELECT
                    finding.id AS finding_id,
                    finding.claim_id,
                    finding.assessment,
                    finding.rationale,
                    finding.publication_status,
                    finding.policy_version,
                    finding.verification_run_id,
                    CASE
                        WHEN source_assessment.id IS NULL THEN NULL
                        ELSE json_build_object(
                            'assessment', source_assessment.assessment,
                            'assessment_version', source_assessment.assessment_version,
                            'requirement_profile_version', source_assessment.requirement_profile_version,
                            'rationale_codes', source_assessment.rationale_codes
                        )
                    END AS source_methodology,
                    finding.created_at::text AS created_at,
                    (
                        SELECT min(publication_review.created_at)::text
                        FROM review_event publication_review
                        WHERE
                            publication_review.entity_type = 'FINDING'
                            AND publication_review.entity_id = finding.id
                            AND publication_review.action = 'APPROVED'
                    ) AS published_at,
                    COALESCE((
                        SELECT json_agg(
                            publication_review.id
                            ORDER BY publication_review.created_at,
                                publication_review.id
                        )
                        FROM review_event publication_review
                        WHERE
                            publication_review.entity_type = 'FINDING'
                            AND publication_review.entity_id = finding.id
                            AND publication_review.action = 'APPROVED'
                    ), '[]'::json) AS publication_review_ids,
                    finding.supersedes_id,
                    claim.normalized_claim,
                    claim.claim_type,
                    claim.temporal_scope,
                    claim.check_worthy,
                    content.id AS content_id,
                    content.canonical_url AS source_url,
                    content.title AS source_title,
                    content.published_at::text AS source_published_at,
                    CASE
                        WHEN person.id IS NULL THEN NULL
                        ELSE json_build_object(
                            'id', person.id,
                            'name', person.canonical_name,
                            'public_roles', COALESCE((
                                SELECT json_agg(json_build_object(
                                    'organization_id', role.organization_id,
                                    'organization_name', organization.canonical_name,
                                    'role', role.role,
                                    'start_date', role.start_date::text,
                                    'end_date', role.end_date::text,
                                    'review_event_ids', COALESCE((
                                        SELECT json_agg(review.id ORDER BY review.id)
                                        FROM review_event review
                                        WHERE review.entity_type =
                                            'PERSON_ROLE_INTERVAL'
                                          AND review.entity_id = role.id
                                          AND review.action = 'APPROVED'
                                    ), '[]'::json)
                                ) ORDER BY role.start_date, role.role)
                                FROM person_role_interval role
                                JOIN organization
                                    ON organization.id = role.organization_id
                                WHERE role.person_id = person.id
                                  AND role.is_public_role = true
                                  AND role.status = 'ACTIVE'
                                  AND role.start_date <= COALESCE(
                                      NULLIF(claim.temporal_scope->>'statement_date', '')::date,
                                      content.published_at::date,
                                      CURRENT_DATE
                                  )
                                  AND (
                                      role.end_date IS NULL
                                      OR COALESCE(
                                          NULLIF(claim.temporal_scope->>'statement_date', '')::date,
                                          content.published_at::date,
                                          CURRENT_DATE
                                      ) < role.end_date
                                  )
                                  AND EXISTS (
                                      SELECT 1
                                      FROM review_event role_review
                                      WHERE role_review.entity_type =
                                          'PERSON_ROLE_INTERVAL'
                                        AND role_review.entity_id = role.id
                                        AND role_review.action = 'APPROVED'
                                  )
                            ), '[]'::json)
                        )
                    END AS speaker,
                    COALESCE((
                        SELECT json_agg(json_build_object(
                            'segment_id', segment.id,
                            'segment_index', segment.segment_index,
                            'start_ms', segment.start_ms,
                            'end_ms', segment.end_ms,
                            'transcript_candidates', COALESCE((
                                SELECT json_agg(json_build_object(
                                    'segment_id', candidate_segment.id,
                                    'variant_id', variant.id,
                                    'provider_id', variant.provider_id,
                                    'source_kind', variant.source_kind,
                                    'transcript_sha256', variant.raw_text_sha256
                                ) ORDER BY candidate_segment.id)
                                FROM canonical_segment_candidate candidate_link
                                JOIN transcript_segment candidate_segment
                                    ON candidate_segment.id =
                                        candidate_link.transcript_segment_id
                                JOIN transcript_variant variant
                                    ON variant.id = candidate_segment.variant_id
                                WHERE
                                    candidate_link.canonical_segment_id =
                                        segment.id
                                    AND variant.content_id = segment.content_id
                            ), '[]'::json)
                        ) ORDER BY segment.segment_index)
                        FROM claim_segment link
                        JOIN canonical_transcript_segment segment
                            ON segment.id = link.segment_id
                        WHERE link.claim_id = claim.id
                    ), '[]'::json) AS source_segments,
                    COALESCE((
                        SELECT json_agg(json_build_object(
                            'id', provenance.id,
                            'selector_type', provenance.selector_type,
                            'quote_sha256', provenance.quote_sha256,
                            'source_sha256', provenance.source_sha256,
                            'start_char', provenance.start_char,
                            'end_char', provenance.end_char,
                            'attribution_method', provenance.attribution_method,
                            'attribution_version', provenance.attribution_version,
                            'review_event_ids', COALESCE((
                                SELECT json_agg(review.id ORDER BY review.id)
                                FROM review_event review
                                WHERE
                                    review.entity_type = 'CLAIM_TEXT_PROVENANCE'
                                    AND review.entity_id = provenance.id
                                    AND review.action = 'APPROVED'
                            ), '[]'::json)
                        ) ORDER BY provenance.id)
                        FROM claim_text_provenance provenance
                        WHERE
                            provenance.claim_id = claim.id
                            AND provenance.content_id = content.id
                            AND provenance.person_id = claim.speaker_person_id
                            AND provenance.status = 'APPROVED'
                            AND EXISTS (
                                SELECT 1
                                FROM review_event review
                                WHERE
                                    review.entity_type = 'CLAIM_TEXT_PROVENANCE'
                                    AND review.entity_id = provenance.id
                                    AND review.action = 'APPROVED'
                            )
                    ), '[]'::json) AS source_text_provenance,
                    COALESCE((
                        SELECT json_agg(json_build_object(
                            'id', evidence.id,
                            'url', evidence.canonical_url,
                            'publisher', evidence.publisher,
                            'source_type', evidence.source_type,
                            'publication_date', evidence.publication_date::text,
                            'observed_at', evidence.observed_at::text,
                            'content_sha256', evidence.content_sha256,
                            'reference_period', evidence.reference_period,
                            'rights_status', evidence.rights_status,
                            'relation', source_link.relation,
                            'verification_observation_ids', COALESCE((
                                SELECT json_agg(
                                    observation.id ORDER BY observation.id
                                )
                                FROM evidence_observation observation
                                WHERE
                                    observation.evidence_id = evidence.id
                                    AND verification.observation_ids ?
                                        observation.id
                            ), '[]'::json),
                            'evidence_review_ids', COALESCE((
                                SELECT json_agg(review.id ORDER BY review.id)
                                FROM claim_evidence_candidate candidate
                                JOIN review_event review
                                    ON review.entity_type =
                                        'CLAIM_EVIDENCE_CANDIDATE'
                                    AND review.entity_id =
                                        candidate.claim_id || '|' ||
                                        candidate.evidence_id || '|' ||
                                        candidate.retrieval_version
                                    AND review.action = 'APPROVED'
                                WHERE
                                    candidate.claim_id = claim.id
                                    AND candidate.evidence_id = evidence.id
                                    AND candidate.status = 'APPROVED'
                            ), '[]'::json),
                            'observation_review_ids', COALESCE((
                                SELECT json_agg(review.id ORDER BY review.id)
                                FROM evidence_observation observation
                                JOIN review_event review
                                    ON review.entity_type =
                                        'EVIDENCE_OBSERVATION'
                                    AND review.entity_id = observation.id
                                    AND review.action = 'APPROVED'
                                WHERE
                                    observation.evidence_id = evidence.id
                                    AND verification.observation_ids ?
                                        observation.id
                                    AND observation.status = 'APPROVED'
                            ), '[]'::json)
                        ) ORDER BY evidence.id)
                        FROM finding_evidence source_link
                        JOIN evidence ON evidence.id = source_link.evidence_id
                        WHERE source_link.finding_id = finding.id
                    ), '[]'::json) AS evidence,
                    COALESCE((
                        SELECT json_agg(json_build_object(
                            'id', correction.id,
                            'finding_id', correction.finding_id,
                            'previous_finding_id', correction.previous_finding_id,
                            'reason', left(correction.reason, 2000),
                            'changed_fields', correction.changed_fields,
                            'created_at', correction.created_at::text,
                            'publication_review_approved', EXISTS (
                                SELECT 1
                                FROM review_event correction_review
                                WHERE
                                    correction_review.entity_type = 'CORRECTION'
                                    AND correction_review.entity_id = correction.id
                                    AND correction_review.action = 'APPROVED'
                            )
                        ) ORDER BY correction.created_at, correction.id)
                        FROM correction
                        WHERE
                            (
                                correction.finding_id = finding.id
                                OR correction.previous_finding_id = finding.id
                            )
                            AND correction.public_visibility = 'PUBLIC'
                            AND EXISTS (
                                SELECT 1
                                FROM finding current
                                JOIN finding previous
                                    ON previous.id =
                                        correction.previous_finding_id
                                WHERE
                                    current.id = correction.finding_id
                                    AND current.supersedes_id = previous.id
                                    AND current.claim_id = previous.claim_id
                                    AND NOT EXISTS (
                                        SELECT 1
                                        FROM finding child
                                        WHERE child.supersedes_id = current.id
                                    )
                                    AND EXISTS (
                                        SELECT 1
                                        FROM reanalysis_trigger trigger
                                        WHERE
                                            trigger.claim_id = current.claim_id
                                            AND trigger.trigger_type =
                                                'CORRECTION'
                                            AND trigger.source_type =
                                                'CORRECTION'
                                            AND trigger.source_id =
                                                correction.id
                                            AND trigger.status = 'PROCESSED'
                                    )
                            )
                            AND EXISTS (
                                SELECT 1
                                FROM review_event correction_review
                                WHERE
                                    correction_review.entity_type = 'CORRECTION'
                                    AND correction_review.entity_id = correction.id
                                    AND correction_review.action = 'APPROVED'
                            )
                    ), '[]'::json) AS corrections,
                    COALESCE((
                        SELECT json_agg(json_build_object(
                            'id', reply.id,
                            'submitter_name', reply.submitter_name,
                            'submitter_role', reply.submitter_role,
                            'submitted_at', reply.submitted_at::text,
                            'body', left(reply.body, 4000),
                            'evidence_urls', reply.evidence_urls,
                            'status', reply.status,
                            'publication_review_approved', EXISTS (
                                SELECT 1
                                FROM review_event reply_review
                                WHERE
                                    reply_review.entity_type = 'RIGHT_OF_REPLY'
                                    AND reply_review.entity_id = reply.id
                                    AND reply_review.action = 'APPROVED'
                            )
                        ) ORDER BY reply.submitted_at, reply.id)
                        FROM right_of_reply reply
                        WHERE
                            reply.finding_id = finding.id
                            AND reply.public_visibility = 'PUBLIC'
                            AND reply.status = 'PUBLISHED'
                            AND reply.reanalysis_job_id IS NOT NULL
                            AND EXISTS (
                                SELECT 1
                                FROM reanalysis_trigger trigger
                                WHERE
                                    trigger.claim_id = finding.claim_id
                                    AND trigger.trigger_type =
                                        'RIGHT_OF_REPLY'
                                    AND trigger.source_type =
                                        'RIGHT_OF_REPLY'
                                    AND trigger.source_id = reply.id
                                    AND trigger.status = 'PROCESSED'
                            )
                            AND EXISTS (
                                SELECT 1
                                FROM review_event reply_review
                                WHERE
                                    reply_review.entity_type = 'RIGHT_OF_REPLY'
                                    AND reply_review.entity_id = reply.id
                                    AND reply_review.action = 'APPROVED'
                            )
                    ), '[]'::json) AS rights_of_reply,
                    COALESCE((
                        SELECT json_agg(json_build_object(
                            'candidate_id', speaker_candidate.id,
                            'review_event_ids', COALESCE((
                                SELECT json_agg(review.id ORDER BY review.id)
                                FROM review_event review
                                WHERE
                                    review.entity_type =
                                        'SPEAKER_IDENTITY_CANDIDATE'
                                    AND review.entity_id = speaker_candidate.id
                                    AND review.action = 'APPROVED'
                            ), '[]'::json)
                        ) ORDER BY speaker_candidate.id)
                        FROM speaker_identity_candidate speaker_candidate
                        WHERE
                            speaker_candidate.content_id = content.id
                            AND speaker_candidate.person_id = claim.speaker_person_id
                            AND speaker_candidate.status = 'APPROVED'
                            AND EXISTS (
                                SELECT 1
                                FROM review_event speaker_review
                                WHERE
                                    speaker_review.entity_type =
                                        'SPEAKER_IDENTITY_CANDIDATE'
                                    AND speaker_review.entity_id =
                                        speaker_candidate.id
                                    AND speaker_review.action = 'APPROVED'
                            )
                            AND EXISTS (
                                SELECT 1
                                FROM claim_segment link
                                JOIN canonical_transcript_segment segment
                                    ON segment.id = link.segment_id
                                WHERE
                                    link.claim_id = claim.id
                                    AND segment.start_ms >= speaker_candidate.start_ms
                                    AND segment.end_ms <= speaker_candidate.end_ms
                            )
                    ), '[]'::json) AS speaker_provenance,
                    COALESCE((
                        SELECT json_agg(json_build_object(
                            'id', relation.id,
                            'relation_type', relation.relation_type,
                            'relation_version', relation.relation_version,
                            'status', relation.status,
                            'rationale_codes', relation.rationale_codes,
                            'review_event_id', relation_review.id,
                            'role', CASE
                                WHEN relation.subject_claim_id = claim.id
                                    THEN 'SUBJECT'
                                ELSE 'OBJECT'
                            END,
                            'related_claim_id', CASE
                                WHEN relation.subject_claim_id = claim.id
                                    THEN relation.object_claim_id
                                ELSE relation.subject_claim_id
                            END,
                            'related_claim', related.normalized_claim,
                            'related_statement_date',
                                related.temporal_scope->>'statement_date'
                        ) ORDER BY relation.id)
                        FROM claim_relation_candidate relation
                        JOIN atomic_claim related
                            ON related.id = CASE
                                WHEN relation.subject_claim_id = claim.id
                                    THEN relation.object_claim_id
                                ELSE relation.subject_claim_id
                            END
                        JOIN review_event relation_review
                            ON relation_review.entity_type =
                                'RELATION_CANDIDATE'
                            AND relation_review.entity_id = relation.id
                            AND relation_review.action = 'APPROVED'
                        WHERE
                            relation.status = 'APPROVED'
                            AND (
                                relation.subject_claim_id = claim.id
                                OR relation.object_claim_id = claim.id
                            )
                            AND EXISTS (
                                SELECT 1
                                FROM finding related_finding
                                WHERE
                                    related_finding.claim_id = related.id
                                    AND related_finding.publication_status =
                                        'PUBLISH'
                            )
                            AND NOT EXISTS (
                                SELECT 1
                                FROM review_event relation_superseded
                                WHERE
                                    relation_superseded.entity_type =
                                        'RELATION_CANDIDATE'
                                    AND relation_superseded.entity_id =
                                        relation.id
                                    AND relation_superseded.action IN (
                                        'REJECTED', 'SUPERSEDED'
                                    )
                                    AND relation_superseded.created_at >
                                        relation_review.created_at
                            )
                    ), '[]'::json) AS relations
                FROM finding
                JOIN atomic_claim claim ON claim.id = finding.claim_id
                JOIN content_item content ON content.id = claim.content_id
                JOIN verification_run verification
                    ON verification.id = finding.verification_run_id
                LEFT JOIN evidence_set_assessment source_assessment
                    ON source_assessment.id = verification.source_intelligence_assessment_id
                LEFT JOIN person ON person.id = claim.speaker_person_id
                WHERE
                    verification.claim_id = claim.id
                    AND finding.assessment = verification.assessment
                    AND finding.publication_status IN (
                        'PUBLISH', 'DISPUTED', 'CORRECTED', 'RETRACTED'
                    )
                    AND jsonb_array_length(verification.blockers) = 0
                    AND jsonb_typeof(verification.evidence_ids) = 'array'
                    AND jsonb_array_length(verification.evidence_ids) > 0
                    AND jsonb_typeof(verification.observation_ids) = 'array'
                    AND jsonb_array_length(verification.observation_ids) > 0
                    AND EXISTS (
                        SELECT 1
                        FROM review_event review
                        WHERE
                            review.entity_type = 'FINDING'
                            AND review.entity_id = finding.id
                            AND review.action = 'APPROVED'
                    )
                    AND (
                        EXISTS (
                            SELECT 1
                            FROM claim_segment link
                            WHERE link.claim_id = claim.id
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM claim_text_provenance provenance
                            WHERE
                                provenance.claim_id = claim.id
                                AND provenance.content_id = claim.content_id
                                AND provenance.person_id = claim.speaker_person_id
                                AND provenance.status = 'APPROVED'
                                AND EXISTS (
                                    SELECT 1
                                    FROM review_event provenance_review
                                    WHERE
                                        provenance_review.entity_type =
                                            'CLAIM_TEXT_PROVENANCE'
                                        AND provenance_review.entity_id = provenance.id
                                        AND provenance_review.action = 'APPROVED'
                                )
                        )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM claim_segment link
                        JOIN canonical_transcript_segment segment
                            ON segment.id = link.segment_id
                        WHERE
                            link.claim_id = claim.id
                            AND segment.publication_blocked = true
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM claim_segment link
                        JOIN canonical_transcript_segment segment
                            ON segment.id = link.segment_id
                        WHERE
                            link.claim_id = claim.id
                            AND NOT EXISTS (
                                SELECT 1
                                FROM canonical_segment_candidate candidate_link
                                JOIN transcript_segment candidate_segment
                                    ON candidate_segment.id =
                                        candidate_link.transcript_segment_id
                                JOIN transcript_variant candidate_variant
                                    ON candidate_variant.id =
                                        candidate_segment.variant_id
                                WHERE
                                    candidate_link.canonical_segment_id =
                                        segment.id
                                    AND candidate_variant.content_id =
                                        segment.content_id
                            )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM claim_segment link
                        JOIN canonical_transcript_segment segment
                            ON segment.id = link.segment_id
                        WHERE
                            link.claim_id = claim.id
                            AND NOT EXISTS (
                                SELECT 1
                                FROM review_event freshness_review
                                WHERE
                                    freshness_review.entity_type = 'FINDING'
                                    AND freshness_review.entity_id = finding.id
                                    AND freshness_review.action = 'APPROVED'
                                    AND freshness_review.created_at >=
                                        segment.updated_at
                            )
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM finding_evidence source_link
                        WHERE source_link.finding_id = finding.id
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding_evidence source_link
                        WHERE
                            source_link.finding_id = finding.id
                            AND NOT EXISTS (
                                SELECT 1
                                FROM claim_evidence_candidate candidate
                                WHERE
                                    candidate.claim_id = claim.id
                                    AND candidate.evidence_id =
                                        source_link.evidence_id
                                    AND candidate.status = 'APPROVED'
                                    AND EXISTS (
                                        SELECT 1
                                        FROM review_event evidence_review
                                        WHERE
                                            evidence_review.entity_type =
                                                'CLAIM_EVIDENCE_CANDIDATE'
                                            AND evidence_review.entity_id =
                                                candidate.claim_id || '|' ||
                                                candidate.evidence_id || '|' ||
                                                candidate.retrieval_version
                                            AND evidence_review.action =
                                                'APPROVED'
                                    )
                            )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding_evidence source_link
                        WHERE
                            source_link.finding_id = finding.id
                            AND NOT EXISTS (
                                SELECT 1
                                FROM evidence_observation observation
                                WHERE
                                    observation.evidence_id =
                                        source_link.evidence_id
                                    AND observation.status = 'APPROVED'
                                    AND verification.observation_ids ?
                                        observation.id
                                    AND EXISTS (
                                        SELECT 1
                                        FROM review_event observation_review
                                        WHERE
                                            observation_review.entity_type =
                                                'EVIDENCE_OBSERVATION'
                                            AND observation_review.entity_id =
                                                observation.id
                                            AND observation_review.action =
                                                'APPROVED'
                                    )
                            )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(
                            verification.evidence_ids
                        ) expected(evidence_id)
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM finding_evidence source_link
                            WHERE
                                source_link.finding_id = finding.id
                                AND source_link.evidence_id = expected.evidence_id
                        )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding_evidence source_link
                        WHERE
                            source_link.finding_id = finding.id
                            AND NOT (
                                verification.evidence_ids ? source_link.evidence_id
                            )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements_text(
                            verification.observation_ids
                        ) expected(observation_id)
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM evidence_observation observation
                            JOIN finding_evidence source_link
                                ON source_link.evidence_id =
                                    observation.evidence_id
                            WHERE
                                source_link.finding_id = finding.id
                                AND observation.id = expected.observation_id
                                AND observation.status = 'APPROVED'
                                AND EXISTS (
                                    SELECT 1
                                    FROM review_event observation_review
                                    WHERE
                                        observation_review.entity_type =
                                            'EVIDENCE_OBSERVATION'
                                        AND observation_review.entity_id =
                                            observation.id
                                        AND observation_review.action =
                                            'APPROVED'
                                )
                        )
                    )
                    AND claim.speaker_person_id IS NOT NULL
                    AND NOT EXISTS (
                            SELECT 1
                            FROM claim_segment link
                            JOIN canonical_transcript_segment segment
                                ON segment.id = link.segment_id
                            WHERE
                                link.claim_id = claim.id
                                AND (
                                    segment.speaker_person_id IS DISTINCT FROM
                                        claim.speaker_person_id
                                    OR NOT EXISTS (
                                        SELECT 1
                                        FROM speaker_identity_candidate speaker_candidate
                                        WHERE
                                            speaker_candidate.content_id =
                                                segment.content_id
                                            AND speaker_candidate.person_id =
                                                claim.speaker_person_id
                                            AND speaker_candidate.status = 'APPROVED'
                                            AND EXISTS (
                                                SELECT 1
                                                FROM review_event speaker_review
                                                WHERE
                                                    speaker_review.entity_type =
                                                        'SPEAKER_IDENTITY_CANDIDATE'
                                                    AND speaker_review.entity_id =
                                                        speaker_candidate.id
                                                    AND speaker_review.action =
                                                        'APPROVED'
                                            )
                                            AND segment.start_ms >=
                                                speaker_candidate.start_ms
                                            AND segment.end_ms <=
                                                speaker_candidate.end_ms
                                    )
                                )
                        )
            ) row_data;
            """
        )
        return json.loads(raw or "[]")


def _safe_http_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("unsafe public URL")
    return parsed.geturl()


def _bounded(value: object, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _bounded_ids(value: object, *, limit: int = 128) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > limit:
        raise ValueError("invalid provenance ID list")
    result = []
    for item in value:
        text = str(item).strip()
        if not text or len(text) > 512:
            raise ValueError("invalid provenance ID")
        result.append(text)
    return result


def _sha256_hex(value: object, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = str(value or "").strip().lower()
    if optional and not text:
        return None
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError("invalid sha256 provenance value")
    return text


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("publication_status") or "")
    try:
        publication_status = FindingPublicationStatus(status)
        assessment = VerificationAssessment(str(row.get("assessment") or ""))
        claim_type = ClaimType(str(row.get("claim_type") or ""))
    except ValueError as exc:
        raise ValueError("finding vocabulary is not canonical") from exc
    if publication_status not in PUBLIC_FINDING_STATUSES:
        raise ValueError("finding is not publicly visible")
    if assessment in {
        VerificationAssessment.INSUFFICIENT_EVIDENCE,
        VerificationAssessment.UNRESOLVED,
    }:
        raise ValueError("non-publishable assessment cannot enter public projection")
    source_url = _safe_http_url(str(row.get("source_url") or ""))
    evidence_rows = []
    for item in row.get("evidence") or []:
        if not isinstance(item, dict):
            raise ValueError("invalid evidence row")
        observation_ids = _bounded_ids(
            item.get("verification_observation_ids")
        )
        evidence_review_ids = _bounded_ids(item.get("evidence_review_ids"))
        observation_review_ids = _bounded_ids(
            item.get("observation_review_ids")
        )
        evidence_rows.append(
            {
                "id": str(item["id"]),
                "url": _safe_http_url(str(item.get("url") or "")),
                "publisher": _bounded(item.get("publisher"), 300),
                "source_type": _bounded(item.get("source_type"), 100),
                "publication_date": _bounded(item.get("publication_date"), 64),
                "observed_at": _bounded(item.get("observed_at"), 64),
                "content_sha256": _bounded(item.get("content_sha256"), 128),
                "reference_period": _bounded(item.get("reference_period"), 200),
                "rights_status": _bounded(item.get("rights_status"), 100),
                "relation": _bounded(item.get("relation"), 100),
                "verification_observation_ids": observation_ids,
                "evidence_review_ids": evidence_review_ids,
                "observation_review_ids": observation_review_ids,
            }
        )
    if not evidence_rows:
        raise ValueError("public finding has no evidence")

    source_methodology = None
    raw_methodology = row.get("source_methodology")
    if raw_methodology is not None:
        if not isinstance(raw_methodology, dict):
            raise ValueError("invalid source methodology")
        if raw_methodology.get("assessment") != "SUFFICIENT_FOR_RULE":
            raise ValueError("non-sufficient source methodology cannot be public")
        raw_codes = raw_methodology.get("rationale_codes") or []
        if not isinstance(raw_codes, list) or len(raw_codes) > 32:
            raise ValueError("invalid source methodology rationale")
        source_methodology = {
            "assessment": "SUFFICIENT_FOR_RULE",
            "assessment_version": _bounded(
                raw_methodology.get("assessment_version"), 200
            ),
            "requirement_profile_version": _bounded(
                raw_methodology.get("requirement_profile_version"), 200
            ),
            "rationale_codes": [
                _bounded(code, 200) for code in raw_codes if _bounded(code, 200)
            ],
        }

    segments = []
    for item in row.get("source_segments") or []:
        if not isinstance(item, dict):
            raise ValueError("invalid segment row")
        transcript_candidates = []
        for candidate in item.get("transcript_candidates") or []:
            if not isinstance(candidate, dict):
                raise ValueError("invalid transcript provenance")
            transcript_candidates.append(
                {
                    "segment_id": str(candidate["segment_id"]),
                    "variant_id": str(candidate["variant_id"]),
                    "provider_id": _bounded(candidate.get("provider_id"), 200),
                    "source_kind": _bounded(candidate.get("source_kind"), 200),
                    "transcript_sha256": _bounded(
                        candidate.get("transcript_sha256"), 128
                    ),
                }
            )
        if not transcript_candidates:
            raise ValueError("source segment lacks transcript provenance")
        segments.append(
            {
                "segment_id": str(item["segment_id"]),
                "segment_index": int(item["segment_index"]),
                "start_ms": int(item["start_ms"]),
                "end_ms": int(item["end_ms"]),
                "transcript_candidates": transcript_candidates,
            }
        )

    text_provenance = []
    for item in row.get("source_text_provenance") or []:
        if not isinstance(item, dict):
            raise ValueError("invalid text provenance row")
        selector_type = str(item.get("selector_type") or "")
        attribution_method = str(item.get("attribution_method") or "")
        attribution_version = str(item.get("attribution_version") or "")
        if selector_type not in TEXT_SELECTOR_TYPES:
            raise ValueError("invalid text provenance selector")
        if attribution_method not in TEXT_ATTRIBUTION_METHODS:
            raise ValueError("invalid text provenance attribution method")
        if attribution_version != TEXT_PROVENANCE_VERSION:
            raise ValueError("invalid text provenance version")
        start_char = item.get("start_char")
        end_char = item.get("end_char")
        if (start_char is None) != (end_char is None):
            raise ValueError("invalid text provenance position pair")
        if start_char is not None:
            start_char = int(start_char)
            end_char = int(end_char)
            if start_char < 0 or end_char <= start_char:
                raise ValueError("invalid text provenance position")
        if selector_type == "TEXT_POSITION_HASH" and start_char is None:
            raise ValueError("text position selector requires bounds")
        text_provenance.append(
            {
                "id": str(item["id"]),
                "selector_type": selector_type,
                "quote_sha256": _sha256_hex(item.get("quote_sha256")),
                "source_sha256": _sha256_hex(
                    item.get("source_sha256"), optional=True
                ),
                "start_char": start_char,
                "end_char": end_char,
                "attribution_method": attribution_method,
                "attribution_version": attribution_version,
                "review_event_ids": _bounded_ids(item.get("review_event_ids")),
            }
        )
    if not segments and not text_provenance:
        raise ValueError("public finding has no approved source provenance")

    speaker = row.get("speaker")
    if not isinstance(speaker, dict):
        raise ValueError("public claim requires approved speaker identity")
    provenance = []
    for item in row.get("speaker_provenance") or []:
        if not isinstance(item, dict):
            raise ValueError("invalid speaker provenance")
        provenance.append(
            {
                "candidate_id": str(item["candidate_id"]),
                "review_event_ids": _bounded_ids(
                    item.get("review_event_ids")
                ),
                "provenance_kind": "TIMED_SPEAKER",
            }
        )
    for item in text_provenance:
        provenance.append(
            {
                "candidate_id": item["id"],
                "review_event_ids": list(item["review_event_ids"]),
                "provenance_kind": "TEXT_ATTRIBUTION",
            }
        )
    if not provenance:
        raise ValueError("speaker attribution lacks approved provenance")
    public_roles = []
    for role in speaker.get("public_roles") or []:
        if not isinstance(role, dict):
            raise ValueError("invalid public role")
        try:
            review_ids = _bounded_ids(role.get("review_event_ids"))
        except ValueError:
            review_ids = []
        organization_id = _bounded(role.get("organization_id"), 300)
        role_name = _bounded(role.get("role"), 300)
        if not organization_id or not role_name or not review_ids:
            continue
        public_roles.append(
            {
                "organization_id": organization_id,
                "organization_name": _bounded(role.get("organization_name"), 300),
                "role": role_name,
                "start_date": _bounded(role.get("start_date"), 64),
                "end_date": _bounded(role.get("end_date"), 64),
                "review_event_ids": review_ids,
            }
        )
    clean_speaker = {
        "id": str(speaker["id"]),
        "name": _bounded(speaker.get("name"), 300),
        "public_role": (
            public_roles[0]["role"] if public_roles else None
        ),
        "public_roles": public_roles,
        "provenance": provenance,
    }

    replies = []
    for reply in row.get("rights_of_reply") or []:
        if not isinstance(reply, dict):
            continue
        if (
            reply.get("status") != "PUBLISHED"
            or reply.get("publication_review_approved") is not True
        ):
            continue
        urls = []
        raw_urls = reply.get("evidence_urls") or []
        if not isinstance(raw_urls, list) or len(raw_urls) > 32:
            continue
        for value in raw_urls:
            try:
                candidate_url = str(value)
                if len(candidate_url) > 2048:
                    continue
                urls.append(_safe_http_url(candidate_url))
            except ValueError:
                continue
        replies.append(
            {
                "id": str(reply["id"]),
                "submitter_name": _bounded(reply.get("submitter_name"), 300),
                "submitter_role": _bounded(reply.get("submitter_role"), 300),
                "submitted_at": _bounded(reply.get("submitted_at"), 64),
                "body": _bounded(reply.get("body"), 4000),
                "evidence_urls": urls,
                "status": _bounded(reply.get("status"), 100),
            }
        )

    corrections = []
    for correction in row.get("corrections") or []:
        if not isinstance(correction, dict):
            continue
        if correction.get("publication_review_approved") is not True:
            continue
        changed_fields = (
            correction.get("changed_fields")
            if isinstance(correction.get("changed_fields"), dict)
            else {}
        )
        if len(
            json.dumps(
                changed_fields,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ) > 32_768:
            continue
        corrections.append(
            {
                "id": str(correction["id"]),
                "finding_id": _bounded(correction.get("finding_id"), 300),
                "previous_finding_id": _bounded(
                    correction.get("previous_finding_id"), 300
                ),
                "reason": _bounded(correction.get("reason"), 2000),
                "changed_fields": changed_fields,
                "created_at": _bounded(correction.get("created_at"), 64),
            }
        )

    relations = []
    for relation in row.get("relations") or []:
        if not isinstance(relation, dict):
            raise ValueError("invalid public relation row")
        try:
            relation_type = RelationCandidateType(
                str(relation.get("relation_type") or "")
            )
        except ValueError as exc:
            raise ValueError("public relation type is not canonical") from exc
        review_id = _bounded(relation.get("review_event_id"), 512)
        if not review_id:
            raise ValueError("public relation requires one approval review event")
        related_claim = _bounded(relation.get("related_claim"), 4000)
        related_claim_id = _bounded(relation.get("related_claim_id"), 300)
        if not related_claim or not related_claim_id:
            raise ValueError("public relation requires a related claim")
        relations.append(
            {
                "id": str(relation["id"]),
                "relation_type": relation_type.value,
                "relation_version": str(relation["relation_version"]),
                "status": "APPROVED",
                "role": str(relation["role"]),
                "related_claim_id": related_claim_id,
                "related_claim": related_claim,
                "related_statement_date": _bounded(
                    relation.get("related_statement_date"), 64
                ),
                "rationale_codes": [
                    str(code)[:200]
                    for code in (relation.get("rationale_codes") or [])[:32]
                ],
                "review_event_id": review_id,
            }
        )

    publication_review_ids = _bounded_ids(row.get("publication_review_ids"))
    dossier = {
        "finding_id": str(row["finding_id"]),
        "claim_id": str(row["claim_id"]),
        "claim": _bounded(row.get("normalized_claim"), 4000),
        "claim_type": claim_type.value,
        "claim_contract": {
            "version": 1,
            "temporal_scope": row.get("temporal_scope")
            if isinstance(row.get("temporal_scope"), dict)
            else {},
            "check_worthy": row.get("check_worthy") is True,
            "speaker_approval_required": True,
            "source_segment_ids": [segment["segment_id"] for segment in segments],
            "source_text_provenance_ids": [item["id"] for item in text_provenance],
        },
        "speaker": clean_speaker,
        "source": {
            "content_id": str(row["content_id"]),
            "url": source_url,
            "title": _bounded(row.get("source_title"), 500),
            "published_at": _bounded(row.get("source_published_at"), 64),
            "segments": segments,
            "text_provenance": text_provenance,
        },
        "finding": {
            "assessment": assessment.value,
            "publication_status": publication_status.value,
            "rationale": _bounded(row.get("rationale"), 8000),
            "policy_version": _bounded(row.get("policy_version"), 200),
            "verification_run_id": str(row["verification_run_id"]),
            "created_at": _bounded(row.get("created_at"), 64),
            "published_at": _bounded(row.get("published_at"), 64),
            "publication_review_ids": publication_review_ids,
            "supersedes_id": _bounded(row.get("supersedes_id"), 300),
        },
        "evidence": evidence_rows,
        "corrections": corrections,
        "rights_of_reply": replies,
        "relations": relations,
    }
    if source_methodology is not None:
        dossier["source_methodology"] = source_methodology
    return validate_dossier(dossier)

def build_public_projection(
    source: ProjectionSource,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    dossiers = []
    omitted = 0
    for row in source.projectable_findings():
        try:
            dossiers.append(_sanitize_row(row))
        except (KeyError, TypeError, ValueError):
            omitted += 1
    dossiers.sort(key=lambda item: (item["claim_id"], item["finding_id"]))
    canonical = json.dumps(
        dossiers,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    bundle = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "generated_at": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset_sha256": hashlib.sha256(canonical).hexdigest(),
        "methodology": {
            "claim_level_only": True,
            "aggregate_person_score": False,
            "requires_publication_gate": True,
            "requires_approved_evidence": True,
            "requires_resolved_transcript": True,
        },
        "dossier_count": len(dossiers),
        "omitted_count": omitted,
        "dossiers": dossiers,
    }
    return validate_public_bundle(bundle)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _dossier_filename(finding_id: str) -> str:
    return hashlib.sha256(finding_id.encode()).hexdigest()[:24]


def dossier_jsonld(dossier: dict[str, Any]) -> dict[str, Any]:
    finding = dossier["finding"]
    source = dossier["source"]
    speaker = dossier["speaker"]
    citations = []
    for evidence in dossier["evidence"]:
        citation: dict[str, Any] = {
            "@type": "CreativeWork",
            "@id": evidence["url"],
            "url": evidence["url"],
        }
        if evidence.get("publisher"):
            citation["publisher"] = {
                "@type": "Organization",
                "name": evidence["publisher"],
            }
        if evidence.get("publication_date"):
            citation["datePublished"] = evidence["publication_date"]
        citations.append(citation)

    reviewed_claim = {
        "@type": "Claim",
        "@id": f"urn:dichiarazioni-pubbliche:{dossier['claim_id']}",
        "text": dossier["claim"],
        "author": {
            "@type": "Person",
            "@id": f"urn:dichiarazioni-pubbliche:{speaker['id']}",
            "name": speaker.get("name") or speaker["id"],
        },
        "appearance": {
            "@type": "CreativeWork",
            "@id": source["url"],
            "url": source["url"],
            "name": source.get("title"),
            "datePublished": source.get("published_at"),
        },
    }
    for role in speaker.get("public_roles") or []:
        if role.get("organization_id") and role.get("role"):
            reviewed_claim["author"].setdefault("worksFor", []).append(
                {
                    "@type": "Organization",
                    "id": f"urn:dichiarazioni-pubbliche:{role['organization_id']}",
                    "name": role.get("organization_name") or role["organization_id"],
                }
            )
    return {
        "@context": "https://schema.org",
        "@type": "ClaimReview",
        "@id": f"urn:dichiarazioni-pubbliche:{dossier['finding_id']}",
        "claimReviewed": dossier["claim"],
        "itemReviewed": reviewed_claim,
        "author": {
            "@type": "Organization",
            "name": "Dichiarazioni Pubbliche",
        },
        "datePublished": finding.get("published_at"),
        "reviewRating": {
            "@type": "Rating",
            "alternateName": finding.get("assessment"),
        },
        "citation": citations,
        "additionalProperty": [
            {
                "@type": "PropertyValue",
                "name": "publicationStatus",
                "value": finding.get("publication_status"),
            },
            {
                "@type": "PropertyValue",
                "name": "policyVersion",
                "value": finding.get("policy_version"),
            },
            {
                "@type": "PropertyValue",
                "name": "verificationRunId",
                "value": finding.get("verification_run_id"),
            },
        ],
    }


def projection_jsonld(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Dichiarazioni Pubbliche — ClaimReview",
        "numberOfItems": len(payload.get("dossiers") or []),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "item": dossier_jsonld(dossier),
            }
            for index, dossier in enumerate(
                payload.get("dossiers") or [],
                start=1,
            )
        ],
    }


def _json_for_html(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        encoded.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def render_dossier_html(dossier: dict[str, Any]) -> str:
    finding = dossier["finding"]
    source = dossier["source"]
    evidence_html = "".join(
        (
            '<li><a href="'
            + html.escape(item["url"], quote=True)
            + '">'
            + html.escape(item.get("publisher") or item["id"])
            + "</a></li>"
        )
        for item in dossier["evidence"]
    )
    speaker = dossier.get("speaker")
    speaker_html = ""
    if speaker:
        speaker_html = (
            "<p>Speaker: "
            + html.escape(speaker.get("name") or speaker["id"])
            + "</p>"
        )
    return (
        '<!doctype html><html lang="it"><meta charset="utf-8">'
        '<script type="application/ld+json">'
        + _json_for_html(dossier_jsonld(dossier))
        + "</script>"
        "<title>Dichiarazioni Pubbliche — dossier</title><body>"
        "<main><h1>"
        + html.escape(dossier.get("claim") or "Claim")
        + "</h1>"
        + speaker_html
        + "<p>Assessment: "
        + html.escape(finding.get("assessment") or "")
        + "</p><p>"
        + html.escape(finding.get("rationale") or "")
        + '</p><p>Fonte: <a href="'
        + html.escape(source["url"], quote=True)
        + '">'
        + html.escape(source.get("title") or source["content_id"])
        + "</a></p><h2>Evidence</h2><ul>"
        + evidence_html
        + "</ul></main></body></html>"
    )


def write_public_bundle(output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    claims_dir = output_dir / "claims"
    desired_claim_files: set[str] = set()
    for dossier in payload.get("dossiers") or []:
        name = _dossier_filename(str(dossier["finding_id"]))
        desired_claim_files.update(
            {f"{name}.json", f"{name}.html", f"{name}.jsonld"}
        )

    # The public directory is a projection, not an append-only artifact store.
    # Remove stale projection-owned claim files before writing the next bundle.
    # Under-publication after a crash is safer than leaving an old dossier
    # publicly reachable after its current row stops satisfying the gates.
    if claims_dir.is_dir():
        for path in claims_dir.iterdir():
            if (
                path.is_file()
                and path.suffix in {".json", ".html", ".jsonld"}
                and path.name not in desired_claim_files
            ):
                path.unlink()

    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    _atomic_write(output_dir / "index.json", encoded)
    _atomic_write(
        output_dir / "index.jsonld",
        (
            json.dumps(
                projection_jsonld(payload),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode(),
    )
    for dossier in payload.get("dossiers") or []:
        # A claim may have multiple published finding versions. Filenames must
        # therefore be finding-versioned or a correction would overwrite the
        # historical dossier for the same claim.
        name = _dossier_filename(str(dossier["finding_id"]))
        _atomic_write(
            output_dir / "claims" / f"{name}.json",
            (
                json.dumps(dossier, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode(),
        )
        _atomic_write(
            output_dir / "claims" / f"{name}.html",
            render_dossier_html(dossier).encode(),
        )
        _atomic_write(
            output_dir / "claims" / f"{name}.jsonld",
            (
                json.dumps(
                    dossier_jsonld(dossier),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode(),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fail-closed public read projection.")
    parser.add_argument("--database-url", default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_public_projection(PublicProjectionStore(args.database_url))
    write_public_bundle(args.output, payload)
    print(
        json.dumps(
            {
                "schema_version": payload["schema_version"],
                "dossier_count": payload["dossier_count"],
                "omitted_count": payload["omitted_count"],
                "dataset_sha256": payload["dataset_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
