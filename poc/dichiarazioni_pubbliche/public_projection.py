from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.citation_assurance import assertion_text_sha256
from dichiarazioni_pubbliche.domain_vocabulary import (
    ClaimType,
    FindingPublicationStatus,
    RelationCandidateType,
    VerificationAssessment,
)
from dichiarazioni_pubbliche.knowledge_repository import (
    EntityIdentifierRecord,
    EntityResolutionCandidateRecord,
)
from dichiarazioni_pubbliche.public_attribution import (
    RoleInterval,
    evaluate_public_attribution,
)
from dichiarazioni_pubbliche.public_internal_guard import forbidden_public_internal_paths
from dichiarazioni_pubbliche.production_projection_revalidation import (
    ProductionProjectionRevalidator,
)
from dichiarazioni_pubbliche.provenance_quarantine import (
    BoundedDependencyGraph,
    InMemoryProvenanceHoldRegistry,
)
from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_FINDING_STATUSES,
    PUBLIC_SCHEMA_VERSION,
    projection_dataset_sha256,
    validate_content,
    validate_dossier,
    validate_public_bundle,
    validate_topic,
)
from dichiarazioni_pubbliche.linked_data import (
    projection_linked_data_receipt,
    projection_ntriples,
    public_resource_uri,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.speaker_runtime import SpeakerIdentityCandidate
from dichiarazioni_pubbliche.text_provenance import (
    ALLOWED_ATTRIBUTION_METHODS as TEXT_ATTRIBUTION_METHODS,
    ALLOWED_SELECTOR_TYPES as TEXT_SELECTOR_TYPES,
    TEXT_PROVENANCE_VERSION,
)
from dichiarazioni_pubbliche.wording_contract import (
    DERIVED_REPRESENTATION_ROLE,
    SOURCE_OCCURRENCE_ROLE,
    validate_wording_contract_metadata,
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
                    (
                        SELECT assertion.assertion_text_sha256
                        FROM finding_assertion assertion
                        WHERE
                            assertion.finding_id = finding.id
                            AND assertion.material = true
                            AND assertion.assertion_type = 'RATIONALE_MATERIAL'
                            AND assertion.required_relation = 'SUPPORT'
                            AND assertion.assertion_text = finding.rationale
                        ORDER BY assertion.created_at DESC, assertion.id DESC
                        LIMIT 1
                    ) AS finding_assertion_sha256,
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
                    claim.metadata->'wording' AS wording,
                    claim.metadata#>>'{context_integrity,quote_sha256}'
                        AS source_occurrence_quote_sha256,
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
                    json_build_object(
                        'speaker_candidates', COALESCE((
                            SELECT json_agg(json_build_object(
                                'id', candidate.id,
                                'content_id', candidate.content_id,
                                'person_id', candidate.person_id,
                                'start_ms', candidate.start_ms,
                                'end_ms', candidate.end_ms,
                                'speaker_label', candidate.speaker_label,
                                'attribution_method', candidate.attribution_method,
                                'attribution_version', candidate.attribution_version,
                                'source_ref', candidate.source_ref,
                                'confidence', candidate.confidence,
                                'status', candidate.status,
                                'review_event_ids', COALESCE((
                                    SELECT json_agg(review.id ORDER BY review.id)
                                    FROM review_event review
                                    WHERE
                                        review.entity_type =
                                            'SPEAKER_IDENTITY_CANDIDATE'
                                        AND review.entity_id = candidate.id
                                        AND review.action = 'APPROVED'
                                ), '[]'::json)
                            ) ORDER BY candidate.id)
                            FROM speaker_identity_candidate candidate
                            WHERE
                                candidate.content_id = content.id
                                AND candidate.person_id = claim.speaker_person_id
                                AND candidate.status = 'APPROVED'
                                AND EXISTS (
                                    SELECT 1
                                    FROM review_event candidate_review
                                    WHERE
                                        candidate_review.entity_type =
                                            'SPEAKER_IDENTITY_CANDIDATE'
                                        AND candidate_review.entity_id = candidate.id
                                        AND candidate_review.action = 'APPROVED'
                                )
                        ), '[]'::json),
                        'resolution_candidates', COALESCE((
                            SELECT json_agg(json_build_object(
                                'id', resolution.id,
                                'content_id', resolution.content_id,
                                'passage_id', resolution.passage_id,
                                'mention_text', resolution.mention_text,
                                'mention_text_sha256', resolution.mention_text_sha256,
                                'entity_type', resolution.entity_type,
                                'target_id', resolution.target_person_id,
                                'resolution_method', resolution.resolution_method,
                                'resolution_version', resolution.resolution_version,
                                'supporting_features', resolution.supporting_features,
                                'contradicting_features',
                                    resolution.contradicting_features,
                                'retrieval_score', resolution.retrieval_score,
                                'status', resolution.status,
                                'review_event_ids', COALESCE((
                                    SELECT json_agg(review.id ORDER BY review.id)
                                    FROM review_event review
                                    WHERE
                                        review.entity_type =
                                            'ENTITY_RESOLUTION_CANDIDATE'
                                        AND review.entity_id = resolution.id
                                        AND review.action = 'APPROVED'
                                ), '[]'::json)
                            ) ORDER BY resolution.id)
                            FROM entity_resolution_candidate resolution
                            WHERE
                                resolution.content_id = content.id
                                AND resolution.entity_type = 'PERSON'
                                AND resolution.status = 'APPROVED'
                                AND EXISTS (
                                    SELECT 1
                                    FROM review_event resolution_review
                                    WHERE
                                        resolution_review.entity_type =
                                            'ENTITY_RESOLUTION_CANDIDATE'
                                        AND resolution_review.entity_id = resolution.id
                                        AND resolution_review.action = 'APPROVED'
                                )
                                AND EXISTS (
                                    SELECT 1
                                    FROM entity_resolution_candidate selected_resolution
                                    WHERE
                                        selected_resolution.content_id = content.id
                                        AND selected_resolution.entity_type = 'PERSON'
                                        AND selected_resolution.target_person_id =
                                            claim.speaker_person_id
                                        AND selected_resolution.status = 'APPROVED'
                                        AND selected_resolution.passage_id IS NOT DISTINCT
                                            FROM resolution.passage_id
                                        AND selected_resolution.mention_text_sha256 =
                                            resolution.mention_text_sha256
                                        AND EXISTS (
                                            SELECT 1
                                            FROM review_event selected_review
                                            WHERE
                                                selected_review.entity_type =
                                                    'ENTITY_RESOLUTION_CANDIDATE'
                                                AND selected_review.entity_id =
                                                    selected_resolution.id
                                                AND selected_review.action = 'APPROVED'
                                        )
                                )
                        ), '[]'::json),
                        'identifiers', COALESCE((
                            SELECT json_agg(json_build_object(
                                'id', identifier.id,
                                'entity_type', identifier.entity_type,
                                'entity_id', identifier.person_id,
                                'identifier_kind', identifier.identifier_kind,
                                'identifier_value', identifier.identifier_value,
                                'authority', identifier.authority,
                                'identifier_version', identifier.identifier_version,
                                'source_ref', identifier.source_ref,
                                'status', identifier.status,
                                'supersedes_id', identifier.supersedes_id
                            ) ORDER BY identifier.id)
                            FROM entity_identifier identifier
                            WHERE
                                identifier.entity_type = 'PERSON'
                                AND identifier.person_id = claim.speaker_person_id
                        ), '[]'::json),
                        'role_intervals', COALESCE((
                            SELECT json_agg(json_build_object(
                                'id', role.id,
                                'person_id', role.person_id,
                                'organization_id', role.organization_id,
                                'organization_name', organization.canonical_name,
                                'role', role.role,
                                'start_date', role.start_date::text,
                                'end_date', role.end_date::text,
                                'source_ref', role.source_ref,
                                'status', role.status,
                                'review_event_ids', COALESCE((
                                    SELECT json_agg(review.id ORDER BY review.id)
                                    FROM review_event review
                                    WHERE
                                        review.entity_type =
                                            'PERSON_ROLE_INTERVAL'
                                        AND review.entity_id = role.id
                                        AND review.action = 'APPROVED'
                                ), '[]'::json)
                            ) ORDER BY role.start_date, role.id)
                            FROM person_role_interval role
                            JOIN organization
                              ON organization.id = role.organization_id
                            WHERE
                                role.person_id = claim.speaker_person_id
                                AND role.is_public_role = true
                        ), '[]'::json)
                    ) AS public_attribution_input,
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
                            AND speaker_candidate.attribution_method IN (
                                'MANUAL_REVIEW',
                                'TRANSCRIPT_LABEL',
                                'OFFICIAL_RECORD'
                            )
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
                                    AND upper(candidate_variant.source_kind) IN (
                                        'OFFICIAL_TRANSCRIPT',
                                        'HUMAN_AUDIO_VERIFIED'
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
                            AND NOT CASE
                                WHEN jsonb_typeof(
                                    claim.metadata#>'{context_integrity,quote_start}'
                                ) = 'number'
                                AND jsonb_typeof(
                                    claim.metadata#>'{context_integrity,quote_end}'
                                ) = 'number'
                                AND (
                                    claim.metadata#>>'{context_integrity,quote_start}'
                                )::numeric >= 0
                                AND (
                                    claim.metadata#>>'{context_integrity,quote_start}'
                                )::numeric = trunc((
                                    claim.metadata#>>'{context_integrity,quote_start}'
                                )::numeric)
                                AND (
                                    claim.metadata#>>'{context_integrity,quote_end}'
                                )::numeric = trunc((
                                    claim.metadata#>>'{context_integrity,quote_end}'
                                )::numeric)
                                AND (
                                    claim.metadata#>>'{context_integrity,quote_end}'
                                )::numeric > (
                                    claim.metadata#>>'{context_integrity,quote_start}'
                                )::numeric
                                AND (
                                    claim.metadata#>>'{context_integrity,quote_end}'
                                )::numeric <= char_length(segment.canonical_text)
                                AND (
                                    claim.metadata#>>'{context_integrity,quote_sha256}'
                                ) ~ '^[0-9a-f]{64}$'
                                THEN encode(
                                    sha256(convert_to(substring(
                                        segment.canonical_text
                                        FROM ((
                                            claim.metadata#>>
                                                '{context_integrity,quote_start}'
                                        )::numeric + 1)::integer
                                        FOR ((
                                            claim.metadata#>>
                                                '{context_integrity,quote_end}'
                                        )::numeric - (
                                            claim.metadata#>>
                                                '{context_integrity,quote_start}'
                                        )::numeric)::integer
                                    ), 'UTF8')),
                                    'hex'
                                ) = claim.metadata#>>
                                    '{context_integrity,quote_sha256}'
                                ELSE false
                            END
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
                    AND EXISTS (
                        SELECT 1
                        FROM finding_assertion assertion
                        WHERE
                            assertion.finding_id = finding.id
                            AND assertion.material = true
                            AND assertion.assertion_type = 'RATIONALE_MATERIAL'
                            AND assertion.required_relation = 'SUPPORT'
                            AND assertion.assertion_text = finding.rationale
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM finding_assertion assertion
                        WHERE
                            assertion.finding_id = finding.id
                            AND assertion.material = true
                            AND NOT EXISTS (
                                SELECT 1
                                FROM finding_assertion_citation citation
                                JOIN finding_evidence source_link
                                  ON source_link.finding_id = finding.id
                                 AND source_link.evidence_id = citation.evidence_id
                                WHERE
                                    citation.assertion_id = assertion.id
                                    AND citation.relation =
                                        assertion.required_relation
                                    AND (
                                        EXISTS (
                                            SELECT 1
                                            FROM evidence_observation observation
                                            WHERE
                                                observation.id = citation.observation_id
                                                AND observation.evidence_id =
                                                    citation.evidence_id
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
                                        OR finding_assertion_passage_binding_valid(
                                            citation.id
                                        )
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
                            AND NOT (
                                EXISTS (
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
                                OR EXISTS (
                                    SELECT 1
                                    FROM finding_assertion assertion
                                    JOIN finding_assertion_citation citation
                                      ON citation.assertion_id = assertion.id
                                     AND citation.evidence_id =
                                         source_link.evidence_id
                                    WHERE
                                        assertion.finding_id = finding.id
                                        AND assertion.material = true
                                        AND citation.relation =
                                            assertion.required_relation
                                        AND finding_assertion_passage_binding_valid(
                                            citation.id
                                        )
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
                    AND claim.metadata->>'speech_mode' = 'DIRECT_UTTERANCE'
                    AND claim.metadata#>>'{context_integrity,state}' IN (
                        'CLEAR_AUTOMATIC',
                        'APPROVED_CURATED'
                    )
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
                                            AND speaker_candidate.attribution_method IN (
                                                'MANUAL_REVIEW',
                                                'TRANSCRIPT_LABEL',
                                                'OFFICIAL_RECORD'
                                            )
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


    def projectable_topics(self) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(row_data ORDER BY canonical_name, topic_id)::text, '[]')
            FROM (
                SELECT
                    topic.id AS topic_id,
                    topic.slug,
                    topic.canonical_name,
                    topic.scope_text,
                    topic.entity_version,
                    COALESCE((
                        SELECT json_agg(review.id ORDER BY review.created_at, review.id)
                        FROM review_event review
                        WHERE review.entity_type = 'TOPIC'
                          AND review.entity_id = topic.id
                          AND review.action = 'APPROVED'
                    ), '[]'::json) AS review_event_ids,
                    COALESCE((
                        SELECT json_agg(json_build_object(
                            'membership_id', membership.id,
                            'claim_id', membership.claim_id,
                            'source_resolution_candidate_id',
                                membership.source_resolution_candidate_id,
                            'review_event_ids', COALESCE((
                                SELECT json_agg(review.id ORDER BY review.created_at, review.id)
                                FROM review_event review
                                WHERE review.entity_type = 'CLAIM_TOPIC_MEMBERSHIP'
                                  AND review.entity_id = membership.id
                                  AND review.action = 'APPROVED'
                            ), '[]'::json)
                        ) ORDER BY membership.created_at, membership.id)
                        FROM claim_topic_membership membership
                        WHERE membership.topic_id = topic.id
                          AND membership.status = 'APPROVED'
                          AND (
                              SELECT review.action
                              FROM review_event review
                              WHERE review.entity_type = 'CLAIM_TOPIC_MEMBERSHIP'
                                AND review.entity_id = membership.id
                              ORDER BY review.created_at DESC, review.id DESC
                              LIMIT 1
                          ) = 'APPROVED'
                    ), '[]'::json) AS memberships
                FROM topic
                WHERE topic.status = 'ACTIVE'
                  AND (
                      SELECT review.action
                      FROM review_event review
                      WHERE review.entity_type = 'TOPIC'
                        AND review.entity_id = topic.id
                      ORDER BY review.created_at DESC, review.id DESC
                      LIMIT 1
                  ) = 'APPROVED'
            ) row_data;
            """
        )
        return json.loads(raw or "[]")

    def projectable_contents(self) -> list[dict[str, Any]]:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(row_data ORDER BY title, content_id)::text, '[]')
            FROM (
                SELECT
                    candidate.content_id,
                    candidate.slug,
                    candidate.canonical_url AS url,
                    candidate.title,
                    candidate.published_at,
                    candidate.content_kind,
                    candidate.duration_ms,
                    candidate.public_media_url,
                    candidate.media_policy_version,
                    candidate.publication_version,
                    COALESCE((
                        SELECT json_agg(review.id ORDER BY review.created_at, review.id)
                        FROM review_event review
                        WHERE review.entity_type = 'CONTENT_PUBLICATION_CANDIDATE'
                          AND review.entity_id = candidate.id
                          AND review.action = 'APPROVED'
                    ), '[]'::json) AS review_event_ids
                FROM content_publication_candidate candidate
                WHERE candidate.status = 'APPROVED'
                  AND (
                      SELECT review.action
                      FROM review_event review
                      WHERE review.entity_type = 'CONTENT_PUBLICATION_CANDIDATE'
                        AND review.entity_id = candidate.id
                      ORDER BY review.created_at DESC, review.id DESC
                      LIMIT 1
                  ) = 'APPROVED'
            ) row_data;
            """
        )
        return json.loads(raw or "[]")


class ProductionPublicProjectionStore(PublicProjectionStore):
    """Candidate reader plus mandatory DP-308/309/310 production revalidation."""

    def __init__(
        self,
        database_url: str | None = None,
        psql: str = "psql",
        *,
        reviewer_authority_root: str | Path | None = None,
        local_hold_registry: InMemoryProvenanceHoldRegistry | None = None,
        local_hold_graph: BoundedDependencyGraph | None = None,
    ) -> None:
        super().__init__(database_url, psql)
        self._publication_revalidator = ProductionProjectionRevalidator(
            database_url,
            reviewer_authority_root=reviewer_authority_root,
            local_hold_registry=local_hold_registry,
            local_hold_graph=local_hold_graph,
            psql=psql,
        )

    def revalidate_publication_candidate(
        self,
        row: dict[str, Any],
        dossier: dict[str, Any],
    ) -> bool:
        return self._publication_revalidator.revalidate(row=row, dossier=dossier)


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


def _bounded_ids(
    value: object,
    *,
    limit: int = 128,
    allow_empty: bool = False,
) -> list[str]:
    if (
        not isinstance(value, list)
        or (not value and not allow_empty)
        or len(value) > limit
    ):
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


def _iso_date(value: object, *, field: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required for public attribution")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} is invalid for public attribution") from exc


def _timed_public_attribution(
    row: dict[str, Any],
    *,
    speaker: dict[str, Any],
    segments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Apply public-attribution-v1 to timed speaker occurrences.

    ``public_attribution_input`` is deliberately an internal projection row field. It may
    contain private resolution features, scores, aliases and source references needed by
    the decision, but this function returns only the approved speaker provenance plus the
    single role interval (if any) that is valid at statement time.
    """

    raw = row.get("public_attribution_input")
    if not isinstance(raw, dict):
        raise ValueError("public attribution input is missing")
    person_id = str(speaker.get("id") or "").strip()
    content_id = str(row.get("content_id") or "").strip()
    if not person_id or not content_id:
        raise ValueError("public attribution identity is incomplete")
    temporal_scope = row.get("temporal_scope")
    if not isinstance(temporal_scope, dict):
        raise ValueError("public attribution temporal scope is missing")
    statement_date = _iso_date(
        temporal_scope.get("statement_date"),
        field="statement_date",
    )

    speaker_candidates: list[SpeakerIdentityCandidate] = []
    candidate_reviews: dict[str, list[str]] = {}
    for item in raw.get("speaker_candidates") or []:
        if not isinstance(item, dict) or item.get("status") != "APPROVED":
            continue
        review_ids = _bounded_ids(item.get("review_event_ids"))
        candidate = SpeakerIdentityCandidate(
            candidate_id=str(item["id"]),
            content_id=str(item["content_id"]),
            person_id=str(item["person_id"]),
            start_ms=int(item["start_ms"]),
            end_ms=int(item["end_ms"]),
            attribution_method=str(item["attribution_method"]),
            attribution_version=str(item["attribution_version"]),
            speaker_label=_bounded(item.get("speaker_label"), 300),
            source_ref=dict(item.get("source_ref") or {}),
            confidence=(
                None
                if item.get("confidence") is None
                else float(item["confidence"])
            ),
        )
        speaker_candidates.append(candidate)
        candidate_reviews[candidate.candidate_id] = review_ids

    resolution_candidates: list[EntityResolutionCandidateRecord] = []
    for item in raw.get("resolution_candidates") or []:
        if not isinstance(item, dict) or item.get("status") != "APPROVED":
            continue
        _bounded_ids(item.get("review_event_ids"))
        supporting = item.get("supporting_features") or []
        contradicting = item.get("contradicting_features") or []
        if not isinstance(supporting, list) or not isinstance(contradicting, list):
            raise ValueError("public attribution resolution features are invalid")
        resolution_candidates.append(
            EntityResolutionCandidateRecord(
                id=str(item["id"]),
                content_id=str(item["content_id"]),
                passage_id=_bounded(item.get("passage_id"), 512),
                mention_text=str(item["mention_text"]),
                mention_text_sha256=str(item["mention_text_sha256"]),
                entity_type=str(item["entity_type"]),
                target_id=str(item["target_id"]),
                resolution_method=str(item["resolution_method"]),
                supporting_features=tuple(dict(value) for value in supporting),
                contradicting_features=tuple(dict(value) for value in contradicting),
                retrieval_score=(
                    None
                    if item.get("retrieval_score") is None
                    else float(item["retrieval_score"])
                ),
                resolution_version=str(item["resolution_version"]),
                status=str(item["status"]),
            )
        )

    identifiers: list[EntityIdentifierRecord] = []
    for item in raw.get("identifiers") or []:
        if not isinstance(item, dict):
            raise ValueError("public attribution identifier is invalid")
        identifiers.append(
            EntityIdentifierRecord(
                id=str(item["id"]),
                entity_type=str(item["entity_type"]),
                entity_id=str(item["entity_id"]),
                identifier_kind=str(item["identifier_kind"]),
                identifier_value=str(item["identifier_value"]),
                authority=str(item["authority"]),
                source_ref=dict(item.get("source_ref") or {}),
                identifier_version=str(item["identifier_version"]),
                status=str(item["status"]),
                supersedes_id=_bounded(item.get("supersedes_id"), 512),
            )
        )

    role_intervals: list[RoleInterval] = []
    role_public: dict[str, dict[str, Any]] = {}
    for item in raw.get("role_intervals") or []:
        if not isinstance(item, dict):
            raise ValueError("public attribution role interval is invalid")
        try:
            review_ids = _bounded_ids(item.get("review_event_ids"))
        except ValueError:
            review_ids = []
        interval_id = str(item["id"])
        interval = RoleInterval(
            interval_id=interval_id,
            person_id=str(item["person_id"]),
            organization_id=str(item["organization_id"]),
            role=str(item["role"]),
            start_date=_iso_date(item.get("start_date"), field="role.start_date"),
            end_date=(
                None
                if not item.get("end_date")
                else _iso_date(item.get("end_date"), field="role.end_date")
            ),
            status=str(item.get("status") or ""),
            review_event_ids=tuple(review_ids),
            source_ref=dict(item.get("source_ref") or {}),
        )
        role_intervals.append(interval)
        role_public[interval_id] = {
            "organization_id": interval.organization_id,
            "organization_name": _bounded(item.get("organization_name"), 300),
            "role": interval.role,
            "start_date": interval.start_date.isoformat(),
            "end_date": None if interval.end_date is None else interval.end_date.isoformat(),
            "review_event_ids": review_ids,
        }

    selected_candidate_ids: set[str] = set()
    selected_role_id: str | None = None
    role_decision_seen = False
    for segment in segments:
        start_ms = int(segment["start_ms"])
        end_ms = int(segment["end_ms"])
        decisions = []
        for candidate in sorted(
            speaker_candidates,
            key=lambda value: value.candidate_id,
        ):
            if candidate.start_ms > start_ms or candidate.end_ms < end_ms:
                continue
            decision = evaluate_public_attribution(
                person_id=person_id,
                content_id=content_id,
                occurrence_start_ms=start_ms,
                occurrence_end_ms=end_ms,
                statement_date=statement_date,
                speaker_candidate=candidate,
                resolution_candidates=resolution_candidates,
                identifiers=identifiers,
                role_intervals=role_intervals,
            )
            if decision.publication_allowed:
                decisions.append((candidate, decision))
        if not decisions:
            raise ValueError("public attribution gate rejected timed speaker occurrence")
        candidate, decision = decisions[0]
        if decision.person_id != person_id:
            raise ValueError("public attribution gate returned a mismatched person")
        selected_candidate_ids.add(candidate.candidate_id)
        if not role_decision_seen:
            selected_role_id = decision.role_interval_id
            role_decision_seen = True
        elif selected_role_id != decision.role_interval_id:
            raise ValueError("public attribution role decision is inconsistent")

    provenance = [
        {
            "candidate_id": candidate_id,
            "review_event_ids": list(candidate_reviews[candidate_id]),
            "provenance_kind": "TIMED_SPEAKER",
        }
        for candidate_id in sorted(selected_candidate_ids)
    ]
    raw_provenance: dict[str, list[str]] = {}
    for item in row.get("speaker_provenance") or []:
        if not isinstance(item, dict):
            raise ValueError("invalid speaker provenance")
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not candidate_id:
            raise ValueError("speaker provenance candidate is missing")
        raw_provenance[candidate_id] = _bounded_ids(item.get("review_event_ids"))
    for candidate_id in selected_candidate_ids:
        if raw_provenance.get(candidate_id) != candidate_reviews[candidate_id]:
            raise ValueError("public attribution speaker provenance mismatch")

    selected_role = None
    if selected_role_id is not None:
        selected_role = role_public.get(selected_role_id)
        if selected_role is None or not selected_role["review_event_ids"]:
            raise ValueError("public attribution approved role is missing")
        role_confirmed = False
        for raw_role in speaker.get("public_roles") or []:
            if not isinstance(raw_role, dict):
                continue
            try:
                raw_review_ids = _bounded_ids(raw_role.get("review_event_ids"))
            except ValueError:
                continue
            if (
                _bounded(raw_role.get("organization_id"), 300)
                == selected_role["organization_id"]
                and _bounded(raw_role.get("role"), 300) == selected_role["role"]
                and _bounded(raw_role.get("start_date"), 64)
                == selected_role["start_date"]
                and _bounded(raw_role.get("end_date"), 64)
                == selected_role["end_date"]
                and raw_review_ids == selected_role["review_event_ids"]
            ):
                role_confirmed = True
                break
        if not role_confirmed:
            selected_role = None
    return provenance, selected_role


def _sanitize_public_wording(
    raw: object,
    *,
    normalized_claim: str,
    source_occurrence_quote_sha256: object,
    segments: list[dict[str, Any]],
    text_provenance: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        clean = validate_wording_contract_metadata(raw)
    except ValueError as exc:
        raise ValueError("public wording contract is invalid") from exc

    source = clean["source_occurrence"]
    normalized = clean["normalized_claim"]
    source_hash = _sha256_hex(source.get("text_sha256"))
    quote_hash = _sha256_hex(source_occurrence_quote_sha256)
    if source_hash != quote_hash:
        raise ValueError("public source occurrence hash mismatch")
    normalized_hash = hashlib.sha256(
        str(normalized_claim).encode("utf-8")
    ).hexdigest()
    if _sha256_hex(normalized.get("text_sha256")) != normalized_hash:
        raise ValueError("public normalized claim wording hash mismatch")
    # DP-305's current public profile is metadata-only: it grants no source/derived
    # excerpt authority. A value labelled PARAPHRASE must therefore not be an exact
    # byte-for-byte copy of the private source occurrence body.  Hash comparison lets
    # the projection enforce that boundary without loading the protected body itself.
    if normalized_hash == source_hash:
        raise ValueError(
            "public normalized claim duplicates private source wording body"
        )

    source_type = str(source.get("wording_type") or "")
    source_direct = source.get("direct_quote_eligible") is True
    if source_type == "VERBATIM_ORIGINAL":
        if not source_direct:
            raise ValueError("verbatim source occurrence lost direct-quote authority")
    elif source_type == "REPORTED_QUOTE":
        if source_direct:
            raise ValueError("reported quote cannot carry direct-quote authority")
    else:
        raise ValueError("public source wording type is invalid")
    if str(source.get("representation_role") or "") != SOURCE_OCCURRENCE_ROLE:
        raise ValueError("public source wording role is invalid")
    if str(normalized.get("wording_type") or "") != "PARAPHRASE":
        raise ValueError("public normalized claim must be a paraphrase")
    if normalized.get("direct_quote_eligible") is not False:
        raise ValueError("public normalized claim cannot carry direct-quote authority")
    if str(normalized.get("representation_role") or "") != DERIVED_REPRESENTATION_ROLE:
        raise ValueError("public normalized claim wording role is invalid")
    if str(normalized.get("source_wording_type") or "") != source_type:
        raise ValueError("public normalized claim source wording type mismatch")

    occurrence_id = _bounded(source.get("occurrence_id"), 300)
    if not occurrence_id:
        raise ValueError("public source occurrence id is missing")
    source_language = _bounded(source.get("language"), 35)

    representations: list[dict[str, Any]] = []
    raw_representations = clean.get("representations") or []
    if not isinstance(raw_representations, list) or len(raw_representations) > 16:
        raise ValueError("public wording representation list is invalid")
    for representation in raw_representations:
        if not isinstance(representation, dict):
            raise ValueError("public wording representation is invalid")
        wording_type = str(representation.get("wording_type") or "")
        if wording_type not in {"PARAPHRASE", "SUMMARY", "TRANSLATION"}:
            raise ValueError("public derived wording type is invalid")
        if representation.get("direct_quote_eligible") is not False:
            raise ValueError("public derived wording cannot carry direct-quote authority")
        if (
            str(representation.get("representation_role") or "")
            != DERIVED_REPRESENTATION_ROLE
        ):
            raise ValueError("public derived wording role is invalid")
        if str(representation.get("source_wording_type") or "") != source_type:
            raise ValueError("public derived wording source type mismatch")
        source_occurrence_id = _bounded(representation.get("occurrence_id"), 300)
        if source_occurrence_id != occurrence_id:
            raise ValueError("public derived wording occurrence mismatch")
        signal_codes = representation.get("signal_codes") or []
        if not isinstance(signal_codes, list) or len(signal_codes) > 32:
            raise ValueError("public wording signal codes are invalid")
        representation_hash = _sha256_hex(representation.get("text_sha256"))
        # SUMMARY/TRANSLATION/PARAPHRASE representation bodies stay private under the
        # current DP-305 no-body profile.  Do not let the public normalized claim become
        # a covert copy of one of those bodies merely because it is labelled PARAPHRASE.
        if representation_hash == normalized_hash:
            raise ValueError(
                "public normalized claim duplicates private derived wording body"
            )
        public_representation = {
            "wording_type": wording_type,
            "text_sha256": representation_hash,
            "source_occurrence_id": occurrence_id,
            "source_wording_type": source_type,
            "language": _bounded(representation.get("language"), 35),
            "source_language": _bounded(
                representation.get("source_language"), 35
            ),
            "derivation_method": _bounded(
                representation.get("derivation_method"), 200
            ),
            "derivation_version": _bounded(
                representation.get("derivation_version"), 200
            ),
            "review_state": _bounded(representation.get("review_state"), 100),
            "signal_codes": [
                code
                for raw_code in signal_codes
                if (code := _bounded(raw_code, 200)) is not None
            ],
            "direct_quote_eligible": False,
            "representation_role": DERIVED_REPRESENTATION_ROLE,
        }
        if wording_type == "TRANSLATION":
            if not public_representation["source_language"]:
                raise ValueError("public translation source language is missing")
            if not public_representation["language"]:
                raise ValueError("public translation target language is missing")
            if public_representation["source_language"] != source_language:
                raise ValueError("public translation source language mismatch")
            if public_representation["review_state"] not in {
                "NEEDS_REVIEW",
                "HUMAN_REVIEWED",
                "REJECTED",
            }:
                raise ValueError("public translation review state is invalid")
        representations.append(public_representation)

    return {
        "version": "wording-contract-v1",
        "source_occurrence": {
            "occurrence_id": occurrence_id,
            "wording_type": source_type,
            "text_sha256": source_hash,
            "language": source_language,
            "direct_quote_eligible": source_direct,
            "representation_role": SOURCE_OCCURRENCE_ROLE,
        },
        "normalized_claim": {
            "wording_type": "PARAPHRASE",
            "text_sha256": _sha256_hex(normalized.get("text_sha256")),
            "source_occurrence_id": occurrence_id,
            "source_wording_type": source_type,
            "language": _bounded(normalized.get("language"), 35),
            "derivation_method": _bounded(normalized.get("derivation_method"), 200),
            "derivation_version": _bounded(normalized.get("derivation_version"), 200),
            "direct_quote_eligible": False,
            "representation_role": DERIVED_REPRESENTATION_ROLE,
        },
        "representations": representations,
        "public_provenance": {
            "segment_ids": [str(item["segment_id"]) for item in segments],
            "text_provenance_ids": [str(item["id"]) for item in text_provenance],
        },
    }


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
    rationale = str(row.get("rationale") or "").strip()
    if not rationale:
        raise ValueError("public finding rationale is missing")
    assertion_sha = _sha256_hex(row.get("finding_assertion_sha256"))
    if assertion_sha != assertion_text_sha256(rationale):
        raise ValueError("public finding rationale assertion hash mismatch")
    source_url = _safe_http_url(str(row.get("source_url") or ""))
    evidence_rows = []
    for item in row.get("evidence") or []:
        if not isinstance(item, dict):
            raise ValueError("invalid evidence row")
        observation_ids = _bounded_ids(
            item.get("verification_observation_ids"),
            allow_empty=True,
        )
        evidence_review_ids = _bounded_ids(item.get("evidence_review_ids"))
        observation_review_ids = _bounded_ids(
            item.get("observation_review_ids"),
            allow_empty=True,
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
    timed_role = None
    if segments:
        provenance, timed_role = _timed_public_attribution(
            row,
            speaker=speaker,
            segments=segments,
        )
    else:
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
    if segments:
        public_roles = [] if timed_role is None else [timed_role]
    else:
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
        if forbidden_public_internal_paths(changed_fields):
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
    normalized_claim = _bounded(row.get("normalized_claim"), 4000)
    if not normalized_claim:
        raise ValueError("public normalized claim is missing")
    wording = _sanitize_public_wording(
        row.get("wording"),
        normalized_claim=normalized_claim,
        source_occurrence_quote_sha256=row.get("source_occurrence_quote_sha256"),
        segments=segments,
        text_provenance=text_provenance,
    )
    dossier = {
        "finding_id": str(row["finding_id"]),
        "claim_id": str(row["claim_id"]),
        "claim": normalized_claim,
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
            "rationale": _bounded(rationale, 8000),
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
        "wording": wording,
    }
    if source_methodology is not None:
        dossier["source_methodology"] = source_methodology
    return validate_dossier(dossier)


_PUBLIC_TOPIC_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _sanitize_topic_row(
    row: dict[str, Any],
    public_findings_by_claim: dict[str, list[str]],
) -> dict[str, Any]:
    topic_id = _bounded(row.get("topic_id"), 300)
    slug = _bounded(row.get("slug"), 200)
    canonical_name = _bounded(row.get("canonical_name"), 500)
    scope_text = _bounded(row.get("scope_text"), 4000)
    entity_version = _bounded(row.get("entity_version"), 200)
    if not topic_id or not slug or not canonical_name or not entity_version:
        raise ValueError("public topic identity is incomplete")
    if not _PUBLIC_TOPIC_SLUG_RE.fullmatch(slug):
        raise ValueError("public topic slug is not canonical")
    if entity_version != "knowledge-entity-v1":
        raise ValueError("public topic entity version is unsupported")

    topic_review_ids = _bounded_ids(row.get("review_event_ids"))
    memberships: list[dict[str, Any]] = []
    seen_claims: set[str] = set()
    for membership in row.get("memberships") or []:
        if not isinstance(membership, dict):
            raise ValueError("invalid public topic membership")
        membership_id = _bounded(membership.get("membership_id"), 300)
        claim_id = _bounded(membership.get("claim_id"), 300)
        if not membership_id or not claim_id:
            raise ValueError("public topic membership identity is incomplete")
        if claim_id in seen_claims:
            raise ValueError("duplicate public topic claim membership")
        finding_ids = sorted(public_findings_by_claim.get(claim_id, []))
        if not finding_ids:
            # Membership may be reviewed in the knowledge layer while the claim
            # itself is private/non-projectable. The public projection omits the
            # membership rather than leaking that operational existence.
            continue
        memberships.append(
            {
                "membership_id": membership_id,
                "claim_id": claim_id,
                "finding_ids": finding_ids,
                "review_event_ids": _bounded_ids(membership.get("review_event_ids")),
                "source_resolution_candidate_id": _bounded(
                    membership.get("source_resolution_candidate_id"), 300
                ),
            }
        )
        seen_claims.add(claim_id)

    topic = {
        "topic_id": topic_id,
        "slug": slug,
        "canonical_name": canonical_name,
        "scope_text": scope_text,
        "entity_version": entity_version,
        "review_event_ids": topic_review_ids,
        "memberships": memberships,
    }
    return validate_topic(topic)


def _sanitize_content_row(
    row: dict[str, Any],
    public_findings_by_content: dict[str, list[str]],
) -> dict[str, Any]:
    content_id = str(row.get("content_id") or "").strip()
    slug = str(row.get("slug") or "").strip()
    title = str(row.get("title") or "").strip()
    publication_version = str(row.get("publication_version") or "").strip()
    if not content_id or not slug or not title:
        raise ValueError("public Content identity is incomplete")
    content_kind = str(row.get("content_kind") or "").strip()
    duration_raw = row.get("duration_ms")
    duration_ms = None
    if duration_raw is not None:
        if isinstance(duration_raw, bool):
            raise ValueError("public Content duration is invalid")
        duration_ms = int(duration_raw)
        if duration_ms < 0:
            raise ValueError("public Content duration is invalid")
    media_url = row.get("public_media_url")
    if media_url is not None:
        media_url = _safe_http_url(str(media_url))
    media_policy = _bounded(row.get("media_policy_version"), 200)
    content = {
        "content_id": content_id,
        "slug": slug,
        "url": _safe_http_url(str(row.get("url") or "")),
        "title": title[:500],
        "published_at": _bounded(row.get("published_at"), 64),
        "content_kind": content_kind,
        "duration_ms": duration_ms,
        "public_media_url": media_url,
        "media_policy_version": media_policy,
        "publication_version": publication_version,
        "review_event_ids": _bounded_ids(row.get("review_event_ids")),
        "finding_ids": sorted(public_findings_by_content.get(content_id, [])),
    }
    return validate_content(content)

def build_public_projection(
    source: ProjectionSource,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    dossiers = []
    omitted = 0
    for row in source.projectable_findings():
        try:
            dossier = _sanitize_row(row)
            revalidate = getattr(source, "revalidate_publication_candidate", None)
            if callable(revalidate) and not revalidate(row, dossier):
                omitted += 1
                continue
            dossiers.append(dossier)
        except (KeyError, TypeError, ValueError):
            omitted += 1
    dossiers.sort(key=lambda item: (item["claim_id"], item["finding_id"]))
    public_findings_by_claim: dict[str, list[str]] = {}
    for dossier in dossiers:
        public_findings_by_claim.setdefault(str(dossier["claim_id"]), []).append(
            str(dossier["finding_id"])
        )

    topics: list[dict[str, Any]] = []
    projectable_topics = getattr(source, "projectable_topics", None)
    if callable(projectable_topics):
        for row in projectable_topics():
            try:
                topics.append(_sanitize_topic_row(row, public_findings_by_claim))
            except (KeyError, TypeError, ValueError):
                # Topic publication is independently fail-closed. An invalid
                # public Topic must not make otherwise-valid Statement records
                # unavailable.
                continue
    topics.sort(key=lambda item: (item["canonical_name"].casefold(), item["topic_id"]))
    public_findings_by_content: dict[str, list[str]] = {}
    for dossier in dossiers:
        public_findings_by_content.setdefault(
            str(dossier["source"]["content_id"]), []
        ).append(str(dossier["finding_id"]))

    contents: list[dict[str, Any]] = []
    projectable_contents = getattr(source, "projectable_contents", None)
    if callable(projectable_contents):
        for row in projectable_contents():
            try:
                contents.append(
                    _sanitize_content_row(row, public_findings_by_content)
                )
            except (KeyError, TypeError, ValueError):
                # Content publication is independently fail-closed. Invalid
                # reviewed metadata is omitted without hiding valid findings.
                continue
    contents.sort(key=lambda item: (item["title"].casefold(), item["content_id"]))
    bundle = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "generated_at": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset_sha256": "",
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
        "topics": topics,
        "contents": contents,
    }
    bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
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
        "@id": public_resource_uri("statement", dossier["claim_id"]),
        "text": dossier["claim"],
        "author": {
            "@type": "Person",
            "@id": public_resource_uri("person", speaker["id"]),
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
    wording = dossier.get("wording")
    if isinstance(wording, dict):
        source_wording = wording.get("source_occurrence") or {}
        normalized_wording = wording.get("normalized_claim") or {}
        reviewed_claim["additionalProperty"] = [
            {
                "@type": "PropertyValue",
                "name": "wordingContractVersion",
                "value": wording.get("version"),
            },
            {
                "@type": "PropertyValue",
                "name": "wordingType",
                "value": normalized_wording.get("wording_type"),
            },
            {
                "@type": "PropertyValue",
                "name": "representationRole",
                "value": normalized_wording.get("representation_role"),
            },
            {
                "@type": "PropertyValue",
                "name": "directQuoteEligible",
                "value": normalized_wording.get("direct_quote_eligible"),
            },
            {
                "@type": "PropertyValue",
                "name": "sourceWordingType",
                "value": normalized_wording.get("source_wording_type"),
            },
            {
                "@type": "PropertyValue",
                "name": "sourceOccurrenceId",
                "value": normalized_wording.get("source_occurrence_id"),
            },
        ]
        reviewed_claim["isBasedOn"] = {
            "@type": "CreativeWork",
            "identifier": source_wording.get("occurrence_id"),
            "inLanguage": source_wording.get("language"),
            "additionalProperty": [
                {
                    "@type": "PropertyValue",
                    "name": "wordingType",
                    "value": source_wording.get("wording_type"),
                },
                {
                    "@type": "PropertyValue",
                    "name": "representationRole",
                    "value": source_wording.get("representation_role"),
                },
                {
                    "@type": "PropertyValue",
                    "name": "directQuoteEligible",
                    "value": source_wording.get("direct_quote_eligible"),
                },
                {
                    "@type": "PropertyValue",
                    "name": "textSha256",
                    "value": source_wording.get("text_sha256"),
                },
            ],
        }
        derived_jsonld: list[dict[str, Any]] = []
        for representation in wording.get("representations") or []:
            derived_jsonld.append(
                {
                    "@type": "CreativeWork",
                    "identifier": representation.get("text_sha256"),
                    "inLanguage": representation.get("language"),
                    "additionalProperty": [
                        {
                            "@type": "PropertyValue",
                            "name": "wordingType",
                            "value": representation.get("wording_type"),
                        },
                        {
                            "@type": "PropertyValue",
                            "name": "representationRole",
                            "value": representation.get("representation_role"),
                        },
                        {
                            "@type": "PropertyValue",
                            "name": "directQuoteEligible",
                            "value": representation.get("direct_quote_eligible"),
                        },
                        {
                            "@type": "PropertyValue",
                            "name": "sourceOccurrenceId",
                            "value": representation.get("source_occurrence_id"),
                        },
                        {
                            "@type": "PropertyValue",
                            "name": "sourceWordingType",
                            "value": representation.get("source_wording_type"),
                        },
                        {
                            "@type": "PropertyValue",
                            "name": "sourceLanguage",
                            "value": representation.get("source_language"),
                        },
                        {
                            "@type": "PropertyValue",
                            "name": "reviewState",
                            "value": representation.get("review_state"),
                        },
                    ],
                }
            )
        if derived_jsonld:
            reviewed_claim["subjectOf"] = derived_jsonld
    for role in speaker.get("public_roles") or []:
        if role.get("organization_id") and role.get("role"):
            reviewed_claim["author"].setdefault("worksFor", []).append(
                {
                    "@type": "Organization",
                    "id": public_resource_uri(
                        "organization",
                        role["organization_id"],
                    ),
                    "name": role.get("organization_name") or role["organization_id"],
                }
            )
    return {
        "@context": "https://schema.org",
        "@type": "ClaimReview",
        "@id": public_resource_uri("finding", dossier["finding_id"]),
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
    document = {
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
    topics = payload.get("topics") or []
    if topics:
        document["about"] = [
            {
                "@type": "Thing",
                "identifier": topic["topic_id"],
                "name": topic["canonical_name"],
                "description": topic.get("scope_text"),
                "url": f"/temi/{topic['slug']}/",
            }
            for topic in topics
        ]
    return document


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
    wording = dossier.get("wording")
    wording_attrs = ""
    wording_html = ""
    if isinstance(wording, dict):
        normalized_wording = wording.get("normalized_claim") or {}
        source_wording = wording.get("source_occurrence") or {}
        wording_type = html.escape(
            str(normalized_wording.get("wording_type") or ""), quote=True
        )
        direct_quote = (
            "true"
            if normalized_wording.get("direct_quote_eligible") is True
            else "false"
        )
        source_type = html.escape(
            str(source_wording.get("wording_type") or ""), quote=False
        )
        wording_attrs = (
            f' data-wording-type="{wording_type}"'
            f' data-direct-quote-eligible="{direct_quote}"'
        )
        wording_html = (
            '<p class="wording-meta">Wording: '
            + html.escape(str(normalized_wording.get("wording_type") or ""))
            + "; source occurrence: "
            + source_type
            + "</p>"
        )
    return (
        '<!doctype html><html lang="it"><meta charset="utf-8">'
        '<script type="application/ld+json">'
        + _json_for_html(dossier_jsonld(dossier))
        + "</script>"
        "<title>Dichiarazioni Pubbliche — dossier</title><body>"
        "<main><h1"
        + wording_attrs
        + ">"
        + html.escape(dossier.get("claim") or "Claim")
        + "</h1>"
        + wording_html
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
    _atomic_write(
        output_dir / "index.nt",
        projection_ntriples(payload).encode("utf-8"),
    )
    _atomic_write(
        output_dir / "linked-data-receipt.json",
        (
            json.dumps(
                projection_linked_data_receipt(payload),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
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
    parser.add_argument(
        "--reviewer-authority-root",
        type=Path,
        default=(
            Path(os.environ["DICHIARAZIONI_PUBBLICHE_REVIEWER_AUTHORITY_ROOT"])
            if os.environ.get("DICHIARAZIONI_PUBBLICHE_REVIEWER_AUTHORITY_ROOT")
            else None
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_public_projection(
        ProductionPublicProjectionStore(
            args.database_url,
            reviewer_authority_root=args.reviewer_authority_root,
        )
    )
    write_public_bundle(args.output, payload)
    print(
        json.dumps(
            {
                "schema_version": payload["schema_version"],
                "dossier_count": payload["dossier_count"],
                "omitted_count": payload["omitted_count"],
                "dataset_sha256": payload["dataset_sha256"],
                "linked_data": {
                    "artifact": "index.nt",
                    "receipt": "linked-data-receipt.json",
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
