"""OpenAPI 3.1 description of the DP-402 public read-only API.

The document is generated from the same route table, vocabulary constants, and
projection fixture that the handlers use, so it cannot drift into a second field
vocabulary or a second route contract (DP-403 AC-403.1 / AC-403.8).

The examples are synthetic: every string in this module is either a canonical
domain term, a schema/version identifier, or a fabricated record built from
fictional identifiers. No real person, no real claim, and no real evidence URL is
described here (DP-403 AC-403.6).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dichiarazioni_pubbliche.domain_vocabulary import (
    DOMAIN_VOCABULARY_VERSION,
    VOCABULARIES,
)
from dichiarazioni_pubbliche.public_api import (
    API_BASE_PATH,
    API_CONTRACT_VERSION,
    API_MAJOR_VERSION,
    API_VERSION_HEADER,
    DEFAULT_LIMIT,
    MAX_LIMIT,
    ROUTES,
)
from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_FINDING_STATUSES,
    PUBLIC_SCHEMA_VERSION,
    PUBLISHABLE_ASSESSMENTS,
)

if TYPE_CHECKING:  # pragma: no cover
    from dichiarazioni_pubbliche.public_api import PublicIndex

OPENAPI_VERSION = "3.1.0"

# Fictional identifiers. `example.test` is reserved for documentation and can
# never resolve, so no example can be mistaken for a real source.
FICTIONAL_SOURCE_URL = "https://example.test/fictional-source"
FICTIONAL_EVIDENCE_URL = "https://example.test/fictional-evidence"

DEPRECATION_POLICY = {
    "version_boundary": (
        "The URL major version (/api/v1) is the compatibility boundary. A breaking "
        "change is served under a new major version."
    ),
    "backward_compatible": [
        "adding an optional response field",
        "adding a new endpoint documented in this document",
        "relaxing a documented default limit",
    ],
    "breaking": [
        "renaming a field",
        "changing the meaning or unit of a field",
        "making an optional field required",
        "removing a field",
        "changing identifier semantics",
        "changing an assessment, relation, or publication-status meaning",
    ],
    "enum_values": (
        "New assessment, publication-status, relation, and claim-type values are "
        "owned by the public schema contract, not by this document, and are never "
        "added silently where an existing consumer could read them as a safety or "
        "policy decision."
    ),
    "sunset": (
        "A deprecation announces the replacement endpoint, a first deprecation "
        "date, and a sunset date no earlier than 90 days later. Deprecated "
        "endpoints emit the Deprecation and Sunset headers and stay readable until "
        "sunset. No endpoint is ever removed silently."
    ),
    "contract_gate": (
        "This document describes the v1 HTTP contract over the "
        f"{PUBLIC_SCHEMA_VERSION} public projection. The URL major version and the "
        "projection schema version are independent axes; a future projection schema "
        "that is not backward compatible requires a new URL major version."
    ),
    "current_contract_status": (
        "DRAFT: served and cacheable, but not yet announced as stable. The "
        "same-origin MiniPC read path has been runtime-proved; the remaining "
        "gate is contract/release ratification, not transport reachability."
    ),
}

READ_ONLY_DESCRIPTION = (
    "Read-only over the fail-closed public projection. No PostgreSQL, no provider, "
    "no filesystem walk, and no LLM call occurs in the request path. A finding is "
    "served only because it is already PUBLISH/DISPUTED/CORRECTED/RETRACTED in the "
    "projection; this API never re-implements or relaxes the publication gate."
)


def _envelope_example(data: Any, index: "PublicIndex | None", **meta: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "api_version": API_CONTRACT_VERSION,
        "public_schema_version": (
            index.schema_version if index is not None else PUBLIC_SCHEMA_VERSION
        ),
        "contract_status": "DRAFT",
        "dataset_fingerprint": (
            index.dataset_sha256 if index is not None else "0" * 64
        ),
        "projection_generated_at": (
            index.generated_at if index is not None else "2026-01-01T00:00:00+00:00"
        ),
    }
    payload.update(meta)
    return {"data": data, "meta": payload}


def error_example(code: str, message: str, request_id: str = "a1b2c3d4e5f60718") -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        },
    }


# --------------------------------------------------------------------------- #
# Fictional example payloads
# --------------------------------------------------------------------------- #


def fictional_dossier(
    *,
    finding_id: str = "finding:fictional:1",
    claim_id: str = "claim:fictional:1",
    assessment: str = "SUPPORTED",
    publication_status: str = "PUBLISH",
    rationale: str = (
        "Fictional example. The published official register shows a figure close "
        "to the one stated, for the reference period covered by the claim."
    ),
    claim: str = "Fictional example: the published register records a figure close to the stated one.",
    with_correction: bool = False,
    with_reply: bool = False,
    with_relations: bool = False,
) -> dict[str, Any]:
    dossier: dict[str, Any] = {
        "claim": claim,
        "claim_contract": {
            "check_worthy": True,
            "source_segment_ids": ["segment:fictional:1"],
            "source_text_provenance_ids": [],
            "speaker_approval_required": True,
            "temporal_scope": {"statement_date": "2026-01-15"},
            "version": 1,
        },
        "claim_id": claim_id,
        "claim_type": "NUMERIC_STATISTIC",
        "corrections": (
            [
                {
                    "changed_fields": {"finding.rationale": "Superseded wording."},
                    "created_at": "2026-02-02T09:00:00+00:00",
                    "finding_id": "finding:fictional:2",
                    "id": "correction:fictional:1",
                    "previous_finding_id": "finding:fictional:1",
                    "reason": "Fictional example: the rationale was restated after review.",
                }
            ]
            if with_correction
            else []
        ),
        "evidence": [
            {
                "content_sha256": "f" * 64,
                "evidence_review_ids": ["review:fictional:evidence:1"],
                "id": "evidence:fictional:1",
                "observation_review_ids": ["review:fictional:observation:1"],
                "observed_at": "2026-01-20T08:00:00+00:00",
                "publication_date": "2026-01-10",
                "publisher": "Fictional official register",
                "reference_period": "2025",
                "relation": "VERIFICATION_INPUT",
                "rights_status": "PUBLIC_OFFICIAL",
                "source_type": "PRIMARY_OFFICIAL",
                "url": FICTIONAL_EVIDENCE_URL,
                "verification_observation_ids": ["observation:fictional:1"],
            }
        ],
        "finding": {
            "assessment": assessment,
            "created_at": "2026-01-20T08:00:00+00:00",
            "policy_version": "policy-v1",
            "publication_review_ids": ["review:fictional:finding:1"],
            "publication_status": publication_status,
            "published_at": "2026-01-20T08:00:00+00:00",
            "rationale": rationale,
            "supersedes_id": "finding:fictional:0" if with_correction else None,
            "verification_run_id": "verification:fictional:1",
        },
        "finding_id": finding_id,
        "relations": (
            [
                {
                    "id": "relation:fictional:1",
                    "related_claim": "Fictional example: an earlier statement of the same proposition.",
                    "related_claim_id": "claim:fictional:1",
                    "related_statement_date": "2025-11-01",
                    "rationale_codes": ["SAME_PROPOSITION"],
                    "relation_type": "SAME_PROPOSITION",
                    "relation_version": "claim-relation-v1",
                    "review_event_id": "review:fictional:relation:1",
                    "role": "SAME_PROPOSITION",
                    "status": "APPROVED",
                }
            ]
            if with_relations
            else []
        ),
        "rights_of_reply": (
            [
                {
                    "body": "Fictional example: a published right of reply, after its own review.",
                    "evidence_urls": [FICTIONAL_EVIDENCE_URL],
                    "id": "reply:fictional:1",
                    "status": "PUBLISHED",
                    "submitted_at": "2026-01-25T10:00:00+00:00",
                    "submitter_name": "Fictional submitter",
                    "submitter_role": "Fictional role",
                }
            ]
            if with_reply
            else []
        ),
        "source": {
            "content_id": "content:fictional:1",
            "published_at": "2026-01-15T12:00:00+00:00",
            "segments": [
                {
                    "end_ms": 8000,
                    "segment_id": "segment:fictional:1",
                    "segment_index": 0,
                    "start_ms": 1000,
                    "transcript_candidates": [
                        {
                            "provider_id": "platform-captions",
                            "segment_id": "segment:raw:fictional:1",
                            "source_kind": "PLATFORM_CAPTION",
                            "transcript_sha256": "1" * 64,
                            "variant_id": "transcript:fictional:1",
                        }
                    ],
                }
            ],
            "text_provenance": [],
            "title": "Fictional public statement",
            "url": FICTIONAL_SOURCE_URL,
        },
        "speaker": {
            "id": "person:fictional:1",
            "name": "Fictional public figure",
            "provenance": [
                {
                    "candidate_id": "speaker-candidate:fictional:1",
                    "provenance_kind": "TIMED_SPEAKER",
                    "review_event_ids": ["review:fictional:speaker:1"],
                }
            ],
            "public_role": "Fictional public role",
            "public_roles": [
                {
                    "end_date": None,
                    "organization_id": "org:fictional:1",
                    "organization_name": "Fictional organization",
                    "review_event_ids": ["review:fictional:role:1"],
                    "role": "Fictional public role",
                    "start_date": "2025-01-01",
                }
            ],
        },
    }
    return dossier


def fictional_summary(*, finding_id: str = "finding:fictional:1") -> dict[str, Any]:
    return {
        "assessment": "SUPPORTED",
        "claim": "Fictional example: the published register records a figure close to the stated one.",
        "claim_id": "claim:fictional:1",
        "claim_type": "NUMERIC_STATISTIC",
        "content_id": "content:fictional:1",
        "content_url": FICTIONAL_SOURCE_URL,
        "correction_count": 0,
        "finding_id": finding_id,
        "link": f"{API_BASE_PATH}/findings/{finding_id}",
        "person_id": "person:fictional:1",
        "person_name": "Fictional public figure",
        "publication_status": "PUBLISH",
        "published_at": "2026-01-20T08:00:00+00:00",
        "published_right_of_reply_count": 0,
    }


def fictional_health(index: "PublicIndex | None" = None) -> dict[str, Any]:
    return {
        "api_version": API_CONTRACT_VERSION,
        "dataset_fingerprint": index.dataset_sha256 if index else "0" * 64,
        "dossier_count": index.dossier_count if index else 0,
        "domain_vocabulary_version": DOMAIN_VOCABULARY_VERSION,
        "omitted_count": index.omitted_count if index else 0,
        "projection_generated_at": (
            index.generated_at if index else "2026-01-01T00:00:00+00:00"
        ),
        "public_schema_version": (
            index.schema_version if index else PUBLIC_SCHEMA_VERSION
        ),
        "status": "ok",
    }


def fictional_schema() -> dict[str, Any]:
    return {
        "api_version": API_CONTRACT_VERSION,
        "public_schema_version": PUBLIC_SCHEMA_VERSION,
        "domain_vocabulary_version": DOMAIN_VOCABULARY_VERSION,
        "vocabulary_versions": {
            "claim_type": VOCABULARIES["claim_type"][0],
            "finding_publication_status": VOCABULARIES["finding_publication_status"][0],
            "relation_candidate": VOCABULARIES["relation_candidate"][0],
            "verification_assessment": VOCABULARIES["verification_assessment"][0],
        },
        "public_finding_statuses": sorted(PUBLIC_FINDING_STATUSES),
        "publishable_assessments": sorted(PUBLISHABLE_ASSESSMENTS),
        "pagination": {
            "cursor": "opaque, versioned, bound to the request filter set",
            "default_limit": DEFAULT_LIMIT,
            "max_limit": MAX_LIMIT,
            "order": "published_at desc, finding_id asc",
        },
        "guarantees": {
            "database_in_request_path": False,
            "llm_in_request_path": False,
            "person_score": False,
            "publication_gate": "the fail-closed public projection is the only input",
            "ranking": False,
            "read_only": True,
        },
    }


def fictional_topics() -> list[dict[str, Any]]:
    return [
        {
            "topic_id": "topic:fictional:health-policy",
            "slug": "politiche-sanitarie",
            "canonical_name": "Politiche sanitarie",
            "scope_text": "Decisioni pubbliche relative all'organizzazione dei servizi sanitari.",
            "entity_version": "knowledge-entity-v1",
            "review_event_ids": ["review:topic:fictional:1"],
            "memberships": [
                {
                    "membership_id": "topic-membership:fictional:1",
                    "claim_id": "claim:fictional:1",
                    "finding_ids": ["finding:fictional:1"],
                    "review_event_ids": ["review:topic-membership:fictional:1"],
                    "source_resolution_candidate_id": None,
                }
            ],
            "finding_count": 1,
            "people": ["person:fictional:1"],
        }
    ]


def fictional_people() -> list[dict[str, Any]]:
    return [
        {
            "finding_count": 1,
            "name": "Fictional public figure",
            "person_id": "person:fictional:1",
            "topics": ["NUMERIC_STATISTIC"],
            "claim_types": ["NUMERIC_STATISTIC"],
            "subject_topic_ids": ["topic:fictional:health-policy"],
        }
    ]


def fictional_record() -> dict[str, Any]:
    return {
        "finding_count": 1,
        "findings": [fictional_summary()],
        "published_at": "2026-01-15T12:00:00+00:00",
        "record_id": "content-fictional-1",
        "segment_count": 1,
        "slug": "content-fictional-1",
        "title": "Fictional public statement",
        "url": FICTIONAL_SOURCE_URL,
    }


# --------------------------------------------------------------------------- #
# Components
# --------------------------------------------------------------------------- #


def _dossier_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "description": (
            "A published finding version, exactly as emitted by the public "
            "projection. Contains no raw transcript body, no evidence body, no "
            "provider receipt, and no person-level score or ranking."
        ),
        "required": [
            "claim",
            "claim_contract",
            "claim_id",
            "claim_type",
            "corrections",
            "evidence",
            "finding",
            "finding_id",
            "rights_of_reply",
            "source",
            "speaker",
        ],
        "properties": {
            "claim": {"type": ["string", "null"]},
            "claim_id": {"type": "string"},
            "claim_type": {"type": "string", "enum": list(VOCABULARIES["claim_type"][1])},
            "finding_id": {"type": "string"},
            "claim_contract": {
                "type": "object",
                "required": [
                    "check_worthy",
                    "speaker_approval_required",
                    "source_segment_ids",
                    "source_text_provenance_ids",
                    "temporal_scope",
                    "version",
                ],
                "properties": {
                    "check_worthy": {"type": "boolean"},
                    "speaker_approval_required": {"const": True},
                    "source_segment_ids": {"type": "array", "items": {"type": "string"}},
                    "source_text_provenance_ids": {"type": "array", "items": {"type": "string"}},
                    "temporal_scope": {"type": "object", "additionalProperties": True},
                    "version": {"const": 1},
                },
            },
            "speaker": {
                "type": "object",
                "required": ["id", "provenance"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": ["string", "null"]},
                    "public_role": {
                        "type": ["string", "null"],
                        "deprecated": True,
                        "description": (
                            "Legacy timeless role. Prefer public_roles, which are "
                            "dated and review-backed."
                        ),
                    },
                    "public_roles": {"type": "array", "items": {"$ref": "#/components/schemas/PublicRole"}},
                    "provenance": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": [
                                "candidate_id",
                                "provenance_kind",
                                "review_event_ids",
                            ],
                            "properties": {
                                "candidate_id": {"type": "string"},
                                "provenance_kind": {
                                    "type": "string",
                                    "enum": ["TIMED_SPEAKER", "TEXT_ATTRIBUTION"],
                                },
                                "review_event_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "source": {
                "type": "object",
                "required": ["content_id", "segments", "text_provenance", "url"],
                "anyOf": [
                    {"properties": {"segments": {"minItems": 1}}},
                    {"properties": {"text_provenance": {"minItems": 1}}},
                ],
                "properties": {
                    "content_id": {"type": "string"},
                    "url": {"type": "string", "format": "uri"},
                    "title": {"type": ["string", "null"]},
                    "published_at": {"type": ["string", "null"]},
                    "segments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "end_ms",
                                "segment_id",
                                "segment_index",
                                "start_ms",
                                "transcript_candidates",
                            ],
                            "properties": {
                                "end_ms": {"type": "integer", "minimum": 0},
                                "start_ms": {"type": "integer", "minimum": 0},
                                "segment_id": {"type": "string"},
                                "segment_index": {"type": "integer", "minimum": 0},
                                "transcript_candidates": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "required": ["segment_id", "variant_id"],
                                        "properties": {
                                            "segment_id": {"type": "string"},
                                            "variant_id": {"type": "string"},
                                            "provider_id": {"type": ["string", "null"]},
                                            "source_kind": {"type": ["string", "null"]},
                                            "transcript_sha256": {"type": ["string", "null"]},
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "text_provenance": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "attribution_method",
                                "attribution_version",
                                "id",
                                "quote_sha256",
                                "review_event_ids",
                                "selector_type",
                            ],
                            "properties": {
                                "id": {"type": "string"},
                                "selector_type": {
                                    "type": "string",
                                    "enum": ["TEXT_QUOTE_HASH", "TEXT_POSITION_HASH"],
                                },
                                "quote_sha256": {
                                    "type": "string",
                                    "pattern": "^[0-9a-f]{64}$",
                                },
                                "source_sha256": {
                                    "type": ["string", "null"],
                                    "pattern": "^[0-9a-f]{64}$",
                                },
                                "start_char": {"type": ["integer", "null"], "minimum": 0},
                                "end_char": {"type": ["integer", "null"], "minimum": 1},
                                "attribution_method": {
                                    "type": "string",
                                    "enum": [
                                        "SOURCE_BYLINE",
                                        "SOURCE_QUOTE",
                                        "ACCOUNT_OWNER",
                                        "OFFICIAL_RECORD",
                                        "MANUAL_REVIEW",
                                    ],
                                },
                                "attribution_version": {
                                    "const": "text-source-provenance-v1"
                                },
                                "review_event_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "finding": {
                "type": "object",
                "required": [
                    "assessment",
                    "publication_status",
                    "publication_review_ids",
                    "verification_run_id",
                ],
                "properties": {
                    "assessment": {
                        "type": "string",
                        "enum": sorted(PUBLISHABLE_ASSESSMENTS),
                        "description": "Claim-level assessment. Never a person score.",
                    },
                    "publication_status": {
                        "type": "string",
                        "enum": sorted(PUBLIC_FINDING_STATUSES),
                    },
                    "rationale": {"type": ["string", "null"]},
                    "policy_version": {"type": ["string", "null"]},
                    "verification_run_id": {"type": "string"},
                    "created_at": {"type": ["string", "null"]},
                    "published_at": {"type": ["string", "null"]},
                    "supersedes_id": {"type": ["string", "null"]},
                    "publication_review_ids": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                },
            },
            "evidence": {
                "type": "array",
                "minItems": 1,
                "description": (
                    "Approved evidence metadata only: identifiers, URL, dates, and "
                    "review identifiers. No evidence body or excerpt."
                ),
                "items": {
                    "type": "object",
                    "required": ["id", "url"],
                    "properties": {
                        "id": {"type": "string"},
                        "url": {"type": "string", "format": "uri"},
                        "publisher": {"type": ["string", "null"]},
                        "source_type": {"type": ["string", "null"]},
                        "publication_date": {"type": ["string", "null"]},
                        "observed_at": {"type": ["string", "null"]},
                        "content_sha256": {"type": ["string", "null"]},
                        "reference_period": {"type": ["string", "null"]},
                        "rights_status": {"type": ["string", "null"]},
                        "relation": {"type": ["string", "null"]},
                        "verification_observation_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "evidence_review_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "observation_review_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
            "corrections": {
                "type": "array",
                "description": "Append-only corrections with an explicit review approval.",
                "items": {
                    "type": "object",
                    "required": ["id", "finding_id"],
                    "properties": {
                        "id": {"type": "string"},
                        "finding_id": {"type": ["string", "null"]},
                        "previous_finding_id": {"type": ["string", "null"]},
                        "reason": {"type": ["string", "null"]},
                        "changed_fields": {"type": "object", "additionalProperties": True},
                        "created_at": {"type": ["string", "null"]},
                    },
                },
            },
            "rights_of_reply": {
                "type": "array",
                "description": (
                    "Only replies that passed their own publication review. A "
                    "pending or private reply is never projected."
                ),
                "items": {
                    "type": "object",
                    "required": ["id", "status"],
                    "properties": {
                        "id": {"type": "string"},
                        "status": {"const": "PUBLISHED"},
                        "submitter_name": {"type": ["string", "null"]},
                        "submitter_role": {"type": ["string", "null"]},
                        "submitted_at": {"type": ["string", "null"]},
                        "body": {"type": ["string", "null"]},
                        "evidence_urls": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "relations": {
                "type": "array",
                "description": (
                    "Reviewed longitudinal relations. A relation is never an "
                    "accusation of intent."
                ),
                "items": {
                    "type": "object",
                    "required": ["id", "relation_type", "status", "review_event_id"],
                    "properties": {
                        "id": {"type": "string"},
                        "relation_type": {
                            "type": "string",
                            "enum": list(VOCABULARIES["relation_candidate"][1]),
                        },
                        "relation_version": {"type": "string"},
                        "status": {"const": "APPROVED"},
                        "role": {"type": "string"},
                        "related_claim_id": {"type": "string"},
                        "related_claim": {"type": "string"},
                        "related_statement_date": {"type": ["string", "null"]},
                        "rationale_codes": {"type": "array", "items": {"type": "string"}},
                        "review_event_id": {"type": "string"},
                    },
                },
            },
        },
    }


def _components() -> dict[str, Any]:
    envelope_meta = {
        "type": "object",
        "required": [
            "api_version",
            "public_schema_version",
            "dataset_fingerprint",
            "projection_generated_at",
        ],
        "properties": {
            "api_version": {"const": API_CONTRACT_VERSION},
            "public_schema_version": {"const": PUBLIC_SCHEMA_VERSION},
            "contract_status": {
                "type": "string",
                "description": (
                    "DRAFT until contract/release ratification. The same-origin "
                    "MiniPC read path has already been runtime-proved."
                ),
            },
            "dataset_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "projection_generated_at": {"type": "string"},
            "count": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            "total": {"type": "integer", "minimum": 0},
            "next_cursor": {"type": ["string", "null"]},
            "link": {"type": "string"},
        },
    }
    return {
        "securitySchemes": {},
        "schemas": {
            "Meta": envelope_meta,
            "PublicRole": {
                "type": "object",
                "required": ["organization_id", "role", "review_event_ids"],
                "properties": {
                    "organization_id": {"type": "string"},
                    "organization_name": {"type": ["string", "null"]},
                    "role": {"type": "string"},
                    "start_date": {"type": ["string", "null"]},
                    "end_date": {"type": ["string", "null"]},
                    "review_event_ids": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                },
            },
            "FindingSummary": {
                "type": "object",
                "description": (
                    "Bounded public summary of one published finding version. "
                    "Contains no score, no ranking, and no transcript or evidence body."
                ),
                "required": ["finding_id", "claim_id", "claim_type", "assessment", "publication_status"],
                "properties": {
                    "finding_id": {"type": "string"},
                    "claim_id": {"type": "string"},
                    "claim": {"type": ["string", "null"]},
                    "claim_type": {"type": "string", "enum": list(VOCABULARIES["claim_type"][1])},
                    "assessment": {"type": "string", "enum": sorted(PUBLISHABLE_ASSESSMENTS)},
                    "publication_status": {"type": "string", "enum": sorted(PUBLIC_FINDING_STATUSES)},
                    "published_at": {"type": ["string", "null"]},
                    "person_id": {"type": "string"},
                    "person_name": {"type": ["string", "null"]},
                    "content_id": {"type": "string"},
                    "content_url": {"type": ["string", "null"]},
                    "correction_count": {"type": "integer", "minimum": 0},
                    "published_right_of_reply_count": {"type": "integer", "minimum": 0},
                    "link": {"type": "string"},
                },
            },
            "Record": {
                "type": "object",
                "required": ["record_id", "slug", "findings"],
                "properties": {
                    "record_id": {"type": "string"},
                    "slug": {"type": "string"},
                    "url": {"type": ["string", "null"]},
                    "title": {"type": ["string", "null"]},
                    "published_at": {"type": ["string", "null"]},
                    "segment_count": {"type": "integer", "minimum": 0},
                    "finding_count": {"type": "integer", "minimum": 0},
                    "findings": {"type": "array", "items": {"$ref": "#/components/schemas/FindingSummary"}},
                },
            },
            "Topic": {
                "type": "object",
                "description": (
                    "A first-class reviewed public subject Topic. It is never inferred "
                    "from claim_type or generated from free text in the HTTP layer."
                ),
                "required": [
                    "topic_id", "slug", "canonical_name", "entity_version",
                    "review_event_ids", "memberships", "finding_count", "people"
                ],
                "properties": {
                    "topic_id": {"type": "string"},
                    "slug": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "scope_text": {"type": ["string", "null"]},
                    "entity_version": {"type": "string"},
                    "review_event_ids": {"type": "array", "items": {"type": "string"}},
                    "memberships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "membership_id", "claim_id", "finding_ids",
                                "review_event_ids", "source_resolution_candidate_id"
                            ],
                            "properties": {
                                "membership_id": {"type": "string"},
                                "claim_id": {"type": "string"},
                                "finding_ids": {"type": "array", "items": {"type": "string"}},
                                "review_event_ids": {"type": "array", "items": {"type": "string"}},
                                "source_resolution_candidate_id": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "finding_count": {"type": "integer", "minimum": 0},
                    "people": {"type": "array", "items": {"type": "string"}},
                },
            },
            "PersonSummary": {
                "type": "object",
                "description": (
                    "A public figure appearing in the public record. This is a "
                    "disambiguation identity, never a score or a ranking."
                ),
                "required": ["person_id", "finding_count"],
                "properties": {
                    "person_id": {"type": "string"},
                    "name": {"type": ["string", "null"]},
                    "finding_count": {"type": "integer", "minimum": 0},
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "deprecated": True,
                        "description": "Deprecated pre-DP-430 alias containing claim-type codes.",
                    },
                    "claim_types": {"type": "array", "items": {"type": "string"}},
                    "subject_topic_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
            "Health": {
                "type": "object",
                "required": ["status", "api_version", "public_schema_version"],
                "properties": {
                    "status": {"const": "ok"},
                    "api_version": {"const": API_CONTRACT_VERSION},
                    "public_schema_version": {"const": PUBLIC_SCHEMA_VERSION},
                    "domain_vocabulary_version": {"type": "string"},
                    "projection_generated_at": {"type": "string"},
                    "dataset_fingerprint": {"type": "string"},
                    "dossier_count": {"type": "integer", "minimum": 0},
                    "omitted_count": {"type": "integer", "minimum": 0},
                },
            },
            "Dossier": _dossier_schema(),
            "Error": {
                "type": "object",
                "required": ["error"],
                "properties": {
                    "error": {
                        "type": "object",
                        "required": ["code", "message", "request_id"],
                        "properties": {
                            "code": {
                                "type": "string",
                                "enum": [
                                    "INVALID_QUERY",
                                    "INVALID_PARAMETER",
                                    "INVALID_PARAMETER_VALUE",
                                    "INVALID_CURSOR",
                                    "UNSUPPORTED_PARAMETER",
                                    "METHOD_NOT_ALLOWED",
                                    "RESOURCE_NOT_FOUND",
                                    "PUBLIC_PROJECTION_UNAVAILABLE",
                                    "INTERNAL_ERROR",
                                ],
                            },
                            "message": {"type": "string"},
                            "request_id": {"type": "string"},
                        },
                    }
                },
            },
        },
        "responses": {
            "NotFound": {
                "description": (
                    "The resource is unknown, private, unsafe, or not projectable. "
                    "The response is identical in every case and never reveals "
                    "whether an operational record exists."
                ),
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"},
                        "example": error_example(
                            "RESOURCE_NOT_FOUND",
                            "Resource is not available in the public record.",
                        ),
                    }
                },
            },
            "BadRequest": {
                "description": "Malformed path or query, unsupported parameter, or invalid cursor.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"},
                        "examples": {
                            "unknownParameter": {
                                "summary": "Unknown query parameter (typed 400, never a silent empty page)",
                                "value": error_example(
                                    "UNSUPPORTED_PARAMETER",
                                    "Unsupported query parameter(s): colour",
                                ),
                            },
                            "invalidCursor": {
                                "summary": "Cursor issued for another filter set or contract version",
                                "value": error_example(
                                    "INVALID_CURSOR",
                                    "Cursor was issued for a different filter set.",
                                ),
                            },
                        },
                    }
                },
            },
            "MethodNotAllowed": {
                "description": "Write and unsafe methods are rejected with Allow: GET, HEAD.",
                "headers": {
                    "Allow": {
                        "schema": {"const": "GET, HEAD"},
                        "description": "Always exactly `GET, HEAD`.",
                    }
                },
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"},
                        "example": error_example(
                            "METHOD_NOT_ALLOWED", "This API is read-only."
                        ),
                    }
                },
            },
            "ProjectionUnavailable": {
                "description": (
                    "The public projection is missing, invalid, stale, or "
                    "contract-incompatible. The API fails closed: no partial data "
                    "and no fabricated record."
                ),
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"},
                        "example": error_example(
                            "PUBLIC_PROJECTION_UNAVAILABLE",
                            "The public projection is missing, invalid, stale, or contract-incompatible.",
                        ),
                    }
                },
            },
            "InternalError": {
                "description": "Generic failure with a request id only. No stack trace, no SQL.",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"},
                        "example": error_example("INTERNAL_ERROR", "Unexpected server error."),
                    }
                },
            },
        },
        "parameters": {
            "Limit": {
                "name": "limit",
                "in": "query",
                "required": False,
                "description": f"Page size. Default {DEFAULT_LIMIT}, maximum {MAX_LIMIT}.",
                "schema": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_LIMIT,
                    "default": DEFAULT_LIMIT,
                },
            },
            "Cursor": {
                "name": "cursor",
                "in": "query",
                "required": False,
                "description": (
                    "Opaque continuation cursor from `meta.next_cursor`. It is "
                    "version-checked and bound to the request's filter set: reusing "
                    "it with different filters is a 400, never a silently "
                    "reinterpreted page."
                ),
                "schema": {"type": "string"},
            },
            "Topic": {
                "name": "topic",
                "in": "query",
                "required": False,
                "deprecated": True,
                "description": (
                    "Deprecated compatibility alias for `claim_type`. It filters the "
                    "claim-type vocabulary and does not select first-class subject Topics."
                ),
                "schema": {"type": "string"},
                "examples": {"numericStatistic": {"value": "NUMERIC_STATISTIC"}},
            },
            "ClaimType": {
                "name": "claim_type",
                "in": "query",
                "required": False,
                "description": "Comma-separated canonical claim-type codes.",
                "schema": {"type": "string"},
                "examples": {"numericStatistic": {"value": "NUMERIC_STATISTIC"}},
            },
            "Assessment": {
                "name": "assessment",
                "in": "query",
                "required": False,
                "description": "Comma-separated claim-level assessment codes.",
                "schema": {"type": "string"},
                "examples": {"supported": {"value": "SUPPORTED"}},
            },
            "Status": {
                "name": "status",
                "in": "query",
                "required": False,
                "description": "Comma-separated public publication-status codes.",
                "schema": {"type": "string"},
                "examples": {"publish": {"value": "PUBLISH"}},
            },
            "Person": {
                "name": "person",
                "in": "query",
                "required": False,
                "description": "Comma-separated stable speaker identifiers.",
                "schema": {"type": "string"},
            },
            "Content": {
                "name": "content",
                "in": "query",
                "required": False,
                "description": "Comma-separated stable content identifiers.",
                "schema": {"type": "string"},
            },
            "PublishedFrom": {
                "name": "published_from",
                "in": "query",
                "required": False,
                "description": "Inclusive ISO 8601 lower bound on publication time, with timezone.",
                "schema": {"type": "string", "format": "date-time"},
            },
            "PublishedTo": {
                "name": "published_to",
                "in": "query",
                "required": False,
                "description": "Inclusive ISO 8601 upper bound on publication time, with timezone.",
                "schema": {"type": "string", "format": "date-time"},
            },
        },
    }


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

_CACHE_HEADERS = {
    "ETag": {
        "description": (
            "Content validator derived from the canonical response bytes, which "
            "in turn derive from the projection fingerprint. It changes whenever a "
            "served finding version, correction, or published right of reply changes."
        ),
        "schema": {"type": "string"},
    },
    "Last-Modified": {"description": "Bundle modification time.", "schema": {"type": "string"}},
    "Cache-Control": {
        "description": "public, max-age=300, stale-while-revalidate=86400 for data; max-age=3600 for contract documents.",
        "schema": {"type": "string"},
    },
    API_VERSION_HEADER: {"description": "Contract major version served.", "schema": {"type": "string"}},
    "X-Content-Type-Options": {"schema": {"const": "nosniff"}},
    "Vary": {"description": "Always `Accept`.", "schema": {"type": "string"}},
    "Link": {
        "description": 'Points at the machine-readable service description: <{API_BASE_PATH}/openapi.json>; rel="service-desc"',
        "schema": {"type": "string"},
    },
    "Deprecation": {
        "description": "Present only on a deprecated endpoint, per the deprecation policy.",
        "schema": {"type": "string"},
    },
    "Sunset": {
        "description": "Present only on a deprecated endpoint; HTTP-date of the announced sunset.",
        "schema": {"type": "string"},
    },
}

_COLLECTION_PARAM_NAMES = (
    "Limit",
    "Cursor",
    "ClaimType",
    "Topic",
    "Assessment",
    "Status",
    "Person",
    "Content",
    "PublishedFrom",
    "PublishedTo",
)


def _headers(*names: str) -> dict[str, Any]:
    return {name: _CACHE_HEADERS[name] for name in names}


def _json(content_schema: dict[str, Any], example: Any, summary: str) -> dict[str, Any]:
    return {
        "description": summary,
        "headers": _headers(
            "ETag",
            "Last-Modified",
            "Cache-Control",
            API_VERSION_HEADER,
            "X-Content-Type-Options",
            "Vary",
            "Link",
        ),
        "content": {
            "application/json": {"schema": content_schema, "example": example}
        },
    }


def _ok(schema_ref: str, example: Any, summary: str) -> dict[str, Any]:
    return {
        "description": summary,
        "headers": _headers(
            "ETag",
            "Last-Modified",
            "Cache-Control",
            API_VERSION_HEADER,
            "X-Content-Type-Options",
            "Vary",
            "Link",
        ),
        "content": {
            "application/json": {
                "schema": {
                    "allOf": [
                        {
                            "type": "object",
                            "required": ["data", "meta"],
                            "properties": {
                                "data": {"$ref": schema_ref},
                                "meta": {"$ref": "#/components/schemas/Meta"},
                            },
                        }
                    ]
                },
                "example": example,
            }
        },
    }


_ERROR_STATUS = {
    "BadRequest": "400",
    "NotFound": "404",
    "MethodNotAllowed": "405",
    "ProjectionUnavailable": "503",
    "InternalError": "500",
}


def _errors(*names: str) -> dict[str, Any]:
    """Reference component responses keyed by their HTTP status code."""
    return {
        _ERROR_STATUS[name]: {"$ref": f"#/components/responses/{name}"} for name in names
    }


def build_openapi_document(index: "PublicIndex | None" = None) -> dict[str, Any]:
    """Return the OpenAPI 3.1 document.

    The path table is derived from ``public_api.ROUTES`` so the document cannot
    describe a route the server does not serve, nor omit one it does.
    """
    components = _components()
    paths: dict[str, Any] = {}

    for route in ROUTES:
        if route.name in ("health", "schema", "findings", "topics", "people"):
            schema_ref = {
                "health": "#/components/schemas/Health",
                "schema": {"type": "object", "additionalProperties": True},
                "findings": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/FindingSummary"},
                },
                "topics": {"type": "array", "items": {"$ref": "#/components/schemas/Topic"}},
                "people": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/PersonSummary"},
                },
            }[route.name]
            example = {
                "health": _envelope_example(fictional_health(index), index, link=f"{API_BASE_PATH}/health"),
                "schema": _envelope_example(fictional_schema(), index, link=f"{API_BASE_PATH}/schema"),
                "findings": _envelope_example(
                    [fictional_summary()],
                    index,
                    count=1,
                    limit=DEFAULT_LIMIT,
                    total=1,
                    next_cursor=None,
                    link=f"{API_BASE_PATH}/findings",
                ),
                "topics": _envelope_example(
                    fictional_topics(), index, count=1, link=f"{API_BASE_PATH}/topics"
                ),
                "people": _envelope_example(
                    fictional_people(), index, count=1, link=f"{API_BASE_PATH}/people"
                ),
            }[route.name]
            summary = {
                "health": "Liveness plus the served projection fingerprint and vocabulary versions.",
                "schema": "The public contract descriptor: vocabularies, bounds, facets, and guarantees.",
                "findings": "Bounded, deterministic collection of published finding versions.",
                "topics": "First-class reviewed public subject Topics present in the projection.",
                "people": "Public figures actually present in the projection, with counts.",
            }[route.name]
            path_item: dict[str, Any] = {
                "get": {
                    "summary": summary,
                    "description": READ_ONLY_DESCRIPTION,
                    "operationId": f"{route.name}",
                    "security": [],
                    "parameters": (
                        [{"$ref": f"#/components/parameters/{name}"} for name in _COLLECTION_PARAM_NAMES]
                        if route.name == "findings"
                        else []
                    ),
                    "responses": {
                        "200": _ok(schema_ref, example, summary),
                        **_errors("BadRequest", "MethodNotAllowed", "ProjectionUnavailable", "InternalError"),
                    },
                },
                "head": {
                    "summary": f"HEAD {route.pattern}: same status, headers, and validators as GET, without a body.",
                    "operationId": f"{route.name}_head",
                    "security": [],
                    "responses": {
                        "200": {
                            "description": "Same headers and validators as GET; no body.",
                            "headers": _headers(
                                "ETag",
                                "Last-Modified",
                                "Cache-Control",
                                API_VERSION_HEADER,
                                "X-Content-Type-Options",
                                "Vary",
                                "Link",
                            ),
                        },
                        **_errors("BadRequest", "MethodNotAllowed", "ProjectionUnavailable"),
                    },
                },
            }
            paths[route.pattern] = path_item
            continue

        if route.name == "finding":
            path_item = {
                "get": {
                    "summary": "One immutable published finding version.",
                    "description": (
                        READ_ONLY_DESCRIPTION
                        + " The id is the opaque projection finding_id; a display name is never used to resolve a record."
                    ),
                    "operationId": "get_finding",
                    "security": [],
                    "parameters": [
                        {
                            "name": "finding_id",
                            "in": "path",
                            "required": True,
                            "description": "Stable opaque finding identifier from the projection.",
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": _ok(
                            "#/components/schemas/Dossier",
                            _envelope_example(fictional_dossier(), index, link=f"{API_BASE_PATH}/findings/finding:fictional:1"),
                            "Published finding version with approved provenance identifiers.",
                        ),
                        **_errors("BadRequest", "NotFound", "MethodNotAllowed", "ProjectionUnavailable", "InternalError"),
                    },
                },
                "head": {
                    "summary": "HEAD for one finding version.",
                    "operationId": "get_finding_head",
                    "security": [],
                    "parameters": [
                        {
                            "name": "finding_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Same headers and validators as GET; no body.",
                            "headers": _headers("ETag", "Last-Modified", "Cache-Control", API_VERSION_HEADER),
                        },
                        **_errors("NotFound", "MethodNotAllowed", "ProjectionUnavailable"),
                    },
                },
            }
            paths[route.pattern] = path_item
            continue

        if route.name == "record":
            path_item = {
                "get": {
                    "summary": "One public record (the content of a statement) and its published finding versions.",
                    "description": (
                        READ_ONLY_DESCRIPTION
                        + " The slug is derived from the projection's own stable content_id, not from a display title."
                    ),
                    "operationId": "get_record",
                    "security": [],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "description": "Lowercase slug of the stable content identifier.",
                            "schema": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                        }
                    ],
                    "responses": {
                        "200": _ok(
                            "#/components/schemas/Record",
                            _envelope_example(fictional_record(), index, link=f"{API_BASE_PATH}/records/content-fictional-1"),
                            "One public record with its published finding versions.",
                        ),
                        **_errors("BadRequest", "NotFound", "MethodNotAllowed", "ProjectionUnavailable", "InternalError"),
                    },
                },
                "head": {
                    "summary": "HEAD for one public record.",
                    "operationId": "get_record_head",
                    "security": [],
                    "parameters": [
                        {"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "Same headers and validators as GET; no body.",
                            "headers": _headers("ETag", "Last-Modified", "Cache-Control", API_VERSION_HEADER),
                        },
                        **_errors("NotFound", "MethodNotAllowed", "ProjectionUnavailable"),
                    },
                },
            }
            paths[route.pattern] = path_item
            continue

        if route.name == "index":
            path_item = {
                "get": {
                    "summary": "The whole public projection bundle, byte-stable and CDN-cacheable.",
                    "description": (
                        READ_ONLY_DESCRIPTION
                        + " This is the same fail-closed artifact the static bundle is built from, re-serialized deterministically (sorted keys, no whitespace drift), so its canonical bytes are stable for a given dataset fingerprint."
                    ),
                    "operationId": "get_index",
                    "security": [],
                    "responses": {
                        "200": _json(
                            {"$ref": "#/components/schemas/PublicBundle"},
                            {
                                "schema_version": PUBLIC_SCHEMA_VERSION,
                                "generated_at": index.generated_at if index else "2026-01-01T00:00:00+00:00",
                                "dataset_sha256": index.dataset_sha256 if index else "0" * 64,
                                "methodology": {
                                    "claim_level_only": True,
                                    "aggregate_person_score": False,
                                    "requires_publication_gate": True,
                                    "requires_approved_evidence": True,
                                    "requires_resolved_transcript": True,
                                },
                                "dossier_count": 1,
                                "omitted_count": 0,
                                "dossiers": [fictional_dossier()],
                            },
                            "The fail-closed public projection bundle.",
                        ),
                        **_errors("BadRequest", "MethodNotAllowed", "ProjectionUnavailable", "InternalError"),
                    },
                },
                "head": {
                    "summary": "HEAD for the projection bundle.",
                    "operationId": "get_index_head",
                    "security": [],
                    "responses": {
                        "200": {
                            "description": "Same headers and validators as GET; no body.",
                            "headers": _headers("ETag", "Last-Modified", "Cache-Control", API_VERSION_HEADER),
                        },
                        **_errors(
                            "BadRequest",
                            "MethodNotAllowed",
                            "ProjectionUnavailable",
                            "InternalError",
                        ),
                    },
                },
            }
            paths[route.pattern] = path_item
            continue

        if route.name == "openapi":
            # The document describes itself; reference the served object rather
            # than embedding a second copy.
            path_item = {
                "get": {
                    "summary": "This OpenAPI 3.1 document.",
                    "description": "Self-describing service description; no second field vocabulary.",
                    "operationId": "get_openapi",
                    "security": [],
                    "responses": {
                        "200": _json(
                            {"type": "object"},
                            {"openapi": OPENAPI_VERSION, "info": {"title": "Dichiarazioni Pubbliche public API (self-reference)"}},
                            "The served OpenAPI document.",
                        ),
                        **_errors("MethodNotAllowed", "ProjectionUnavailable", "InternalError"),
                    },
                },
                "head": {
                    "summary": "HEAD for this document.",
                    "operationId": "get_openapi_head",
                    "security": [],
                    "responses": {
                        "200": {
                            "description": "Same headers and validators as GET; no body.",
                            "headers": _headers("Cache-Control", API_VERSION_HEADER),
                        },
                        **_errors("MethodNotAllowed", "ProjectionUnavailable", "InternalError"),
                    },
                },
            }
            paths[route.pattern] = path_item

    components["schemas"]["PublicBundle"] = {
        "type": "object",
        "description": "The fail-closed public projection bundle, exactly as the static build consumes it.",
        "required": [
            "schema_version",
            "generated_at",
            "dataset_sha256",
            "methodology",
            "dossier_count",
            "omitted_count",
            "dossiers",
        ],
        "properties": {
            "schema_version": {"const": PUBLIC_SCHEMA_VERSION},
            "generated_at": {"type": "string"},
            "dataset_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "methodology": {
                "type": "object",
                "required": ["claim_level_only", "aggregate_person_score"],
                "properties": {
                    "claim_level_only": {"const": True},
                    "aggregate_person_score": {"const": False},
                    "requires_publication_gate": {"type": "boolean"},
                    "requires_approved_evidence": {"type": "boolean"},
                    "requires_resolved_transcript": {"type": "boolean"},
                },
            },
            "dossier_count": {"type": "integer", "minimum": 0},
            "omitted_count": {
                "type": "integer",
                "minimum": 0,
                "description": "Records the publication gate held. It is an aggregate count, never a record.",
            },
            "dossiers": {"type": "array", "items": {"$ref": "#/components/schemas/Dossier"}},
        },
    }

    document = {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": "Dichiarazioni Pubbliche public read-only API",
            "version": API_CONTRACT_VERSION,
            "summary": (
                "Stable, read-only, cacheable access to the fail-closed public "
                "projection of published finding versions."
            ),
            "description": (
                "Dichiarazioni Pubbliche is an open public-record system for verifiable public "
                "statements. This API serves only what the publication gate already "
                "approved, with provenance identifiers, assessment, and "
                "correction/right-of-reply history.\n\n"
                "It is a pure reader over a pre-built projection bundle: no "
                "database, no provider, and no LLM is used in the request path, and "
                "the product remains fully readable while every model provider is "
                "offline. The API is read-only (GET/HEAD only), unauthenticated, and "
                "designed to be deployed next to a static host.\n\n"
                "Semantics that a consumer must not flatten: retrieved evidence is "
                "not approved evidence; approved evidence is not a verified claim; a "
                "verified claim is not a published finding; a false claim is not a "
                "deliberate falsehood; a position change is not a lie; a "
                "contradiction is not proof of intent. There is no person score, no "
                "ranking, and no political recommendation, and the API will never "
                "return one."
            ),
            "x-dichiarazioni-pubbliche": {
                "public_schema_version": PUBLIC_SCHEMA_VERSION,
                "domain_vocabulary_version": DOMAIN_VOCABULARY_VERSION,
                "api_contract_status": "DRAFT",
                "api_major_version": API_MAJOR_VERSION,
                "read_only": True,
                "llm_in_request_path": False,
                "authentication": None,
                "rate_limiting": {
                    "status": "contract defined, enforcement not implemented (DP-508)",
                    "expectation": (
                        "Requests are served from cache and are expected to be "
                        "infrequent. No rate-limit enforcement or authentication is "
                        "present in this deployment; clients must not treat the "
                        "absence of a 429 as unlimited throughput."
                    ),
                    "contract": {
                        "429": {
                            "error_code": "RATE_LIMITED",
                            "retry_after": "Retry-After header, seconds",
                            "note": (
                                "Reserved for a future release. Clients should "
                                "handle 429 defensively even though this "
                                "implementation never emits it."
                            ),
                        }
                    },
                },
                "publication_guarantees": [
                    "A finding is served only because it is already in the fail-closed public projection.",
                    "The API never re-implements, relaxes, or bypasses the publication gate.",
                    "A non-PUBLISH dossier is not in the bundle and therefore is not served.",
                    "The API returns 503 rather than partial data when the projection is missing, stale, or incompatible.",
                    "Raw transcript bodies, evidence bodies, provider receipts, secrets, and private replies are never returned.",
                ],
            },
            "x-deprecation-policy": DEPRECATION_POLICY,
        },
        "servers": [
            {
                "url": "/",
                "description": (
                    "Same-origin base. The API is designed to sit next to the "
                    "static public site; see the DP-401 hosting contract for the "
                    "selected adapter."
                ),
            }
        ],
        "security": [],
        "tags": [
            {"name": "contract", "description": "Contract, health, and discovery documents."},
            {"name": "findings", "description": "Published finding versions."},
            {"name": "facets", "description": "Topics, people, and public records."},
        ],
        "paths": dict(sorted(paths.items())),
        "components": components,
    }
    return document


def openapi_document_bytes(index: "PublicIndex | None" = None) -> bytes:
    """Deterministic serialization of the document, for the checked-in artifact."""
    return (
        json.dumps(build_openapi_document(index), ensure_ascii=False, indent=2, sort_keys=True).encode()
        + b"\n"
    )



def write_openapi_document(path: str, index: "PublicIndex | None" = None) -> str:
    """Write the generated document to ``path`` so a static host can serve it."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(openapi_document_bytes(index))
    return str(target)


