from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from dichiarazioni_pubbliche.domain_vocabulary import (
    VERIFICATION_ASSESSMENT_VERSION,
    VerificationAssessment,
)


INSERT_VERIFICATION_RUN_SQL_V1 = f"""
WITH inserted AS (
    INSERT INTO verification_run (
        id, claim_id, verification_kind, verification_version,
        verification_rule, input_fingerprint, statement_cutoff,
        assessment, evidence_ids, observation_ids, blockers,
        rationale_codes, result
    ) VALUES (
        :'run_id', :'claim_id', :'verification_kind',
        '{VERIFICATION_ASSESSMENT_VERSION}', :'verification_rule'::jsonb,
        :'input_fingerprint', :'statement_cutoff'::date,
        :'assessment', :'evidence_ids'::jsonb,
        :'observation_ids'::jsonb, :'blockers'::jsonb,
        :'rationale_codes'::jsonb, :'result'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
)
SELECT EXISTS(SELECT 1 FROM inserted)::text;
""".strip()



LATEST_VERIFICATION_TEMPLATE_SQL_V1 = """
SELECT COALESCE(json_build_object(
    'verification_kind', verification_kind,
    'verification_rule', verification_rule,
    'statement_cutoff', statement_cutoff::text,
    'verification_version', verification_version
)::text, '')
FROM verification_run
WHERE claim_id = :'claim_id'
ORDER BY created_at DESC, id DESC
LIMIT 1;
""".strip()



ALLOWED_VERIFICATION_RUN_FIELDS = frozenset(
    {
        "id",
        "run_id",
        "claim_id",
        "verification_kind",
        "verification_version",
        "verification_rule",
        "input_fingerprint",
        "statement_cutoff",
        "assessment",
        "evidence_ids",
        "observation_ids",
        "blockers",
        "rationale_codes",
        "result",
    }
)

REQUIRED_VERIFICATION_RUN_FIELDS = frozenset(
    {
        "run_id",
        "claim_id",
        "verification_kind",
        "verification_rule",
        "input_fingerprint",
        "statement_cutoff",
        "assessment",
    }
)


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"VERIFICATION_{field_name.upper()}_REQUIRED")
    return value.strip()


def _iso_date(value: Any, field_name: str) -> str:
    text = _required_str(value, field_name)
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        raise ValueError(f"VERIFICATION_{field_name.upper()}_INVALID_DATE")
    if not (text[:4].isdigit() and text[5:7].isdigit() and text[8:].isdigit()):
        raise ValueError(f"VERIFICATION_{field_name.upper()}_INVALID_DATE")
    return text


@dataclass(frozen=True)
class VerificationRunRecord:
    run_id: str
    claim_id: str
    verification_kind: str
    verification_rule: dict[str, Any]
    input_fingerprint: str
    statement_cutoff: str
    assessment: str
    verification_version: str = VERIFICATION_ASSESSMENT_VERSION
    evidence_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    rationale_codes: tuple[str, ...] = ()
    result: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required_str(self.run_id, "run_id")
        _required_str(self.claim_id, "claim_id")
        _required_str(self.verification_kind, "verification_kind")
        _required_str(self.input_fingerprint, "input_fingerprint")
        _iso_date(self.statement_cutoff, "statement_cutoff")

        if self.verification_version != VERIFICATION_ASSESSMENT_VERSION:
            raise ValueError(
                f"VERIFICATION_VERSION_MISMATCH: expected '{VERIFICATION_ASSESSMENT_VERSION}', got '{self.verification_version}'"
            )
        try:
            VerificationAssessment(self.assessment)
        except ValueError as exc:
            raise ValueError(
                f"VERIFICATION_ASSESSMENT_INVALID: '{self.assessment}' is not a valid VerificationAssessment"
            ) from exc

        if not isinstance(self.verification_rule, Mapping):
            raise ValueError("VERIFICATION_RULE_INVALID: must be a mapping")
        if not isinstance(self.result, Mapping):
            raise ValueError("VERIFICATION_RESULT_INVALID: must be a mapping")

        for name, seq in (
            ("evidence_ids", self.evidence_ids),
            ("observation_ids", self.observation_ids),
            ("blockers", self.blockers),
            ("rationale_codes", self.rationale_codes),
        ):
            if not isinstance(seq, tuple):
                raise ValueError(f"VERIFICATION_{name.upper()}_INVALID: must be a tuple")
            for item in seq:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(f"VERIFICATION_{name.upper()}_ITEM_INVALID")

    @property
    def id(self) -> str:
        return self.run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "claim_id": self.claim_id,
            "verification_kind": self.verification_kind,
            "verification_version": self.verification_version,
            "verification_rule": dict(self.verification_rule),
            "input_fingerprint": self.input_fingerprint,
            "statement_cutoff": self.statement_cutoff,
            "assessment": self.assessment,
            "evidence_ids": list(self.evidence_ids),
            "observation_ids": list(self.observation_ids),
            "blockers": list(self.blockers),
            "rationale_codes": list(self.rationale_codes),
            "result": dict(self.result),
        }


