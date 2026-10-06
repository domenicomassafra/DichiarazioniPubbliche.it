from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


FINDING_RECORD_VERSION_CONTRACT = "finding-record-version-v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class FindingRecordVersion:
    finding_id: str
    fingerprint_sha256: str
    record_version: str
    contract_version: str = FINDING_RECORD_VERSION_CONTRACT

    def __post_init__(self) -> None:
        if not str(self.finding_id or "").strip():
            raise ValueError("FINDING_RECORD_VERSION_FINDING_ID_REQUIRED")
        fingerprint = str(self.fingerprint_sha256 or "").strip().lower()
        if not _SHA256_RE.fullmatch(fingerprint):
            raise ValueError("FINDING_RECORD_VERSION_FINGERPRINT_INVALID")
        expected = f"{self.contract_version}:{fingerprint}"
        if self.record_version != expected:
            raise ValueError("FINDING_RECORD_VERSION_VALUE_INVALID")


def _required_text(value: object, code: str, *, limit: int = 512) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(code)
    if len(text) > limit:
        raise ValueError(f"{code}_TOO_LONG")
    return text


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(code)
    return value


def _rows(value: object, code: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(code)
    rows: list[Mapping[str, Any]] = []
    for item in value:
        rows.append(_mapping(item, code))
    return rows


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text_sha256(value: object) -> str:
    return hashlib.sha256(str(value if value is not None else "").encode("utf-8")).hexdigest()


def _canonical_string_list(value: object, code: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(code)
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(code)
        cleaned.append(_required_text(item, code))
    return sorted(cleaned)


def _binding_metadata_refs(value: object, *keys: str) -> dict[str, object]:
    metadata = _mapping(value if value is not None else {}, "FINDING_RECORD_VERSION_METADATA_INVALID")
    return {key: metadata[key] for key in keys if key in metadata}


def _persisted_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    finding = _mapping(raw.get("finding"), "FINDING_RECORD_VERSION_FINDING_INVALID")
    finding_id = _required_text(
        finding.get("id"), "FINDING_RECORD_VERSION_FINDING_ID_REQUIRED"
    )

    # This fingerprint owns the current Finding envelope and its direct persisted bindings.
    # It deliberately does not hash the current source/transcript/person/privacy/rights state;
    # DP-308's safety binding owns those referenced objects and their policy freshness.
    finding_material = {
        "id": finding_id,
        "claim_id": _required_text(
            finding.get("claim_id"), "FINDING_RECORD_VERSION_CLAIM_ID_REQUIRED"
        ),
        "assessment": _required_text(
            finding.get("assessment"), "FINDING_RECORD_VERSION_ASSESSMENT_REQUIRED"
        ),
        "assessment_version": _required_text(
            finding.get("assessment_version"),
            "FINDING_RECORD_VERSION_ASSESSMENT_VERSION_REQUIRED",
        ),
        "rationale_sha256": _text_sha256(finding.get("rationale")),
        "publication_status": _required_text(
            finding.get("publication_status"),
            "FINDING_RECORD_VERSION_PUBLICATION_STATUS_REQUIRED",
        ),
        "publication_status_version": _required_text(
            finding.get("publication_status_version"),
            "FINDING_RECORD_VERSION_PUBLICATION_STATUS_VERSION_REQUIRED",
        ),
        "policy_version": _required_text(
            finding.get("policy_version"),
            "FINDING_RECORD_VERSION_POLICY_VERSION_REQUIRED",
        ),
        "model_bundle_sha256": _json_sha256(finding.get("model_bundle") or {}),
        "verification_run_id": (
            str(finding.get("verification_run_id")).strip()
            if finding.get("verification_run_id") is not None
            else None
        ),
        "supersedes_id": (
            str(finding.get("supersedes_id")).strip()
            if finding.get("supersedes_id") is not None
            else None
        ),
    }

    verification_raw = raw.get("verification")
    verification_material: dict[str, Any] | None = None
    if verification_raw is not None:
        verification = _mapping(
            verification_raw, "FINDING_RECORD_VERSION_VERIFICATION_INVALID"
        )
        verification_material = {
            "id": _required_text(
                verification.get("id"),
                "FINDING_RECORD_VERSION_VERIFICATION_ID_REQUIRED",
            ),
            "claim_id": _required_text(
                verification.get("claim_id"),
                "FINDING_RECORD_VERSION_VERIFICATION_CLAIM_ID_REQUIRED",
            ),
            "source_intelligence_assessment_id": verification.get(
                "source_intelligence_assessment_id"
            ),
            "verification_kind": _required_text(
                verification.get("verification_kind"),
                "FINDING_RECORD_VERSION_VERIFICATION_KIND_REQUIRED",
            ),
            "verification_version": _required_text(
                verification.get("verification_version"),
                "FINDING_RECORD_VERSION_VERIFICATION_VERSION_REQUIRED",
            ),
            "verification_rule_sha256": _json_sha256(
                verification.get("verification_rule") or {}
            ),
            "input_fingerprint": _required_text(
                verification.get("input_fingerprint"),
                "FINDING_RECORD_VERSION_VERIFICATION_INPUT_REQUIRED",
            ),
            "statement_cutoff": _required_text(
                verification.get("statement_cutoff"),
                "FINDING_RECORD_VERSION_STATEMENT_CUTOFF_REQUIRED",
            ),
            "assessment": _required_text(
                verification.get("assessment"),
                "FINDING_RECORD_VERSION_VERIFICATION_ASSESSMENT_REQUIRED",
            ),
            "evidence_ids": _canonical_string_list(
                verification.get("evidence_ids"),
                "FINDING_RECORD_VERSION_VERIFICATION_EVIDENCE_IDS_INVALID",
            ),
            "observation_ids": _canonical_string_list(
                verification.get("observation_ids"),
                "FINDING_RECORD_VERSION_VERIFICATION_OBSERVATION_IDS_INVALID",
            ),
            "blockers": _canonical_string_list(
                verification.get("blockers"),
                "FINDING_RECORD_VERSION_VERIFICATION_BLOCKERS_INVALID",
            ),
            "rationale_codes": _canonical_string_list(
                verification.get("rationale_codes"),
                "FINDING_RECORD_VERSION_VERIFICATION_RATIONALE_CODES_INVALID",
            ),
            "result_sha256": _json_sha256(verification.get("result") or {}),
        }

    evidence_rows = []
    for row in _rows(
        raw.get("finding_evidence"), "FINDING_RECORD_VERSION_EVIDENCE_BINDING_INVALID"
    ):
        evidence_rows.append(
            {
                "evidence_id": _required_text(
                    row.get("evidence_id"),
                    "FINDING_RECORD_VERSION_EVIDENCE_ID_REQUIRED",
                ),
                "relation": _required_text(
                    row.get("relation"),
                    "FINDING_RECORD_VERSION_EVIDENCE_RELATION_REQUIRED",
                ),
            }
        )
    evidence_rows.sort(key=lambda row: (row["evidence_id"], row["relation"]))

    assertion_rows = []
    for row in _rows(
        raw.get("assertions"), "FINDING_RECORD_VERSION_ASSERTION_INVALID"
    ):
        citation_rows = []
        for citation in _rows(
            row.get("citations"), "FINDING_RECORD_VERSION_CITATION_INVALID"
        ):
            citation_rows.append(
                {
                    "id": _required_text(
                        citation.get("id"),
                        "FINDING_RECORD_VERSION_CITATION_ID_REQUIRED",
                    ),
                    "evidence_id": _required_text(
                        citation.get("evidence_id"),
                        "FINDING_RECORD_VERSION_CITATION_EVIDENCE_ID_REQUIRED",
                    ),
                    "observation_id": citation.get("observation_id"),
                    "passage_id": citation.get("passage_id"),
                    "passage_text_sha256": citation.get("passage_text_sha256"),
                    "source_content_sha256": citation.get("source_content_sha256"),
                    "relation": _required_text(
                        citation.get("relation"),
                        "FINDING_RECORD_VERSION_CITATION_RELATION_REQUIRED",
                    ),
                    "citation_version": _required_text(
                        citation.get("citation_version"),
                        "FINDING_RECORD_VERSION_CITATION_VERSION_REQUIRED",
                    ),
                    "binding_metadata": _binding_metadata_refs(
                        citation.get("metadata"),
                        "verification_run_id",
                        "binding_version",
                    ),
                }
            )
        citation_rows.sort(key=lambda citation: citation["id"])
        assertion_rows.append(
            {
                "id": _required_text(
                    row.get("id"), "FINDING_RECORD_VERSION_ASSERTION_ID_REQUIRED"
                ),
                "assertion_text_sha256": _required_text(
                    row.get("assertion_text_sha256"),
                    "FINDING_RECORD_VERSION_ASSERTION_HASH_REQUIRED",
                ),
                "current_text_sha256": _text_sha256(row.get("assertion_text")),
                "assertion_type": _required_text(
                    row.get("assertion_type"),
                    "FINDING_RECORD_VERSION_ASSERTION_TYPE_REQUIRED",
                ),
                "material": bool(row.get("material")),
                "required_relation": _required_text(
                    row.get("required_relation"),
                    "FINDING_RECORD_VERSION_ASSERTION_RELATION_REQUIRED",
                ),
                "assertion_version": _required_text(
                    row.get("assertion_version"),
                    "FINDING_RECORD_VERSION_ASSERTION_VERSION_REQUIRED",
                ),
                "binding_metadata": _binding_metadata_refs(
                    row.get("metadata"), "verification_run_id"
                ),
                "citations": citation_rows,
            }
        )
    assertion_rows.sort(key=lambda row: row["id"])

    return {
        "contract_version": FINDING_RECORD_VERSION_CONTRACT,
        "finding": finding_material,
        "verification": verification_material,
        "finding_evidence": evidence_rows,
        "assertions": assertion_rows,
    }


_CURRENT_FINDING_RECORD_SQL = r"""
SELECT json_build_object(
    'finding', json_build_object(
        'id', finding.id,
        'claim_id', finding.claim_id,
        'assessment', finding.assessment,
        'assessment_version', finding.assessment_version,
        'rationale', finding.rationale,
        'publication_status', finding.publication_status,
        'publication_status_version', finding.publication_status_version,
        'policy_version', finding.policy_version,
        'model_bundle', finding.model_bundle,
        'verification_run_id', finding.verification_run_id,
        'supersedes_id', finding.supersedes_id
    ),
    'verification', CASE
        WHEN verification.id IS NULL THEN NULL
        ELSE json_build_object(
            'id', verification.id,
            'claim_id', verification.claim_id,
            'source_intelligence_assessment_id', verification.source_intelligence_assessment_id,
            'verification_kind', verification.verification_kind,
            'verification_version', verification.verification_version,
            'verification_rule', verification.verification_rule,
            'input_fingerprint', verification.input_fingerprint,
            'statement_cutoff', verification.statement_cutoff::text,
            'assessment', verification.assessment,
            'evidence_ids', verification.evidence_ids,
            'observation_ids', verification.observation_ids,
            'blockers', verification.blockers,
            'rationale_codes', verification.rationale_codes,
            'result', verification.result
        )
    END,
    'finding_evidence', COALESCE((
        SELECT json_agg(
            json_build_object(
                'evidence_id', finding_evidence.evidence_id,
                'relation', finding_evidence.relation
            )
            ORDER BY finding_evidence.evidence_id, finding_evidence.relation
        )
        FROM finding_evidence
        WHERE finding_evidence.finding_id = finding.id
    ), '[]'::json),
    'assertions', COALESCE((
        SELECT json_agg(
            json_build_object(
                'id', assertion.id,
                'assertion_text', assertion.assertion_text,
                'assertion_text_sha256', assertion.assertion_text_sha256,
                'assertion_type', assertion.assertion_type,
                'material', assertion.material,
                'required_relation', assertion.required_relation,
                'assertion_version', assertion.assertion_version,
                'metadata', assertion.metadata,
                'citations', COALESCE((
                    SELECT json_agg(
                        json_build_object(
                            'id', citation.id,
                            'evidence_id', citation.evidence_id,
                            'observation_id', citation.observation_id,
                            'passage_id', citation.passage_id,
                            'passage_text_sha256', citation.passage_text_sha256,
                            'source_content_sha256', citation.source_content_sha256,
                            'relation', citation.relation,
                            'citation_version', citation.citation_version,
                            'metadata', citation.metadata
                        )
                        ORDER BY citation.id
                    )
                    FROM finding_assertion_citation citation
                    WHERE citation.assertion_id = assertion.id
                ), '[]'::json)
            )
            ORDER BY assertion.id
        )
        FROM finding_assertion assertion
        WHERE assertion.finding_id = finding.id
    ), '[]'::json)
)::text
FROM finding
LEFT JOIN verification_run verification
  ON verification.id = finding.verification_run_id
WHERE finding.id = :'finding_id';
"""


class FindingRecordVersionStore(PsqlRuntime):
    def current_record_version(self, finding_id: str) -> FindingRecordVersion:
        clean_finding_id = _required_text(
            finding_id, "FINDING_RECORD_VERSION_FINDING_ID_REQUIRED"
        )
        raw = self.run(_CURRENT_FINDING_RECORD_SQL, finding_id=clean_finding_id)
        if not raw:
            raise ValueError("FINDING_RECORD_VERSION_NOT_FOUND")
        try:
            current = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("FINDING_RECORD_VERSION_PERSISTED_STATE_INVALID") from exc
        material = _persisted_payload(
            _mapping(current, "FINDING_RECORD_VERSION_PERSISTED_STATE_INVALID")
        )
        fingerprint = _json_sha256(material)
        return FindingRecordVersion(
            finding_id=clean_finding_id,
            fingerprint_sha256=fingerprint,
            record_version=f"{FINDING_RECORD_VERSION_CONTRACT}:{fingerprint}",
        )


__all__ = [
    "FINDING_RECORD_VERSION_CONTRACT",
    "FindingRecordVersion",
    "FindingRecordVersionStore",
]
