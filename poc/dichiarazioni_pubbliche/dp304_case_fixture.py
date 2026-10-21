"""DP-304 fictional case fixture: one public-role statement, deliberately contaminated.

The row is an *operational* record: it carries raw transcript text, an evidence
excerpt, reviewer notes, contact/identity data and sensitive markers so the
deny-by-default gates can be exercised against realistic contamination. Every
sentinel is fictional and must never reach a public surface.

This module is pure data plus one selector table; it performs no I/O.
"""

from __future__ import annotations

import hashlib
from typing import Any

from dichiarazioni_pubbliche.citation_assurance import assertion_text_sha256
from dichiarazioni_pubbliche.policy.privacy_policy import DataClass
from dichiarazioni_pubbliche.wording_contract import wording_contract_metadata

CASE_SUBJECT = "person:dp304-canary-council-member"
CASE_RECORD = "finding:dp304-canary-0001"
CASE_CLAIM = "claim:dp304-canary-0001"
CASE_CONTENT = "content:dp304-canary"

SENTINELS: dict[str, str] = {
    "raw_transcript": "DP304-CANARY-RAW-TRANSCRIPT-MUST-NOT-ESCAPE",
    "evidence_excerpt": "DP304-CANARY-EVIDENCE-EXCERPT-MUST-NOT-ESCAPE",
    "reviewer_note": "DP304-CANARY-REVIEWER-NOTE-MUST-NOT-ESCAPE",
    "contact_email": "dp304.canary.contact@example.test",
    "exact_private_location": "DP304-CANARY-EXACT-PRIVATE-LOCATION",
    "identity_document": "DP304CANARYDOC000001",
    "minor_reference": "DP304-CANARY-MINOR-REFERENCE",
    "victim_reference": "DP304-CANARY-VICTIM-REFERENCE",
    "health_note": "DP304-CANARY-HEALTH-NOTE",
}

# field_name, data_class, relevance_reason, explicitly_approved, expect_public.
# Only the five allowlisted fields may be published; the rest must be refused or
# held even when a reviewer marks them "approved".
CASE_FIELDS: tuple[tuple[str, DataClass, str | None, bool, bool], ...] = (
    ("finding_id", DataClass.PUBLIC_CORE, "PUBLIC_ROLE", False, True),
    ("person_name", DataClass.PUBLIC_CORE, "PUBLIC_ROLE", False, True),
    ("public_role_interval", DataClass.PUBLIC_CORE, "PUBLIC_ROLE", False, True),
    ("source_url", DataClass.PUBLIC_CORE, "OFFICIAL_RECORD", False, True),
    ("normalized_claim", DataClass.PUBLIC_SAFE_TEXT, "PUBLIC_ROLE", True, True),
    ("raw_transcript", DataClass.OPERATIONAL_PRIVATE, "PUBLIC_ROLE", False, False),
    ("evidence_excerpt", DataClass.OPERATIONAL_PRIVATE, "OFFICIAL_RECORD", True, False),
    ("reviewer_note", DataClass.OPERATIONAL_PRIVATE, "PUBLIC_ROLE", False, False),
    ("contact_email", DataClass.HIGH_RISK_IDENTITY, "PUBLIC_ROLE", True, False),
    ("exact_private_location", DataClass.HIGH_RISK_IDENTITY, "PUBLIC_ROLE", True, False),
    ("identity_document", DataClass.HIGH_RISK_IDENTITY, "PUBLIC_ROLE", True, False),
    ("minor_reference", DataClass.HIGH_RISK_IDENTITY, "PUBLIC_ROLE", True, False),
    ("victim_reference", DataClass.SENSITIVE_CANDIDATE, "PUBLIC_ROLE", True, False),
    ("health_note", DataClass.SENSITIVE_CANDIDATE, "PUBLIC_ROLE", True, False),
)