def normalize_verification_run_record(data: Any) -> VerificationRunRecord:
    if isinstance(data, VerificationRunRecord):
        return data
    if hasattr(data, "__dataclass_fields__") and not isinstance(data, type):
        data = asdict(data)
    elif not isinstance(data, Mapping):
        raise ValueError(
            f"VERIFICATION_RECORD_INVALID_TYPE: expected Mapping or VerificationRunRecord, got {type(data).__name__}"
        )

    unknown = set(data.keys()) - ALLOWED_VERIFICATION_RUN_FIELDS
    if unknown:
        raise ValueError(
            f"VERIFICATION_RECORD_UNKNOWN_FIELDS: unexpected key(s) {sorted(unknown)}"
        )

    raw_dict = dict(data)
    if "run_id" not in raw_dict and "id" in raw_dict:
        raw_dict["run_id"] = raw_dict["id"]

    missing = REQUIRED_VERIFICATION_RUN_FIELDS - set(raw_dict.keys())
    if missing:
        raise ValueError(
            f"VERIFICATION_RECORD_MISSING_FIELDS: missing required key(s) {sorted(missing)}"
        )

    run_id = _required_str(raw_dict["run_id"], "run_id")
    claim_id = _required_str(raw_dict["claim_id"], "claim_id")
    verification_kind = _required_str(
        raw_dict["verification_kind"], "verification_kind"
    )
    input_fingerprint = _required_str(
        raw_dict["input_fingerprint"], "input_fingerprint"
    )
    statement_cutoff = _iso_date(
        raw_dict["statement_cutoff"], "statement_cutoff"
    )

    assessment_raw = raw_dict["assessment"]
    if isinstance(assessment_raw, VerificationAssessment):
        assessment = assessment_raw.value
    else:
        try:
            assessment = VerificationAssessment(str(assessment_raw)).value
        except ValueError as exc:
            raise ValueError(
                f"VERIFICATION_ASSESSMENT_INVALID: '{assessment_raw}' is not a valid VerificationAssessment"
            ) from exc

    verification_version = raw_dict.get(
        "verification_version", VERIFICATION_ASSESSMENT_VERSION
    )
    if verification_version != VERIFICATION_ASSESSMENT_VERSION:
        raise ValueError(
            f"VERIFICATION_VERSION_MISMATCH: expected '{VERIFICATION_ASSESSMENT_VERSION}', got '{verification_version}'"
        )

    rule_raw = raw_dict["verification_rule"]
    if isinstance(rule_raw, Mapping):
        verification_rule = dict(rule_raw)
    elif hasattr(rule_raw, "__dataclass_fields__"):
        verification_rule = asdict(rule_raw)
    else:
        raise ValueError("VERIFICATION_RULE_INVALID: must be a mapping")

    result_raw = raw_dict.get("result")
    if result_raw is None:
        result = {}
    elif isinstance(result_raw, Mapping):
        result = dict(result_raw)
    elif hasattr(result_raw, "__dataclass_fields__"):
        result = asdict(result_raw)
    else:
        raise ValueError("VERIFICATION_RESULT_INVALID: must be a mapping")

    def _seq_to_tuple(key: str) -> tuple[str, ...]:
        raw = raw_dict.get(key)
        if raw is None:
            return ()
        if not isinstance(raw, (list, tuple)):
            raise ValueError(f"VERIFICATION_{key.upper()}_INVALID: must be list or tuple")
        items = []
        for x in raw:
            if not isinstance(x, str) or not x.strip():
                raise ValueError(f"VERIFICATION_{key.upper()}_ITEM_INVALID")
            items.append(x.strip())
        return tuple(items)

    evidence_ids = _seq_to_tuple("evidence_ids")
    observation_ids = _seq_to_tuple("observation_ids")
    blockers = _seq_to_tuple("blockers")
    rationale_codes = _seq_to_tuple("rationale_codes")

    return VerificationRunRecord(
        run_id=run_id,
        claim_id=claim_id,
        verification_kind=verification_kind,
        verification_rule=verification_rule,
        input_fingerprint=input_fingerprint,
        statement_cutoff=statement_cutoff,
        assessment=assessment,
        verification_version=verification_version,
        evidence_ids=evidence_ids,
        observation_ids=observation_ids,
        blockers=blockers,
        rationale_codes=rationale_codes,
        result=result,
    )




