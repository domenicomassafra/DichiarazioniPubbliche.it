from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from dichiarazioni_pubbliche.domain_vocabulary import (
    FINDING_PUBLICATION_STATUS_VERSION,
    VERIFICATION_ASSESSMENT_VERSION,
    FindingPublicationStatus,
    VerificationAssessment,
)


INSERT_FINDING_DRAFT_SQL_V1 = f"""
WITH eligible AS (
    SELECT 1
    FROM verification_run verification
    WHERE
        verification.id = :'verification_run_id'
        AND verification.claim_id = :'claim_id'
        AND verification.assessment = :'assessment'
        AND verification.evidence_ids @> :'evidence_ids'::jsonb
        AND :'evidence_ids'::jsonb @> verification.evidence_ids
),
inserted AS (
    INSERT INTO finding (
        id, claim_id, assessment, assessment_version, rationale,
        publication_status, publication_status_version,
        policy_version, model_bundle, verification_run_id,
        supersedes_id
    )
    SELECT
        :'finding_id', :'claim_id', :'assessment',
        '{VERIFICATION_ASSESSMENT_VERSION}', :'rationale',
        :'publication_status', '{FINDING_PUBLICATION_STATUS_VERSION}',
        :'policy_version',
        :'model_bundle'::jsonb, :'verification_run_id',
        NULLIF(:'supersedes_id','')
    FROM eligible
    ON CONFLICT (id) DO NOTHING
    RETURNING id
),
linked AS (
    INSERT INTO finding_evidence (finding_id, evidence_id, relation)
    SELECT inserted.id, evidence_id_row.value, 'VERIFICATION_INPUT'
    FROM inserted
    CROSS JOIN LATERAL jsonb_array_elements_text(
        :'evidence_ids'::jsonb
    ) evidence_id_row(value)
    JOIN evidence source ON source.id = evidence_id_row.value
    ON CONFLICT DO NOTHING
    RETURNING finding_id
)
SELECT EXISTS(SELECT 1 FROM inserted)::text;
""".strip()



ALLOWED_FINDING_RECORD_FIELDS = frozenset(
    {
        "finding_id",
        "claim_id",
        "verification_run_id",
        "assessment",
        "assessment_version",
        "rationale",
        "publication_status",
        "publication_status_version",
        "policy_version",
        "evidence_ids",
        "model_bundle",
        "supersedes_id",
    }
)

REQUIRED_FINDING_RECORD_FIELDS = frozenset(
    {
        "finding_id",
        "claim_id",
        "verification_run_id",
        "assessment",
        "rationale",
        "publication_status",
        "policy_version",
    }
)


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"FINDING_{field_name.upper()}_REQUIRED")
    return value.strip()


@dataclass(frozen=True)
class FindingRecord:
    finding_id: str
    claim_id: str
    verification_run_id: str
    assessment: str
    assessment_version: str
    rationale: str
    publication_status: str
    publication_status_version: str
    policy_version: str
    evidence_ids: tuple[str, ...]
    model_bundle: dict[str, Any]
    supersedes_id: str | None = None

    def __post_init__(self) -> None:
        if self.assessment_version != VERIFICATION_ASSESSMENT_VERSION:
            raise ValueError(
                f"FINDING_ASSESSMENT_VERSION_MISMATCH: expected '{VERIFICATION_ASSESSMENT_VERSION}', got '{self.assessment_version}'"
            )
        if self.publication_status_version != FINDING_PUBLICATION_STATUS_VERSION:
            raise ValueError(
                f"FINDING_PUBLICATION_STATUS_VERSION_MISMATCH: expected '{FINDING_PUBLICATION_STATUS_VERSION}', got '{self.publication_status_version}'"
            )
        try:
            VerificationAssessment(self.assessment)
        except ValueError as exc:
            raise ValueError(
                f"FINDING_ASSESSMENT_INVALID: '{self.assessment}' is not a valid VerificationAssessment"
            ) from exc
        try:
            FindingPublicationStatus(self.publication_status)
        except ValueError as exc:
            raise ValueError(
                f"FINDING_PUBLICATION_STATUS_INVALID: '{self.publication_status}' is not a valid FindingPublicationStatus"
            ) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "claim_id": self.claim_id,
            "verification_run_id": self.verification_run_id,
            "assessment": self.assessment,
            "assessment_version": self.assessment_version,
            "rationale": self.rationale,
            "publication_status": self.publication_status,
            "publication_status_version": self.publication_status_version,
            "policy_version": self.policy_version,
            "evidence_ids": list(self.evidence_ids),
            "model_bundle": dict(self.model_bundle),
            "supersedes_id": self.supersedes_id,
        }




