from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from dichiarazioni_pubbliche.domain_vocabulary import (
    INFERENCE_VERSION,
    InferenceKind,
    InferenceRiskClass,
    InferenceSupportLevel,
)


INSERT_INFERENCE_CANDIDATE_SQL_V1 = """
WITH inserted AS (
    INSERT INTO inference_candidate (
        id, claim_id, conclusion_text, inference_kind, support_level,
        premise_refs, assumptions, alternative_hypotheses, countervailing_factors, disconfirmers,
        risk_class, inference_version, status, publication_blocked, metadata
    ) VALUES (
        :'id', :'claim_id', :'conclusion_text', :'inference_kind', :'support_level',
        :'premise_refs'::jsonb, :'assumptions'::jsonb,
        :'alternative_hypotheses'::jsonb, :'countervailing_factors'::jsonb, :'disconfirmers'::jsonb,
        :'risk_class', :'inference_version', 'CANDIDATE', true, :'metadata'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
)
SELECT EXISTS(SELECT 1 FROM inserted)::text;
""".strip()


ALLOWED_INFERENCE_FIELDS = frozenset(
    {
        "id",
        "claim_id",
        "conclusion_text",
        "inference_kind",
        "support_level",
        "premise_refs",
        "assumptions",
        "alternative_hypotheses",
        "countervailing_factors",
        "disconfirmers",
        "risk_class",
        "inference_version",
        "status",
        "publication_blocked",
        "metadata",
    }
)

REQUIRED_INFERENCE_FIELDS = frozenset(
    {
        "claim_id",
        "conclusion_text",
        "inference_kind",
        "support_level",
        "premise_refs",
    }
)


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"INFERENCE_{field_name.upper()}_REQUIRED")
    return value.strip()


