from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from dichiarazioni_pubbliche.reanalysis_runtime import (
    ReanalysisTrigger,
    deterministic_reanalysis_job_id,
    deterministic_reanalysis_trigger,
)
from dichiarazioni_pubbliche.source_revalidation import (
    SOURCE_REVALIDATION_VERSION,
    RevalidationDecision,
    RevalidationDisposition,
    SourceSnapshot,
    snapshot_ref,
)


SUPERSESSION_REANALYSIS_VERSION = "supersession-reanalysis-v1"
SUPERSESSION_TRIGGER_SOURCE_TYPE = "REVIEWED_SOURCE_SUPERSESSION"


class SupersessionReanalysisError(ValueError):
    pass


@dataclass(frozen=True)
class EffectiveSourceVersionBinding:
    source_id: str
    version_id: str
    content_sha256: str
    valid_from: str
    valid_until: str | None


@dataclass(frozen=True)
class ReviewedSupersessionReanalysisRequest:
    request_id: str
    review_event_id: str
    reviewed_entity_ref: str
    decision_event_key: str
    previous_snapshot_ref: str
    current_snapshot_ref: str
    previous: EffectiveSourceVersionBinding
    current: EffectiveSourceVersionBinding
    affected_claim_ids: tuple[str, ...]
    affected_finding_ids: tuple[str, ...]
    triggers: tuple[ReanalysisTrigger, ...]
    reanalysis_job_ids: tuple[str, ...]
    version: str = SUPERSESSION_REANALYSIS_VERSION

def _required_text(value: object, field: str, *, maximum: int = 512) -> str:
    text = str(value or "").strip()
    if not text:
        raise SupersessionReanalysisError(f"SUPERSESSION_REANALYSIS_{field}_REQUIRED")
    if len(text) > maximum:
        raise SupersessionReanalysisError(f"SUPERSESSION_REANALYSIS_{field}_TOO_LONG")
    return text


def _sha256(value: object, field: str) -> str:
    text = _required_text(value, field, maximum=64).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise SupersessionReanalysisError(f"SUPERSESSION_REANALYSIS_{field}_INVALID")
    return text


def _iso_date(value: object, field: str, *, required: bool) -> str | None:
    if value in (None, ""):
        if required:
            raise SupersessionReanalysisError(f"SUPERSESSION_REANALYSIS_{field}_REQUIRED")
        return None
    text = _required_text(value, field, maximum=10)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise SupersessionReanalysisError(
            f"SUPERSESSION_REANALYSIS_{field}_INVALID"
        ) from exc
    return parsed.isoformat()


def _binding(
    snapshot: SourceSnapshot,
    *,
    valid_from: object,
    valid_until: object,
    prefix: str,
) -> EffectiveSourceVersionBinding:
    source_id = _required_text(snapshot.source_id, f"{prefix}_SOURCE_ID")
    version_id = _required_text(snapshot.source_version, f"{prefix}_VERSION_ID")
    content_sha256 = _sha256(snapshot.content_sha256, f"{prefix}_CONTENT_SHA256")
    start = _iso_date(valid_from, f"{prefix}_VALID_FROM", required=True)
    end = _iso_date(valid_until, f"{prefix}_VALID_UNTIL", required=False)
    assert start is not None
    if end is not None and date.fromisoformat(end) <= date.fromisoformat(start):
        raise SupersessionReanalysisError(
            f"SUPERSESSION_REANALYSIS_{prefix}_EFFECTIVE_INTERVAL_INVALID"
        )
    return EffectiveSourceVersionBinding(
        source_id=source_id,
        version_id=version_id,
        content_sha256=content_sha256,
        valid_from=start,
        valid_until=end,
    )


def _ids(values: Iterable[object], field: str, *, required: bool) -> tuple[str, ...]:
    normalized = tuple(
        sorted({_required_text(value, field) for value in values})
    )
    if required and not normalized:
        raise SupersessionReanalysisError(f"SUPERSESSION_REANALYSIS_{field}_REQUIRED")
    return normalized


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _expected_decision_event_key(
    decision: RevalidationDecision,
    previous: SourceSnapshot,
    current: SourceSnapshot,
) -> str:
    change_codes = sorted(
        set(decision.material_change_codes + decision.benign_change_codes)
    )
    return _fingerprint(
        {
            "version": SOURCE_REVALIDATION_VERSION,
            "source_id": previous.source_id,
            "previous_snapshot_ref": snapshot_ref(previous),
            "current_snapshot_ref": snapshot_ref(current),
            "change_codes": change_codes,
        }
    )