def normalize_finding_record(data: Any) -> FindingRecord:
    if isinstance(data, FindingRecord):
        return data
    if hasattr(data, "__dataclass_fields__") and not isinstance(data, type):
        data = asdict(data)
    elif not isinstance(data, Mapping):
        raise ValueError(
            f"FINDING_RECORD_INVALID_TYPE: expected Mapping or FindingRecord, got {type(data).__name__}"
        )

    unknown = set(data.keys()) - ALLOWED_FINDING_RECORD_FIELDS
    if unknown:
        raise ValueError(
            f"FINDING_RECORD_UNKNOWN_FIELDS: unexpected key(s) {sorted(unknown)}"
        )

    missing = REQUIRED_FINDING_RECORD_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"FINDING_RECORD_MISSING_FIELDS: missing required key(s) {sorted(missing)}"
        )

    finding_id = _required_str(data["finding_id"], "finding_id")
    claim_id = _required_str(data["claim_id"], "claim_id")
    verification_run_id = _required_str(
        data["verification_run_id"], "verification_run_id"
    )

    assessment_raw = data["assessment"]
    try:
        if isinstance(assessment_raw, VerificationAssessment):
            assessment = assessment_raw.value
        else:
            assessment = VerificationAssessment(str(assessment_raw)).value
    except ValueError as exc:
        raise ValueError(
            f"FINDING_ASSESSMENT_INVALID: '{assessment_raw}' is not a valid VerificationAssessment"
        ) from exc

    assessment_version = data.get(
        "assessment_version", VERIFICATION_ASSESSMENT_VERSION
    )
    if assessment_version != VERIFICATION_ASSESSMENT_VERSION:
        raise ValueError(
            f"FINDING_ASSESSMENT_VERSION_MISMATCH: expected '{VERIFICATION_ASSESSMENT_VERSION}', got '{assessment_version}'"
        )

    rationale = str(data["rationale"])

    status_raw = data["publication_status"]
    try:
        if isinstance(status_raw, FindingPublicationStatus):
            publication_status = status_raw.value
        else:
            publication_status = FindingPublicationStatus(str(status_raw)).value
    except ValueError as exc:
        raise ValueError(
            f"FINDING_PUBLICATION_STATUS_INVALID: '{status_raw}' is not a valid FindingPublicationStatus"
        ) from exc

    status_version = data.get(
        "publication_status_version", FINDING_PUBLICATION_STATUS_VERSION
    )
    if status_version != FINDING_PUBLICATION_STATUS_VERSION:
        raise ValueError(
            f"FINDING_PUBLICATION_STATUS_VERSION_MISMATCH: expected '{FINDING_PUBLICATION_STATUS_VERSION}', got '{status_version}'"
        )

    policy_version = _required_str(data["policy_version"], "policy_version")

    evidence_ids_raw = data.get("evidence_ids", ())
    if not isinstance(evidence_ids_raw, (list, tuple, set, frozenset)):
        raise ValueError(
            "FINDING_EVIDENCE_IDS_INVALID: expected iterable of strings"
        )
    evidence_ids = tuple(
        _required_str(eid, "evidence_id") for eid in evidence_ids_raw
    )

    model_bundle_raw = data.get("model_bundle", {})
    if not isinstance(model_bundle_raw, Mapping):
        raise ValueError("FINDING_MODEL_BUNDLE_INVALID: expected dict/mapping")
    model_bundle = dict(model_bundle_raw)

    supersedes_id_raw = data.get("supersedes_id")
    if supersedes_id_raw is None or (
        isinstance(supersedes_id_raw, str) and not supersedes_id_raw.strip()
    ):
        supersedes_id = None
    else:
        supersedes_id = _required_str(supersedes_id_raw, "supersedes_id")

    return FindingRecord(
        finding_id=finding_id,
        claim_id=claim_id,
        verification_run_id=verification_run_id,
        assessment=assessment,
        assessment_version=assessment_version,
        rationale=rationale,
        publication_status=publication_status,
        publication_status_version=status_version,
        policy_version=policy_version,
        evidence_ids=evidence_ids,
        model_bundle=model_bundle,
        supersedes_id=supersedes_id,
    )




def finding_record_to_sql_parameters(
    record: FindingRecord | Mapping[str, Any],
) -> dict[str, Any]:
    norm = normalize_finding_record(record)
    return {
        "finding_id": norm.finding_id,
        "claim_id": norm.claim_id,
        "verification_run_id": norm.verification_run_id,
        "assessment": norm.assessment,
        "rationale": norm.rationale,
        "publication_status": norm.publication_status,
        "policy_version": norm.policy_version,
        "model_bundle": json.dumps(
            norm.model_bundle,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "supersedes_id": norm.supersedes_id or "",
        "evidence_ids": json.dumps(
            list(norm.evidence_ids),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }


# Compatibility aliases retained by the module's public export surface.
FINDING_INSERT_STATEMENT_V1 = INSERT_FINDING_DRAFT_SQL_V1
FindingDraftRecord = FindingRecord
normalize_finding_draft = normalize_finding_record


__all__ = [
    "ALLOWED_FINDING_RECORD_FIELDS",
    "FINDING_INSERT_STATEMENT_V1",
    "FindingDraftRecord",
    "FindingRecord",
    "INSERT_FINDING_DRAFT_SQL_V1",
    "REQUIRED_FINDING_RECORD_FIELDS",
    "finding_record_to_sql_parameters",
    "normalize_finding_draft",
    "normalize_finding_record",
]