def verification_run_to_sql_parameters(
    record: VerificationRunRecord | Mapping[str, Any],
) -> dict[str, str]:
    rec = normalize_verification_run_record(record)
    return {
        "run_id": rec.run_id,
        "claim_id": rec.claim_id,
        "verification_kind": rec.verification_kind,
        "verification_version": rec.verification_version,
        "verification_rule": json.dumps(
            rec.verification_rule, ensure_ascii=False, separators=(",", ":")
        ),
        "input_fingerprint": rec.input_fingerprint,
        "statement_cutoff": rec.statement_cutoff,
        "assessment": rec.assessment,
        "evidence_ids": json.dumps(
            list(rec.evidence_ids), separators=(",", ":")
        ),
        "observation_ids": json.dumps(
            list(rec.observation_ids), separators=(",", ":")
        ),
        "blockers": json.dumps(list(rec.blockers), separators=(",", ":")),
        "rationale_codes": json.dumps(
            list(rec.rationale_codes), separators=(",", ":")
        ),
        "result": json.dumps(
            rec.result, ensure_ascii=False, separators=(",", ":")
        ),
    }


# Compatibility aliases retained by the module's public export surface.
INSERT_VERIFICATION_RUN_SQL = INSERT_VERIFICATION_RUN_SQL_V1
LATEST_VERIFICATION_TEMPLATE_SQL = LATEST_VERIFICATION_TEMPLATE_SQL_V1
VERIFICATION_RUN_INSERT_STATEMENT_V1 = INSERT_VERIFICATION_RUN_SQL_V1


__all__ = [
    "ALLOWED_VERIFICATION_RUN_FIELDS",
    "INSERT_VERIFICATION_RUN_SQL",
    "INSERT_VERIFICATION_RUN_SQL_V1",
    "LATEST_VERIFICATION_TEMPLATE_SQL",
    "LATEST_VERIFICATION_TEMPLATE_SQL_V1",
    "REQUIRED_VERIFICATION_RUN_FIELDS",
    "VERIFICATION_ASSESSMENT_VERSION",
    "VERIFICATION_RUN_INSERT_STATEMENT_V1",
    "VerificationRunRecord",
    "normalize_verification_run_record",
    "verification_run_to_sql_parameters",
]