def _string_tuple(value: Any, field_name: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError(f"INFERENCE_{field_name.upper()}_INVALID: expected list of strings")
    normalized = tuple(str(item).strip() for item in value if str(item).strip())
    if nonempty and not normalized:
        raise ValueError(f"INFERENCE_{field_name.upper()}_REQUIRED")
    return normalized


def deterministic_inference_id(
    *,
    claim_id: str,
    conclusion_text: str,
    inference_kind: str,
    premise_refs: tuple[str, ...] | list[str],
    inference_version: str = INFERENCE_VERSION,
) -> str:
    material = {
        "claim_id": _required_str(claim_id, "claim_id"),
        "conclusion_text": _required_str(conclusion_text, "conclusion_text"),
        "inference_kind": InferenceKind(inference_kind).value,
        "premise_refs": sorted(_string_tuple(premise_refs, "premise_refs", nonempty=True)),
        "inference_version": inference_version,
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "inference:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class InferenceCandidateRecord:
    claim_id: str
    conclusion_text: str
    inference_kind: str
    support_level: str
    premise_refs: tuple[str, ...]
    id: str | None = None
    assumptions: tuple[str, ...] = ()
    alternative_hypotheses: tuple[str, ...] = ()
    countervailing_factors: tuple[str, ...] = ()
    disconfirmers: tuple[str, ...] = ()
    risk_class: str = InferenceRiskClass.STANDARD.value
    inference_version: str = INFERENCE_VERSION
    status: str = "CANDIDATE"
    publication_blocked: bool = True
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _required_str(self.claim_id, "claim_id")
        _required_str(self.conclusion_text, "conclusion_text")
        InferenceKind(self.inference_kind)
        InferenceSupportLevel(self.support_level)
        InferenceRiskClass(self.risk_class)
        if self.inference_version != INFERENCE_VERSION:
            raise ValueError(
                f"INFERENCE_VERSION_MISMATCH: expected '{INFERENCE_VERSION}', got '{self.inference_version}'"
            )
        if self.status != "CANDIDATE":
            raise ValueError("INFERENCE_STATUS_INVALID: new inference records must be CANDIDATE")
        if self.publication_blocked is not True:
            raise ValueError(
                "INFERENCE_PUBLICATION_BLOCK_REQUIRED: reasoned inference v1 is private/review-only"
            )
        _string_tuple(self.premise_refs, "premise_refs", nonempty=True)
        if self.inference_kind in {
            InferenceKind.ABDUCTIVE_BEST_EXPLANATION.value,
            InferenceKind.STATISTICAL.value,
            InferenceKind.EXCLUSION.value,
            InferenceKind.COMPOSITE.value,
        } and not self.alternative_hypotheses:
            raise ValueError(
                "INFERENCE_ALTERNATIVES_REQUIRED: non-deductive inference must record alternatives"
            )
        if self.risk_class in {
            InferenceRiskClass.CRIMINAL_ALLEGATION.value,
            InferenceRiskClass.IDENTITY_ATTRIBUTION.value,
            InferenceRiskClass.INTENT_ATTRIBUTION.value,
        }:
            if not self.countervailing_factors:
                raise ValueError(
                    "INFERENCE_COUNTERVAILING_FACTORS_REQUIRED: high-risk inference must record facts that cut against or complicate the conclusion"
                )
            if not self.disconfirmers:
                raise ValueError(
                    "INFERENCE_DISCONFIRMERS_REQUIRED: high-risk inference must state what would weaken it"
                )

    @property
    def resolved_id(self) -> str:
        return self.id or deterministic_inference_id(
            claim_id=self.claim_id,
            conclusion_text=self.conclusion_text,
            inference_kind=self.inference_kind,
            premise_refs=self.premise_refs,
            inference_version=self.inference_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.resolved_id,
            "claim_id": self.claim_id,
            "conclusion_text": self.conclusion_text,
            "inference_kind": self.inference_kind,
            "support_level": self.support_level,
            "premise_refs": list(self.premise_refs),
            "assumptions": list(self.assumptions),
            "alternative_hypotheses": list(self.alternative_hypotheses),
            "countervailing_factors": list(self.countervailing_factors),
            "disconfirmers": list(self.disconfirmers),
            "risk_class": self.risk_class,
            "inference_version": self.inference_version,
            "status": self.status,
            "publication_blocked": self.publication_blocked,
            "metadata": dict(self.metadata or {}),
        }


def normalize_inference_candidate_record(data: Any) -> InferenceCandidateRecord:
    if isinstance(data, InferenceCandidateRecord):
        return data
    if hasattr(data, "__dataclass_fields__") and not isinstance(data, type):
        data = asdict(data)
    elif not isinstance(data, Mapping):
        raise ValueError(
            f"INFERENCE_RECORD_INVALID_TYPE: expected Mapping or InferenceCandidateRecord, got {type(data).__name__}"
        )

    unknown = set(data.keys()) - ALLOWED_INFERENCE_FIELDS
    if unknown:
        raise ValueError(
            f"INFERENCE_RECORD_UNKNOWN_FIELDS: unexpected key(s) {sorted(unknown)}"
        )
    missing = REQUIRED_INFERENCE_FIELDS - set(data.keys())
    if missing:
        raise ValueError(
            f"INFERENCE_RECORD_MISSING_FIELDS: missing required key(s) {sorted(missing)}"
        )

    claim_id = _required_str(data["claim_id"], "claim_id")
    conclusion_text = _required_str(data["conclusion_text"], "conclusion_text")
    try:
        inference_kind = InferenceKind(str(data["inference_kind"])).value
    except ValueError as exc:
        raise ValueError("INFERENCE_KIND_INVALID") from exc
    try:
        support_level = InferenceSupportLevel(str(data["support_level"])).value
    except ValueError as exc:
        raise ValueError("INFERENCE_SUPPORT_LEVEL_INVALID") from exc
    try:
        risk_class = InferenceRiskClass(
            str(data.get("risk_class", InferenceRiskClass.STANDARD.value))
        ).value
    except ValueError as exc:
        raise ValueError("INFERENCE_RISK_CLASS_INVALID") from exc

    version = str(data.get("inference_version", INFERENCE_VERSION))
    status = str(data.get("status", "CANDIDATE"))
    publication_blocked = data.get("publication_blocked", True)
    if publication_blocked is not True:
        raise ValueError(
            "INFERENCE_PUBLICATION_BLOCK_REQUIRED: reasoned inference v1 is private/review-only"
        )

    premise_refs = _string_tuple(data["premise_refs"], "premise_refs", nonempty=True)
    assumptions = _string_tuple(data.get("assumptions", ()), "assumptions")
    alternatives = _string_tuple(
        data.get("alternative_hypotheses", ()), "alternative_hypotheses"
    )
    countervailing_factors = _string_tuple(
        data.get("countervailing_factors", ()), "countervailing_factors"
    )
    disconfirmers = _string_tuple(data.get("disconfirmers", ()), "disconfirmers")
    metadata_raw = data.get("metadata", {})
    if metadata_raw is None:
        metadata: dict[str, Any] = {}
    elif isinstance(metadata_raw, Mapping):
        metadata = dict(metadata_raw)
    else:
        raise ValueError("INFERENCE_METADATA_INVALID")

    supplied_id = data.get("id")
    if supplied_id is not None:
        supplied_id = _required_str(supplied_id, "id")

    return InferenceCandidateRecord(
        id=supplied_id,
        claim_id=claim_id,
        conclusion_text=conclusion_text,
        inference_kind=inference_kind,
        support_level=support_level,
        premise_refs=premise_refs,
        assumptions=assumptions,
        alternative_hypotheses=alternatives,
        countervailing_factors=countervailing_factors,
        disconfirmers=disconfirmers,
        risk_class=risk_class,
        inference_version=version,
        status=status,
        publication_blocked=True,
        metadata=metadata,
    )


def inference_candidate_to_sql_parameters(
    record: InferenceCandidateRecord | Mapping[str, Any],
) -> dict[str, Any]:
    norm = normalize_inference_candidate_record(record)
    return {
        "id": norm.resolved_id,
        "claim_id": norm.claim_id,
        "conclusion_text": norm.conclusion_text,
        "inference_kind": norm.inference_kind,
        "support_level": norm.support_level,
        "premise_refs": json.dumps(list(norm.premise_refs), ensure_ascii=False),
        "assumptions": json.dumps(list(norm.assumptions), ensure_ascii=False),
        "alternative_hypotheses": json.dumps(
            list(norm.alternative_hypotheses), ensure_ascii=False
        ),
        "countervailing_factors": json.dumps(
            list(norm.countervailing_factors), ensure_ascii=False
        ),
        "disconfirmers": json.dumps(list(norm.disconfirmers), ensure_ascii=False),
        "risk_class": norm.risk_class,
        "inference_version": norm.inference_version,
        "metadata": json.dumps(norm.metadata or {}, ensure_ascii=False),
    }


__all__ = [
    "ALLOWED_INFERENCE_FIELDS",
    "INSERT_INFERENCE_CANDIDATE_SQL_V1",
    "REQUIRED_INFERENCE_FIELDS",
    "InferenceCandidateRecord",
    "deterministic_inference_id",
    "inference_candidate_to_sql_parameters",
    "normalize_inference_candidate_record",
]