def build_reviewed_supersession_reanalysis_request(
    *,
    decision: RevalidationDecision,
    previous: SourceSnapshot,
    current: SourceSnapshot,
    review_event_id: str,
    review_action: str,
    reviewed_entity_ref: str,
    previous_valid_from: str,
    previous_valid_until: str | None,
    current_valid_from: str,
    current_valid_until: str | None,
    affected_claim_ids: Iterable[str],
    affected_finding_ids: Iterable[str] = (),
) -> ReviewedSupersessionReanalysisRequest:
    """Build the replay-stable reanalysis request implied by one reviewed supersession.

    This is a pure bridge between DP-511 source revalidation and the existing reanalysis
    trigger contract. The returned request is executable input for the existing reanalysis
    trigger/job seam; constructing it performs no queue, database, finding, or publication
    mutation.
    """

    review_id = _required_text(review_event_id, "REVIEW_EVENT_ID")
    if str(review_action or "").strip().upper() != "APPROVED":
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_APPROVED_REVIEW_REQUIRED"
        )
    review_target = _required_text(
        reviewed_entity_ref,
        "REVIEWED_ENTITY_REF",
        maximum=64,
    )
    if decision.version != SOURCE_REVALIDATION_VERSION:
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_DECISION_VERSION_MISMATCH"
        )
    if decision.disposition is not RevalidationDisposition.HOLD_REQUIRED:
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_LOAD_BEARING_HOLD_REQUIRED"
        )
    if not decision.needs_reanalysis or not decision.needs_targeted_hold:
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_LOAD_BEARING_DECISION_REQUIRED"
        )
    if "OFFICIAL_VERSION_SUPERSEDED" not in decision.material_change_codes:
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_OFFICIAL_SUPERSESSION_REQUIRED"
        )

    previous_ref = snapshot_ref(previous)
    current_ref = snapshot_ref(current)
    if decision.previous_snapshot_ref != previous_ref:
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_PREVIOUS_SNAPSHOT_REF_MISMATCH"
        )
    if decision.current_snapshot_ref != current_ref:
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_CURRENT_SNAPSHOT_REF_MISMATCH"
        )
    if decision.event_key != _expected_decision_event_key(decision, previous, current):
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_DECISION_EVENT_KEY_MISMATCH"
        )
    if review_target != decision.event_key:
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_REVIEW_TARGET_MISMATCH"
        )
    if str(previous.source_id or "").strip() != str(current.source_id or "").strip():
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_SOURCE_ID_MISMATCH"
        )
    if str(current.supersedes_version or "").strip() != str(previous.source_version or "").strip():
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_DIRECT_SUPERSESSION_REQUIRED"
        )

    old_binding = _binding(
        previous,
        valid_from=previous_valid_from,
        valid_until=previous_valid_until,
        prefix="PREVIOUS",
    )
    new_binding = _binding(
        current,
        valid_from=current_valid_from,
        valid_until=current_valid_until,
        prefix="CURRENT",
    )
    if old_binding.version_id == new_binding.version_id:
        raise SupersessionReanalysisError(
            "SUPERSESSION_REANALYSIS_VERSION_CHANGE_REQUIRED"
        )

    claims = _ids(affected_claim_ids, "AFFECTED_CLAIM_ID", required=True)
    findings = _ids(affected_finding_ids, "AFFECTED_FINDING_ID", required=False)
    payload = {
        "version": SUPERSESSION_REANALYSIS_VERSION,
        "review_event_id": review_id,
        "reviewed_entity_ref": review_target,
        "decision_event_key": _required_text(
            decision.event_key,
            "DECISION_EVENT_KEY",
            maximum=64,
        ),
        "previous_snapshot_ref": previous_ref,
        "current_snapshot_ref": current_ref,
        "previous": {
            "source_id": old_binding.source_id,
            "version_id": old_binding.version_id,
            "content_sha256": old_binding.content_sha256,
            "valid_from": old_binding.valid_from,
            "valid_until": old_binding.valid_until,
        },
        "current": {
            "source_id": new_binding.source_id,
            "version_id": new_binding.version_id,
            "content_sha256": new_binding.content_sha256,
            "valid_from": new_binding.valid_from,
            "valid_until": new_binding.valid_until,
        },
        "affected_claim_ids": list(claims),
        "affected_finding_ids": list(findings),
    }
    fingerprint = _fingerprint(payload)
    request_id = f"supersession-reanalysis:{fingerprint}"
    triggers = tuple(
        deterministic_reanalysis_trigger(
            claim_id=claim_id,
            trigger_type="MANUAL_REVIEW",
            source_type=SUPERSESSION_TRIGGER_SOURCE_TYPE,
            source_id=request_id,
            source_hash=new_binding.content_sha256,
        )
        for claim_id in claims
    )
    jobs = tuple(deterministic_reanalysis_job_id(trigger.trigger_id) for trigger in triggers)
    return ReviewedSupersessionReanalysisRequest(
        request_id=request_id,
        review_event_id=review_id,
        reviewed_entity_ref=review_target,
        decision_event_key=decision.event_key,
        previous_snapshot_ref=previous_ref,
        current_snapshot_ref=current_ref,
        previous=old_binding,
        current=new_binding,
        affected_claim_ids=claims,
        affected_finding_ids=findings,
        triggers=triggers,
        reanalysis_job_ids=jobs,
    )


__all__ = [
    "SUPERSESSION_REANALYSIS_VERSION",
    "SUPERSESSION_TRIGGER_SOURCE_TYPE",
    "EffectiveSourceVersionBinding",
    "ReviewedSupersessionReanalysisRequest",
    "SupersessionReanalysisError",
    "build_reviewed_supersession_reanalysis_request",
]