# --------------------------------------------------------------------------- #
# Agent-facing documentation (DP-404)
#
# Generated from the same contract constants and route table as the OpenAPI
# document, so it cannot introduce a second API list or a conflicting route
# name (DP-404 AC-404.1 / AC-404.8).
# --------------------------------------------------------------------------- #

_LLMS_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "1. What this is",
        """
Dichiarazioni Pubbliche is an open, Italy-first public-record system for verifiable public
statements. It preserves what a public figure said, when and where they said it,
the source and wording supporting the attribution, the evidence relevant to a
checkable claim, and the history of later review, correction, reply, or change.

It is not a leaderboard, not a "who is trustworthy" service, and not a political
recommendation engine. It is a provenance record you can audit yourself.

Everything you can read publicly has already passed the publication gate. There
is no endpoint, parameter, or key that exposes a draft, a held record, or a
private reply.
""",
    ),
    (
        "2. Public surfaces",
        """
- Human-readable dossier pages, one per public statement.
- Public JSON and JSON-LD, derived from the same fail-closed read model.
- A read-only HTTP API described below, served from that same read model.

The web pages and the API are two renderings of one artifact. They cannot
disagree about what is published.
""",
    ),
    (
        "3. Contract and discovery",
        """
- API base path: /api/v1 (same-origin with the static site)
- OpenAPI 3.1 document: /api/v1/openapi.json
- Contract descriptor: /api/v1/schema
- Health, dataset fingerprint, vocabulary versions: /api/v1/health
- Bounded finding collection: /api/v1/findings
- One published finding version: /api/v1/findings/{finding_id}
- One public record (statement) and its findings: /api/v1/records/{slug}
- First-class reviewed subject Topics present in the projection: /api/v1/topics
- Public figures present in the projection: /api/v1/people
- The full fail-closed projection bundle: /api/v1/index.json
- This document: /llms.txt

The API is unauthenticated and read-only: GET and HEAD only, no key, no
registration. Every response carries ETag, Last-Modified, and Cache-Control, so
a correctly behaving client revalidates instead of refetching.
""",
    ),
    (
        "4. Vocabulary and the publication boundary",
        """
These distinctions are load-bearing. Collapsing any of them produces a wrong
answer, not merely an imprecise one:

- retrieved evidence != approved evidence
- approved evidence != verified claim
- verified claim != published finding
- false claim != deliberate falsehood
- position change != lie
- contradiction != proof of intent
- speaker appearance != approved segment attribution
- public projection != operational database

An `assessment` is a claim-level result, never a score attached to a person. A
`publication_status` records the editorial state of one specific finding version.
There is no field anywhere in this API for a person score, a rank, a ranking, or a
political recommendation, and there never will be.
""",
    ),
    (
        "5. Provenance, time, corrections, and replies",
        """
- Every served finding version carries approved speaker provenance, source
  segment identifiers, transcript variant hashes, a verification run identifier,
  and publication review identifiers.
- Raw transcript text, canonical transcript bodies, and evidence bodies are
  private operational data and are never returned.
- A finding is versioned. A correction never overwrites history: a superseding
  finding links back through `supersedes_id` and `corrections[].previous_finding_id`.
- A right of reply begins private, is re-analysed, and appears only after its own
  publication review. A pending or private reply is not projected at all.
- A published record is not judged with evidence that only became available
  later, unless the finding explicitly concerns a later outcome.
""",
    ),
    (
        "6. Request and response shapes (fictional)",
        """
All identifiers and URLs below are fictional. `example.test` is reserved for
documentation and never resolves. These are shapes, not claims about anyone.

Request:

    GET /api/v1/findings?claim_type=NUMERIC_STATISTIC&assessment=SUPPORTED&limit=25

Response (truncated):

    {
      "data": [
        {
          "finding_id": "finding:fictional:1",
          "claim_id": "claim:fictional:1",
          "claim": "Fictional example: the published register records a figure close to the stated one.",
          "claim_type": "NUMERIC_STATISTIC",
          "assessment": "SUPPORTED",
          "publication_status": "PUBLISH",
          "published_at": "2026-01-20T08:00:00+00:00",
          "person_id": "person:fictional:1",
          "person_name": "Fictional public figure",
          "content_id": "content:fictional:1",
          "content_url": "https://example.test/fictional-source",
          "correction_count": 0,
          "published_right_of_reply_count": 0,
          "link": "/api/v1/findings/finding:fictional:1"
        }
      ],
      "meta": {
        "api_version": "v1",
        "public_schema_version": "SCHEMA_VERSION",
        "dataset_fingerprint": "sha256 of the served dataset",
        "count": 1, "limit": 25, "total": 1, "next_cursor": null
      }
    }

An empty collection is a success, not a failure:

    {"data": [], "meta": {"count": 0, "total": 0, "next_cursor": null}}

An unknown, private, or held resource is a 404 that never reveals whether an
operational record exists:

    {"error": {"code": "RESOURCE_NOT_FOUND", "message": "Resource is not available in the public record.", "request_id": "..."}}

Filtering is fail-closed: an unknown parameter or an unknown enum value is a
typed 400, never a silently empty page.

    GET /api/v1/findings?colour=blue
    -> 400 {"error": {"code": "UNSUPPORTED_PARAMETER", ...}}
""",
    ),
    (
        "7. Limits, unsupported states, and safe failure behavior",
        """
- No full-text, semantic, or vector search. Collection access is bounded and
  deterministic: default limit 25, maximum limit 100, ordered by publication
  time descending with the finding id as a stable tie-breaker.
- Pagination uses an opaque cursor. Reusing a cursor with a different filter set
  is a 400, not a reinterpreted page.
- If the projection is missing, stale, tampered, or built against an incompatible
  schema, every endpoint returns 503. It never serves partial data and never
  invents a placeholder record.
- Assessments are limited to the publishable set: SUPPORTED, FACTUALLY_FALSE,
  OUTDATED_DATA. INSUFFICIENT_EVIDENCE and UNRESOLVED are not publishable and so
  never appear in a public response.
- An empty public dataset means "nothing has been published yet", not "no records
  exist". Absence is not a finding.
""",
    ),
    (
        "8. What an agent must not do with this API",
        """
- Do not call a model to decide whether a statement is true. The assessment in
  the record is the output of a deterministic verification run, already made.
- Do not infer speaker identity from voice, face, or appearance. Attribution is
  non-biometric by design and rests on approved review events.
- Do not treat a candidate relation as an accusation. Only reviewed, approved
  relations are published, and a contradiction is not proof of intent.
- Do not present a person-level score, a ranking, or a political recommendation.
  The record contains no such field; deriving one is a misuse of it.
- Do not publish, approve evidence, or submit a reply through this API. It is
  read-only by construction: POST, PUT, PATCH, and DELETE return 405.
- Do not use a model-generated URL or query as evidence. Every evidence URL here
  was fetched and observed by the pipeline, never invented.
""",
    ),
)


