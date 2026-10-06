from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from dichiarazioni_pubbliche.challenge_persistence import (
    ChallengeHoldDisposition,
    ChallengeHoldResult,
)
from dichiarazioni_pubbliche.correction_propagation import CorrectionPropagationReceipt


@dataclass(frozen=True)
class ProjectionArtifact:
    artifact_id: str
    relative_path: str
    entity_kind: str
    entity_id: str
    view: str
    projection_owned: bool = True


@dataclass(frozen=True)
class ProjectionCleanupReceipt:
    removed: tuple[str, ...]
    retained: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.blockers


def _safe_target(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise ValueError("PROJECTION_CLEANUP_PATH_INVALID")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    if resolved_root not in resolved.parents:
        raise ValueError("PROJECTION_CLEANUP_PATH_ESCAPE")
    return resolved


def _delete_selected(root: Path, artifacts: Iterable[ProjectionArtifact], selected: set[str]) -> ProjectionCleanupReceipt:
    selected_artifacts = [artifact for artifact in artifacts if artifact.artifact_id in selected]
    removed: list[str] = []
    retained: list[str] = []
    blockers: list[str] = []
    targets: list[tuple[ProjectionArtifact, Path]] = []
    for artifact in selected_artifacts:
        if not artifact.projection_owned:
            blockers.append(f"NON_PROJECTION_ARTIFACT:{artifact.artifact_id}")
            retained.append(artifact.relative_path)
            continue
        try:
            target = _safe_target(root, artifact.relative_path)
        except ValueError as exc:
            blockers.append(str(exc))
            retained.append(artifact.relative_path)
            continue
        if target.is_dir():
            blockers.append(f"PROJECTION_CLEANUP_DIRECTORY_FORBIDDEN:{artifact.artifact_id}")
            retained.append(artifact.relative_path)
            continue
        targets.append((artifact, target))
    if blockers:
        retained.extend(
            artifact.relative_path
            for artifact, target in targets
            if target.exists()
        )
        return ProjectionCleanupReceipt(
            (), tuple(sorted(set(retained))), tuple(dict.fromkeys(blockers))
        )
    for artifact, target in targets:
        if target.exists():
            target.unlink()
            removed.append(artifact.relative_path)
    return ProjectionCleanupReceipt(tuple(sorted(removed)), tuple(sorted(retained)), tuple(dict.fromkeys(blockers)))


def cleanup_takedown_current_artifacts(
    root: Path,
    *,
    finding_id: str,
    hold: ChallengeHoldResult,
    artifacts: Iterable[ProjectionArtifact],
) -> ProjectionCleanupReceipt:
    if hold.finding_id != finding_id or hold.disposition is not ChallengeHoldDisposition.HOLD:
        return ProjectionCleanupReceipt((), (), ("TAKEDOWN_HOLD_NOT_AUTHORITATIVE",))
    selected = {
        artifact.artifact_id
        for artifact in artifacts
        if artifact.entity_kind == "finding"
        and artifact.entity_id == finding_id
        and artifact.view == "CURRENT"
        and artifact.projection_owned
    }
    return _delete_selected(root, artifacts, selected)


def cleanup_dp431_stale_artifacts(
    root: Path,
    *,
    receipt: CorrectionPropagationReceipt,
    artifact_map: Mapping[str, ProjectionArtifact],
) -> ProjectionCleanupReceipt:
    selected = set(receipt.stale_artifacts) | set(receipt.orphan_artifacts)
    missing = sorted(selected - set(artifact_map))
    result = _delete_selected(root, artifact_map.values(), selected)
    blockers = list(result.blockers)
    blockers.extend(f"STALE_ARTIFACT_MAPPING_MISSING:{artifact}" for artifact in missing)
    return ProjectionCleanupReceipt(result.removed, result.retained, tuple(blockers))


__all__ = [
    "ProjectionArtifact", "ProjectionCleanupReceipt", "cleanup_dp431_stale_artifacts",
    "cleanup_takedown_current_artifacts",
]
