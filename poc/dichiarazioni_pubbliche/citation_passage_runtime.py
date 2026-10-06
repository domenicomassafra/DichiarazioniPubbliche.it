from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Protocol

from dichiarazioni_pubbliche.citation_assurance import CITATION_RELATIONS


PASSAGE_CITATION_BINDING_VERSION = "finding-passage-citation-binding-v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SqlRunner(Protocol):
    def run(self, sql: str, **variables: object) -> str: ...


@dataclass(frozen=True)
class PersistedPassageCitationBinding:
    citation_id: str
    assertion_id: str
    evidence_id: str
    passage_id: str
    relation: str
    passage_text_sha256: str
    source_content_sha256: str
    verification_run_id: str
    binding_version: str = PASSAGE_CITATION_BINDING_VERSION


def _required_text(value: object, code: str, *, maximum: int = 512) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"DP224_{code}_REQUIRED")
    if len(text) > maximum:
        raise ValueError(f"DP224_{code}_TOO_LONG")
    return text


def _sha256(value: object, code: str) -> str:
    text = _required_text(value, code, maximum=64).lower()
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f"DP224_{code}_INVALID")
    return text


def deterministic_passage_citation_id(
    *,
    assertion_id: str,
    evidence_id: str,
    passage_id: str,
    relation: str,
    passage_text_sha256: str,
    source_content_sha256: str,
) -> str:
    assertion = _required_text(assertion_id, "ASSERTION_ID")
    evidence = _required_text(evidence_id, "EVIDENCE_ID")
    passage = _required_text(passage_id, "PASSAGE_ID")
    relation_value = _required_text(relation, "RELATION", maximum=32).upper()
    if relation_value not in CITATION_RELATIONS:
        raise ValueError("DP224_RELATION_INVALID")
    passage_hash = _sha256(passage_text_sha256, "PASSAGE_TEXT_SHA256")
    source_hash = _sha256(source_content_sha256, "SOURCE_CONTENT_SHA256")
    material = "\0".join(
        (
            PASSAGE_CITATION_BINDING_VERSION,
            assertion,
            evidence,
            passage,
            relation_value,
            passage_hash,
            source_hash,
        )
    ).encode("utf-8")
    return "finding-citation-passage:" + hashlib.sha256(material).hexdigest()


_PERSIST_PASSAGE_CITATION_SQL = r"""
WITH eligible AS (
    SELECT
        assertion.id AS assertion_id,
        finding.verification_run_id,
        cited_evidence.id AS evidence_id,
        cited_passage.id AS passage_id
    FROM finding_assertion assertion
    JOIN finding
      ON finding.id = assertion.finding_id
    JOIN verification_run verification
      ON verification.id = finding.verification_run_id
     AND verification.claim_id = finding.claim_id
    JOIN finding_evidence source_link
      ON source_link.finding_id = finding.id
     AND source_link.evidence_id = :'evidence_id'
    JOIN evidence cited_evidence
      ON cited_evidence.id = source_link.evidence_id
    JOIN passage cited_passage
      ON cited_passage.id = :'passage_id'
    JOIN content_capture cited_capture
      ON cited_capture.id = cited_passage.capture_id
     AND cited_capture.content_id = cited_passage.content_id
    WHERE
        assertion.id = :'assertion_id'
        AND assertion.material = true
        AND assertion.required_relation = :'relation'
        AND jsonb_typeof(verification.evidence_ids) = 'array'
        AND verification.evidence_ids ? cited_evidence.id
        AND cited_passage.text_sha256 = :'passage_text_sha256'
        AND cited_capture.content_sha256 = :'source_content_sha256'
        AND cited_evidence.content_sha256 = :'source_content_sha256'
        AND (
            cited_passage.private_text IS NULL
            OR encode(
                sha256(convert_to(cited_passage.private_text, 'UTF8')),
                'hex'
            ) = :'passage_text_sha256'
        )
        AND NOT EXISTS (
            SELECT 1
            FROM evidence_observation structured_observation
            WHERE structured_observation.evidence_id = cited_evidence.id
        )
        AND EXISTS (
            SELECT 1
            FROM claim_evidence_candidate candidate
            WHERE
                candidate.claim_id = finding.claim_id
                AND candidate.evidence_id = cited_evidence.id
                AND candidate.status = 'APPROVED'
                AND EXISTS (
                    SELECT 1
                    FROM review_event evidence_review
                    WHERE
                        evidence_review.entity_type = 'CLAIM_EVIDENCE_CANDIDATE'
                        AND evidence_review.entity_id =
                            candidate.claim_id || '|' ||
                            candidate.evidence_id || '|' ||
                            candidate.retrieval_version
                        AND evidence_review.action = 'APPROVED'
                )
        )
),
inserted AS (
    INSERT INTO finding_assertion_citation (
        id,
        assertion_id,
        evidence_id,
        observation_id,
        passage_id,
        passage_text_sha256,
        source_content_sha256,
        relation,
        citation_version,
        metadata
    )
    SELECT
        :'citation_id',
        eligible.assertion_id,
        eligible.evidence_id,
        NULL,
        eligible.passage_id,
        :'passage_text_sha256',
        :'source_content_sha256',
        :'relation',
        'finding-citation-v1',
        jsonb_build_object(
            'binding_version', :'binding_version',
            'verification_run_id', eligible.verification_run_id
        )
    FROM eligible
    ON CONFLICT DO NOTHING
    RETURNING id
),
current_exact AS (
    SELECT
        inserted.id,
        eligible.verification_run_id
    FROM inserted
    CROSS JOIN eligible
    UNION ALL
    SELECT
        citation.id,
        eligible.verification_run_id
    FROM finding_assertion_citation citation
    JOIN eligible
      ON eligible.assertion_id = citation.assertion_id
     AND eligible.evidence_id = citation.evidence_id
     AND eligible.passage_id = citation.passage_id
    WHERE
        citation.id = :'citation_id'
        AND citation.observation_id IS NULL
        AND citation.relation = :'relation'
        AND citation.citation_version = 'finding-citation-v1'
        AND citation.passage_text_sha256 = :'passage_text_sha256'
        AND citation.source_content_sha256 = :'source_content_sha256'
        AND citation.metadata->>'binding_version' = :'binding_version'
        AND citation.metadata->>'verification_run_id' =
            eligible.verification_run_id
        AND finding_assertion_passage_binding_valid(citation.id)
)
SELECT json_build_object(
    'citation_id', current_exact.id,
    'assertion_id', :'assertion_id',
    'evidence_id', :'evidence_id',
    'passage_id', :'passage_id',
    'relation', :'relation',
    'passage_text_sha256', :'passage_text_sha256',
    'source_content_sha256', :'source_content_sha256',
    'verification_run_id', current_exact.verification_run_id,
    'binding_version', :'binding_version'
)::text
FROM current_exact;
"""