def build_llms_txt(index: "PublicIndex | None" = None) -> str:
    """Generate the agent-facing discovery document, following llms.txt."""
    schema_version = index.schema_version if index is not None else PUBLIC_SCHEMA_VERSION
    fingerprint = index.dataset_sha256 if index is not None else "unavailable"
    generated_at = index.generated_at if index is not None else "unavailable"
    head = [
        "# Dichiarazioni Pubbliche",
        "",
        "> Open, Italy-first public records of verifiable public statements. "
        "Read-only API over the `" + schema_version + "` public projection. "
        "Contract status: DRAFT.",
        "",
        "CONTRACT GATE: this document describes the `/api/v1` HTTP contract over the",
        "`" + schema_version + "` public projection. Per DP-105, the public projection",
        "schema version and the URL major version are independent axes, and no",
        "stable-v1 compatibility decision is ratified yet: the `/api/v1` URL segment",
        "is not a stability promise. This compatibility gate is not ratified. Read",
        "this document as accurate about what the API returns, and as carrying no",
        "ratified compatibility guarantee. The same-origin MiniPC read path is",
        "runtime-proved; stability/release ratification remains separate.",
        "",
    ]
    parts: list[str] = ["\n".join(head)]
    for title, body in _LLMS_SECTIONS:
        parts.append("## " + title + "\n\n" + body.replace("SCHEMA_VERSION", schema_version))
    document_fingerprint = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    parts.append(
        "\n".join(
            [
                "## 9. Contract identity",
                "",
                "- public projection schema: " + schema_version,
                "- domain vocabulary: " + DOMAIN_VOCABULARY_VERSION,
                "- API contract version: v1 (contract status: DRAFT)",
                "- served dataset fingerprint: " + fingerprint,
                "- projection generated at: " + generated_at,
                "- document fingerprint (sha256 of this text, excluding this line): "
                + document_fingerprint,
                "",
            ]
        )
    )
    return "\n".join(parts)


