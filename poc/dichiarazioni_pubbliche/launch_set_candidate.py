from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping


LAUNCH_SET_CANDIDATE_VERSION = "launch-set-candidate-v1"
LAUNCH_SNAPSHOT_CANDIDATE_VERSION = "launch-snapshot-candidate-v1"
ROLLBACK_RECEIPT_CANDIDATE_VERSION = "rollback-receipt-candidate-v1"
MIN_INCLUDED_SOURCE_FAMILIES = 3
MAX_SOURCE_ROWS = 100
MAX_SOURCE_IDS = 100


class LaunchSetCandidateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "LAUNCH_SET_CANDIDATE_ERROR").strip().upper()[:240]
        super().__init__(self.code)


class LaunchSourceState(StrEnum):
    INCLUDED = "INCLUDED"
    HELD = "HELD"
    EXCLUDED = "EXCLUDED"
    REMOVED = "REMOVED"


class GateState(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    PENDING = "PENDING"


_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_HEX40_64 = re.compile(r"^[0-9a-f]{40,64}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_ROW_FIELDS = frozenset(
    {
        "source_id",
        "source_family",
        "state",
        "rights_state",
        "privacy_state",
        "provider_state",
        "rights_decision_ref",
        "privacy_decision_ref",
        "policy_decision_ref",
        "discovery_path_id",
        "transcript_path_id",
        "speaker_path_id",
        "evidence_path_id",
        "provider_path_id",
        "health_owner",
        "disclosure_decision_ref",
        "config_sha256",
    }
)

_INCLUDED_REQUIRED_REFS = (
    "rights_decision_ref",
    "privacy_decision_ref",
    "policy_decision_ref",
    "discovery_path_id",
    "transcript_path_id",
    "speaker_path_id",
    "evidence_path_id",
    "provider_path_id",
    "health_owner",
    "disclosure_decision_ref",
    "config_sha256",
)


def _sha(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: object, name: str, *, maximum: int = 256) -> str:
    if isinstance(value, bool):
        raise LaunchSetCandidateError(f"LAUNCH_SET_{name}_INVALID")
    text = str(value or "").strip()
    if not text:
        raise LaunchSetCandidateError(f"LAUNCH_SET_{name}_REQUIRED")
    if len(text) > maximum:
        raise LaunchSetCandidateError(f"LAUNCH_SET_{name}_TOO_LONG")
    return text


def _optional_text(value: object, name: str, *, maximum: int = 256) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > maximum:
        raise LaunchSetCandidateError(f"LAUNCH_SET_{name}_TOO_LONG")
    return text


def _stable_id(value: object, name: str) -> str:
    text = _text(value, name, maximum=128)
    if not _STABLE_ID.fullmatch(text):
        raise LaunchSetCandidateError(f"LAUNCH_SET_{name}_INVALID")
    return text


def _sha256(value: object, name: str) -> str:
    text = _text(value, name, maximum=64).lower()
    if not _HEX64.fullmatch(text):
        raise LaunchSetCandidateError(f"LAUNCH_SET_{name}_INVALID")
    return text


def _enum(value: object, enum_type: type[StrEnum], name: str) -> StrEnum:
    try:
        return value if isinstance(value, enum_type) else enum_type(str(value))
    except ValueError as exc:
        raise LaunchSetCandidateError(f"LAUNCH_SET_{name}_INVALID") from exc


@dataclass(frozen=True)
class LaunchSourceCandidate:
    source_id: str
    source_family: str
    state: LaunchSourceState
    rights_state: GateState
    privacy_state: GateState
    provider_state: GateState
    rights_decision_ref: str | None = None
    privacy_decision_ref: str | None = None
    policy_decision_ref: str | None = None
    discovery_path_id: str | None = None
    transcript_path_id: str | None = None
    speaker_path_id: str | None = None
    evidence_path_id: str | None = None
    provider_path_id: str | None = None
    health_owner: str | None = None
    disclosure_decision_ref: str | None = None
    config_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _stable_id(self.source_id, "SOURCE_ID"))
        object.__setattr__(
            self,
            "source_family",
            _stable_id(self.source_family, "SOURCE_FAMILY"),
        )
        object.__setattr__(
            self,
            "state",
            _enum(self.state, LaunchSourceState, "STATE"),
        )
        for field in ("rights_state", "privacy_state", "provider_state"):
            object.__setattr__(
                self,
                field,
                _enum(getattr(self, field), GateState, field.upper()),
            )
        for field in (
            "rights_decision_ref",
            "privacy_decision_ref",
            "policy_decision_ref",
            "discovery_path_id",
            "transcript_path_id",
            "speaker_path_id",
            "evidence_path_id",
            "provider_path_id",
            "health_owner",
            "disclosure_decision_ref",
        ):
            object.__setattr__(
                self,
                field,
                _optional_text(getattr(self, field), field.upper()),
            )
        if self.config_sha256 is not None:
            object.__setattr__(
                self,
                "config_sha256",
                _sha256(self.config_sha256, "CONFIG_SHA256"),
            )
        if self.state is LaunchSourceState.INCLUDED:
            for field in _INCLUDED_REQUIRED_REFS:
                if getattr(self, field) in (None, ""):
                    raise LaunchSetCandidateError(
                        f"LAUNCH_SET_INCLUDED_{field.upper()}_REQUIRED"
                    )
            for gate_name in ("rights_state", "privacy_state", "provider_state"):
                if getattr(self, gate_name) is not GateState.READY:
                    raise LaunchSetCandidateError(
                        f"LAUNCH_SET_INCLUDED_{gate_name.upper()}_NOT_READY"
                    )

    def canonical(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_family": self.source_family,
            "state": self.state.value,
            "rights_state": self.rights_state.value,
            "privacy_state": self.privacy_state.value,
            "provider_state": self.provider_state.value,
            "rights_decision_ref": self.rights_decision_ref,
            "privacy_decision_ref": self.privacy_decision_ref,
            "policy_decision_ref": self.policy_decision_ref,
            "discovery_path_id": self.discovery_path_id,
            "transcript_path_id": self.transcript_path_id,
            "speaker_path_id": self.speaker_path_id,
            "evidence_path_id": self.evidence_path_id,
            "provider_path_id": self.provider_path_id,
            "health_owner": self.health_owner,
            "disclosure_decision_ref": self.disclosure_decision_ref,
            "config_sha256": self.config_sha256,
        }