def persist_unstructured_passage_citation(
    store: SqlRunner,
    *,
    assertion_id: str,
    evidence_id: str,
    passage_id: str,
    relation: str,
    passage_text_sha256: str,
    source_content_sha256: str,
) -> PersistedPassageCitationBinding:
    assertion = _required_text(assertion_id, "ASSERTION_ID")
    evidence = _required_text(evidence_id, "EVIDENCE_ID")
    passage = _required_text(passage_id, "PASSAGE_ID")
    relation_value = _required_text(relation, "RELATION", maximum=32).upper()
    if relation_value not in CITATION_RELATIONS:
        raise ValueError("DP224_RELATION_INVALID")
    passage_hash = _sha256(passage_text_sha256, "PASSAGE_TEXT_SHA256")
    source_hash = _sha256(source_content_sha256, "SOURCE_CONTENT_SHA256")
    citation_id = deterministic_passage_citation_id(
        assertion_id=assertion,
        evidence_id=evidence,
        passage_id=passage,
        relation=relation_value,
        passage_text_sha256=passage_hash,
        source_content_sha256=source_hash,
    )
    raw = store.run(
        _PERSIST_PASSAGE_CITATION_SQL,
        citation_id=citation_id,
        assertion_id=assertion,
        evidence_id=evidence,
        passage_id=passage,
        relation=relation_value,
        passage_text_sha256=passage_hash,
        source_content_sha256=source_hash,
        binding_version=PASSAGE_CITATION_BINDING_VERSION,
    )
    if not raw:
        raise ValueError("DP224_PASSAGE_CITATION_BINDING_NOT_ELIGIBLE")
    payload = json.loads(raw)
    return PersistedPassageCitationBinding(
        citation_id=str(payload["citation_id"]),
        assertion_id=str(payload["assertion_id"]),
        evidence_id=str(payload["evidence_id"]),
        passage_id=str(payload["passage_id"]),
        relation=str(payload["relation"]),
        passage_text_sha256=str(payload["passage_text_sha256"]),
        source_content_sha256=str(payload["source_content_sha256"]),
        verification_run_id=str(payload["verification_run_id"]),
        binding_version=str(payload["binding_version"]),
    )


__all__ = [
    "PASSAGE_CITATION_BINDING_VERSION",
    "PersistedPassageCitationBinding",
    "SqlRunner",
    "deterministic_passage_citation_id",
    "persist_unstructured_passage_citation",
]