_API_README = """# Dichiarazioni Pubbliche public API (contract v1, DRAFT)

Status: contract `v1` over the `{schema_version}` public projection.
Contract status: **DRAFT** — served and cacheable, with same-origin MiniPC
runtime proof complete; stable-v1 compatibility/release ratification remains open.

## What this is

A read-only, cacheable HTTP surface over the Dichiarazioni Pubbliche public projection. The
projection is a fail-closed, sanitized, finding-versioned read model produced by
the publication pipeline. This API reads it and nothing else.

## Run it

```bash
export DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH=/path/to/projection/index.json
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.public_api --port 8787
```

`DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH` is the same variable the static web build uses.
Point both at the same bundle and the API and the static site cannot diverge.

## Guarantees

- **No LLM, provider, or database in the request path.** Reads stay available
  with every model provider offline.
- **Read-only.** `GET` and `HEAD` only. `POST`, `PUT`, `PATCH`, `DELETE`, and
  method-override requests return `405` with `Allow: GET, HEAD`.
- **The publication gate is never re-implemented here.** A finding is served
  because it is already in the projection. A dossier that is not PUBLISH,
  DISPUTED, CORRECTED, or RETRACTED is not in the bundle, so it is not served.
- **Fail closed.** A missing, stale, tampered, or contract-incompatible
  projection returns `503` on every endpoint: no partial data, no placeholder.
- **Cacheable.** `ETag`, `Last-Modified`, and `Cache-Control` on every response;
  a matching `If-None-Match` returns `304`.
- **No private data.** No raw transcript body, no evidence body, no provider
  receipt, no secret, no private reply, no person score, no ranking.

## Endpoints

| Method | Path | Meaning |
|---|---|---|
| GET, HEAD | `/api/v1/health` | Liveness, projection fingerprint, vocabulary versions |
| GET, HEAD | `/api/v1/schema` | Public contract descriptor: vocabularies, bounds, guarantees |
| GET, HEAD | `/api/v1/findings` | Bounded, deterministic collection of published finding versions |
| GET, HEAD | `/api/v1/findings/{{finding_id}}` | One immutable published finding version |
| GET, HEAD | `/api/v1/records/{{slug}}` | One public record (statement) and its published findings |
| GET, HEAD | `/api/v1/topics` | First-class reviewed subject Topics present in the projection |
| GET, HEAD | `/api/v1/people` | Public figures present in the projection |
| GET, HEAD | `/api/v1/openapi.json` | This API as an OpenAPI 3.1 document |
| GET, HEAD | `/api/v1/index.json` | The full fail-closed projection bundle |

## Collection contract

- `limit`: default `{default_limit}`, maximum `{max_limit}`. Out of range is a `400`.
- `cursor`: opaque continuation from `meta.next_cursor`. Version-checked and bound
  to the request's filter set; reusing one with different filters is a `400`.
- Order: `published_at` descending, `finding_id` ascending as a stable
  tie-breaker. Deterministic for a given dataset fingerprint.
- Filters, all optional, all comma-separated and AND-combined: `claim_type`
  (canonical claim-type code), `assessment`, `status`, `person` (speaker id), `content`
  (content id), `published_from`, `published_to` (ISO 8601 with an explicit
  timezone).
- `topic` remains a deprecated compatibility alias for `claim_type` in the draft
  v1 contract. It never selects the first-class subject resources served by
  `/api/v1/topics`.
- An empty collection is `200` with `data: []`. It never fabricates a record.
- An unknown or malformed parameter is a typed `400`, never a silent empty page.

## Examples

```bash
curl -sS http://127.0.0.1:8787/api/v1/health

curl -sS 'http://127.0.0.1:8787/api/v1/findings?limit=2&assessment=SUPPORTED'

curl -sS 'http://127.0.0.1:8787/api/v1/findings/{sample_finding}'

curl -sS http://127.0.0.1:8787/api/v1/topics

curl -sSI http://127.0.0.1:8787/api/v1/openapi.json
```

Revalidate instead of refetching:

```bash
etag=$(curl -sSI http://127.0.0.1:8787/api/v1/findings \\
  | sed -n 's/^[Ee][Tt]ag: //p' | tr -d '\\r')
curl -sS -o /dev/null -w '%{{http_code}}\\n' \\
  -H "If-None-Match: $etag" http://127.0.0.1:8787/api/v1/findings
# 304
```

## Errors

```json
{{"error": {{"code": "MACHINE_READABLE_CODE", "message": "Short public explanation", "request_id": "opaque"}}}}
```

| Condition | Status | Code |
|---|---:|---|
| Malformed query or unknown parameter | 400 | `INVALID_QUERY`, `UNSUPPORTED_PARAMETER`, `INVALID_PARAMETER_VALUE` |
| Invalid or cross-filter cursor | 400 | `INVALID_CURSOR` |
| Write method or method override | 405 | `METHOD_NOT_ALLOWED` (with `Allow: GET, HEAD`) |
| Unknown, private, or non-projectable resource | 404 | `RESOURCE_NOT_FOUND` |
| Projection missing, invalid, stale, incompatible | 503 | `PUBLIC_PROJECTION_UNAVAILABLE` |
| Unexpected failure | 500 | `INTERNAL_ERROR` |

Error responses are `Cache-Control: no-store` and never contain a stack trace, a
SQL fragment, or any hint that an operational record exists.

## Rate limits

No authentication and no rate-limit enforcement ship in this deployment. The
contract reserves `429 RATE_LIMITED` with a `Retry-After` header for a future
release (DP-508); clients should handle it defensively and must not read its
absence as unlimited throughput. The intended shape is a CDN-cached static read
served to infrequent, revalidating clients.

## Versioning and deprecation

`/api/v1` is the compatibility boundary. Adding an optional field or a new documented
endpoint is compatible. Renaming a field, changing its meaning, making an optional
field required, removing a field, changing identifier semantics, or changing an
assessment, relation, or publication-status meaning is breaking and requires a
new major version. A deprecation names its replacement, a first deprecation date,
and a sunset date at least 90 days later; the endpoint stays readable and emits
`Deprecation` and `Sunset` until then. Nothing is removed silently.

## Contract artifacts

- `docs/api/openapi.v1.json` — the generated OpenAPI 3.1 document.
- `docs/api/llms.txt` — the generated agent-facing discovery document.
- `poc/dichiarazioni_pubbliche/openapi.py` — the generator, so all three agree.

```bash
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.openapi --docs-dir docs/api
```
"""