def case_row() -> dict[str, Any]:
    """Operational row for the fictional statement, with private sentinels."""
    claim = "Il consiglio comunale ha approvato il bilancio con 12 voti favorevoli."
    source_text = "Il consiglio comunale ha approvato il bilancio con dodici voti favorevoli."
    quote_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    mention = "Consigliere Comunale Fittizio"
    rationale = "Il verbale ufficiale della seduta riporta l'esito della votazione."
    return {
        "finding_id": CASE_RECORD,
        "claim_id": CASE_CLAIM,
        "assessment": "SUPPORTED",
        "rationale": rationale,
        "finding_assertion_sha256": assertion_text_sha256(rationale),
        "publication_status": "PUBLISH",
        "policy_version": "policy-v1",
        "verification_run_id": "verification:dp304-canary",
        "created_at": "2026-10-20T09:00:00+00:00",
        "published_at": "2026-10-20T09:30:00+00:00",
        "publication_review_ids": ["review:dp304-canary-finding"],
        "supersedes_id": None,
        "normalized_claim": claim,
        "source_occurrence_quote_sha256": quote_sha,
        "wording": wording_contract_metadata(
            occurrence_id="statement:dp304-canary",
            source_text_sha256=quote_sha,
            normalized_claim=claim,
            language="it",
            derivation_version="candidate-extraction-v1",
            source_provenance={
                "selector_type": "MEDIA_SEGMENT_REF",
                "canonical_segment_id": "segment:dp304-canary",
                "quote_local_start_char": 0,
                "quote_local_end_char": len(claim),
            },
        ),
        "claim_type": "NUMERIC_STATISTIC",
        "temporal_scope": {
            "statement_date": "2026-10-19",
            "valid_from": None,
            "valid_until": None,
        },
        "check_worthy": True,
        "content_id": CASE_CONTENT,
        "source_url": "https://example.test/dp304-canary",
        "source_title": "Verbale della seduta",
        "source_published_at": "2026-10-19T18:00:00+00:00",
        "speaker": {
            "id": CASE_SUBJECT,
            "name": "Consigliere Comunale Fittizio",
            "public_role": "Consigliere comunale",
            "public_roles": [
                {
                    "organization_id": "org:dp304-canary",
                    "organization_name": "Comune Fittizio",
                    "role": "Consigliere comunale",
                    "start_date": "2026-01-01",
                    "end_date": None,
                    "review_event_ids": ["review:dp304-canary-role"],
                }
            ],
        },
        "source_segments": [
            {
                "segment_id": "segment:dp304-canary",
                "segment_index": 0,
                "start_ms": 0,
                "end_ms": 15_000,
                "transcript_candidates": [
                    {
                        "segment_id": "segment:dp304-canary-raw",
                        "variant_id": "transcript:dp304-canary",
                        "provider_id": "local-fixture",
                        "source_kind": "PLATFORM_CAPTION",
                        "transcript_sha256": hashlib.sha256(
                            SENTINELS["raw_transcript"].encode()
                        ).hexdigest(),
                    }
                ],
            }
        ],
        "evidence": [
            {
                "id": "evidence:dp304-canary",
                "url": "https://example.test/dp304-canary-verbale",
                "publisher": "Comune Fittizio",
                "source_type": "PRIMARY_OFFICIAL",
                "publication_date": "2026-10-19",
                "observed_at": "2026-10-20T09:05:00+00:00",
                "content_sha256": "a" * 64,
                "reference_period": "2026",
                "rights_status": "UNKNOWN",
                "relation": "VERIFICATION_INPUT",
                "verification_observation_ids": ["evidence-observation:dp304-canary"],
                "evidence_review_ids": ["review:dp304-canary-evidence"],
                "observation_review_ids": ["review:dp304-canary-observation"],
                "excerpt": SENTINELS["evidence_excerpt"],
            }
        ],
        "existing_factchecks": [],
        "corrections": [],
        "rights_of_reply": [],
        "speaker_provenance": [
            {
                "candidate_id": "speaker-candidate:dp304-canary",
                "review_event_ids": ["review:dp304-canary-speaker"],
            }
        ],
        "public_attribution_input": {
            "speaker_candidates": [
                {
                    "id": "speaker-candidate:dp304-canary",
                    "content_id": CASE_CONTENT,
                    "person_id": CASE_SUBJECT,
                    "start_ms": 0,
                    "end_ms": 15_000,
                    "speaker_label": SENTINELS["raw_transcript"],
                    "attribution_method": "MANUAL_REVIEW",
                    "attribution_version": "speaker-attribution-v1",
                    "source_ref": {"private_feature": SENTINELS["reviewer_note"]},
                    "confidence": 0.99,
                    "status": "APPROVED",
                    "review_event_ids": ["review:dp304-canary-speaker"],
                }
            ],
            "resolution_candidates": [
                {
                    "id": "resolution:dp304-canary",
                    "content_id": CASE_CONTENT,
                    "passage_id": "passage:dp304-canary",
                    "mention_text": mention,
                    "mention_text_sha256": hashlib.sha256(mention.encode()).hexdigest(),
                    "entity_type": "PERSON",
                    "target_id": CASE_SUBJECT,
                    "resolution_method": "MANUAL_REVIEW",
                    "resolution_version": "entity-resolution-v1",
                    "supporting_features": [
                        {"code": "IDENTIFIER_ID", "value": "identifier:dp304-canary"}
                    ],
                    "contradicting_features": [],
                    "retrieval_score": 0.95,
                    "status": "APPROVED",
                    "review_event_ids": ["review:dp304-canary-resolution"],
                }
            ],
            "identifiers": [
                {
                    "id": "identifier:dp304-canary",
                    "entity_type": "PERSON",
                    "entity_id": CASE_SUBJECT,
                    "identifier_kind": "OFFICIAL_PERSON_ID",
                    "identifier_value": SENTINELS["identity_document"],
                    "authority": "OFFICIAL_REGISTER",
                    "identifier_version": "entity-identifier-v1",
                    "source_ref": {"private_identifier_source": SENTINELS["reviewer_note"]},
                    "status": "ACTIVE",
                    "supersedes_id": None,
                }
            ],
            "role_intervals": [
                {
                    "id": "role:dp304-canary",
                    "person_id": CASE_SUBJECT,
                    "organization_id": "org:dp304-canary",
                    "organization_name": "Comune Fittizio",
                    "role": "Consigliere comunale",
                    "start_date": "2026-01-01",
                    "end_date": None,
                    "source_ref": {"private_role_source": SENTINELS["reviewer_note"]},
                    "status": "ACTIVE",
                    "review_event_ids": ["review:dp304-canary-role"],
                }
            ],
        },
        "raw_text": SENTINELS["raw_transcript"],
        "reviewer_note": SENTINELS["reviewer_note"],
        "contact_email": SENTINELS["contact_email"],
        "exact_private_location": SENTINELS["exact_private_location"],
        "identity_document": SENTINELS["identity_document"],
        "minor_reference": SENTINELS["minor_reference"],
        "victim_reference": SENTINELS["victim_reference"],
        "health_note": SENTINELS["health_note"],
    }