@dataclass(frozen=True)
class LaunchSetCandidateManifest:
    rows: tuple[LaunchSourceCandidate, ...]
    manifest_sha256: str
    candidate_status: str
    blockers: tuple[str, ...]
    included_source_ids: tuple[str, ...]
    included_source_families: tuple[str, ...]
    held_count: int
    omitted_count: int
    launch_state: str = "BLOCKED"
    launch_authorized: bool = False
    version: str = LAUNCH_SET_CANDIDATE_VERSION


def _row_from_mapping(raw: Mapping[str, object]) -> LaunchSourceCandidate:
    unknown = set(raw) - _ROW_FIELDS
    if unknown:
        raise LaunchSetCandidateError(
            "LAUNCH_SET_ROW_UNKNOWN_FIELDS:" + ",".join(sorted(unknown))
        )
    return LaunchSourceCandidate(**dict(raw))


def validate_launch_set_candidate(
    rows: Iterable[LaunchSourceCandidate | Mapping[str, object]],
) -> LaunchSetCandidateManifest:
    normalized: list[LaunchSourceCandidate] = []
    seen_ids: set[str] = set()
    for raw in rows:
        row = raw if isinstance(raw, LaunchSourceCandidate) else _row_from_mapping(raw)
        if row.source_id in seen_ids:
            raise LaunchSetCandidateError("LAUNCH_SET_SOURCE_ID_DUPLICATE")
        seen_ids.add(row.source_id)
        normalized.append(row)
    if not normalized:
        raise LaunchSetCandidateError("LAUNCH_SET_ROWS_REQUIRED")
    if len(normalized) > MAX_SOURCE_ROWS:
        raise LaunchSetCandidateError("LAUNCH_SET_ROW_LIMIT")

    canonical_rows = tuple(sorted(normalized, key=lambda row: row.source_id))
    included = tuple(row for row in canonical_rows if row.state is LaunchSourceState.INCLUDED)
    families = tuple(sorted({row.source_family for row in included}))
    blockers: list[str] = []
    if not included:
        blockers.append("NO_INCLUDED_SOURCES")
    if len(families) < MIN_INCLUDED_SOURCE_FAMILIES:
        blockers.append(
            f"INCLUDED_SOURCE_FAMILY_MINIMUM_NOT_MET:{len(families)}:{MIN_INCLUDED_SOURCE_FAMILIES}"
        )

    payload = {
        "version": LAUNCH_SET_CANDIDATE_VERSION,
        "rows": [row.canonical() for row in canonical_rows],
    }
    return LaunchSetCandidateManifest(
        rows=canonical_rows,
        manifest_sha256=_sha(payload),
        candidate_status="READY_FOR_OWNER_REVIEW" if not blockers else "BLOCKED",
        blockers=tuple(blockers),
        included_source_ids=tuple(row.source_id for row in included),
        included_source_families=families,
        held_count=sum(row.state is LaunchSourceState.HELD for row in canonical_rows),
        omitted_count=sum(
            row.state in {LaunchSourceState.EXCLUDED, LaunchSourceState.REMOVED}
            for row in canonical_rows
        ),
    )


@dataclass(frozen=True)
class LaunchSnapshotCandidate:
    candidate_commit: str
    effective_config_sha256: str
    policy_version: str
    public_schema_version: str
    api_version: str
    source_ids: tuple[str, ...]
    included_source_ids: tuple[str, ...]
    launch_set_manifest_sha256: str
    public_projection_sha256: str
    held_count: int
    omitted_count: int
    snapshot_sha256: str
    launch_state: str = "BLOCKED"
    launch_authorized: bool = False
    version: str = LAUNCH_SNAPSHOT_CANDIDATE_VERSION