def build_api_readme(index: "PublicIndex | None" = None) -> str:
    """Human-facing API reference with copy-paste examples and the limits."""
    sample_finding = index.entries[0].finding_id if index is not None else "finding:fictional:1"
    return (
        _API_README.replace("{schema_version}", index.schema_version if index else PUBLIC_SCHEMA_VERSION)
        .replace("{default_limit}", str(DEFAULT_LIMIT))
        .replace("{max_limit}", str(MAX_LIMIT))
        .replace("{sample_finding}", sample_finding)
    )


def write_docs(docs_dir: str, index: "PublicIndex | None" = None) -> list[str]:
    """Regenerate every contract artifact from the same source of truth."""
    target = Path(docs_dir)
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for name, payload in (
        ("openapi.v1.json", openapi_document_bytes(index)),
        ("llms.txt", build_llms_txt(index).encode("utf-8")),
        ("README.md", build_api_readme(index).encode("utf-8")),
    ):
        path = target / name
        path.write_bytes(payload)
        written.append(str(path))
    return written


if __name__ == "__main__":  # pragma: no cover - contributor tool
    import argparse
    import sys

    from dichiarazioni_pubbliche.public_api import PublicApiError, load_index, projection_path_from_env

    parser = argparse.ArgumentParser(
        description="Regenerate the checked-in API contract artifacts."
    )
    parser.add_argument("--docs-dir", default="docs/api")
    args = parser.parse_args()

    loaded = None
    configured = projection_path_from_env()
    if configured:
        try:
            loaded = load_index(configured)
        except PublicApiError:
            # A missing projection must not fabricate a stable document; the
            # contract identity fields fall back to the pinned constants.
            loaded = None
    for written in write_docs(args.docs_dir, loaded):
        print(written)
    sys.exit(0)

__all__ = [
    "DEPRECATION_POLICY",
    "FICTIONAL_EVIDENCE_URL",
    "FICTIONAL_SOURCE_URL",
    "OPENAPI_VERSION",
    "build_api_readme",
    "build_llms_txt",
    "build_openapi_document",
    "fictional_dossier",
    "fictional_summary",
    "openapi_document_bytes",
    "write_docs",
    "write_openapi_document",
]
