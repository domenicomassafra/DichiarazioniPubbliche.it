from __future__ import annotations

import hashlib
from dataclasses import dataclass


ALLOWED_TRIGGER_TYPES = {
    "EVIDENCE_APPROVED",
    "EVIDENCE_HASH_CHANGED",
    "RIGHT_OF_REPLY",
    "CORRECTION",
    "RELATION_APPROVED",
    "MANUAL_REVIEW",
}


@dataclass(frozen=True)
class ReanalysisTrigger:
    trigger_id: str
    claim_id: str
    trigger_type: str
    source_type: str
    source_id: str
    source_hash: str | None


def deterministic_reanalysis_trigger(
    *,
    claim_id: str,
    trigger_type: str,
    source_type: str,
    source_id: str,
    source_hash: str | None = None,
) -> ReanalysisTrigger:
    if trigger_type not in ALLOWED_TRIGGER_TYPES:
        raise ValueError("REANALYSIS_TRIGGER_TYPE_INVALID")
    for name, value in {
        "claim_id": claim_id,
        "source_type": source_type,
        "source_id": source_id,
    }.items():
        if not str(value).strip():
            raise ValueError(f"REANALYSIS_{name.upper()}_REQUIRED")
    material = "\0".join(
        (
            claim_id.strip(),
            trigger_type,
            source_type.strip(),
            source_id.strip(),
            (source_hash or "").strip().lower(),
        )
    ).encode()
    return ReanalysisTrigger(
        trigger_id="reanalysis:" + hashlib.sha256(material).hexdigest(),
        claim_id=claim_id.strip(),
        trigger_type=trigger_type,
        source_type=source_type.strip(),
        source_id=source_id.strip(),
        source_hash=(source_hash or "").strip().lower() or None,
    )


def deterministic_reanalysis_job_id(trigger_id: str) -> str:
    if not trigger_id.startswith("reanalysis:"):
        raise ValueError("REANALYSIS_TRIGGER_ID_INVALID")
    return "job:" + hashlib.sha256(
        ("REANALYZE_CLAIM\0" + trigger_id).encode()
    ).hexdigest()