def build_launch_snapshot_candidate(
    *,
    manifest: LaunchSetCandidateManifest,
    candidate_commit: str,
    effective_config_sha256: str,
    policy_version: str,
    public_schema_version: str,
    api_version: str,
    public_projection_sha256: str,
) -> LaunchSnapshotCandidate:
    commit = _text(candidate_commit, "CANDIDATE_COMMIT", maximum=64).lower()
    if not _HEX40_64.fullmatch(commit):
        raise LaunchSetCandidateError("LAUNCH_SET_CANDIDATE_COMMIT_INVALID")
    config_sha256 = _sha256(effective_config_sha256, "EFFECTIVE_CONFIG_SHA256")
    projection_sha256 = _sha256(public_projection_sha256, "PUBLIC_PROJECTION_SHA256")
    policy = _stable_id(policy_version, "POLICY_VERSION")
    schema = _stable_id(public_schema_version, "PUBLIC_SCHEMA_VERSION")
    api = _stable_id(api_version, "API_VERSION")
    source_ids = tuple(row.source_id for row in manifest.rows)
    if len(source_ids) > MAX_SOURCE_IDS:
        raise LaunchSetCandidateError("LAUNCH_SET_SNAPSHOT_SOURCE_ID_LIMIT")

    payload = {
        "version": LAUNCH_SNAPSHOT_CANDIDATE_VERSION,
        "candidate_commit": commit,
        "effective_config_sha256": config_sha256,
        "policy_version": policy,
        "public_schema_version": schema,
        "api_version": api,
        "source_ids": list(source_ids),
        "included_source_ids": list(manifest.included_source_ids),
        "launch_set_manifest_sha256": manifest.manifest_sha256,
        "public_projection_sha256": projection_sha256,
        "held_count": manifest.held_count,
        "omitted_count": manifest.omitted_count,
    }
    return LaunchSnapshotCandidate(
        candidate_commit=commit,
        effective_config_sha256=config_sha256,
        policy_version=policy,
        public_schema_version=schema,
        api_version=api,
        source_ids=source_ids,
        included_source_ids=manifest.included_source_ids,
        launch_set_manifest_sha256=manifest.manifest_sha256,
        public_projection_sha256=projection_sha256,
        held_count=manifest.held_count,
        omitted_count=manifest.omitted_count,
        snapshot_sha256=_sha(payload),
    )


@dataclass(frozen=True)
class RollbackReceiptCandidate:
    rollback_id: str
    rejected_snapshot_sha256: str
    restore_target_snapshot_sha256: str
    expected_projection_sha256: str
    reason_code: str
    actor_ref: str
    receipt_sha256: str
    execution_state: str = "NOT_EXECUTED"
    launch_authorized: bool = False
    version: str = ROLLBACK_RECEIPT_CANDIDATE_VERSION


def build_rollback_receipt_candidate(
    *,
    rejected_snapshot: LaunchSnapshotCandidate,
    restore_target_snapshot: LaunchSnapshotCandidate,
    rollback_id: str,
    reason_code: str,
    actor_ref: str,
) -> RollbackReceiptCandidate:
    rollback = _stable_id(rollback_id, "ROLLBACK_ID")
    reason = _stable_id(reason_code, "ROLLBACK_REASON_CODE")
    actor = _stable_id(actor_ref, "ROLLBACK_ACTOR_REF")
    if rejected_snapshot.snapshot_sha256 == restore_target_snapshot.snapshot_sha256:
        raise LaunchSetCandidateError("LAUNCH_SET_ROLLBACK_TARGET_UNCHANGED")
    payload = {
        "version": ROLLBACK_RECEIPT_CANDIDATE_VERSION,
        "rollback_id": rollback,
        "rejected_snapshot_sha256": rejected_snapshot.snapshot_sha256,
        "restore_target_snapshot_sha256": restore_target_snapshot.snapshot_sha256,
        "expected_projection_sha256": restore_target_snapshot.public_projection_sha256,
        "reason_code": reason,
        "actor_ref": actor,
        "execution_state": "NOT_EXECUTED",
    }
    return RollbackReceiptCandidate(
        rollback_id=rollback,
        rejected_snapshot_sha256=rejected_snapshot.snapshot_sha256,
        restore_target_snapshot_sha256=restore_target_snapshot.snapshot_sha256,
        expected_projection_sha256=restore_target_snapshot.public_projection_sha256,
        reason_code=reason,
        actor_ref=actor,
        receipt_sha256=_sha(payload),
    )


__all__ = [
    "GateState",
    "LAUNCH_SET_CANDIDATE_VERSION",
    "LAUNCH_SNAPSHOT_CANDIDATE_VERSION",
    "LaunchSetCandidateError",
    "LaunchSetCandidateManifest",
    "LaunchSnapshotCandidate",
    "LaunchSourceCandidate",
    "LaunchSourceState",
    "MIN_INCLUDED_SOURCE_FAMILIES",
    "ROLLBACK_RECEIPT_CANDIDATE_VERSION",
    "RollbackReceiptCandidate",
    "build_launch_snapshot_candidate",
    "build_rollback_receipt_candidate",
    "validate_launch_set_candidate",
]
